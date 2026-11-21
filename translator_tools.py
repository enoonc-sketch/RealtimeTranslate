"""v2.15.4 常用翻译软件功能 —— 纯逻辑模块（不碰 Tk / 网络 / Windows，可单测）。

参考了 Pot、Bob、欧路、有道词典、DeepL 桌面版等常见功能，代码全部自己写：
  - 多引擎对照：同一段文字同时给几个引擎翻，按完成顺序列出（compare_plan / CompareResult）
  - 命名格式转换：camelCase / snake_case / kebab-case / CONSTANT / Title（程序员常用，Bob、Pot 都有）
  - 译文风格：口语 / 正式 / 学术 / 简洁 —— 给支持的引擎（DeepL formality）传参，其余引擎做轻量后处理提示
  - 文本清理：去掉 PDF 复制带的页眉页脚行号、合并全角空格、统一引号（「去格式」）
  - 输入翻译（打字识别增强）：在任意输入框里打母语，按触发键把刚打的一句替换成译文
"""
import re

# ---------------------------------------------------------------- 命名格式
_WORD_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")


def split_identifier(text):
    """把各种写法拆成小写单词列表：'parseHTTPResponse_v2' -> ['parse','http','response','v','2']。"""
    out = []
    for part in re.split(r"[\s_\-./]+", (text or "").strip()):
        out.extend(m.group(0).lower() for m in _WORD_RE.finditer(part))
    return out


CASE_STYLES = ("camel", "pascal", "snake", "kebab", "constant", "title", "lower")
CASE_NAMES = {"camel": "camelCase", "pascal": "PascalCase", "snake": "snake_case",
              "kebab": "kebab-case", "constant": "CONSTANT_CASE", "title": "Title Case",
              "lower": "lower case"}


def to_case(text, style):
    w = split_identifier(text)
    if not w:
        return ""
    if style == "camel":
        return w[0] + "".join(x.capitalize() for x in w[1:])
    if style == "pascal":
        return "".join(x.capitalize() for x in w)
    if style == "snake":
        return "_".join(w)
    if style == "kebab":
        return "-".join(w)
    if style == "constant":
        return "_".join(w).upper()
    if style == "title":
        return " ".join(x.capitalize() for x in w)
    return " ".join(w)


def all_cases(text):
    """[(样式名, 结果), ...]，去掉重复和空结果。"""
    seen, out = set(), []
    for st in CASE_STYLES:
        v = to_case(text, st)
        if v and v not in seen:
            seen.add(v)
            out.append((CASE_NAMES[st], v))
    return out


def looks_like_identifier(text):
    """像不像变量名 / 函数名（中文→英文后提供命名格式用）：短、只有字母数字和分隔符。"""
    t = (text or "").strip()
    return 0 < len(t) <= 60 and bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 _\-]*", t)) and len(t.split()) <= 6


# ---------------------------------------------------------------- 文本清理（去格式）
_PAGE_NO = re.compile(r"^\s*(第\s*\d+\s*页|page\s*\d+(\s*of\s*\d+)?|-\s*\d+\s*-|\d+\s*/\s*\d+|\d{1,4})\s*$", re.I)
_LINE_NO = re.compile(r"^\s*\d{1,4}[\s:|]\s*(?=\S)")
_QUOTES = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'", "\u00a0": " ", "\u3000": " "})


def clean_text(text, strip_line_numbers=False):
    """「去格式」：删独立页码行、可选删代码行号、统一引号和空格、压多余空行。纯函数。"""
    lines = []
    for ln in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _PAGE_NO.match(ln):
            continue
        if strip_line_numbers:
            ln = _LINE_NO.sub("", ln)
        lines.append(ln.translate(_QUOTES).rstrip())
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return out.strip()


# ---------------------------------------------------------------- 译文风格
STYLES = {"default": "默认", "formal": "正式", "casual": "口语", "concise": "简洁"}


def deepl_formality(style):
    """DeepL 的 formality 参数（只有部分目标语言支持；不支持时 DeepL 会报 400，调用方降级）。"""
    return {"formal": "prefer_more", "casual": "prefer_less"}.get(style)


# ---------------------------------------------------------------- 多引擎对照
def compare_plan(engines, configured, max_n=4):
    """多引擎对照要跑哪些引擎（纯函数）：去掉「自动」「离线」以外不可用的，保持顺序，最多 max_n 个。
    engines：界面上的引擎列表；configured(name) -> 这个引擎能不能用（需要 Key 的没填就不能）。"""
    out = []
    for e in engines:
        if e == "自动":
            continue
        try:
            if not configured(e):
                continue
        except Exception:      # noqa: BLE001
            continue
        out.append(e)
        if len(out) >= max_n:
            break
    return out


class CompareResult:
    """收集多引擎结果（任意顺序到达），按「先完成的在前」给界面。"""

    def __init__(self, engines):
        self.engines = list(engines)
        self.done = []            # [(engine, ok, text, ms)]

    def add(self, engine, ok, text, ms):
        if engine in self.engines and engine not in (e for e, *_ in self.done):
            self.done.append((engine, bool(ok), text or "", int(ms)))

    def pending(self):
        got = {e for e, *_ in self.done}
        return [e for e in self.engines if e not in got]

    def finished(self):
        return not self.pending()

    def agreement(self):
        """成功结果里最多有几个引擎给出了相同译文（去空白比较），用来提示「这几家一致」。"""
        norm = {}
        for e, ok, t, _ in self.done:
            if ok and t.strip():
                k = re.sub(r"\s+", "", t)
                norm.setdefault(k, []).append(e)
        return max(norm.values(), key=len) if norm else []


# ---------------------------------------------------------------- 输入翻译（打字识别增强）
INPUT_TRIGGERS = {"space3": "连按 3 次空格", "f9": "按 F9", "ctrl_enter": "按 Ctrl+Enter（翻译并发送前替换）"}


class InputTranslator:
    """输入翻译状态机：记录当前输入框里「这一句」打了什么，按触发键时给出要替换的原文。

    设计：
      - 和打字检测共用按键流（feed），但独立维护一句话的缓冲（含空格和标点，回车 / 切窗口清空）。
      - 触发 space3：连续 3 个空格 —— 返回 {"kind": "replace", "text": 句子, "erase": 要删掉的字符数}，
        erase 包含句子本身 + 刚打的 3 个空格；调用方发 erase 次退格，再粘贴译文。
      - 触发 f9：调用方收到 F9 时调 trigger()。
      - 只在 Windows 上可靠（需要注入退格 + 粘贴）；IME 输入的中文由键盘钩子拿不到组字结果，
        所以中文句子用「先选中再 Ctrl+Alt+R 翻译并替换」路径，这里主要服务英文 / 拼音输入法上屏后的文本。
      - 缓冲只在内存，敏感内容（交给调用方的 is_sensitive 函数判定）不翻。
    """
    MAX = 400

    def __init__(self, trigger="space3", is_sensitive=None):
        self.trigger_kind = trigger if trigger in INPUT_TRIGGERS else "space3"
        self.buf = ""
        self._spaces = 0
        self.is_sensitive = is_sensitive or (lambda t: False)

    def clear(self):
        self.buf, self._spaces = "", 0

    def feed(self, ch):
        if ch in ("\n", "\r", "\x1b", "\t"):
            self.clear()
            return None
        if ch in ("\b", "\x7f"):
            self.buf = self.buf[:-1]
            self._spaces = 0
            return None
        if not isinstance(ch, str) or len(ch) != 1 or not ch.isprintable():
            return None
        if ch == " ":
            self._spaces += 1
            self.buf = (self.buf + ch)[-self.MAX:]
            if self.trigger_kind == "space3" and self._spaces >= 3:
                return self._make(trailing=3)
            return None
        self._spaces = 0
        self.buf = (self.buf + ch)[-self.MAX:]
        return None

    def trigger(self):
        return self._make(trailing=0)

    def _make(self, trailing):
        body = self.buf[:-trailing] if trailing else self.buf
        text = body.strip()
        erase = len(self.buf)
        self.clear()
        if len(text) < 2 or not any(c.isalpha() for c in text) or self.is_sensitive(text):
            return None
        lead = len(body) - len(body.lstrip())          # 句首的空格不删
        return {"kind": "replace", "text": text, "erase": erase - lead}
