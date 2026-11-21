"""打字检测翻译 —— 纯逻辑模块（无 OS 依赖，可单测）。

设计（v2.14 打字检测翻译）：
- 主触发是“打字过程中”：每打完一个词（空格 / 标点 / 回车分隔）就立即
  翻译刚打完的词/句，不等停顿。正在打的当前词实时跟进：每多打一个字符
  就更新候选译文，但用约 250 毫秒防抖节流，避免每键都发一次网络请求
  （防抖只节流，不等于等停顿）。
- 停顿触发只作兜底：打完一句话停住满 typing_pause_ms（默认 1000 毫秒）
  时也翻一次当前片段。
- 同一气泡内随打字更新译文（由调用方用 typing seq + Bubble.update 实现，
  本模块只产出“该翻什么、何时翻”的事件，不碰任何界面）。
- 性能保护：连续打字时最多每 300 毫秒发一次翻译请求；正在翻译的词被
  继续修改时，调用方用已有的 cancelled 机制取消旧请求，只保留最新一次；
  防抖节流绝不丢最后一次——pending 的 live 片段会在下一轮 tick 里补发。
- 隐私：缓冲只放内存，绝不写盘、绝不写日志、绝不进历史。suppressed 为真
  （密码框 / 终端 / 主窗口获得焦点）时不捕获、立即清空缓冲。

本模块不知道 Windows 钩子、pynput、Tk、翻译引擎：平台监听只负责把按键
事件转发进来（字符 / 退格 / Esc / 分隔符），翻译由调用方走已有的
translate()，气泡由调用方复用悬停取词的 Bubble/MiniWin。
"""

import re
import time

MAX_FRAGMENT = 200          # 片段上限（字符）
MIN_CHARS = 2               # 太短不翻
LIVE_DEBOUNCE_MS = 250      # 当前词实时跟进的防抖（毫秒）
MIN_REQUEST_INTERVAL_MS = 300   # 连续打字时最多每 300 毫秒发一次请求
DEFAULT_PAUSE_MS = 1000     # 停顿兜底（毫秒），可调 500–3000
PAUSE_MIN_MS = 500
PAUSE_MAX_MS = 3000

# 分隔符：空格 / 制表 / 换行 / 回车 / 标点。句末标点同时是句子终结符。
WORD_DELIMITERS = set(" \t\n\r,.;:!?，。；：、！？…—\"'\"'()[]{}<>«»")
SENTENCE_TERMINATORS = set(".!?。！？\n\r")
BACKSPACE_CHARS = {"\b", "\x7f"}
ESCAPE_CHARS = {"\x1b"}

# 敏感内容判定：与 desktop_translator.is_sensitive_clip 同款规则（镜像，
# 本模块不能 import desktop_translator，会循环依赖）。验证码 / 身份证号 /
# API 密钥 / 密码令牌 / 长串高熵 token —— 像敏感剪贴板一样不翻译。
_SENSITIVE_RES = [
    re.compile(r"^\d{6,}$"),
    re.compile(r"^sk-[A-Za-z0-9\-_]{16,}$"),
    re.compile(r"^\d{17}[\dXx]$"),
    re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z0-9\-_+/=]{32,}$"),
]
_SENSITIVE_KW_RE = re.compile(
    r"(password|passwd|pwd|token|secret|api[-_]?key|access[-_]?key)\s*[:=]\s*\S+",
    re.IGNORECASE)

# 敏感键名（B-1）：出现在 "key: value" / "key=value" 里的键。词按分隔符拆开后，
# 单看 "password" 或 "abc123" 都不触发敏感规则（见 _SENSITIVE_KW_RE），所以缓冲
# 要记住“上一个词是敏感键名、后面跟了 : 或 =”，下一个完成的词就是值，也抑制；
# 键名本身在跟了 :/= 时也不翻。误杀面很小：只有“键名 + :/=” 这种键值对写法才
# 抑制，正常句子里的 password/token（后面没跟 :/=）照常翻。
_SENSITIVE_KEY_RE = re.compile(
    r"(password|passwd|pwd|token|secret|api[-_]?key|access[-_]?key"
    r"|密码|账号|帳號|密钥|令牌)$",
    re.IGNORECASE)
# 能把键名“封口”的分隔符：英文冒号/等号、全角冒号（中文输入 "账号：xxx"）。
_SENSITIVE_KEY_DELIMITERS = set(":=\uff1a")


def is_sensitive_text(text):
    """文本像不像敏感信息（验证码、身份证号、API 密钥、密码/令牌）。纯函数。"""
    t = (text or "").strip()
    if not t:
        return False
    if _SENSITIVE_KW_RE.search(t):
        return True
    lines = [ln for ln in t.splitlines() if ln.strip()]
    if len(lines) == 1:
        s = lines[0]
        for rx in _SENSITIVE_RES:
            if rx.match(s):
                return True
    return False


def _has_letter(text):
    return any(ch.isalpha() for ch in text)


def is_eligible(text):
    """这段文本值不值得翻：≥2 字符、≤200 字符、含字母（纯数字/符号不翻）、
    不是敏感内容。纯函数。"""
    t = (text or "").strip()
    if len(t) < MIN_CHARS or len(t) > MAX_FRAGMENT:
        return False
    if not _has_letter(t):
        return False
    if is_sensitive_text(t):
        return False
    return True


def _last_word(text):
    """文本里最后一个词（按空白和标点切）。"""
    parts = [p for p in re.split(r"[\s,.;:!?，。；：、！？…—\"'\"'()\[\]{}<>«»]+", text) if p]
    return parts[-1] if parts else ""


class TypingBuffer:
    """当前输入片段的内存缓冲（只放内存，永不写盘）。

    scope="word"：按词触发——空格/标点/回车一到就立即返回刚打完的词。
    scope="sentence"：按句触发——空格/逗号只累积，句末标点/回车才返回整句；
    实时跟进的目标是当前整句片段，停顿兜底翻的也是当前整句。
    """

    def __init__(self, scope="word", pause_ms=DEFAULT_PAUSE_MS, now_fn=None):
        self.scope = scope if scope in ("word", "sentence") else "word"
        self.pause_ms = max(PAUSE_MIN_MS, min(int(pause_ms or DEFAULT_PAUSE_MS), PAUSE_MAX_MS))
        self._now = now_fn or time.monotonic
        self.text = ""              # 当前片段（word 模式是当前词，sentence 模式是当前句）
        self.suppressed = False     # 密码框 / 终端 / 主窗口获得焦点时为真
        self.last_key_at = None
        self.last_translated = None
        self.last_request_at = None
        self._live_dirty = False    # 当前词自上次 live 发送后又改了
        self._live_sent = None      # 上次 live 发出去的片段
        self._sensitive_key_pending = False  # B-1：上一个词是敏感键名且跟了 :/=，
        # 下一个完成的词就是它的值，也抑制（live/pause 跟进一并抑制）
        self._last_word_text = ""   # B-1：上一个完成的词（处理 "password : value"
        # 这种键名与冒号之间隔了空格的写法：冒号到时词已打完，先翻了键名，
        # 但值仍可凭它抑制）

    # -- 配置 -------------------------------------------------------------
    def set_scope(self, scope):
        if scope in ("word", "sentence"):
            self.scope = scope
            self.clear()

    def set_pause_ms(self, pause_ms):
        try:
            v = int(pause_ms)
        except Exception:
            return
        self.pause_ms = max(PAUSE_MIN_MS, min(v, PAUSE_MAX_MS))

    def set_suppressed(self, suppressed):
        self.suppressed = bool(suppressed)
        if self.suppressed:
            self.clear()

    # -- 状态 -------------------------------------------------------------
    def clear(self):
        self.text = ""
        self._live_dirty = False
        self._live_sent = None
        self.last_key_at = None
        self._sensitive_key_pending = False
        self._last_word_text = ""

    def current_fragment(self):
        """当前实时跟进的目标：word 模式是当前词，sentence 模式是当前整句。"""
        if self.scope == "word":
            return _last_word(self.text)
        return self.text.strip()

    def _mark_key(self, now):
        self.last_key_at = now

    # -- 输入 -------------------------------------------------------------
    def feed(self, ch, now=None):
        """喂一个按键。返回事件 dict 或 None。

        {"kind": "word", "text": ...}   打完一个词/句，立即翻译（主触发）
        {"kind": "clear"}               Esc：清空缓冲
        {"kind": "edit"}                普通字符/退格：缓冲变了，等 tick 做 live 跟进
        None                            不翻译（被抑制、空词、不合格等）
        """
        now = self._now() if now is None else now
        if self.suppressed:
            self.clear()
            return None
        if ch in ESCAPE_CHARS:
            self.clear()
            return {"kind": "clear"}
        if ch in BACKSPACE_CHARS:
            if self.text:
                self.text = self.text[:-1]
                self._live_dirty = True
                self._mark_key(now)
                if not self.text:
                    # 值被删空了：没东西可抑制，待命的敏感键失效
                    self._sensitive_key_pending = False
            return {"kind": "edit"}
        # 分隔符（空格/制表/换行/标点）先于可打印判定：\n、\t 不是可打印字符，
        # 但它们是打词的主触发，不能被挡掉。
        if ch in WORD_DELIMITERS:
            return self._feed_delimiter(ch, now)
        if not isinstance(ch, str) or len(ch) != 1 or not ch.isprintable():
            return None
        self._mark_key(now)
        self.text = (self.text + ch)[-MAX_FRAGMENT:]
        self._live_dirty = True
        return {"kind": "edit"}

    def _feed_delimiter(self, ch, now):
        self._mark_key(now)
        if self.scope == "word":
            word = _last_word(self.text)
            self.text = ""
            self._live_dirty = False
            self._live_sent = None
            if word:
                self._last_word_text = word
                if ch in _SENSITIVE_KEY_DELIMITERS and _SENSITIVE_KEY_RE.search(word):
                    # 键名 + :/=：键名本身不翻，下一个完成的词是值，也不翻
                    self._sensitive_key_pending = True
                    return None
                if self._sensitive_key_pending:
                    # 上一个词是敏感键名，这个词是它的值：抑制并解除待命
                    self._sensitive_key_pending = False
                    return None
            elif ch in _SENSITIVE_KEY_DELIMITERS and _SENSITIVE_KEY_RE.search(self._last_word_text):
                # "password : value"：键名与冒号之间隔了空格，冒号到时词已打完
                # （键名已翻出，无法撤回），但值仍可凭上一个词抑制
                self._sensitive_key_pending = True
                return None
            if word and is_eligible(word) and word != self.last_translated:
                return {"kind": "word", "text": word}
            return None
        # sentence 模式：分隔符先累积进句子
        self.text = (self.text + ch)[-MAX_FRAGMENT:]
        self._live_dirty = True
        if ch in SENTENCE_TERMINATORS:
            sentence = self.text.strip()
            self.text = ""
            self._live_dirty = False
            self._live_sent = None
            if sentence and is_eligible(sentence) and sentence != self.last_translated:
                return {"kind": "word", "text": sentence}
        return None

    # -- 节流 / 兜底 -------------------------------------------------------
    def tick(self, now=None):
        """由调用方每 ~100ms 调一次。返回事件 dict 或 None。

        {"kind": "live", "text": ...}   当前词实时跟进（防抖 250ms + 限速 300ms）
        {"kind": "pause", "text": ...}  停顿兜底（满 pause_ms，翻当前片段）
        防抖节流绝不丢最后一次：限速未到时 pending 留着，下一轮 tick 再发。
        """
        now = self._now() if now is None else now
        if self.suppressed or not self.text.strip() or self.last_key_at is None:
            return None
        if self._sensitive_key_pending:
            # B-1：正在打的很可能是敏感键的值（password: abc***），live 跟进与
            # 停顿兜底都抑制；值打完由 _feed_delimiter 在词完成时抑制
            return None
        fragment = self.current_fragment()
        if not fragment or not is_eligible(fragment) or fragment == self.last_translated:
            return None
        # 停顿兜底优先：打完一句话停住了，翻当前片段
        if (now - self.last_key_at) * 1000 >= self.pause_ms:
            return {"kind": "pause", "text": fragment}
        # 实时跟进：当前词改了，且自上次按键已过防抖，且距上次请求已过限速
        if not self._live_dirty or fragment == self._live_sent:
            return None
        if (now - self.last_key_at) * 1000 < LIVE_DEBOUNCE_MS:
            return None
        if self.last_request_at is not None and (now - self.last_request_at) * 1000 < MIN_REQUEST_INTERVAL_MS:
            return None
        self._live_sent = fragment
        self._live_dirty = False
        return {"kind": "live", "text": fragment}

    def mark_translated(self, text, now=None):
        """一次翻译请求已发出：记下它（去重 + 限速的依据）。"""
        now = self._now() if now is None else now
        self.last_translated = text
        self.last_request_at = now
        if text == self._live_sent:
            self._live_dirty = False
