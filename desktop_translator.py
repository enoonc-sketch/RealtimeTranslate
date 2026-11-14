#!/usr/bin/env python3
"""
实时翻译 — 桌面独立版 v2.4，Windows / macOS / Linux(X11)

功能
  1. 输入即译：窗口里打字或粘贴，停顿约 0.35 秒自动翻译
  2. 全局快捷键 Ctrl+Alt+T：任意软件里选中文字后按下，自动复制并翻译
     （Windows 不需要安装任何依赖；macOS / Linux 需要 pip install pynput）
  3. 监听剪贴板：开启后，任何地方复制文字都会自动翻译
  4. 长文档：按段落分块并发翻译，保留分段；可“双语对照”、可“合并断行”
  5. 中英智能互译：原文语言与目标语言相同时，自动改译成英文/中文
  6. 引擎：Google（在线） / 微软（在线免费 Edge 端点） / 离线（Argos 语言包，由 ctranslate2 本地推理）
  7. 网络检查：一键诊断联网 / DNS / 代理 / 各引擎，并给出推荐；断网时可自动改用离线
  8. 在线下载离线语言包：程序内直接取官方列表、勾选下载、自动安装（不必手动找文件）
  9. 指针取词：把鼠标放在文字上按 Ctrl+Alt+D，就在指针旁弹出小气泡显示译文（不打开主窗口）
 10. 托盘图标（Windows）：只用标准库 ctypes 调 Shell_NotifyIconW，
     不依赖 pystray / Pillow；点 × 是隐藏到托盘，右键菜单可显示 / 截图 / 退出
 11. 悬停取词（Windows）：鼠标在文字上停住约 0.8 秒就自动取词——
     先用系统 OCR（Windows.Media.Ocr，截图里认字）定位光标下的单词，
     认不到且光标是「I」形时退回双击取词；图片、游戏、扫描 PDF 里也能用
 12. 截图翻译（Windows，Ctrl+Alt+S）：框选屏幕任意区域 → 系统 OCR
     认字 → 翻译。截图用 ctypes GDI BitBlt，OCR 用系统自带引擎，
     全程不装第三方库
"""
import collections
import itertools
import json
import math
import os
import queue
import re
import socket
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from tkinter import ttk, messagebox, filedialog

import netcheck
import offline_engine
import pack_downloader
import runtime_installer
import tray_win32
import screen_win
import ocr_win

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

keyboard = None
if not IS_WIN:
    try:
        from pynput import keyboard
    except Exception:
        keyboard = None

HOTKEY_LABEL = "Ctrl+Alt+T"
PYNPUT_HOTKEY = "<ctrl>+<alt>+t"
POINTER_LABEL = "Ctrl+Alt+D"
PYNPUT_POINTER = "<ctrl>+<alt>+d"
SCREENSHOT_LABEL = "Ctrl+Alt+S"
PYNPUT_SCREENSHOT = "<ctrl>+<alt>+s"
SCOPE_NAMES = {"word": "单词", "paragraph": "整段"}
SCOPE_CODES = {v: k for k, v in SCOPE_NAMES.items()}
__version__ = "2.4.0"
APP_TITLE = "实时翻译"
MUTEX_NAME = "RealtimeTranslate_SingleInstance"   # 与 installer.iss 的 AppMutex 保持一致
RUN_VALUE = "RealtimeTranslate"
FROZEN = bool(getattr(sys, "frozen", False))
OLD_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".gt_desktop_translator.json")
if IS_WIN:
    DATA_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "RealtimeTranslate")
else:
    DATA_DIR = os.path.join(os.path.expanduser("~"), ".config", "RealtimeTranslate")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
CRASH_LOG = os.path.join(DATA_DIR, "crash.log")
USER_MODELS_DIR = os.path.join(DATA_DIR, "models")      # 用户自己导入 / 在线下载的离线语言包


def _dl_dir():
    return os.path.join(DATA_DIR, "downloads")          # 下载中的临时文件（装好即删）


def _runtime_dir():
    return os.path.join(DATA_DIR, "runtime")           # 程序内下载的离线运行库（标准版用）


def _index_cache():
    return os.path.join(DATA_DIR, "pack_index.json")    # 语言包列表缓存：断网时还能看


def resource_path(name):
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, name)


def _argos_default_dir():
    """兼容已装过 Argos Translate 的机器：直接复用它下载好的语言包。"""
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "argos-translate", "packages")


# 标准版：之前在程序里下载过离线组件的话，启动时就把它加进搜索路径（内置的运行库优先）
try:
    runtime_installer.activate(_runtime_dir())
except Exception:      # noqa: BLE001
    pass

# 优先级：用户导入 > 安装包内置 > 本机已有的 Argos 语言包
OFFLINE = offline_engine.Engine([
    (USER_MODELS_DIR, "用户导入"),
    (resource_path("offline_models"), "内置"),
    (_argos_default_dir(), "Argos"),
])
GOOGLE_ENDPOINT = "https://translate.googleapis.com/translate_a/single"
MS_ENDPOINT = "https://edge.microsoft.com/translate/translatetext"
MAX_LEN = 20000
CHUNK = 1800
WORKERS = 4

LANGS = {
    "zh-CN": "简体中文", "zh-TW": "繁体中文", "en": "英语", "ja": "日语", "ko": "韩语",
    "fr": "法语", "de": "德语", "es": "西班牙语", "ru": "俄语", "pt": "葡萄牙语",
    "it": "意大利语", "ar": "阿拉伯语", "th": "泰语", "vi": "越南语", "id": "印尼语",
    "hi": "印地语", "tr": "土耳其语", "pl": "波兰语", "nl": "荷兰语", "uk": "乌克兰语",
    "sv": "瑞典语", "he": "希伯来语",
}
# 微软常用代码映射
MS_CODE = {
    "zh-CN": "zh-Hans", "zh-TW": "zh-Hant", "en": "en", "ja": "ja", "ko": "ko",
    "fr": "fr", "de": "de", "es": "es", "ru": "ru", "pt": "pt", "it": "it",
    "ar": "ar", "th": "th", "vi": "vi", "id": "id", "auto": "auto",
    "hi": "hi", "tr": "tr", "pl": "pl", "nl": "nl", "uk": "uk", "sv": "sv", "he": "he",
}
# Argos 常用代码（与 ISO 接近）
ARGOS_CODE = {
    "zh-CN": "zh", "zh-TW": "zh", "en": "en", "ja": "ja", "ko": "ko",
    "fr": "fr", "de": "de", "es": "es", "ru": "ru", "pt": "pt", "it": "it",
    "ar": "ar", "th": "th", "vi": "vi", "id": "id",
    "hi": "hi", "tr": "tr", "pl": "pl", "nl": "nl", "uk": "uk", "sv": "sv", "he": "he",
}
AUTO = "自动检测"
NAME2CODE = {v: k for k, v in LANGS.items()}
# 标准版 exe 不含离线运行库：此时不显示「离线」，避免选了必报错
ENGINES = ["Google", "微软"] + (["离线"] if offline_engine.runtime_present() else [])
DEFAULTS = {
    "sl": "auto", "tl": "zh-CN", "top": True, "watch": False, "smart": True,
    "bilingual": False, "reflow": True, "show_src": True, "geometry": "620x760",
    "engine": "Google", "auto_offline": True,
    "pointer": True, "pointer_scope": "word", "pack_mirror": "",
    "hover": True, "hover_ms": 800,
}


def base(code):
    return str(code or "").lower().split("-")[0]


def lang_name(code):
    if code in LANGS:
        return LANGS[code]
    b = base(code)
    if b == "zh":
        return "中文"
    return LANGS.get(b, code or "")


def to_ms(code):
    return MS_CODE.get(code, base(code) or "auto")


def to_argos(code):
    return ARGOS_CODE.get(code, base(code) or "en")


# ---------------------------------------------------------------- 翻译核心
CACHE = collections.OrderedDict()
CACHE_MAX = 800
_cache_lock = threading.Lock()


def _is_rate_limit(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (429, 503)
    s = str(exc).lower()
    return "429" in s or "too many requests" in s


def g_translate(text, sl, tl, attempts=3, timeout=12):
    url = "%s?client=gtx&sl=%s&tl=%s&dt=t&ie=UTF-8&oe=UTF-8" % (
        GOOGLE_ENDPOINT, urllib.parse.quote(sl), urllib.parse.quote(tl))
    body = ("q=" + urllib.parse.quote(text)).encode("utf-8")
    headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    last = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            out = "".join((seg[0] or "") for seg in (data[0] or []) if seg)
            det = data[2] if len(data) > 2 and data[2] else sl
            return out, det
        except Exception as e:
            last = e
            if attempt + 1 >= attempts:
                break
            if _is_rate_limit(e):
                time.sleep(1.2 * (attempt + 1))
            else:
                time.sleep(0.4)
    raise last


_ms_token = {"value": "", "ts": 0.0}
_ms_lock = threading.Lock()
MS_AUTH = "https://edge.microsoft.com/translate/auth"
MS_API = "https://api-edge.cognitive.microsofttranslator.com/translate"
_UA_EDGE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
)


def _ms_get_token(force=False):
    """Edge 翻译端点需要一个免费的短期 token（约 10 分钟有效），缓存复用。"""
    with _ms_lock:
        if not force and _ms_token["value"] and time.time() - _ms_token["ts"] < 480:
            return _ms_token["value"]
        req = urllib.request.Request(MS_AUTH, headers={"User-Agent": _UA_EDGE})
        with urllib.request.urlopen(req, timeout=10) as r:
            tok = r.read().decode("utf-8").strip()
        _ms_token.update(value=tok, ts=time.time())
        return tok


def ms_translate(text, sl, tl, attempts=3, timeout=15):
    """微软 Edge 免费翻译端点（无需自备 Key，token 自动获取并缓存）。"""
    src = to_ms(sl)
    tgt = to_ms(tl)
    if src == "auto":
        src = ""
    payload = json.dumps([{"Text": text}]).encode("utf-8")
    params = "from=%s&to=%s&api-version=3.0&includeSentenceLength=true" % (
        urllib.parse.quote(src), urllib.parse.quote(tgt))
    url = "%s?%s" % (MS_API, params)
    last = None
    for attempt in range(attempts):
        try:
            headers = {
                "Content-Type": "application/json; charset=UTF-8",
                "User-Agent": _UA_EDGE,
                "Authorization": "Bearer " + _ms_get_token(force=attempt > 0 and _is_auth_error(last)),
            }
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            item = data[0] if isinstance(data, list) and data else {}
            translations = item.get("translations") or []
            out = (translations[0].get("text") if translations else "") or ""
            det_obj = item.get("detectedLanguage") or {}
            det = det_obj.get("language") or src or sl
            if str(det).startswith("zh"):
                det = "zh-TW" if "Hant" in str(det) else "zh-CN"
            return out, det
        except Exception as e:
            last = e
            if attempt + 1 < attempts:
                time.sleep(0.6 * (attempt + 1))
    raise last


def _is_auth_error(exc):
    return isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403)


def guess_lang(text):
    """按文字脚本粗略判断语种（仅供离线引擎的「自动检测」使用）。"""
    sample = text[:200]
    ranges = [
        ("ja", "\u3040", "\u30ff"), ("ko", "\uac00", "\ud7a3"),
        ("ru", "\u0400", "\u04ff"), ("ar", "\u0600", "\u06ff"),
        ("th", "\u0e00", "\u0e7f"), ("he", "\u0590", "\u05ff"),
        ("hi", "\u0900", "\u097f"), ("zh", "\u3400", "\u9fff"),
    ]
    for code, lo, hi in ranges:
        if any(lo <= c <= hi for c in sample):
            return code
    return "en"


def offline_translate(text, sl, tl, cancelled=None):
    """离线引擎：读取 Argos 语言包，用 ctranslate2 本地推理。"""
    to_code = to_argos(tl)
    from_code = to_argos(sl) if sl != "auto" else guess_lang(text)
    if not offline_engine.runtime_present():
        raise offline_engine.OfflineError(
            "还没有离线翻译组件。\n请点主界面「离线语言包…」，按提示下载组件；"
            "也可使用「离线版」安装包；从源码运行请执行：pip install ctranslate2 sentencepiece numpy")
    return OFFLINE.translate(text, from_code, to_code, cancelled), from_code


# ---- 在线引擎失败时自动改用离线 ----
AUTO_OFFLINE = True            # 由界面复选框控制
_DOWN_SECONDS = 30             # 判定「在线引擎不通」后，这段时间内直接走离线，不再逐条重试
_state = {"down_until": 0.0, "fallback": 0}
_tl = threading.local()


def offline_possible(text, sl, tl):
    if not (AUTO_OFFLINE and OFFLINE.available()):
        return False
    from_code = to_argos(sl) if sl != "auto" else guess_lang(text)
    return OFFLINE.can_translate(from_code, to_argos(tl))


def reset_online_state():
    _state["down_until"] = 0.0


def fallback_count():
    return _state["fallback"]


def _fallback(text, sl, tl):
    out = offline_translate(text, sl, tl)
    _state["fallback"] += 1
    _tl.skip_cache = True            # 离线译文不要缓存到在线引擎的键下，网络恢复后应重新用在线译
    return out


def _online(text, sl, tl, engine):
    if engine == "微软":
        return ms_translate(text, sl, tl)
    # Google 为主，限流时回退微软
    try:
        return g_translate(text, sl, tl)
    except Exception as e:
        if _is_rate_limit(e):
            try:
                return ms_translate(text, sl, tl)
            except Exception:
                raise RuntimeError(
                    "Google 请求过于频繁（429），且微软端点也失败。\n"
                    "建议：稍等片刻，或切换到「微软 / 离线」引擎。\n"
                    "原始错误：%s" % e)
        raise


def do_translate(text, sl, tl, engine):
    """按引擎翻译；Google 遇 429 回退微软；在线整体不通时（可选）自动改用离线。"""
    engine = (engine or "Google").strip()
    if engine == "离线":
        return offline_translate(text, sl, tl)
    if time.time() < _state["down_until"] and offline_possible(text, sl, tl):
        return _fallback(text, sl, tl)               # 熔断期内：不再等在线超时
    try:
        out = _online(text, sl, tl, engine)
        _state["down_until"] = 0.0
        return out
    except Exception as e:
        if netcheck.is_connectivity_error(e):
            _state["down_until"] = time.time() + _DOWN_SECONDS
        if offline_possible(text, sl, tl):
            try:
                return _fallback(text, sl, tl)
            except Exception:
                pass
        raise


def cached(text, sl, tl, engine):
    key = (text, sl, tl, engine)
    with _cache_lock:
        if key in CACHE:
            CACHE.move_to_end(key)
            return CACHE[key]
    _tl.skip_cache = False
    val = do_translate(text, sl, tl, engine)      # 网络请求放在锁外
    if getattr(_tl, "skip_cache", False):
        _tl.skip_cache = False
        return val
    with _cache_lock:
        CACHE[key] = val
        while len(CACHE) > CACHE_MAX:
            CACHE.popitem(last=False)
    return val


def split_long(s, limit=CHUNK):
    if len(s) <= limit:
        return [s]
    out, cur = [], ""
    for p in re.split(r"(?<=[.!?。！？;；])", s):
        if cur and len(cur) + len(p) > limit:
            out.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        out.append(cur)
    final = []
    for o in out:
        while len(o) > limit:
            final.append(o[:limit])
            o = o[limit:]
        final.append(o)
    return final


def _join(parts, tl):
    sep = "" if base(tl) in ("zh", "ja", "th") else " "
    return sep.join(x.strip() for x in parts)


def translate_unit(unit, sl, tl, engine, cancelled=None):
    parts = []
    for p in split_long(unit):
        if cancelled and cancelled():
            raise RuntimeError("cancelled")
        parts.append(cached(p, sl, tl, engine)[0])
    return _join(parts, tl)


def alt_target(tl):
    return "zh-CN" if base(tl) == "en" else "en"


def translate(text, sl, tl, smart, engine, cancelled=None):
    """单段文字：自动检测 +（可选）中英互译。超长文本会自动分块（旧版会整段一次发送）。"""
    chunks = split_long(text)
    first, det = cached(chunks[0], sl, tl, engine)
    target = tl
    if smart and sl == "auto" and base(det) == base(tl):
        target = alt_target(tl)
        out = translate_unit(text, det, target, engine, cancelled)
    else:
        parts = [first]
        for c in chunks[1:]:
            if cancelled and cancelled():
                raise RuntimeError("cancelled")
            parts.append(cached(c, sl, tl, engine)[0])
        out = _join(parts, tl)
    return out, det, target


_BULLET = re.compile(r"^\s*([-*•●◦▪]|\d+[.)、]|[A-Za-z][.)]|\(\d+\))\s+")
_END = tuple(".!?。！？;；:：")


def _cjk(c):
    return "\u3400" <= c <= "\u9fff"


def to_units(text, reflow):
    """拆成行；reflow 时把被硬换行打断的句子合并（保留标题、列表、空行）。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            if out and out[-1] != "":
                out.append("")
            continue
        if (reflow and out and out[-1] and len(out[-1]) >= 45
                and not out[-1].endswith(_END) and not _BULLET.match(s)):
            glue = "" if (_cjk(out[-1][-1]) and _cjk(s[0])) else " "
            out[-1] = out[-1] + glue + s
        else:
            out.append(s)
    while out and out[-1] == "":
        out.pop()
    return out


def translate_doc(text, sl, tl, smart, reflow, engine, progress, cancelled):
    """返回 (pairs, detected, target)；pairs 是 [(原文行, 译文行)]，空行为 ('','')。"""
    units = to_units(text, reflow)
    texts = [u for u in units if u]
    if not texts:
        return [], sl, tl
    if len(texts) == 1:
        out, det, target = translate(texts[0], sl, tl, smart, engine, cancelled)
        return [(texts[0], out)], det, target

    det, target, src_lang = sl, tl, sl
    if sl == "auto":
        det = cached(" ".join(texts)[:300], "auto", tl, engine)[1]
        src_lang = det
        if smart and base(det) == base(tl):
            target = alt_target(tl)
    counter = itertools.count(1)

    def work(u):
        if cancelled():
            raise RuntimeError("cancelled")
        r = translate_unit(u, src_lang, target, engine, cancelled)
        progress(next(counter), len(texts))
        return r

    with ThreadPoolExecutor(WORKERS) as ex:
        results = iter(list(ex.map(work, texts)))
    pairs = [("", "") if not u else (u, next(results)) for u in units]
    return pairs, det, target


# ---------------------------------------------------------------- Windows 全局热键
def start_hotkey_win(q):
    import ctypes
    import ctypes.wintypes
    user32 = ctypes.windll.user32
    ready, state = threading.Event(), {"ok": False, "pointer_ok": False, "shot_ok": False}

    def loop():
        MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x1, 0x2, 0x4000
        VK_T, VK_D, VK_S = 0x54, 0x44, 0x53
        mods = MOD_ALT | MOD_CONTROL | MOD_NOREPEAT
        state["ok"] = bool(user32.RegisterHotKey(None, 1, mods, VK_T))
        state["pointer_ok"] = bool(user32.RegisterHotKey(None, 2, mods, VK_D))   # 指针取词
        state["shot_ok"] = bool(user32.RegisterHotKey(None, 3, mods, VK_S))      # 截图翻译
        ready.set()
        if not (state["ok"] or state["pointer_ok"] or state["shot_ok"]):
            return
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312:
                q.put(("hotkey", int(msg.wParam)))

    threading.Thread(target=loop, daemon=True).start()
    ready.wait(2)
    start_hotkey_win.pointer_ok = state["pointer_ok"]
    start_hotkey_win.shot_ok = state["shot_ok"]
    return state["ok"]


def send_copy_win():
    import ctypes
    u = ctypes.windll.user32
    t0 = time.time()
    while time.time() - t0 < 1.5 and any(u.GetAsyncKeyState(vk) & 0x8000 for vk in (0x12, 0x11, 0x54)):
        time.sleep(0.03)
    KEYUP = 2
    u.keybd_event(0x11, 0, 0, 0)
    u.keybd_event(0x43, 0, 0, 0)
    u.keybd_event(0x43, 0, KEYUP, 0)
    u.keybd_event(0x11, 0, KEYUP, 0)


def clip_seq_win():
    """Windows 剪贴板序号：内容一变就加 1，比固定等待可靠。"""
    try:
        import ctypes
        return ctypes.windll.user32.GetClipboardSequenceNumber()
    except Exception:
        return 0


# ---------------------------------------------------------------- Windows 指针取词
_TERMINAL_CLASSES = ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS", "mintty",
                     "VirtualConsoleClass", "PuTTY")


def pointer_plan(ibeam, terminal, scope):
    """指针取词该做哪些动作（纯逻辑，便于测试）。

    click2 / click3 = 在指针处双击 / 三击（选中单词 / 整段）；copy = 发送 Ctrl+C。
    只有指针是「I」形文字光标时才会点击，所以不会误点按钮、链接。
    """
    if ibeam:
        return ["click3" if scope == "paragraph" else "click2", "copy"]
    if terminal:
        return []          # 终端里没有选区时 Ctrl+C 会中断正在运行的程序，绝不发送
    return ["copy"]        # 认不出光标形状（软件自绘光标）：只复制已有的选区


def cursor_is_ibeam_win():
    import ctypes
    import ctypes.wintypes as wt

    class CURSORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD),
                    ("hCursor", ctypes.c_void_p), ("ptScreenPos", wt.POINT)]
    u = ctypes.windll.user32
    u.LoadCursorW.restype = ctypes.c_void_p
    u.LoadCursorW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    ibeam = u.LoadCursorW(None, 32513)              # IDC_IBEAM
    ci = CURSORINFO()
    ci.cbSize = ctypes.sizeof(ci)
    if not u.GetCursorInfo(ctypes.byref(ci)):
        return False
    return bool(ci.hCursor) and ci.hCursor == ibeam


def foreground_is_terminal_win():
    import ctypes
    u = ctypes.windll.user32
    u.GetForegroundWindow.restype = ctypes.c_void_p
    u.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    buf = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(u.GetForegroundWindow(), buf, 256)
    return buf.value in _TERMINAL_CLASSES


def wait_keys_up_win(vks, timeout=1.5):
    """等这些键都松开（否则 Ctrl+Alt+点击 会变成别的操作，比如 Ctrl+点链接 = 新标签页打开）。"""
    import ctypes
    u = ctypes.windll.user32
    t0 = time.time()
    while time.time() - t0 < timeout:
        if not any(u.GetAsyncKeyState(vk) & 0x8000 for vk in vks):
            return True
        time.sleep(0.03)
    return False


def click_here_win(n):
    import ctypes
    u = ctypes.windll.user32
    for _ in range(n):
        u.mouse_event(0x2, 0, 0, 0, 0)              # 左键按下（原地，不移动鼠标）
        u.mouse_event(0x4, 0, 0, 0, 0)              # 左键抬起
        time.sleep(0.03)


def screen_bounds():
    """整个虚拟桌面（含多显示器）的 (左, 上, 右, 下)。"""
    if IS_WIN:
        try:
            import ctypes
            g = ctypes.windll.user32.GetSystemMetrics
            l, t, w, h = g(76), g(77), g(78), g(79)
            if w > 0 and h > 0:
                return l, t, l + w, t + h
        except Exception:
            pass
    return None


def no_activate_win(win):
    """让气泡窗口永远不抢焦点（否则会打断你正在用的软件，并让它丢掉选区）。"""
    import ctypes
    u = ctypes.windll.user32
    u.GetParent.restype = ctypes.c_void_p
    u.GetParent.argtypes = [ctypes.c_void_p]
    u.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
    u.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
    hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
    ex = u.GetWindowLongW(hwnd, -20)
    u.SetWindowLongW(hwnd, -20, ex | 0x08000000 | 0x80)      # WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW


def enable_dpi_awareness():
    """高分屏下避免界面发糊（Windows）。"""
    if not IS_WIN:
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Per-monitor
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


_mutex_handle = None


def acquire_single_instance():
    """Windows 单实例：已有实例在运行则唤起它并返回 False。"""
    global _mutex_handle
    if not IS_WIN:
        return True
    try:
        import ctypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        _mutex_handle = k32.CreateMutexW(None, False, MUTEX_NAME)
        if ctypes.get_last_error() == 183:      # ERROR_ALREADY_EXISTS
            u = ctypes.windll.user32
            hwnd = u.FindWindowW(None, APP_TITLE)
            if hwnd:
                u.ShowWindow(hwnd, 9)           # SW_RESTORE
                u.SetForegroundWindow(hwnd)
            return False
    except Exception:
        pass
    return True


def _run_command():
    if FROZEN:
        return '"%s" --minimized' % sys.executable
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        exe = exe[:-10] + "pythonw.exe"
    return '"%s" "%s" --minimized' % (exe, os.path.abspath(__file__))


_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_enabled():
    if not IS_WIN:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.QueryValueEx(k, RUN_VALUE)
        return True
    except Exception:
        return False


def set_autostart(on):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, RUN_VALUE, 0, winreg.REG_SZ, _run_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_VALUE)
            except FileNotFoundError:
                pass


def log_crash(text):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CRASH_LOG, "a", encoding="utf-8") as f:
            f.write("[%s] v%s\n%s\n\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), __version__, text))
    except Exception:
        pass


# ---------------------------------------------------------------- 界面
class Bubble:
    """指针旁的小气泡：显示原文 + 译文。不抢焦点；点一下复制译文，右键 / Esc / 移开指针就消失。"""
    BG, BORDER, GRAY, RED = "#fffdf6", "#c9ced6", "#6b7380", "#b42318"
    MOVE_AWAY = 140          # 指针离开出现位置这么多像素（且不在气泡上）就自动消失
    MAX_SECONDS = 20

    def __init__(self, app):
        self.app = app
        self.win = None
        self.anchor = (0, 0)
        self.t0 = 0.0
        self.copy_text = ""

    def alive(self):
        try:
            return self.win is not None and bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def close(self):
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
        self.win = None

    def show(self, xy, head, body, error=False):
        self.close()
        app = self.app
        self.anchor, self.t0 = xy, time.time()
        w = tk.Toplevel(app.root)
        w.withdraw()
        w.overrideredirect(True)
        try:
            w.attributes("-topmost", True)
        except tk.TclError:
            pass
        frame = tk.Frame(w, bg=self.BG, highlightbackground=self.BORDER, highlightthickness=1,
                         padx=10, pady=7)
        frame.pack()
        self.head = tk.Label(frame, bg=self.BG, fg=self.GRAY, font=app.ui_font, anchor="w",
                             justify="left", wraplength=380)
        self.body = tk.Label(frame, bg=self.BG, font=app.font, anchor="w", justify="left",
                             wraplength=380)
        self.foot = tk.Label(frame, bg=self.BG, fg="#9aa3b2", font=(app.ui_font[0], 8), anchor="w",
                             text="点击复制译文 · 右键或 Esc 关闭")
        self.head.pack(fill="x")
        self.body.pack(fill="x", pady=(2, 2))
        self.foot.pack(fill="x")
        for wd in (w, frame, self.head, self.body, self.foot):
            wd.bind("<Button-1>", self._click)
            wd.bind("<Button-3>", lambda e: self.close())
        w.bind("<Escape>", lambda e: self.close())
        self.win = w
        self._fill(head, body, error)
        w.deiconify()
        if IS_WIN:
            try:
                w.update_idletasks()
                no_activate_win(w)
            except Exception:
                pass
        self._place()
        app.root.after(250, self._watch)

    def update(self, head, body, error=False):
        if self.alive():
            self._fill(head, body, error)
            self._place()

    def _fill(self, head, body, error):
        self.head.configure(text=head)
        self.body.configure(text=body, fg=self.RED if error else "#111111")
        self.copy_text = "" if error else body
        self.foot.configure(text="右键或 Esc 关闭" if error else "点击复制译文 · 右键或 Esc 关闭")

    def _place(self):
        w = self.win
        w.update_idletasks()
        bw, bh = w.winfo_reqwidth(), w.winfo_reqheight()
        l, t, r, b = screen_bounds() or (0, 0, w.winfo_screenwidth(), w.winfo_screenheight())
        x, y = self.anchor
        px, py = x + 14, y + 22
        if px + bw > r - 8:
            px = max(l + 8, r - bw - 8)
        if py + bh > b - 8:
            py = max(t + 8, y - bh - 14)         # 下面放不下就放到指针上方
        w.geometry("+%d+%d" % (px, py))

    def _click(self, _e=None):
        if self.copy_text:
            self.app._set_clip(self.copy_text)
            self.app.last_clip = self.copy_text
            self.app.status.configure(text="已复制译文")
        self.close()

    def _inside(self, px, py):
        w = self.win
        return (w.winfo_rootx() <= px <= w.winfo_rootx() + w.winfo_width()
                and w.winfo_rooty() <= py <= w.winfo_rooty() + w.winfo_height())

    def _watch(self):
        if not self.alive():
            return
        px, py = self.win.winfo_pointerxy()
        inside = self._inside(px, py)
        far = math.hypot(px - self.anchor[0], py - self.anchor[1]) > self.MOVE_AWAY
        if not inside and (far or time.time() - self.t0 > self.MAX_SECONDS):
            self.close()
            return
        self.app.root.after(250, self._watch)


class App:
    def __init__(self):
        self.cfg = self._load_cfg()

        self.q = queue.Queue()
        self.seq = 0
        self.timer = None
        self.detected = ""
        self.pairs = []
        self.last_clip = ""
        self.old_clip = ""
        self.grabbing = False
        self.grab_mode, self.grab_xy, self.grab_scope, self.grab_plan = "main", (0, 0), "word", []
        self.bseq = 0
        self.dl_busy = False
        self.dl_cancel = False
        self.tray = None
        self.hover_last = None
        self.hover_since = 0.0
        self.hover_fired = False
        self.shot_win = None

        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry(self.cfg.get("geometry") or DEFAULTS["geometry"])
        self.root.minsize(520, 420)
        try:
            if IS_WIN:
                self.root.iconbitmap(resource_path("app.ico"))
        except Exception:
            pass
        self.root.report_callback_exception = self._on_tk_error
        self.bubble = Bubble(self)
        self._build_ui()

        self.last_clip = self._get_clip()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: (self.bubble.close(), self.hide_window()))
        self.root.after(100, self._poll)
        self.root.after(600, self._watch_clip)
        self.root.after(1500, self._warmup)
        self._start_hotkey()
        self._start_tray()
        if "--minimized" in sys.argv:
            self.hide_window()

    @staticmethod
    def _load_cfg():
        cfg = dict(DEFAULTS)
        for path in (CONFIG_PATH, OLD_CONFIG_PATH):      # 新位置优先，兼容旧版配置
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    cfg.update(data)
                    break
            except Exception:
                continue
        # 校验，避免坏配置让程序起不来
        if cfg.get("engine") not in ENGINES:
            cfg["engine"] = "Google"
        if cfg.get("tl") not in LANGS:
            cfg["tl"] = DEFAULTS["tl"]
        if cfg.get("sl") != "auto" and cfg.get("sl") not in LANGS:
            cfg["sl"] = "auto"
        if cfg.get("pointer_scope") not in SCOPE_NAMES:
            cfg["pointer_scope"] = "word"
        cfg["pointer"] = bool(cfg.get("pointer", True))
        cfg["hover"] = bool(cfg.get("hover", True))
        try:
            cfg["hover_ms"] = int(cfg.get("hover_ms", 800))
        except Exception:
            cfg["hover_ms"] = 800
        cfg["hover_ms"] = max(300, min(cfg["hover_ms"], 3000))
        if not isinstance(cfg.get("pack_mirror"), str):
            cfg["pack_mirror"] = ""
        if not re.match(r"^\d+x\d+([+-]-?\d+[+-]-?\d+)?$", str(cfg.get("geometry", ""))):
            cfg["geometry"] = DEFAULTS["geometry"]
        return cfg

    def _on_tk_error(self, exc, val, tb):
        import traceback
        text = "".join(traceback.format_exception(exc, val, tb))
        log_crash(text)
        self.status.configure(text="发生内部错误，详见 %s" % CRASH_LOG)

    def hide_window(self):
        # 有托盘时隐藏到托盘（withdraw，任务栏不留窗口，点托盘图标找回）；
        # 没托盘时才最小化——旧版 withdraw 后没有托盘图标，窗口就找不回来了。
        if getattr(self, "tray", None) is not None and self.tray.is_running():
            self.root.withdraw()
        else:
            self.root.iconify()

    def _on_close(self):
        # 点 ×：有托盘就隐藏到托盘（真正退出走托盘右键菜单 / 主界面「退出」按钮）
        if getattr(self, "tray", None) is not None and self.tray.is_running():
            self.hide_window()
        else:
            self.quit()

    def _start_tray(self):
        # 托盘只在 Windows 上有；失败（比如被安全软件拦了）也不影响主程序，
        # 只是退回最小化行为。回调只往队列里放事件，绝不在托盘线程碰 Tk。
        if not IS_WIN:
            return
        try:
            self.tray = tray_win32.TrayIcon(
                icon_path=resource_path("app.ico"), tooltip=APP_TITLE,
                on_show=lambda: self.q.put(("tray_show",)),
                on_screenshot=lambda: self.q.put(("tray_shot",)),
                on_quit=lambda: self.q.put(("tray_quit",)))
            if not self.tray.start():
                self.tray = None
        except Exception:
            self.tray = None

    def _text_with_scroll(self, parent, **kw):
        frame = ttk.Frame(parent)
        sb = ttk.Scrollbar(frame, orient="vertical")
        txt = tk.Text(frame, wrap="word", relief="solid", borderwidth=1, yscrollcommand=sb.set, **kw)
        sb.configure(command=txt.yview)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)
        return frame, txt

    def _build_ui(self):
        if IS_WIN:
            font = ("Microsoft YaHei UI", 11)
            ui_font = ("Microsoft YaHei UI", 10)
        elif IS_MAC:
            font = ("PingFang SC", 13)
            ui_font = ("PingFang SC", 12)
        else:
            font = ("Noto Sans CJK SC", 11)
            ui_font = ("Noto Sans CJK SC", 10)

        self.font, self.ui_font = font, ui_font
        root = self.root
        style = ttk.Style()
        try:
            style.configure("TCombobox", padding=2)
            style.configure("TButton", padding=(8, 3))
            style.configure("TCheckbutton", padding=2)
        except Exception:
            pass

        # —— 第一行：语言 + 引擎 ——
        top = ttk.Frame(root)
        top.pack(fill="x", padx=12, pady=(12, 4))

        names = list(LANGS.values())
        self.sl = ttk.Combobox(top, values=[AUTO] + names, state="readonly", width=11)
        self.tl = ttk.Combobox(top, values=names, state="readonly", width=11)
        self.sl.set(AUTO if self.cfg["sl"] == "auto" else lang_name(self.cfg["sl"]))
        self.tl.set(lang_name(self.cfg["tl"]))
        self.sl.pack(side="left", expand=True, fill="x")
        ttk.Button(top, text="⇄ 互换", width=6, command=self.swap).pack(side="left", padx=6)
        self.tl.pack(side="left", expand=True, fill="x")

        eng_frame = ttk.Frame(root)
        eng_frame.pack(fill="x", padx=12, pady=(2, 6))
        ttk.Label(eng_frame, text="引擎").pack(side="left")
        self.engine = ttk.Combobox(
            eng_frame, values=ENGINES, state="readonly", width=10)
        eng = self.cfg.get("engine", "Google")
        if eng not in ENGINES:
            eng = "Google"
        self.engine.set(eng)
        self.engine.pack(side="left", padx=(6, 12))
        self.engine.bind("<<ComboboxSelected>>", lambda e: (reset_online_state(), self._save(), self._warmup(), self.translate_now()))

        self.engine_hint = ttk.Label(eng_frame, text="", foreground="#5b6676")
        self.engine_hint.pack(side="left")
        self._update_engine_hint()

        for cb in (self.sl, self.tl):
            cb.bind("<<ComboboxSelected>>", lambda e: (self._save(), self.translate_now()))

        # —— 原文 / 译文 ——
        paned = ttk.PanedWindow(root, orient="vertical")
        paned.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        f1, f2 = ttk.Frame(paned), ttk.Frame(paned)
        paned.add(f1, weight=1)
        paned.add(f2, weight=1)
        self.paned, self.f1 = paned, f1

        ttk.Label(f1, text="原文").pack(anchor="w")
        box, self.src = self._text_with_scroll(f1, height=7, font=font, undo=True)
        box.pack(fill="both", expand=True, pady=(2, 6))
        self.src.bind("<<Modified>>", self._on_modified)

        row = ttk.Frame(f2)
        row.pack(fill="x")
        ttk.Label(row, text="译文").pack(side="left")
        self.status = ttk.Label(row, text="", foreground="#5b6676")
        self.status.pack(side="right")
        box2, self.dst = self._text_with_scroll(f2, height=7, font=font, state="disabled")
        box2.pack(fill="both", expand=True, pady=(2, 6))
        self.dst.tag_configure("src", foreground="#6b7380")

        # —— 按钮 ——
        btns = ttk.Frame(root)
        btns.pack(fill="x", padx=12, pady=(2, 0))
        ttk.Button(btns, text="复制译文", command=self.copy_result).pack(side="left")
        ttk.Button(btns, text="清空", command=self.clear).pack(side="left", padx=6)
        ttk.Button(btns, text="网络检查", command=self.open_netcheck).pack(side="left", padx=6)
        ttk.Button(btns, text="离线语言包…", command=self._show_offline_packs).pack(side="left")
        ttk.Button(btns, text="截图翻译", command=self.start_screenshot).pack(side="left", padx=6)
        ttk.Button(btns, text="退出", command=self.quit).pack(side="right")

        # —— 选项区（两行，更整齐） ——
        self.top_var = tk.BooleanVar(value=self.cfg["top"])
        self.watch_var = tk.BooleanVar(value=self.cfg["watch"])
        self.smart_var = tk.BooleanVar(value=self.cfg["smart"])
        self.bi_var = tk.BooleanVar(value=self.cfg["bilingual"])
        self.reflow_var = tk.BooleanVar(value=self.cfg["reflow"])
        self.show_src_var = tk.BooleanVar(value=self.cfg["show_src"])

        opts = ttk.LabelFrame(root, text="选项", padding=(8, 4))
        opts.pack(fill="x", padx=12, pady=(8, 0))

        o1 = ttk.Frame(opts)
        o1.pack(fill="x")
        ttk.Checkbutton(o1, text="窗口置顶", variable=self.top_var, command=self._on_top).pack(side="left")
        ttk.Checkbutton(o1, text="监听剪贴板", variable=self.watch_var, command=self._on_watch).pack(side="left", padx=10)
        ttk.Checkbutton(o1, text="中英智能互译", variable=self.smart_var, command=self._retranslate).pack(side="left")
        ttk.Checkbutton(o1, text="显示原文", variable=self.show_src_var, command=self._on_show_src).pack(side="left", padx=10)

        o2 = ttk.Frame(opts)
        o2.pack(fill="x", pady=(2, 0))
        ttk.Checkbutton(o2, text="双语对照", variable=self.bi_var, command=self._on_bilingual).pack(side="left")
        ttk.Checkbutton(o2, text="合并断行（粘贴 PDF / 文档时用）", variable=self.reflow_var,
                        command=self._retranslate).pack(side="left", padx=10)

        if IS_WIN:
            self.auto_var = tk.BooleanVar(value=autostart_enabled())
            ttk.Checkbutton(o2, text="开机自启（最小化）", variable=self.auto_var,
                            command=self._on_autostart).pack(side="left")

        global AUTO_OFFLINE
        AUTO_OFFLINE = bool(self.cfg.get("auto_offline", True))
        self.auto_off_var = tk.BooleanVar(value=AUTO_OFFLINE)
        o3 = ttk.Frame(opts)
        o3.pack(fill="x", pady=(2, 0))
        ttk.Checkbutton(o3, text="断网 / 在线引擎不可用时，自动改用离线翻译", variable=self.auto_off_var,
                        command=self._on_auto_offline).pack(side="left")

        self.pointer_var = tk.BooleanVar(value=bool(self.cfg.get("pointer", True)))
        self.hover_var = tk.BooleanVar(value=bool(self.cfg.get("hover", True)))
        o4 = ttk.Frame(opts)
        o4.pack(fill="x", pady=(2, 0))
        ttk.Checkbutton(o4, text="指针取词（%s）" % POINTER_LABEL, variable=self.pointer_var,
                        command=self._on_pointer_opt).pack(side="left")
        ttk.Checkbutton(o4, text="悬停取词（鼠标停住自动取词）", variable=self.hover_var,
                        command=self._on_pointer_opt).pack(side="left", padx=(10, 0))
        ttk.Label(o4, text="范围").pack(side="left", padx=(10, 4))
        self.scope_cb = ttk.Combobox(o4, values=list(SCOPE_NAMES.values()), state="readonly", width=6)
        self.scope_cb.set(SCOPE_NAMES[self.cfg.get("pointer_scope", "word")])
        self.scope_cb.pack(side="left")
        self.scope_cb.bind("<<ComboboxSelected>>", lambda e: self._on_pointer_opt())

        self.hint = ttk.Label(root, text="", foreground="#5b6676", wraplength=560)
        self.hint.pack(anchor="w", fill="x", padx=12, pady=(6, 10))
        self.hint.bind("<Configure>", lambda e: self.hint.configure(wraplength=max(200, e.width - 8)))

        root.attributes("-topmost", self.top_var.get())
        if not self.show_src_var.get():
            self.paned.forget(self.f1)
        else:
            self.src.focus_set()

    def _update_engine_hint(self):
        eng = self.engine.get()
        if eng == "离线":
            if not offline_engine.runtime_present():
                self.engine_hint.configure(text="还没有离线组件，点「离线语言包…」下载")
            elif OFFLINE.pairs():
                self.engine_hint.configure(text="本地推理 · 已载入 %d 个语言包" % len(OFFLINE.pairs()))
            else:
                self.engine_hint.configure(text="尚无语言包，点「离线语言包…」下载或导入")
        elif eng == "微软":
            self.engine_hint.configure(text="Edge 免费端点，无需 Key")
        else:
            self.engine_hint.configure(text="Google 免费端点" + ("" if offline_engine.runtime_present() else " · 点「离线语言包…」可下载离线组件"))

    # ------------------------------------------------ 在线安装离线翻译组件（标准版）
    def _offer_runtime_install(self):
        ok, why = runtime_installer.supported()
        if not ok:
            messagebox.showinfo("离线翻译", why, parent=self.root)
            return
        if getattr(self, "rt_win", None) and self.rt_win.winfo_exists():
            self.rt_win.lift()
            return
        if not messagebox.askyesno(
                "离线翻译",
                "还没有离线翻译组件。\n\n"
                "需要先下载约 %d MB（ctranslate2 等，来自 PyPI 官方），装好后直接可用，不用重新构建程序。\n"
                "组件会放在：%s\n\n现在下载吗？" % (runtime_installer.SIZE_HINT_MB, _runtime_dir()),
                parent=self.root):
            return
        self._show_runtime_install()

    def _show_runtime_install(self):
        win = tk.Toplevel(self.root)
        win.title("下载离线翻译组件")
        win.geometry("620x250")
        win.transient(self.root)
        self.rt_win = win
        self.rt_busy, self.rt_cancel = True, False
        self._rt_speed = {"label": None, "t": 0.0, "done": 0, "v": 0.0}
        ttk.Label(win, text="正在下载离线翻译组件（numpy、ctranslate2 等）。下载中途断网可再次点击，会接着下。",
                  wraplength=580).pack(anchor="w", padx=12, pady=(14, 6))
        self.rt_bar = ttk.Progressbar(win, mode="determinate", maximum=100)
        self.rt_bar.pack(fill="x", padx=12)
        self.rt_msg = ttk.Label(win, text="正在连接 PyPI …", foreground="#5b6676", wraplength=580)
        self.rt_msg.pack(anchor="w", padx=12, pady=(4, 6))
        mrow = ttk.Frame(win)
        mrow.pack(fill="x", padx=12)
        ttk.Label(mrow, text="镜像（可选）").pack(side="left")
        self.rt_mirror = tk.StringVar(value=self.cfg.get("pack_mirror", ""))
        ttk.Entry(mrow, textvariable=self.rt_mirror).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Label(win, text="连不上 PyPI 时填，如 pypi.org=镜像域名;files.pythonhosted.org=镜像域名",
                  foreground="#8a93a2", wraplength=580).pack(anchor="w", padx=12, pady=(2, 0))
        brow = ttk.Frame(win)
        brow.pack(fill="x", padx=12, pady=12, side="bottom")
        self.rt_btn = ttk.Button(brow, text="取消", command=self._rt_cancel_or_close)
        self.rt_btn.pack(side="right")
        self.rt_retry = ttk.Button(brow, text="重试", command=self._rt_start, state="disabled")
        self.rt_retry.pack(side="right", padx=6)
        win.protocol("WM_DELETE_WINDOW", self._rt_cancel_or_close)
        self._rt_start()

    def _rt_alive(self):
        return bool(getattr(self, "rt_win", None) and self.rt_win.winfo_exists())

    def _rt_start(self):
        self.rt_busy, self.rt_cancel = True, False
        self.rt_retry.configure(state="disabled")
        self.rt_btn.configure(text="取消")
        self.rt_bar.configure(value=0)
        self.rt_msg.configure(text="正在连接 PyPI …", foreground="#5b6676")
        mirror = self.rt_mirror.get().strip()
        self.cfg["pack_mirror"] = mirror
        self._save()

        def job():
            try:
                versions = runtime_installer.install(
                    _runtime_dir(), replace=mirror,
                    progress=lambda i, n, fn, d, t: self.q.put(("rt_prog", i, n, fn, d, t)),
                    cancelled=lambda: self.rt_cancel)
                self.q.put(("rt_prog", -1, 0, "正在检查组件能否加载…", 0, 0))
                runtime_installer.activate(_runtime_dir())
                runtime_installer.verify_import()
                self.q.put(("rt_done", True, "", False))
            except pack_downloader.Cancelled:
                self.q.put(("rt_done", False, "", True))
            except Exception as e:      # noqa: BLE001
                self.q.put(("rt_done", False, str(e), False))
        threading.Thread(target=job, daemon=True).start()

    def _rt_cancel_or_close(self):
        if self.rt_busy:
            self.rt_cancel = True
            self.rt_msg.configure(text="正在取消…（已下载的部分会保留）")
        elif self._rt_alive():
            self.rt_win.destroy()

    def _on_rt_prog(self, i, n, fn, done, total):
        if not self._rt_alive():
            return
        if i < 0:
            self.rt_msg.configure(text=fn)
            return
        sp, now = self._rt_speed, time.time()
        if sp["label"] != fn or done < sp["done"]:
            sp.update(label=fn, t=now, done=done, v=0.0)
        elif now - sp["t"] >= 0.5:
            inst = (done - sp["done"]) / (now - sp["t"])
            sp.update(t=now, done=done, v=inst if not sp["v"] else sp["v"] * 0.6 + inst * 0.4)
        frac = (done / total) if total else 0
        self.rt_bar.configure(value=min(100.0, (i + frac) * 100.0 / n))
        txt = "（%d/%d）%s   %.0f / %.0f MB" % (i + 1, n, fn.split("-")[0], done / 1e6, (total or 0) / 1e6)
        if sp["v"] > 1000:
            txt += "   %.1f MB/s" % (sp["v"] / 1e6)
        self.rt_msg.configure(text=txt)

    def _on_rt_done(self, ok, err, cancelled):
        self.rt_busy = False
        if ok:
            if "离线" not in ENGINES:
                ENGINES.append("离线")
            self.engine.configure(values=ENGINES)
            OFFLINE.reload()
            self._update_engine_hint()
            if self._rt_alive():
                self.rt_win.destroy()
            self._show_offline_packs()
            self._show_pack_download()          # 接着就是下载语言包
            return
        if self._rt_alive():
            self.rt_btn.configure(text="关闭")
            self.rt_retry.configure(state="normal")
            self.rt_msg.configure(
                text="已取消。再点「重试」会接着下载。" if cancelled else "失败：%s" % err,
                foreground="#5b6676" if cancelled else "#b42318")

    # ------------------------------------------------ 离线语言包管理
    def _show_offline_packs(self):
        if not offline_engine.runtime_present():
            self._offer_runtime_install()
            return
        if getattr(self, "pack_win", None) and self.pack_win.winfo_exists():
            self.pack_win.lift()
            return
        win = tk.Toplevel(self.root)
        win.title("离线语言包")
        win.geometry("660x420")
        win.transient(self.root)
        self.pack_win = win
        ttk.Label(win, text="离线翻译使用 Argos 语言包（.argosmodel），在本机运行，不联网、不上传文字。",
                  wraplength=520).pack(anchor="w", padx=12, pady=(12, 4))
        cols = ("pair", "ver", "src", "state")
        tv = ttk.Treeview(win, columns=cols, show="headings", height=10)
        for c, t, w in (("pair", "翻译方向", 120), ("ver", "版本", 70), ("src", "来源", 90), ("state", "状态", 220)):
            tv.heading(c, text=t)
            tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=12, pady=4)
        self.pack_tv = tv
        self.pack_msg = ttk.Label(win, text="", foreground="#5b6676", wraplength=520)
        self.pack_msg.pack(anchor="w", padx=12)
        row = ttk.Frame(win)
        row.pack(fill="x", padx=12, pady=10)
        ttk.Button(row, text="下载语言包…", command=self._show_pack_download).pack(side="left")
        ttk.Button(row, text="导入语言包…", command=self._import_packs).pack(side="left", padx=6)
        ttk.Button(row, text="打开语言包目录", command=self._open_models_dir).pack(side="left")
        ttk.Button(row, text="手动下载页面", command=self._open_pack_index).pack(side="left", padx=6)
        ttk.Button(row, text="关闭", command=win.destroy).pack(side="right")
        self._refresh_packs()

    def _refresh_packs(self):
        if not (getattr(self, "pack_win", None) and self.pack_win.winfo_exists()):
            return
        tv = self.pack_tv
        tv.delete(*tv.get_children())
        for pkg in sorted(OFFLINE.packs, key=lambda x: (x.from_code, x.to_code)):
            tv.insert("", "end", values=("%s → %s" % (lang_name(pkg.from_code), lang_name(pkg.to_code)),
                                         pkg.version, pkg.source, "可用"))
        for pkg in OFFLINE.broken:
            tv.insert("", "end", values=("%s → %s" % (pkg.from_code or "?", pkg.to_code or "?"),
                                         pkg.version, pkg.source, "不可用：" + pkg.problem))
        if not offline_engine.runtime_present():
            self.pack_msg.configure(text="还没有离线翻译组件（ctranslate2 / sentencepiece）。")
        elif not OFFLINE.packs:
            self.pack_msg.configure(text="还没有语言包。点「下载语言包…」直接联网下载（也可「导入语言包…」选本地 .argosmodel 文件）。")
        else:
            self.pack_msg.configure(
                text="没有直达语言对时会自动经英语中转（如 日→中 = 日→英 + 英→中）。")
        self._update_engine_hint()

    def _import_packs(self):
        paths = filedialog.askopenfilenames(
            parent=self.pack_win, title="选择语言包",
            filetypes=[("Argos 语言包", "*.argosmodel *.zip"), ("所有文件", "*.*")])
        if not paths:
            return
        self.pack_msg.configure(text="正在导入，请稍候…（语言包较大时需要几秒）")

        def job():
            ok, bad = [], []
            for path in paths:
                try:
                    pkg = offline_engine.install_package(path, USER_MODELS_DIR)
                    ok.append("%s → %s" % (pkg.from_code, pkg.to_code))
                except Exception as e:      # noqa: BLE001
                    bad.append("%s：%s" % (os.path.basename(path), e))
            self.q.put(("pack_done", ok, bad))
        threading.Thread(target=job, daemon=True).start()

    def _on_pack_done(self, ok, bad):
        OFFLINE.reload()
        self._refresh_packs()
        if getattr(self, "pack_win", None) and self.pack_win.winfo_exists():
            msg = ""
            if ok:
                msg += "已导入：" + "、".join(ok) + "。"
            if bad:
                msg += "\n失败：\n" + "\n".join(bad)
            self.pack_msg.configure(text=msg or "")
        if ok:
            self.translate_now()

    @staticmethod
    def _open_path(path):
        try:
            os.makedirs(path, exist_ok=True)
            if IS_WIN:
                os.startfile(path)                      # noqa: S606
            else:
                import subprocess
                subprocess.Popen(["open" if IS_MAC else "xdg-open", path])
        except Exception as e:      # noqa: BLE001
            messagebox.showerror("打开目录", str(e))

    def _open_models_dir(self):
        self._open_path(USER_MODELS_DIR)

    def _open_pack_index(self):
        import webbrowser
        webbrowser.open("https://github.com/argosopentech/argospm-index")

    # ------------------------------------------------ 在线下载语言包
    def _show_pack_download(self):
        if getattr(self, "dl_win", None) and self.dl_win.winfo_exists():
            self.dl_win.lift()
            return
        win = tk.Toplevel(self.root)
        win.title("下载离线语言包")
        win.geometry("700x560")
        win.transient(self.root)
        self.dl_win = win
        self.dl_best = {}
        self.dl_iid = {}
        self.dl_note = ttk.Label(win, text="正在获取语言包列表…", foreground="#5b6676", wraplength=660)
        self.dl_note.pack(anchor="w", padx=12, pady=(12, 4))

        frow = ttk.Frame(win)
        frow.pack(fill="x", padx=12)
        ttk.Label(frow, text="搜索").pack(side="left")
        self.dl_filter = tk.StringVar()
        ent = ttk.Entry(frow, textvariable=self.dl_filter)
        ent.pack(side="left", fill="x", expand=True, padx=6)
        self.dl_filter.trace_add("write", lambda *a: self._dl_fill())
        ttk.Label(frow, text="（可输入 日语 / ja / 德 …）", foreground="#8a93a2").pack(side="left")

        # 底部三行先排版（按钮最下、镜像其上、进度再上），列表占满剩余空间
        brow = ttk.Frame(win)
        brow.pack(fill="x", padx=12, pady=(0, 10), side="bottom")
        mrow = ttk.Frame(win)
        mrow.pack(fill="x", padx=12, pady=(0, 6), side="bottom")
        prow = ttk.Frame(win)
        prow.pack(fill="x", padx=12, pady=(0, 4), side="bottom")
        self.dl_bar = ttk.Progressbar(prow, mode="determinate", maximum=100)
        self.dl_bar.pack(fill="x")
        self.dl_prog = ttk.Label(prow, text="", foreground="#5b6676", wraplength=660)
        self.dl_prog.pack(anchor="w", pady=(2, 0))

        cols = ("pair", "code", "ver", "state")
        tv = ttk.Treeview(win, columns=cols, show="headings", height=12, selectmode="extended")
        for c, t, w in (("pair", "翻译方向", 230), ("code", "代码", 90), ("ver", "版本", 80), ("state", "状态", 120)):
            tv.heading(c, text=t)
            tv.column(c, width=w, anchor="w")
        sb = ttk.Scrollbar(win, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 12), pady=6)
        tv.pack(fill="both", expand=True, padx=(12, 0), pady=6)
        self.dl_tv = tv

        ttk.Label(mrow, text="镜像（可选）").pack(side="left")
        self.dl_mirror = tk.StringVar(value=self.cfg.get("pack_mirror", ""))
        ttk.Entry(mrow, textvariable=self.dl_mirror).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Label(mrow, text="下载不动时填：旧域名=新域名", foreground="#8a93a2").pack(side="left")

        ttk.Button(brow, text="下载当前翻译方向所需", command=self._dl_needed).pack(side="left")
        self.dl_btn = ttk.Button(brow, text="下载所选", command=self._dl_selected)
        self.dl_btn.pack(side="left", padx=6)
        ttk.Button(brow, text="刷新列表", command=lambda: self._dl_load(force=True)).pack(side="left")
        self.dl_stop = ttk.Button(brow, text="取消下载", command=self._dl_do_cancel, state="disabled")
        self.dl_stop.pack(side="left", padx=6)
        ttk.Button(brow, text="关闭", command=self._dl_close).pack(side="right")
        win.protocol("WM_DELETE_WINDOW", self._dl_close)
        self._dl_load()
        ent.focus_set()

    def _dl_close(self):
        if self.dl_busy:
            self.dl_cancel = True
        if getattr(self, "dl_win", None) and self.dl_win.winfo_exists():
            self.dl_win.destroy()

    def _dl_alive(self):
        return bool(getattr(self, "dl_win", None) and self.dl_win.winfo_exists())

    def _dl_load(self, force=False):
        self.dl_note.configure(text="正在获取语言包列表…", foreground="#5b6676")
        mirror = self.dl_mirror.get().strip()

        def job():
            try:
                index, note, stale = pack_downloader.fetch_index(
                    _index_cache(), replace=mirror, max_age=None if force else 24 * 3600)
                self.q.put(("dl_index", pack_downloader.best_by_pair(index), note, stale, ""))
            except Exception as e:      # noqa: BLE001
                self.q.put(("dl_index", {}, "", False, str(e)))
        threading.Thread(target=job, daemon=True).start()

    def _on_dl_index(self, best, note, stale, err):
        if not self._dl_alive():
            return
        if err:
            self.dl_note.configure(text=err, foreground="#b42318")
            return
        self.dl_best = best
        self.dl_note.configure(
            text="%s，共 %d 个语言对。选中后点「下载所选」；没有直达语言对时会自动经英语中转。" % (note, len(best)),
            foreground="#b26a00" if stale else "#5b6676")
        self._dl_fill()

    @staticmethod
    def _pack_label(entry):
        a = lang_name(entry.get("from_code")) or entry.get("from_name") or entry.get("from_code")
        b = lang_name(entry.get("to_code")) or entry.get("to_name") or entry.get("to_code")
        if a == entry.get("from_code") and entry.get("from_name"):
            a = entry["from_name"]
        if b == entry.get("to_code") and entry.get("to_name"):
            b = entry["to_name"]
        return "%s → %s" % (a, b)

    def _dl_fill(self):
        if not self._dl_alive():
            return
        tv = self.dl_tv
        keep = {self.dl_iid.get(i) for i in tv.selection()}
        tv.delete(*tv.get_children())
        self.dl_iid = {}
        q = self.dl_filter.get().strip().lower()
        common = {base(c) for c in LANGS}
        rows = []
        for pair, e in self.dl_best.items():
            label = self._pack_label(e)
            hay = (label + " " + pair[0] + " " + pair[1] + " " + str(e.get("from_name", "")) + " " +
                   str(e.get("to_name", ""))).lower()
            if q and q not in hay:
                continue
            rank = 0 if (pair[0] in common and pair[1] in common) else 1
            rows.append((rank, "en" not in pair, label, pair, e))
        for _, _, label, pair, e in sorted(rows, key=lambda r: (r[0], r[1], r[2])):
            iid = tv.insert("", "end", values=(label, "%s-%s" % pair, e.get("package_version", ""),
                                               pack_downloader.status_of(pair, e, OFFLINE)))
            self.dl_iid[iid] = pair
            if pair in keep:
                tv.selection_add(iid)

    def _dl_selected(self):
        pairs = [self.dl_iid[i] for i in self.dl_tv.selection() if i in self.dl_iid]
        if not pairs:
            self.dl_prog.configure(text="请先在列表里选择要下载的语言对（可按住 Ctrl / Shift 多选）。")
            return
        self._dl_start(pairs)

    def _needed_pairs(self):
        """当前翻译方向需要的语言对。源语言为「自动检测」时按中英互译 + 英↔目标语言 处理。"""
        sl, tl = self._codes()
        t = to_argos(tl)
        if sl != "auto":
            return [(to_argos(sl), t)]
        if t == "en":
            return [("zh", "en"), ("en", "zh")]
        return [("en", t), (t, "en")]

    def _dl_needed(self):
        if not self.dl_best:
            self.dl_prog.configure(text="语言包列表还没获取到，请稍候或点「刷新列表」。")
            return
        want, hopeless = [], []
        for f, t in self._needed_pairs():
            need = pack_downloader.missing_for(OFFLINE, f, t, self.dl_best)
            if need is None:
                hopeless.append("%s→%s" % (f, t))
            else:
                want += [n for n in need if n not in want]
        if hopeless:
            self.dl_prog.configure(text="官方列表里没有 %s 的语言包，无法离线翻译这个方向。" % "、".join(hopeless))
            if not want:
                return
        if not want:
            self.dl_prog.configure(text="当前翻译方向的语言包都已安装，不需要下载。")
            return
        self._dl_start(want)

    def _dl_start(self, pairs):
        if self.dl_busy:
            return
        mirror = self.dl_mirror.get().strip()
        self.cfg["pack_mirror"] = mirror
        self._save()
        self.dl_busy, self.dl_cancel = True, False
        self._dl_speed = {"label": None, "t": 0.0, "done": 0, "v": 0.0}
        self.dl_btn.configure(state="disabled")
        self.dl_stop.configure(state="normal")
        best, n = dict(self.dl_best), len(pairs)

        def job():
            ok, bad, last = [], [], [0.0]
            for i, pair in enumerate(pairs):
                label = "%s → %s" % pair
                if self.dl_cancel:
                    break

                def prog(done, total, i=i, label=label):
                    now = time.time()
                    if now - last[0] >= 0.15 or (total and done >= total):
                        last[0] = now
                        self.q.put(("dl_prog", i, n, label, done, total))
                try:
                    self.q.put(("dl_prog", i, n, label, 0, 0))
                    pack_downloader.download_pack(best[pair], USER_MODELS_DIR, _dl_dir(), mirror,
                                                  progress=prog, cancelled=lambda: self.dl_cancel)
                    ok.append(label)
                except pack_downloader.Cancelled:
                    break
                except Exception as e:      # noqa: BLE001
                    bad.append("%s：%s" % (label, e))
            self.q.put(("dl_done", ok, bad, self.dl_cancel))
        threading.Thread(target=job, daemon=True).start()

    def _dl_do_cancel(self):
        self.dl_cancel = True
        if self._dl_alive():
            self.dl_prog.configure(text="正在取消…")

    def _on_dl_prog(self, i, n, label, done, total):
        if not self._dl_alive():
            return
        sp, now = self._dl_speed, time.time()
        if sp["label"] != label or done < sp["done"]:
            sp.update(label=label, t=now, done=done, v=0.0)
        elif now - sp["t"] >= 0.5:
            inst = (done - sp["done"]) / (now - sp["t"])
            sp.update(t=now, done=done, v=inst if not sp["v"] else sp["v"] * 0.6 + inst * 0.4)   # 平滑
        if total:
            self.dl_bar.configure(mode="determinate", value=done * 100.0 / total)
            txt = "（%d/%d）正在下载 %s   %.0f / %.0f MB" % (i + 1, n, label, done / 1e6, total / 1e6)
            if sp["v"] > 1000:
                eta = int((total - done) / sp["v"])
                txt += "   %.1f MB/s，剩约 %s" % (sp["v"] / 1e6, ("%d 分 %d 秒" % (eta // 60, eta % 60)) if eta >= 60 else "%d 秒" % eta)
        else:
            self.dl_bar.configure(mode="determinate", value=0)
            txt = "（%d/%d）正在连接 %s …" % (i + 1, n, label) if not done else \
                "（%d/%d）正在下载 %s   %.0f MB" % (i + 1, n, label, done / 1e6)
        self.dl_prog.configure(text=txt)

    def _on_dl_done(self, ok, bad, cancelled):
        self.dl_busy = False
        OFFLINE.reload()
        self._refresh_packs()
        if self._dl_alive():
            self.dl_btn.configure(state="normal")
            self.dl_stop.configure(state="disabled")
            self.dl_bar.configure(value=100 if (ok and not bad and not cancelled) else 0)
            msg = ""
            if ok:
                msg += "已安装：" + "、".join(ok) + "。"
                if self.engine.get() != "离线":
                    msg += ("把上方「引擎」切到「离线」即可使用" +
                            ("；保持 Google 时，断网会自动改用离线。" if AUTO_OFFLINE else "。"))
            if cancelled:
                msg += "已取消（已下载的部分会保留，再点下载会接着下）。"
            if bad:
                msg += "\n失败：\n" + "\n".join(bad)
            self.dl_prog.configure(text=msg or "没有需要下载的内容。")
            self._dl_fill()
        if ok:
            self._warmup()
            self.translate_now()

    # ------------------------------------------------ 离线引擎预热
    def _warmup(self):
        """选了「离线」引擎时，后台提前载入当前方向的模型，第一次翻译不再卡顿。"""
        if self.engine.get() != "离线" or not offline_engine.runtime_present() or getattr(self, "_warming", False):
            return
        sl, tl = self._codes()
        t = to_argos(tl)
        pkgs = OFFLINE.route(to_argos(sl), t) if sl != "auto" else \
            [p for p in OFFLINE.packs if p.to_code == t or p.from_code == t]
        if not pkgs:
            return
        self._warming = True

        def job():
            try:
                OFFLINE.warmup(pkgs[:2])
            finally:
                self._warming = False
        threading.Thread(target=job, daemon=True).start()

    # ------------------------------------------------ 指针取词
    def _on_pointer_opt(self):
        self.cfg["pointer_scope"] = SCOPE_CODES.get(self.scope_cb.get(), "word")
        self.cfg["hover"] = self.hover_var.get()
        self.hover_fired = False
        self._save()

    def _pointer_empty_msg(self):
        if not IS_WIN:
            return "没有取到文字。请先选中文字，再按 %s。" % POINTER_LABEL
        if not self.grab_plan:
            return "终端窗口里请先选中文字，再按 %s。" % HOTKEY_LABEL
        if self.grab_plan == ["copy"]:
            return ("指针下不是可选文字（光标不是「I」形）。\n"
                    "请把指针放到文字上；或先选中文字，再按 %s。" % HOTKEY_LABEL)
        return "没有取到文字。这个位置的文字可能不可选（图片、按钮等）。"

    def _pointer_translate(self, text, xy):
        self.bseq += 1
        my = self.bseq
        if not text:
            self.bubble.show(xy, "指针取词", self._pointer_empty_msg(), error=True)
            return
        text = text[:1000]
        sl, tl = self._codes()
        head = text.replace("\n", " ")
        head = head if len(head) <= 60 else head[:60] + "…"
        self.bubble.show(xy, head, "翻译中…")
        threading.Thread(target=self._bubble_worker,
                         args=(my, text, sl, tl, self.smart_var.get(), self.engine.get()),
                         daemon=True).start()

    def _bubble_worker(self, my, text, sl, tl, smart, engine):
        try:
            out, det, target = translate(text, sl, tl, smart, engine, cancelled=lambda: my != self.bseq)
            self.q.put(("bubble", my, True, out, "%s → %s" % (lang_name(det), lang_name(target)), text))
        except Exception as e:      # noqa: BLE001
            if my != self.bseq:
                return
            if isinstance(e, offline_engine.OfflineError):
                msg = str(e)
            elif netcheck.is_connectivity_error(e):
                msg = "网络不通，翻译失败。可在主窗口点「网络检查」，或把引擎切到「离线」。"
            else:
                msg = "翻译失败：%s" % e
            self.q.put(("bubble", my, False, msg[:300], "", text))

    def _on_bubble(self, my, ok, out, route, text):
        if my != self.bseq or not self.bubble.alive():
            return
        head = text.replace("\n", " ")
        head = head if len(head) <= 40 else head[:40] + "…"
        self.bubble.update("%s   %s" % (head, route) if ok else head, out, error=not ok)

    # ------------------------------------------------ 悬停取词 / 截图翻译
    def _ocr_lang(self):
        try:
            sl, _tl = self._codes()
        except Exception:
            return None
        return None if sl == "auto" else sl

    def _hover_check(self):
        """悬停取词：鼠标停住不动满 hover_ms 就自动取词（_poll 每 100ms 调一次）。"""
        if not IS_WIN or self.grabbing or getattr(self, "shot_win", None) is not None:
            self.hover_last = None
            return
        try:
            if not self.hover_var.get() or self.bubble.alive():
                self.hover_last = None
                return
            pos = self.root.winfo_pointerxy()
        except Exception:
            return
        try:
            if self.root.winfo_viewable():
                rx, ry = self.root.winfo_rootx(), self.root.winfo_rooty()
                if rx <= pos[0] <= rx + self.root.winfo_width() \
                        and ry <= pos[1] <= ry + self.root.winfo_height():
                    self.hover_last = None      # 在本窗口里不触发，避免自己取自己
                    return
        except Exception:
            pass
        now = time.time()
        if pos != self.hover_last:
            self.hover_last, self.hover_since, self.hover_fired = pos, now, False
            return
        if self.hover_fired:
            return
        if (now - self.hover_since) * 1000 < self.cfg.get("hover_ms", 800):
            return
        self.hover_fired = True
        self._on_hover(pos)

    def _on_hover(self, pos):
        self.grab_mode = "hover"
        self.grab_xy = pos
        threading.Thread(target=self._hover_worker, args=(pos,), daemon=True).start()

    def _hover_worker(self, pos):
        # 先走截图 OCR：截光标周围一小块，认出离光标最近的单词。
        # 这条路不依赖软件本身是否支持选词，图片 / 游戏 / 扫描 PDF 里也能用。
        word, ibeam = None, False
        try:
            if ocr_win.ocr_available():
                bounds = screen_bounds()
                if bounds is None:
                    bounds = (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
                x, y, w, h = screen_win.clamp_region(pos[0] - 210, pos[1] - 55, 420, 110, bounds)
                os.makedirs(DATA_DIR, exist_ok=True)
                tmp = os.path.join(DATA_DIR, "hover.bmp")
                screen_win.capture_file(tmp, x, y, w, h)
                try:
                    words = ocr_win.ocr_words(tmp, lang=self._ocr_lang())
                    word = ocr_win.pick_word_at(words, pos[0] - x, pos[1] - y)
                finally:
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass
        except Exception:
            word = None
        if not word:
            try:
                ibeam = cursor_is_ibeam_win()
            except Exception:
                ibeam = False
        self.q.put(("hover_ocr", word, pos, ibeam))

    def start_screenshot(self):
        """截图翻译：框选屏幕任意区域 → 系统 OCR 认字 → 翻译。"""
        if not IS_WIN:
            self.status.configure(text="截图翻译只支持 Windows")
            return
        if getattr(self, "shot_win", None) is not None or self.grabbing:
            return
        bounds = screen_bounds()
        if bounds is None:
            bounds = (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        left, top, right, bottom = bounds
        width, height = right - left, bottom - top
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        try:
            win.attributes("-alpha", 0.30)
        except Exception:
            pass
        win.geometry("%dx%d+%d+%d" % (width, height, left, top))
        win.configure(bg="black", cursor="crosshair")
        canvas = tk.Canvas(win, bg="black", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        state = {"start": None, "rect": None}

        def cancel(_e=None):
            try:
                win.destroy()
            except Exception:
                pass
            self.shot_win = None

        def on_press(e):
            state["start"] = (left + e.x, top + e.y)

        def on_motion(e):
            if state["start"] is None:
                return
            x0, y0 = state["start"]
            x1, y1 = left + e.x, top + e.y
            if state["rect"] is not None:
                canvas.delete(state["rect"])
            state["rect"] = canvas.create_rectangle(
                x0 - left, y0 - top, x1 - left, y1 - top,
                outline="#ff3b30", width=2)

        def on_release(e):
            if state["start"] is None:
                cancel()
                return
            x0, y0 = state["start"]
            x1, y1 = left + e.x, top + e.y
            rect = (min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            xy = (x0, y0)
            cancel()
            if rect[2] < 10 or rect[3] < 10:
                self.status.configure(text="框选区域太小，请重新框选")
                return
            threading.Thread(target=self._shot_worker, args=(rect, xy), daemon=True).start()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_motion)
        canvas.bind("<ButtonRelease-1>", on_release)
        win.bind("<Escape>", cancel)
        win.bind("<Button-3>", cancel)
        self.shot_win = win
        try:
            win.focus_force()
        except Exception:
            pass

    def _shot_worker(self, rect, xy):
        x, y, w, h = rect
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = os.path.join(DATA_DIR, "shot.bmp")
            time.sleep(0.15)      # 等框选层彻底消失，否则会把黑框也截进去
            screen_win.capture_file(tmp, x, y, w, h)
            try:
                text = ocr_win.ocr_image(tmp, lang=self._ocr_lang())
            finally:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
            self.q.put(("shot_ocr", True, text.strip(), xy))
        except Exception as e:
            self.q.put(("shot_ocr", False, str(e)[:300], xy))

    def _on_shot_ocr(self, ok, text, xy):
        text = (text or "").strip()
        if not ok:
            self.status.configure(text="截图 OCR 失败：%s" % text)
            return
        if not text:
            self.status.configure(text="截图里没有识别到文字（可能需要安装 OCR 语言包，或把框选范围再放大一点）")
            return
        self._set_src(text[:MAX_LEN])
        self.show_window()
        self.translate_now()

    # ------------------------------------------------ 网络检查
    _NET_ORDER = [("net", "基础联网（外网 TCP 直连）"), ("dns", "DNS 解析"), ("proxy", "系统代理"),
                  ("google", "Google 翻译"), ("ms", "微软翻译"), ("offline", "离线引擎")]

    def open_netcheck(self):
        if getattr(self, "net_win", None) and self.net_win.winfo_exists():
            self.net_win.lift()
            self._start_netcheck()
            return
        win = tk.Toplevel(self.root)
        win.title("网络检查")
        win.geometry("600x430")
        win.minsize(460, 320)
        win.transient(self.root)
        self.net_win = win
        box, self.net_txt = self._text_with_scroll(win, height=14, font=("Consolas" if IS_WIN else "monospace", 10),
                                                  state="disabled")
        box.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        for tag, color in (("ok", "#15803d"), ("bad", "#b42318"), ("info", "#5b6676"), ("warn", "#b45309")):
            self.net_txt.tag_configure(tag, foreground=color)
        self.net_txt.tag_configure("head", font=("Microsoft YaHei UI" if IS_WIN else "TkDefaultFont", 10, "bold"))
        row = ttk.Frame(win)
        row.pack(fill="x", padx=12, pady=(0, 12))
        self.net_btn_re = ttk.Button(row, text="重新检测", command=self._start_netcheck)
        self.net_btn_re.pack(side="left")
        ttk.Button(row, text="复制报告", command=self._copy_net_report).pack(side="left", padx=6)
        self.net_btn_sw = ttk.Button(row, text="", command=self._apply_reco, state="disabled")
        self.net_btn_sw.pack(side="left")
        ttk.Button(row, text="关闭", command=win.destroy).pack(side="right")
        self._start_netcheck()

    def _start_netcheck(self):
        self.net_run = getattr(self, "net_run", 0) + 1
        run = self.net_run
        self.net_items, self.net_reco = {}, None
        reset_online_state()
        self.net_btn_sw.configure(state="disabled", text="")
        self.net_btn_re.configure(state="disabled")
        self._render_net()
        info = {"runtime": offline_engine.runtime_present(), "pairs": OFFLINE.describe(),
                "count": len(OFFLINE.pairs())}

        def job():
            checks, reco = netcheck.run_all(
                google_fn=lambda: g_translate("hello", "en", "zh-CN", attempts=1, timeout=8)[0],
                ms_fn=lambda: ms_translate("hello", "en", "zh-CN", attempts=1, timeout=8)[0],
                offline_info=info,
                on_item=lambda c: self.q.put(("net_item", run, c)),
                cancelled=lambda: run != self.net_run)
            self.q.put(("net_done", run, checks, reco))
        threading.Thread(target=job, daemon=True).start()

    def _render_net(self):
        if not (getattr(self, "net_win", None) and self.net_win.winfo_exists()):
            return
        t = self.net_txt
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", "实时翻译 v%s 网络检查\n\n" % __version__, "head")
        for key, name in self._NET_ORDER:
            c = self.net_items.get(key)
            if c is None:
                t.insert("end", "… %s  检测中\n" % name, "info")
                continue
            tag = {True: "ok", False: "bad", None: "info"}[c.ok]
            t.insert("end", c.line() + "\n", tag)
            if c.hint and (c.ok is False or key == "proxy"):
                t.insert("end", "    ↳ " + c.hint + "\n", "info")
        if self.net_reco:
            t.insert("end", "\n结论：" + self.net_reco.message + "\n",
                     {"ok": "ok", "warn": "warn", "bad": "bad"}[self.net_reco.level])
        t.configure(state="disabled")

    def _on_net_done(self, checks, reco):
        self.net_reco = reco
        self.net_btn_re.configure(state="normal")
        cur = self.engine.get()
        if reco.engine and reco.engine != cur and reco.engine in ENGINES:
            self.net_btn_sw.configure(state="normal", text="切换到「%s」" % reco.engine)
        self._render_net()

    def _apply_reco(self):
        if self.net_reco and self.net_reco.engine in ENGINES:
            self.engine.set(self.net_reco.engine)
            self._save()
            self.net_btn_sw.configure(state="disabled", text="已切换")
            self.translate_now()

    def _copy_net_report(self):
        checks = [self.net_items[k] for k, _ in self._NET_ORDER if k in self.net_items]
        if not checks or not self.net_reco:
            return
        text = netcheck.format_report(checks, self.net_reco, "实时翻译 v%s 网络检查 %s" % (
            __version__, time.strftime("%Y-%m-%d %H:%M:%S")))
        self._set_clip(text)
        self.last_clip = text
        self.status.configure(text="已复制网络检查报告")

    def _on_show_src(self):
        shown = str(self.f1) in self.paned.panes()
        if self.show_src_var.get() and not shown:
            self.paned.insert(0, self.f1, weight=1)
            self.src.focus_set()
        elif not self.show_src_var.get() and shown:
            self.paned.forget(self.f1)
        self._save()

    def _codes(self):
        s = self.sl.get()
        sl = "auto" if s == AUTO else NAME2CODE.get(s, "auto")
        return sl, NAME2CODE.get(self.tl.get(), "zh-CN")

    def _save(self):
        sl, tl = self._codes()
        self.cfg.update(
            sl=sl, tl=tl, top=self.top_var.get(), watch=self.watch_var.get(),
            smart=self.smart_var.get(), bilingual=self.bi_var.get(),
            reflow=self.reflow_var.get(), show_src=self.show_src_var.get(),
            geometry=self.root.geometry(), engine=self.engine.get(),
            auto_offline=AUTO_OFFLINE, pointer=self.pointer_var.get(),
            hover=self.hover_var.get(), hover_ms=self.cfg.get("hover_ms", 800),
            pointer_scope=SCOPE_CODES.get(self.scope_cb.get(), "word"))
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = CONFIG_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, ensure_ascii=False, indent=1)
            os.replace(tmp, CONFIG_PATH)
        except Exception:
            pass
        self._update_engine_hint()

    def _retranslate(self):
        self._save()
        self.translate_now()

    def _on_auto_offline(self):
        global AUTO_OFFLINE
        AUTO_OFFLINE = self.auto_off_var.get()
        self._save()

    def _on_autostart(self):
        try:
            set_autostart(self.auto_var.get())
        except Exception as e:
            self.auto_var.set(autostart_enabled())
            messagebox.showerror("开机自启", "设置失败：%s" % e)

    def _on_top(self):
        self.root.attributes("-topmost", self.top_var.get())
        self._save()

    def _on_watch(self):
        if self.watch_var.get():
            self.last_clip = self._get_clip()
        self._save()

    def _on_bilingual(self):
        self._save()
        self.render()

    def _set_src(self, text):
        self.src.delete("1.0", "end")
        self.src.insert("1.0", text)
        self.src.edit_modified(False)
        self.src.edit_reset()

    def _set_dst_error(self, text):
        self.pairs = []
        self.dst.configure(state="normal", foreground="#b42318")
        self.dst.delete("1.0", "end")
        self.dst.insert("1.0", text)
        self.dst.configure(state="disabled")

    def plain_result(self):
        return "\n".join(d for _, d in self.pairs).strip()

    def render(self):
        t = self.dst
        t.configure(state="normal", foreground="#000000")
        t.delete("1.0", "end")
        bi = self.bi_var.get()
        for s, d in self.pairs:
            if not s and not d:
                t.insert("end", "\n")
            elif bi:
                t.insert("end", s + "\n", "src")
                t.insert("end", d + "\n\n")
            else:
                t.insert("end", d + "\n")
        t.configure(state="disabled")

    def _get_clip(self):
        try:
            return self.root.clipboard_get()
        except tk.TclError:
            return ""

    def _set_clip(self, text):
        self.root.clipboard_clear()
        if text:
            self.root.clipboard_append(text)

    def _on_modified(self, _e=None):
        if not self.src.edit_modified():
            return
        self.src.edit_modified(False)
        if self.timer:
            self.root.after_cancel(self.timer)
        self.timer = self.root.after(350, self.translate_now)

    def clear(self):
        self._set_src("")
        self.seq += 1
        self.pairs = []
        self.render()
        self.status.configure(text="")
        self.src.focus_set()

    def copy_result(self):
        text = self.plain_result()
        if text:
            self._set_clip(text)
            self.last_clip = text
            self.status.configure(text="已复制译文")

    def swap(self):
        sl, tl = self._codes()
        new_tl = sl if sl != "auto" else (self.detected or "en")
        self.sl.set(lang_name(tl) if tl in LANGS else AUTO)
        self.tl.set(lang_name(new_tl) if new_tl in LANGS else "英语")
        out = self.plain_result()
        if out:
            self._set_src(out)
        self._save()
        self.translate_now()

    def translate_now(self):
        text = self.src.get("1.0", "end").strip()
        self.seq += 1
        my = self.seq
        if not text:
            self.pairs = []
            self.render()
            self.status.configure(text="")
            return
        sl, tl = self._codes()
        engine = self.engine.get()
        self.truncated = len(text) > MAX_LEN
        self.status.configure(text="翻译中…")
        threading.Thread(
            target=self._worker,
            args=(my, text[:MAX_LEN], sl, tl, self.smart_var.get(),
                  self.reflow_var.get(), engine),
            daemon=True).start()

    def _worker(self, my, text, sl, tl, smart, reflow, engine):
        n0 = fallback_count()
        try:
            res = translate_doc(
                text, sl, tl, smart, reflow, engine,
                progress=lambda d, n: self.q.put(("progress", my, d, n)),
                cancelled=lambda: my != self.seq)
            self.q.put(("result", my, True, res + (fallback_count() > n0,)))
        except Exception as e:
            err = str(e)
            offline_msg = isinstance(e, offline_engine.OfflineError)
            if offline_msg:
                tip = ""
            elif _is_rate_limit(e) or "429" in err:
                tip = "\n\n建议：切换引擎到「微软」或「离线」，或稍后再试。"
            elif engine == "离线":
                tip = "\n\n提示：离线引擎需要语言包，请在「离线语言包…」中查看。"
            elif netcheck.is_connectivity_error(e):
                tip = "\n\n看起来是网络问题 —— 点下方「网络检查」可一键诊断原因。"
            elif engine == "微软":
                tip = "\n\n提示：微软端点可能变更，可切换 Google / 离线，或点「网络检查」。"
            else:
                tip = "\n\n请点「网络检查」诊断；也可切换到「微软」或「离线」引擎。"
            self.q.put(("result", my, False, "翻译失败：%s%s" % (err, tip)))

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        if not self.top_var.get():
            self.root.after(300, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()
        self.src.focus_set()

    def quit(self):
        self._save()
        try:
            if getattr(self, "tray", None) is not None:
                self.tray.stop()
        except Exception:
            pass
        try:
            self.bubble.close()
        except Exception:
            pass
        try:
            if getattr(self, "hk", None):
                self.hk.stop()
        except Exception:
            pass
        try:
            self.root.update()      # 让 Tk 把剪贴板内容交给系统，避免退出后剪贴板被清空
        except Exception:
            pass
        self.root.destroy()

    def _start_hotkey(self):
        ok_text = ("选中文字后按 %s 翻译；指针放在文字上按 %s 就地取词；按 %s 截图翻译；Esc 隐藏到托盘"
                   % (HOTKEY_LABEL, POINTER_LABEL, SCREENSHOT_LABEL)) if IS_WIN else \
                  ("选中文字后按 %s 翻译，或按 %s 在指针旁显示译文；Esc 隐藏窗口" % (HOTKEY_LABEL, POINTER_LABEL))
        if IS_WIN:
            try:
                ok = start_hotkey_win(self.q)
                pok = getattr(start_hotkey_win, "pointer_ok", False)
                sok = getattr(start_hotkey_win, "shot_ok", False)
                missing = []
                if not ok:
                    missing.append(HOTKEY_LABEL)
                if not pok:
                    missing.append(POINTER_LABEL)
                if not sok:
                    missing.append(SCREENSHOT_LABEL)
                if not missing:
                    self.hint.configure(text=ok_text)
                else:
                    self.hint.configure(text="%s 已被其他程序占用，不可用；其余快捷键仍可用" % " / ".join(missing))
            except Exception as e:
                self.hint.configure(text="全局快捷键启动失败：%s" % e)
            return
        if keyboard is None:
            self.hint.configure(text="未安装 pynput，全局快捷键不可用（pip install pynput）")
            return
        try:
            self.hk = keyboard.GlobalHotKeys({PYNPUT_HOTKEY: lambda: self.q.put(("hotkey", 1)),
                                              PYNPUT_POINTER: lambda: self.q.put(("hotkey", 2)),
                                              PYNPUT_SCREENSHOT: lambda: self.q.put(("hotkey", 3))})
            self.hk.daemon = True
            self.hk.start()
            self.hint.configure(text=ok_text)
        except Exception as e:
            self.hint.configure(text="全局快捷键启动失败：%s" % e)

    def _on_hotkey(self, which=1):
        if which == 3:
            self.start_screenshot()
            return
        if self.grabbing:
            return
        pointer = (which == 2)
        if pointer and not self.pointer_var.get():
            return
        self.grab_mode = "pointer" if pointer else "main"
        if pointer:
            self.grab_xy = self.root.winfo_pointerxy()
            self.grab_scope = SCOPE_CODES.get(self.scope_cb.get(), "word")
            self.grab_plan = []
        self.grabbing = True
        self.old_clip = self._get_clip()
        self.root.clipboard_clear()
        self._seq0 = clip_seq_win() if IS_WIN else 0
        threading.Thread(target=self._copy_selection, daemon=True).start()

    def _pointer_grab_win(self):
        """指针取词（Windows）：光标是「I」形才在指针处双击 / 三击选词，再 Ctrl+C。"""
        if not wait_keys_up_win((0x10, 0x11, 0x12, 0x44)):
            return                                    # 快捷键没松开，宁可不取也不乱点
        self.grab_plan = pointer_plan(cursor_is_ibeam_win(), foreground_is_terminal_win(), self.grab_scope)
        for act in self.grab_plan:
            if act.startswith("click"):
                click_here_win(int(act[-1]))
                time.sleep(0.08)
            else:
                send_copy_win()
                t0 = time.time()
                while time.time() - t0 < 1.2 and clip_seq_win() == self._seq0:
                    time.sleep(0.03)
                time.sleep(0.05)

    def _copy_selection(self):
        try:
            if IS_WIN and self.grab_mode == "pointer":
                self._pointer_grab_win()
                return
            if IS_WIN:
                send_copy_win()
                t0 = time.time()
                # 最多等 1.2 秒，剪贴板一更新就继续；慢速软件也不会漏
                while time.time() - t0 < 1.2 and clip_seq_win() == self._seq0:
                    time.sleep(0.03)
                time.sleep(0.05)
                return
            else:
                time.sleep(0.35)
                kb = keyboard.Controller()
                mod = keyboard.Key.cmd if IS_MAC else keyboard.Key.ctrl
                with kb.pressed(mod):
                    kb.press("c")
                    kb.release("c")
            time.sleep(0.25)
        finally:
            self.q.put(("copied",))

    def _on_copied(self):
        text = self._get_clip()
        self._set_clip(self.old_clip)
        self.last_clip = self.old_clip
        self.grabbing = False
        if self.grab_mode == "pointer":
            self._pointer_translate(text.strip(), self.grab_xy)      # 气泡就地显示，不打开主窗口
            return
        self.show_window()
        if text.strip():
            self._set_src(text.strip()[:MAX_LEN])
            self.translate_now()
        else:
            self.status.configure(text="没有检测到选中的文字")

    def _watch_clip(self):
        try:
            if self.watch_var.get() and not self.grabbing:
                clip = self._get_clip()
                if clip and clip != self.last_clip:
                    self.last_clip = clip
                    if clip.strip():
                        self._set_src(clip.strip()[:MAX_LEN])
                        self.show_window()
                        self.translate_now()
        finally:
            self.root.after(600, self._watch_clip)

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "hotkey":
                    self._on_hotkey(msg[1] if len(msg) > 1 else 1)
                elif kind == "copied":
                    self._on_copied()
                elif kind == "progress":
                    _, my, done, total = msg
                    if my == self.seq:
                        self.status.configure(text="翻译中 %d/%d" % (done, total))
                elif kind == "net_item":
                    _, run, c = msg
                    if run == getattr(self, "net_run", 0):
                        self.net_items[c.key] = c
                        self._render_net()
                elif kind == "net_done":
                    _, run, checks, reco = msg
                    if run == getattr(self, "net_run", 0):
                        self.net_items = {c.key: c for c in checks}
                        self._on_net_done(checks, reco)
                elif kind == "pack_done":
                    self._on_pack_done(msg[1], msg[2])
                elif kind == "dl_index":
                    self._on_dl_index(*msg[1:])
                elif kind == "dl_prog":
                    self._on_dl_prog(*msg[1:])
                elif kind == "dl_done":
                    self._on_dl_done(*msg[1:])
                elif kind == "tray_show":
                    self.show_window()
                elif kind == "tray_shot":
                    self.start_screenshot()
                elif kind == "tray_quit":
                    self.quit()
                elif kind == "shot_ocr":
                    self._on_shot_ocr(msg[1], msg[2], msg[3])
                elif kind == "hover_ocr":
                    _, word, xy, ibeam = msg
                    if word:
                        self._pointer_translate(word, xy)
                    elif ibeam:
                        # OCR 没认出，但光标是「I」形：退回双击取词
                        self.grab_mode = "pointer"
                        self.grab_xy = xy
                        self.grab_scope = SCOPE_CODES.get(self.scope_cb.get(), "word")
                        self.grab_plan = []
                        self.grabbing = True
                        self.old_clip = self._get_clip()
                        self.root.clipboard_clear()
                        self._seq0 = clip_seq_win() if IS_WIN else 0
                        threading.Thread(target=self._copy_selection, daemon=True).start()
                elif kind == "bubble":
                    self._on_bubble(*msg[1:])
                elif kind == "rt_prog":
                    self._on_rt_prog(*msg[1:])
                elif kind == "rt_done":
                    self._on_rt_done(*msg[1:])
                elif kind == "result":
                    _, my, ok, payload = msg
                    if my != self.seq:
                        continue
                    if ok:
                        pairs, det, target, fb = payload
                        self.pairs, self.detected = pairs, det
                        self.render()
                        n = sum(1 for s, _ in pairs if s)
                        extra = "（%d 段）" % n if n > 1 else ""
                        eng = self.engine.get()
                        warn = " · 已截断至 %d 字" % MAX_LEN if getattr(self, "truncated", False) else ""
                        if fb and eng != "离线":
                            warn += " · 在线不可用，已自动改用离线"
                        self.status.configure(
                            text="%s → %s%s · %s%s" % (lang_name(det), lang_name(target), extra, eng, warn))
                    else:
                        self._set_dst_error(payload)
                        self.status.configure(text="")
        except queue.Empty:
            pass
        self._hover_check()
        self.root.after(100, self._poll)

    def run(self):
        self.root.mainloop()


def run_selftest():
    """--selftest：不打开界面，检查离线引擎并写报告（窗口版 exe 没有控制台，所以写文件）。"""
    lines = ["实时翻译 v%s 自检  %s" % (__version__, time.strftime("%Y-%m-%d %H:%M:%S")),
             "frozen=%s  python=%s  platform=%s" % (FROZEN, sys.version.split()[0], sys.platform)]
    ok = True
    present = offline_engine.runtime_present()
    lines.append("离线运行库 (ctranslate2 + sentencepiece)：%s" % ("有" if present else "无（标准版属正常，可在程序里下载）"))
    rt = runtime_installer.installed(_runtime_dir())
    lines.append("  程序内下载的组件（%s）：%s" % (_runtime_dir(), ("已安装 %s" % rt) if rt else "未安装"))
    for d, name in OFFLINE.dirs:
        lines.append("  语言包目录[%s]：%s  %s" % (name, d, "存在" if os.path.isdir(d) else "不存在"))
    lines.append("  已识别语言包：%s" % OFFLINE.describe())
    for pkg in OFFLINE.broken:
        lines.append("  ! 不可用：%s（%s）" % (pkg.name, pkg.problem))
    if present:
        samples = {"zh": "你好，世界。", "en": "Hello, how are you?"}
        for fc, tc in OFFLINE.pairs():
            t0 = time.time()
            try:
                out = OFFLINE.translate(samples.get(fc, "Hello."), fc, tc)
                lines.append("  ✔ %s→%s  %d ms  %r" % (fc, tc, (time.time() - t0) * 1000, out[:40]))
            except Exception as e:      # noqa: BLE001
                ok = False
                lines.append("  ✘ %s→%s  %s" % (fc, tc, e))
        if not OFFLINE.pairs():
            ok = False
            lines.append("  ✘ 离线版但没有任何语言包")
    for c in (netcheck.check_connectivity(), netcheck.check_dns()):
        lines.append(c.line())
    lines.append("结果：%s" % ("通过" if ok else "有问题"))
    text = "\n".join(lines)
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, "selftest.txt"), "w", encoding="utf-8") as f:
            f.write(text + "\n")
    except Exception:
        pass
    if sys.stdout:
        try:
            print(text)
        except Exception:
            pass
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(run_selftest())
    enable_dpi_awareness()
    if not acquire_single_instance():
        return
    try:
        App().run()
    except Exception:
        import traceback
        log_crash(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
