#!/usr/bin/env python3
"""
实时翻译 — 桌面独立版 v2.6，Windows / macOS / Linux(X11)

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
     不依赖 pystray / Pillow；点 × 是隐藏到托盘；右键菜单可显示 / 截图 /
     翻译剪贴板，直接开关指针取词、悬停取词、监听剪贴板、置顶、开机自启，
     高级设置（按 常规 / 翻译 / 取词 / 历史 / 托盘 / 离线与网络 / 快捷键与关于 分类），
     切换取词范围（单词 / 整行 / 整段），打开网络检查 / 离线语言包，或退出
 11. 悬停取词（Windows）：鼠标在文字上停住约 0.8 秒就自动取词——
     先用系统 OCR（Windows.Media.Ocr，截图里认字）定位光标下的单词 / 整行 /
     整段（看「范围」），认不到且光标是「I」形时退回双击 / 三击取词；
     图片、游戏、扫描 PDF 里也能用；指针取词（Ctrl+Alt+D）同样支持整行 / 整段
 12. 截图翻译（Windows，Ctrl+Alt+S）：框选屏幕任意区域 → 系统 OCR
     认字 → 翻译。截图用 ctypes GDI BitBlt，OCR 用系统自带引擎，
     全程不装第三方库
 13. v2.5：朗读发音（Windows 自带 System.Speech 语音，原文 / 译文都能读，
     气泡 / 小窗口双击朗读，历史里也能读；语速 -10~10 可调）、
     复制闭环（复制原文、双语复制、翻译完自动复制译文，默认关）、
     自定义全局快捷键（主窗口 / 指针取词 / 截图翻译的组合键都能改，
     保存后重启生效）
 14. v2.6：文档翻译（.txt / .md 按段落、.srt 只翻正文）、图片文件翻译
     （Windows 系统 OCR）、词典释义 + 拼音/注音（Google 引擎、单个词或
     短词组时才显示）、语音输入（Windows 自带语音识别，15 秒超时）、
     生词本（历史里只看单词）、界面字号 10~18、翻译并替换原文
     （Ctrl+Alt+R，翻完直接粘贴回原处，有窗口校验与终端保护）
"""
import base64
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
import history_store
import tray_win32
import screen_win
import ocr_win
import doc_translate

try:
    import tts_win
except Exception:      # noqa: BLE001  非 Windows / 模块缺失时朗读不可用，不影响主程序
    tts_win = None

try:
    import stt_win
except Exception:      # noqa: BLE001  非 Windows / 模块缺失时语音输入不可用，不影响主程序
    stt_win = None

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
REPLACE_LABEL = "Ctrl+Alt+R"
PYNPUT_REPLACE = "<ctrl>+<alt>+r"
# 默认全局快捷键（配置键名 → 默认组合；用户可在高级设置里改，保存后重启生效）
DEFAULT_HOTKEYS = {"hotkey_main": "ctrl+alt+t", "hotkey_pointer": "ctrl+alt+d",
                   "hotkey_shot": "ctrl+alt+s", "hotkey_replace": "ctrl+alt+r"}
HOTKEY_KEYS = ("hotkey_main", "hotkey_pointer", "hotkey_shot", "hotkey_replace")
# Windows RegisterHotKey 的修饰键位（和 start_hotkey_win 里的常量一致）
_MOD_BITS = {"ctrl": 0x2, "alt": 0x1, "shift": 0x4, "win": 0x8}
_MOD_NAMES = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}
_PYNPUT_MODS = {"ctrl": "<ctrl>", "alt": "<alt>", "shift": "<shift>", "win": "<cmd>"}


def parse_hotkey(spec):
    """解析全局快捷键（纯函数，便于测试）。

    接受 "ctrl+alt+t" 这类写法：修饰键 ctrl/alt/shift/win（任意顺序，
    可重复写但只算一次）+ 一个键（单个字母 a-z、数字 0-9 或 F1~F12）。
    返回 (mods, vk, label)：mods 是 Windows 修饰键位、vk 是虚拟键码、
    label 是显示用的 "Ctrl+Alt+T"。不合规就抛 ValueError（裸键、无修饰键、
    两个键、未知键、空串都不行）。
    """
    if not isinstance(spec, str):
        raise ValueError("快捷键必须是字符串")
    parts = [p.strip().lower() for p in spec.replace(" ", "").split("+")]
    if not parts or any(p == "" for p in parts):
        raise ValueError("快捷键不能为空，也不能有多余的 +：%s" % spec)
    mods, mod_names, key = 0, [], None
    for p in parts:
        if p in _MOD_BITS:
            if p not in mod_names:
                mod_names.append(p)
            mods |= _MOD_BITS[p]
        elif key is not None:
            raise ValueError("快捷键只能有一个按键：%s" % spec)
        elif len(p) == 1 and (p.isalpha() or p.isdigit()):
            key = p
        elif re.fullmatch(r"f([1-9]|1[0-2])", p):
            key = p
        else:
            raise ValueError("未知的按键：%s" % p)
    if not mod_names:
        raise ValueError("快捷键至少要带一个修饰键（Ctrl/Alt/Shift/Win）：%s" % spec)
    if key is None:
        raise ValueError("快捷键缺少按键：%s" % spec)
    if key.startswith("f"):
        vk = 0x70 + int(key[1:]) - 1
        key_label = key.upper()
    else:
        vk = ord(key.upper())
        key_label = key.upper()
    order = ("ctrl", "alt", "shift", "win")
    label = "+".join([_MOD_NAMES[m] for m in order if m in mod_names] + [key_label])
    return mods, vk, label


def hotkey_label(spec):
    """组合键的显示文字，如 "ctrl+alt+t" → "Ctrl+Alt+T"（非法时抛 ValueError）。"""
    return parse_hotkey(spec)[2]


def pynput_spec(spec):
    """组合键 → pynput GlobalHotKeys 的写法，如 "ctrl+alt+t" → "<ctrl>+<alt>+t"。"""
    parts = [p.strip().lower() for p in spec.replace(" ", "").split("+") if p.strip()]
    out = []
    for p in parts:
        if p in _PYNPUT_MODS:
            out.append(_PYNPUT_MODS[p])
        elif p.startswith("f") and re.fullmatch(r"f([1-9]|1[0-2])", p):
            out.append("<%s>" % p)
        else:
            out.append(p)
    return "+".join(out)


def validate_hotkey_cfg(cfg):
    """校验配置里的三个快捷键：非法或重复的逐个回落到默认值，绝不抛异常。

    返回新的 dict（只含 hotkey_main / hotkey_pointer / hotkey_shot 三个键）。
    重复按主窗口 → 指针取词 → 截图翻译的顺序判定：先出现的保留，后出现的回默认。
    """
    out, seen = {}, set()
    for k in HOTKEY_KEYS:
        raw = cfg.get(k, DEFAULT_HOTKEYS[k])
        spec = str(raw or "").strip().lower()
        try:
            parse_hotkey(spec)
        except ValueError:
            spec = DEFAULT_HOTKEYS[k]
        if spec in seen:
            spec = DEFAULT_HOTKEYS[k]
            if spec in seen:      # 默认值也被占了（理论上不会）：保持默认，靠调用方去重提示
                pass
        seen.add(spec)
        out[k] = spec
    return out
SCOPE_NAMES = {"word": "单词", "line": "整行", "paragraph": "整段"}
SCOPE_CODES = {v: k for k, v in SCOPE_NAMES.items()}
POPUP_NAMES = {"bubble": "气泡弹窗", "mini": "跟随指针的小窗口", "main": "不弹窗（结果只写入主窗口）"}  # 取词结果怎么显示
POPUP_CODES = {v: k for k, v in POPUP_NAMES.items()}
SHOT_NAMES = {"overlay": "盖在截图上", "main": "显示在主窗口"}                                  # 截图翻译结果怎么显示
SHOT_CODES = {v: k for k, v in SHOT_NAMES.items()}
MINI_SIZE = {"mini_w": (160, 800, 320), "mini_h": (60, 500, 110)}   # 小窗口宽 / 高：(最小, 最大, 默认)
CLOSE_NAMES = {"tray": "隐藏到托盘", "quit": "直接退出"}      # 点窗口 × 时
CLOSE_CODES = {v: k for k, v in CLOSE_NAMES.items()}
__version__ = "2.6.0"
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
HISTORY_PATH = os.path.join(DATA_DIR, "history.db")
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
    "close_action": "tray", "tray_tip": True,
    "history_on": True, "history_max": 2000, "history_reuse": False,
    "popup_mode": "bubble", "mini_w": 320, "mini_h": 110, "shot_mode": "overlay",
    # v2.5：朗读语速（-10~10，默认 0）、自动复制译文（默认关）、自定义全局快捷键
    "tts_rate": 0, "auto_copy": False,
    "hotkey_main": "ctrl+alt+t", "hotkey_pointer": "ctrl+alt+d", "hotkey_shot": "ctrl+alt+s",
    "hotkey_replace": "ctrl+alt+r",
    # v2.6：界面字号（10~18，默认 11）
    "font_size": 11,
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


def g_translate_full(text, sl, tl, attempts=3, timeout=12):
    """Google 翻译（带原始 JSON）：返回 (译文, 检测到的源语言, 原始响应)。

    原始响应存在 _LAST_GOOGLE 里，供词典区解析 data[1] 的词典与
    data[0] 的 transliteration（拼音/读音）用；只在 Google 引擎、
    单个词或短词组时才读它。
    """
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
            _LAST_GOOGLE.update(text=text, sl=sl, tl=tl, data=data)
            return out, det, data
        except Exception as e:
            last = e
            if attempt + 1 >= attempts:
                break
            if _is_rate_limit(e):
                time.sleep(1.2 * (attempt + 1))
            else:
                time.sleep(0.4)
    raise last


_LAST_GOOGLE = {"text": None, "sl": None, "tl": None, "data": None}


def g_translate(text, sl, tl, attempts=3, timeout=12):
    out, det, _data = g_translate_full(text, sl, tl, attempts, timeout)
    return out, det


def parse_dict(data):
    """从 Google 翻译原始 JSON 里解析词典（纯函数，便于测试）。

    结构（translate_a/single 的免费端点返回）：
    - data[1]：词典，形如 [["noun", ["释义1", "释义2"], ...],
      ["verb", [...], ...]]，每项第 0 个是词性、第 1 个是释义列表；
    - data[0] 每句的第 3 个元素：transliteration（拼音/罗马音），
      只有响应里真有这个字段才取，绝不自己编拼音。
    解析不到就返回空 entries / 空 translit，调用方整块隐藏，不报错。
    返回 {"entries": [{"pos": 词性, "meanings": [释义...]}], "translit": str}。
    做法参考了 ScreenLookup（github.com/chaixshot/ScreenLookup，MIT）：
    点词看词性与多义项——只借鉴功能思路，解析代码是自己写的。
    """
    entries, translit = [], ""
    if not isinstance(data, list):
        return {"entries": entries, "translit": translit}
    try:
        for seg in (data[0] or []):
            if isinstance(seg, list) and len(seg) > 3 and isinstance(seg[3], str) and seg[3].strip():
                cand = seg[3].strip()
                if cand not in (seg[0] or "", seg[1] or ""):
                    translit = cand
                    break
    except Exception:
        pass
    try:
        for item in (data[1] or []):
            if not isinstance(item, list) or len(item) < 2:
                continue
            pos = item[0] if isinstance(item[0], str) else ""
            meanings = []
            for m in (item[1] or []):
                if isinstance(m, str) and m.strip():
                    meanings.append(m.strip())
                elif isinstance(m, list):
                    for x in m:
                        if isinstance(x, str) and x.strip():
                            meanings.append(x.strip())
            if pos and meanings:
                entries.append({"pos": pos, "meanings": meanings[:8]})
            if len(entries) >= 6:
                break
    except Exception:
        pass
    return {"entries": entries, "translit": translit}


def is_dict_candidate(text):
    """输入是不是值得查词典的单个词或短词组：去空白后 <=20 字符、1~3 个词、无换行。"""
    t = (text or "").strip()
    if not t or "\n" in t or len(t) > 20:
        return False
    return 1 <= len(t.split()) <= 3


def is_word_entry(src):
    """一条历史记录的原文是不是单词：单个词、无空格、1~30 字符（生词本用）。"""
    t = (src or "").strip()
    return 1 <= len(t) <= 30 and not any(c.isspace() for c in t)


def is_supported_image_file(path):
    """是不是支持翻译的图片文件（.png / .jpg / .jpeg / .bmp / .tif）。"""
    return doc_translate.supported_image_ext(path)


def replace_decision(is_win, same_hwnd, is_terminal):
    """翻译并替换该怎么做（纯逻辑，便于测试）。

    返回 "paste"（前台窗口没变，直接粘贴替换）、"clipboard-only"
    （窗口变了，只把译文放进剪贴板）、"skip-terminal"（终端窗口不替换，
    避免 Ctrl+V / Ctrl+C 语义不同）、"unavailable"（非 Windows）。
    """
    if not is_win:
        return "unavailable"
    if is_terminal:
        return "skip-terminal"
    return "paste" if same_hwnd else "clipboard-only"


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
def start_hotkey_win(q, specs=None):
    """Windows 全局热键：注册三个组合键（主窗口 / 指针取词 / 截图翻译）。

    specs 是 {"hotkey_main": "ctrl+alt+t", ...} 这类配置，不传（None）就用
    默认组合；非法组合逐个回落到默认，绝不抛异常。返回主窗口热键是否注册成功。
    """
    import ctypes
    import ctypes.wintypes
    user32 = ctypes.windll.user32
    ready, state = threading.Event(), {"ok": False, "pointer_ok": False, "shot_ok": False,
                                        "replace_ok": False}
    parsed = {}
    for i, key in enumerate(HOTKEY_KEYS, start=1):
        raw = (specs or {}).get(key, DEFAULT_HOTKEYS[key]) if isinstance(specs, dict) else DEFAULT_HOTKEYS[key]
        try:
            mods, vk, _label = parse_hotkey(raw)
        except ValueError:
            mods, vk, _label = parse_hotkey(DEFAULT_HOTKEYS[key])
        parsed[i] = (mods, vk)

    def loop():
        MOD_NOREPEAT = 0x4000
        names = ("ok", "pointer_ok", "shot_ok", "replace_ok")
        for i, (mods, vk) in parsed.items():
            state[names[i - 1]] = bool(user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk))
        ready.set()
        if not (state["ok"] or state["pointer_ok"] or state["shot_ok"] or state["replace_ok"]):
            return
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312:
                q.put(("hotkey", int(msg.wParam)))

    threading.Thread(target=loop, daemon=True).start()
    ready.wait(2)
    start_hotkey_win.pointer_ok = state["pointer_ok"]
    start_hotkey_win.shot_ok = state["shot_ok"]
    start_hotkey_win.replace_ok = state["replace_ok"]
    return state["ok"]


def foreground_window_win():
    """当前前台窗口句柄（翻译并替换用：粘贴前校验还是刚才那个窗口）。失败返回 0。"""
    try:
        import ctypes
        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = ctypes.c_void_p
        return int(u.GetForegroundWindow() or 0)
    except Exception:
        return 0


def focus_window_win(hwnd):
    """把指定窗口切到前台（翻译并替换粘贴前用）。失败返回 False。"""
    try:
        import ctypes
        return bool(ctypes.windll.user32.SetForegroundWindow(hwnd))
    except Exception:
        return False


def send_paste_win():
    """发送 Ctrl+V（翻译并替换：把剪贴板里的译文粘贴回原处）。"""
    import ctypes
    u = ctypes.windll.user32
    KEYUP = 2
    u.keybd_event(0x11, 0, 0, 0)
    u.keybd_event(0x56, 0, 0, 0)
    u.keybd_event(0x56, 0, KEYUP, 0)
    u.keybd_event(0x11, 0, KEYUP, 0)


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

    click2 / click3 = 在指针处双击 / 三击（选中单词 / 整行或整段）；copy = 发送 Ctrl+C。
    （整行 / 整段优先走截图 OCR，OCR 取不到才退回三击：三击选中的是一行还是一段，
    取决于软件——记事本、代码编辑器是一行，浏览器、Word 是一段。）
    只有指针是「I」形文字光标时才会点击，所以不会误点按钮、链接。
    """
    if ibeam:
        return ["click3" if scope in ("line", "paragraph") else "click2", "copy"]
    if terminal:
        return []          # 终端里没有选区时 Ctrl+C 会中断正在运行的程序，绝不发送
    return ["copy"]        # 认不出光标形状（软件自绘光标）：只复制已有的选区


def tray_menu_items(snap, is_win=True):
    """托盘右键菜单（纯逻辑，便于测试）。snap 是主程序备好的状态快照 dict。

    快捷键显示文字从 snap 里取（"hotkey_main" / "hotkey_pointer" /
    "hotkey_shot"，显示形式如 "Ctrl+Alt+T"），没给就用默认。
    """
    scope = snap.get("scope", "word")
    shot_label = snap.get("hotkey_shot") or SCREENSHOT_LABEL
    pointer_label = snap.get("hotkey_pointer") or POINTER_LABEL
    replace_label = snap.get("hotkey_replace") or REPLACE_LABEL
    items = [
        {"id": "show", "label": "显示主窗口(&S)", "default": True},
        {"id": "shot", "label": "截图翻译(&C)　%s" % shot_label},
        {"id": "clip", "label": "翻译剪贴板内容(&V)"},
        {"id": "replace", "label": "翻译并替换原文(&R)　%s" % replace_label},
        {"sep": True},
        {"id": "pointer", "label": "指针取词　%s" % pointer_label, "checked": bool(snap.get("pointer"))},
        {"id": "hover", "label": "悬停取词", "checked": bool(snap.get("hover"))},
        {"label": "取词范围", "sub": [
            {"id": "scope:%s" % k, "label": v, "checked": scope == k}
            for k, v in SCOPE_NAMES.items()]},
        {"sep": True},
        {"id": "watch", "label": "监听剪贴板", "checked": bool(snap.get("watch"))},
        {"id": "top", "label": "窗口置顶", "checked": bool(snap.get("top"))},
        {"id": "auto_off", "label": "断网时自动用离线翻译", "checked": bool(snap.get("auto_off"))},
    ]
    if is_win:
        items.append({"id": "autostart", "label": "开机自启", "checked": bool(snap.get("autostart"))})
    items += [
        {"sep": True},
        {"id": "history", "label": "翻译历史…"},
        {"id": "history_on", "label": "保存翻译记录", "checked": bool(snap.get("history_on"))},
        {"id": "settings", "label": "高级设置…"},
        {"id": "netcheck", "label": "网络检查…"},
        {"id": "packs", "label": "离线语言包…"},
        {"sep": True},
        {"id": "quit", "label": "退出(&Q)"},
    ]
    return items


def tray_tooltip(snap):
    on = lambda k: "开" if snap.get(k) else "关"
    return "%s｜指针取词:%s 悬停:%s 范围:%s" % (
        APP_TITLE, on("pointer"), on("hover"), SCOPE_NAMES.get(snap.get("scope", "word"), "单词"))


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
    """指针旁的小气泡：显示原文 + 译文。不抢焦点；点一下复制译文并关闭，
    双击朗读译文，右键 / Esc / 移开指针就消失。"""
    BG, BORDER, GRAY, RED = "#fffdf6", "#c9ced6", "#6b7380", "#b42318"
    MOVE_AWAY = 140          # 指针离开出现位置这么多像素（且不在气泡上）就自动消失
    MAX_SECONDS = 20
    CLICK_CLOSE_MS = 250     # 点一下后等这么久再关：等双击（双击到就取消关闭、改朗读）

    def __init__(self, app):
        self.app = app
        self.win = None
        self.anchor = (0, 0)
        self.t0 = 0.0
        self.copy_text = ""
        self.speak_lang = None
        self._click_after = None

    def alive(self):
        try:
            return self.win is not None and bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def close(self):
        if self._click_after is not None:
            try:
                self.app.root.after_cancel(self._click_after)
            except Exception:
                pass
            self._click_after = None
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
        self.win = None

    def show(self, xy, head, body, error=False, lang=None):
        self.close()
        app = self.app
        self.anchor, self.t0 = xy, time.time()
        self.speak_lang = lang
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
                             text="点击复制译文 · 双击朗读译文 · 右键或 Esc 关闭")
        self.head.pack(fill="x")
        self.body.pack(fill="x", pady=(2, 2))
        self.foot.pack(fill="x")
        for wd in (w, frame, self.head, self.body, self.foot):
            wd.bind("<Button-1>", self._click)
            wd.bind("<Double-Button-1>", self._dblclick)
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

    def update(self, head, body, error=False, lang=None):
        if self.alive():
            if lang is not None:
                self.speak_lang = lang
            self._fill(head, body, error)
            self._place()

    def _fill(self, head, body, error):
        self.head.configure(text=head)
        self.body.configure(text=body, fg=self.RED if error else "#111111")
        self.copy_text = "" if error else body
        self.foot.configure(text="右键或 Esc 关闭" if error else "点击复制译文 · 双击朗读译文 · 右键或 Esc 关闭")

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
        # 点一下：立刻复制，关闭稍等 250ms——双击的第二次点击会在这之前到，
        # _dblclick 会取消关闭、改朗读。直接调 _click() 的旧测试要多 pump 一下。
        if self.copy_text:
            self.app._set_clip(self.copy_text)
            self.app.last_clip = self.copy_text
            self.app.status.configure(text="已复制译文")
        if self._click_after is None:
            self._click_after = self.app.root.after(self.CLICK_CLOSE_MS, self._close_after_click)

    def _close_after_click(self):
        self._click_after = None
        self.close()

    def _dblclick(self, _e=None):
        # 双击：取消待关闭，朗读译文（气泡不关，读完还能再点复制）。
        if self._click_after is not None:
            try:
                self.app.root.after_cancel(self._click_after)
            except Exception:
                pass
            self._click_after = None
        if self.copy_text:
            self.app.speak_text(self.copy_text, self.speak_lang)

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


class MiniWin:
    """跟随指针的小窗口：固定大小（高级设置里可调宽 / 高），贴着指针走，显示取词译文。

    和气泡的区别：气泡出现后停在原地，移开就消失；小窗口会一直跟着指针移动，
    直到下一次取词替换它，或超过 MAX_SECONDS 自动消失。它不抢焦点，也不挡鼠标
    （始终放在指针右下方一点点）。截屏 OCR 之前会先藏起来，免得把自己认进去。
    点一下复制译文（窗口不关），双击朗读译文，右键 / Esc 关闭。
    """
    MAX_SECONDS = 15
    FOLLOW_MS = 40
    OFFSET = (16, 22)

    def __init__(self, app):
        self.app = app
        self.win = None
        self.t0 = 0.0
        self.hidden_at = None
        self.copy_text = ""
        self.speak_lang = None

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
        self.hidden_at = None

    def size(self):
        c = self.app.cfg
        return int(c.get("mini_w", 320)), int(c.get("mini_h", 110))

    def show(self, xy, head, body, error=False, lang=None):
        self.close()
        app = self.app
        W, H = self.size()
        self.speak_lang = lang
        w = tk.Toplevel(app.root)
        w.withdraw()
        w.overrideredirect(True)
        try:
            w.attributes("-topmost", True)
        except tk.TclError:
            pass
        frame = tk.Frame(w, bg=Bubble.BG, highlightbackground=Bubble.BORDER, highlightthickness=1,
                         width=W, height=H)
        frame.pack()
        frame.pack_propagate(False)                   # 固定大小：文字太长就裁掉，不撑大窗口
        self.head = tk.Label(frame, bg=Bubble.BG, fg=Bubble.GRAY, font=(app.ui_font[0], 8),
                             anchor="w", justify="left")
        self.body = tk.Label(frame, bg=Bubble.BG, font=app.font, anchor="nw", justify="left",
                             wraplength=max(60, W - 20))
        self.foot = tk.Label(frame, bg=Bubble.BG, fg="#9aa3b2", font=(app.ui_font[0], 8),
                             anchor="w", text="点击复制译文 · 双击朗读译文 · 右键或 Esc 关闭")
        self.head.pack(fill="x", padx=8, pady=(4, 0))
        self.body.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.foot.pack(fill="x", padx=8, pady=(0, 4))
        for wd in (w, frame, self.head, self.body, self.foot):
            wd.bind("<Button-1>", self._click)
            wd.bind("<Double-Button-1>", self._dblclick)
            wd.bind("<Button-3>", lambda e: self.close())
        w.bind("<Escape>", lambda e: self.close())
        self.win = w
        self.t0, self.hidden_at = time.time(), None
        self._fill(head, body, error)
        w.deiconify()
        if IS_WIN:
            try:
                w.update_idletasks()
                no_activate_win(w)
            except Exception:
                pass
        self._follow(xy)

    def update(self, head, body, error=False, lang=None):
        if self.alive():
            if lang is not None:
                self.speak_lang = lang
            self._fill(head, body, error)
            if self.hidden_at is not None:                # 取词时藏起来的，结果来了再显示
                self.hidden_at = None
                self.win.deiconify()
                self._follow()

    def _fill(self, head, body, error):
        self.head.configure(text=head)
        self.body.configure(text=body, fg=Bubble.RED if error else "#111111")
        self.copy_text = "" if error else body
        self.foot.configure(text="右键或 Esc 关闭" if error else "点击复制译文 · 双击朗读译文 · 右键或 Esc 关闭")

    def _click(self, _e=None):
        # 点一下只复制，不关窗口（小窗口是跟随指针的，关了就没法继续跟）。
        if self.copy_text:
            self.app._set_clip(self.copy_text)
            self.app.last_clip = self.copy_text
            self.app.status.configure(text="已复制译文")

    def _dblclick(self, _e=None):
        if self.copy_text:
            self.app.speak_text(self.copy_text, self.speak_lang)

    def hide_for_capture(self):
        """取词截屏前先藏起来（在 Tk 线程调用）。2 秒内没新结果就自己关掉。"""
        if self.alive() and self.hidden_at is None:
            self.win.withdraw()
            self.hidden_at = time.time()

    def place_for(self, px, py):
        W, H = self.size()
        l, t, r, b = screen_bounds() or (0, 0, self.win.winfo_screenwidth(), self.win.winfo_screenheight())
        x, y = px + self.OFFSET[0], py + self.OFFSET[1]
        if x + W > r - 4:
            x = max(l + 4, px - W - self.OFFSET[0])
        if y + H > b - 4:
            y = max(t + 4, py - H - 10)
        return x, y

    def _follow(self, xy=None):
        if not self.alive():
            return
        now = time.time()
        if now - self.t0 > self.MAX_SECONDS or (self.hidden_at is not None and now - self.hidden_at > 2.0):
            self.close()
            return
        if self.hidden_at is None:
            try:
                px, py = xy or self.win.winfo_pointerxy()
                x, y = self.place_for(px, py)
                W, H = self.size()
                self.win.geometry("%dx%d+%d+%d" % (W, H, x, y))
            except tk.TclError:
                return
        self.app.root.after(self.FOLLOW_MS, self._follow)


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
        self._tray_snap = {}
        self._tray_tip = ""
        self.history = history_store.HistoryStore(HISTORY_PATH, max_items=self.cfg.get("history_max", 2000))
        self._req = None                 # (seq, 原文, 请求源语言, 请求目标语言, 来源)：结果回来时用来存记录
        self._kind_hint = "main"
        self._from_hist = None           # 本次结果是从历史里取的（不再重复保存）
        self.hist_win = None
        self.hover_last = None
        self.hover_since = 0.0
        self.hover_fired = False
        self.shot_win = None
        self._tts_kind = None          # 正在朗读的是原文（"src"）还是译文（"dst"），用于再点一次停止

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
        self.mini = MiniWin(self)
        self.shot_overlay = None
        self._build_ui()
        self._fit_min_width()

        self.last_clip = self._get_clip()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: (self.bubble.close(), self.mini.close(), self._close_shot_overlay(),
                                              self.hide_window()))
        self.root.after(100, self._poll)
        self.root.after(600, self._watch_clip)
        self.root.after(1500, self._warmup)
        self._start_hotkey()
        self._start_tray()
        if "--minimized" in sys.argv:
            self.hide_window(tip=False)

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
        if cfg.get("close_action") not in CLOSE_NAMES:
            cfg["close_action"] = "tray"
        cfg["tray_tip"] = bool(cfg.get("tray_tip", True))
        if cfg.get("popup_mode") not in POPUP_NAMES:
            cfg["popup_mode"] = "bubble"
        if cfg.get("shot_mode") not in SHOT_NAMES:
            cfg["shot_mode"] = "overlay"
        for k, (lo, hi, dv) in MINI_SIZE.items():
            try:
                cfg[k] = max(lo, min(int(cfg.get(k, dv)), hi))
            except Exception:
                cfg[k] = dv
        cfg["history_on"] = bool(cfg.get("history_on", True))
        cfg["history_reuse"] = bool(cfg.get("history_reuse", False))
        try:
            cfg["history_max"] = int(cfg.get("history_max", 2000))
        except Exception:
            cfg["history_max"] = 2000
        cfg["history_max"] = max(100, min(cfg["history_max"], 20000))
        if not isinstance(cfg.get("pack_mirror"), str):
            cfg["pack_mirror"] = ""
        # v2.5：朗读语速钳制 -10..10、自动复制开关、快捷键非法/重复回默认
        try:
            cfg["tts_rate"] = int(cfg.get("tts_rate", 0))
        except Exception:
            cfg["tts_rate"] = 0
        cfg["tts_rate"] = max(-10, min(cfg["tts_rate"], 10))
        cfg["auto_copy"] = bool(cfg.get("auto_copy", False))
        cfg.update(validate_hotkey_cfg(cfg))
        # v2.6：界面字号钳制 10~18
        try:
            cfg["font_size"] = int(cfg.get("font_size", 11))
        except Exception:
            cfg["font_size"] = 11
        cfg["font_size"] = max(10, min(cfg["font_size"], 18))
        if not re.match(r"^\d+x\d+([+-]-?\d+[+-]-?\d+)?$", str(cfg.get("geometry", ""))):
            cfg["geometry"] = DEFAULTS["geometry"]
        return cfg

    def _on_tk_error(self, exc, val, tb):
        import traceback
        text = "".join(traceback.format_exception(exc, val, tb))
        log_crash(text)
        self.status.configure(text="发生内部错误，详见 %s" % CRASH_LOG)

    def hide_window(self, tip=True):
        # 有托盘时隐藏到托盘（withdraw，任务栏不留窗口，点托盘图标找回）；
        # 没托盘时才最小化——旧版 withdraw 后没有托盘图标，窗口就找不回来了。
        if getattr(self, "tray", None) is not None and self.tray.is_running():
            self.root.withdraw()
            if tip and self.cfg.get("tray_tip", True) and not self.cfg.get("tray_tip_shown"):
                # 第一次隐藏时弹一次气泡，告诉用户程序没退出、在哪找回
                self.cfg["tray_tip_shown"] = True
                try:
                    self.tray.notify(APP_TITLE, "已隐藏到托盘。单击托盘图标显示窗口，右键可切换取词选项或退出。")
                except Exception:
                    pass                # 气泡只是提示，失败不能影响隐藏窗口
                self._save()
        else:
            self.root.iconify()

    def _on_close(self):
        # 点 ×：按「高级设置 → 常规」里的选择：直接退出，或有托盘就隐藏到托盘
        # （真正退出走托盘右键菜单 / 主界面「退出」按钮）
        if self.cfg.get("close_action", "tray") == "quit":
            self.quit()
        else:
            # 隐藏到托盘；托盘图标建不起来（被安全软件拦截）时改为最小化到任务栏 ——
            # 不管哪种，点 × 都不会把程序关掉；真要退出用「退出」按钮 / 托盘菜单 / 设置里选「直接退出」
            self.hide_window()

    # ---- 自定义全局快捷键：显示文字永远从配置派生，不用写死的常量 ----
    @property
    def hotkey_main_label(self):
        try:
            return hotkey_label(self.cfg.get("hotkey_main", DEFAULT_HOTKEYS["hotkey_main"]))
        except ValueError:
            return HOTKEY_LABEL

    @property
    def hotkey_pointer_label(self):
        try:
            return hotkey_label(self.cfg.get("hotkey_pointer", DEFAULT_HOTKEYS["hotkey_pointer"]))
        except ValueError:
            return POINTER_LABEL

    @property
    def hotkey_shot_label(self):
        try:
            return hotkey_label(self.cfg.get("hotkey_shot", DEFAULT_HOTKEYS["hotkey_shot"]))
        except ValueError:
            return SCREENSHOT_LABEL

    @property
    def hotkey_replace_label(self):
        try:
            return hotkey_label(self.cfg.get("hotkey_replace", DEFAULT_HOTKEYS["hotkey_replace"]))
        except ValueError:
            return REPLACE_LABEL

    def _refresh_tray_state(self):
        """把当前选项拍成快照给托盘菜单读（托盘线程不能碰 Tk），并更新托盘提示文字。"""
        try:
            self._tray_snap = {
                "top": self.top_var.get(), "watch": self.watch_var.get(),
                "pointer": self.pointer_var.get(), "hover": self.hover_var.get(),
                "scope": SCOPE_CODES.get(self.scope_cb.get(), "word"),
                "auto_off": self.auto_off_var.get(),
                "history_on": self.history_on_var.get(),
                "autostart": self.auto_var.get() if hasattr(self, "auto_var") else False,
                "hotkey_main": self.hotkey_main_label,
                "hotkey_pointer": self.hotkey_pointer_label,
                "hotkey_shot": self.hotkey_shot_label,
                "hotkey_replace": self.hotkey_replace_label,
            }
            tray = getattr(self, "tray", None)
            if tray is not None and tray.is_running():
                tip = tray_tooltip(self._tray_snap)
                if tip != self._tray_tip:
                    self._tray_tip = tip
                    tray.set_tooltip(tip)
        except Exception:
            pass

    def _on_tray_cmd(self, cid):
        """托盘菜单命令（在 Tk 线程里执行，走和主窗口选项完全相同的处理函数）。"""
        toggles = {"top": ("top_var", "_on_top"), "watch": ("watch_var", "_on_watch"),
                   "pointer": ("pointer_var", "_on_pointer_opt"),
                   "hover": ("hover_var", "_on_pointer_opt"),
                   "auto_off": ("auto_off_var", "_on_auto_offline"),
                   "autostart": ("auto_var", "_on_autostart"),
                   "history_on": ("history_on_var", "_on_history_opt")}
        if cid in toggles:
            var, handler = toggles[cid]
            v = getattr(self, var, None)
            if v is None:
                return
            v.set(not v.get())
            getattr(self, handler)()
        elif isinstance(cid, str) and cid.startswith("scope:"):
            code = cid.split(":", 1)[1]
            if code in SCOPE_NAMES:
                self.scope_cb.set(SCOPE_NAMES[code])
                self._on_pointer_opt()
        elif cid == "clip":
            self.show_window()
            text = self._get_clip().strip()
            if text:
                self._set_src(text[:MAX_LEN])
                self.translate_now()
            else:
                self.status.configure(text="剪贴板里没有文字")
        elif cid == "replace":
            self._on_replace_hotkey()
        elif cid == "settings":
            self.show_window()
            self.open_settings()
        elif cid == "history":
            self.open_history()
        elif cid == "netcheck":
            self.show_window()
            self.open_netcheck()
        elif cid == "packs":
            self.show_window()
            self._show_offline_packs()
        self._refresh_tray_state()

    def _fit_min_width(self):
        # 选项 / 按钮行是横向排的，写死的 minsize(520) 比内容窄，窗口一缩小
        # 右边的复选框、「范围」下拉、「退出」按钮就被裁掉。这里按各行实际
        # 需要的宽度（随字体 / DPI 变化）算最小宽度，并把过窄的已存宽度撑开。
        try:
            self.root.update_idletasks()
            need = max(w.winfo_reqwidth() for w in self._fit_rows) + 2 * 12 + 4
            min_w = max(520, need)
            self.root.minsize(min_w, 420)
            m = re.match(r"^(\d+)x(\d+)(.*)$", str(self.root.geometry()))
            if m and int(m.group(1)) < min_w:
                self.root.geometry("%dx%d%s" % (min_w, int(m.group(2)), m.group(3)))
        except Exception:
            pass

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
                on_quit=lambda: self.q.put(("tray_quit",)),
                # 菜单在托盘线程里弹出：只读快照，点击后把命令放进队列，由 Tk 线程执行
                menu_provider=lambda: tray_menu_items(self._tray_snap, IS_WIN),
                on_command=lambda cid: self.q.put(("tray_cmd", cid)))
            if not self.tray.start():
                self.tray = None
            else:
                self._refresh_tray_state()
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
            fam, base_size = "Microsoft YaHei UI", 11
        elif IS_MAC:
            fam, base_size = "PingFang SC", 13
        else:
            fam, base_size = "Noto Sans CJK SC", 11
        # v2.6 界面字号：默认 11（设置 → 常规里 10~18 可调，改完立刻生效）
        size = int(self.cfg.get("font_size", 11))
        self._font_family = fam
        font = (fam, size)
        ui_font = (fam, max(8, size - 1))

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
        # v2.6 词典区：平时隐藏；只有 Google 引擎、单个词或短词组且响应里真有
        # 词典/注音时才显示（见 _update_dict_area）。
        self.dict_frame = ttk.Frame(f2)
        self.dict_label = ttk.Label(self.dict_frame, text="", foreground="#5b6676",
                                    font=ui_font, wraplength=560, justify="left")
        self.dict_label.pack(fill="x")

        # —— 按钮 ——
        btns = ttk.Frame(root)
        btns.pack(fill="x", padx=12, pady=(2, 0))
        ttk.Button(btns, text="复制译文", command=self.copy_result).pack(side="left")
        ttk.Button(btns, text="复制原文", command=self.copy_source).pack(side="left", padx=6)
        ttk.Button(btns, text="🔊 原文", command=self.speak_source).pack(side="left")
        ttk.Button(btns, text="🔊 译文", command=self.speak_result).pack(side="left", padx=6)
        ttk.Button(btns, text="清空", command=self.clear).pack(side="left")
        ttk.Button(btns, text="网络检查", command=self.open_netcheck).pack(side="left", padx=6)
        ttk.Button(btns, text="离线语言包…", command=self._show_offline_packs).pack(side="left")
        ttk.Button(btns, text="截图翻译", command=self.start_screenshot).pack(side="left", padx=6)
        ttk.Button(btns, text="翻译文档…", command=self._translate_doc_file).pack(side="left")
        ttk.Button(btns, text="翻译图片…", command=self._translate_image_file).pack(side="left", padx=6)
        ttk.Button(btns, text="🎤 语音输入", command=self.start_voice_input).pack(side="left")
        ttk.Button(btns, text="退出", command=self.quit).pack(side="right")

        # —— 选项区：常用开关留在主窗口，其余按用途归类放进「高级设置」 ——
        self.top_var = tk.BooleanVar(value=self.cfg["top"])
        self.watch_var = tk.BooleanVar(value=self.cfg["watch"])
        self.smart_var = tk.BooleanVar(value=self.cfg["smart"])
        self.bi_var = tk.BooleanVar(value=self.cfg["bilingual"])
        self.reflow_var = tk.BooleanVar(value=self.cfg["reflow"])
        self.show_src_var = tk.BooleanVar(value=self.cfg["show_src"])
        if IS_WIN:
            self.auto_var = tk.BooleanVar(value=autostart_enabled())
        global AUTO_OFFLINE
        AUTO_OFFLINE = bool(self.cfg.get("auto_offline", True))
        self.auto_off_var = tk.BooleanVar(value=AUTO_OFFLINE)
        self.pointer_var = tk.BooleanVar(value=bool(self.cfg.get("pointer", True)))
        self.hover_var = tk.BooleanVar(value=bool(self.cfg.get("hover", True)))
        self.hover_ms_var = tk.IntVar(value=int(self.cfg.get("hover_ms", 800)))
        self.tray_tip_var = tk.BooleanVar(value=bool(self.cfg.get("tray_tip", True)))
        self.history_on_var = tk.BooleanVar(value=bool(self.cfg.get("history_on", True)))
        self.history_reuse_var = tk.BooleanVar(value=bool(self.cfg.get("history_reuse", False)))
        self.history_max_var = tk.IntVar(value=int(self.cfg.get("history_max", 2000)))
        self.tts_rate_var = tk.IntVar(value=int(self.cfg.get("tts_rate", 0)))
        self.auto_copy_var = tk.BooleanVar(value=bool(self.cfg.get("auto_copy", False)))
        self.font_size_var = tk.IntVar(value=int(self.cfg.get("font_size", 11)))
        self._stt_busy = False
        self._replace_hwnd = 0
        self._doc_path = ""

        opts = ttk.LabelFrame(root, text="常用", padding=(8, 4))
        opts.pack(fill="x", padx=12, pady=(8, 0))

        o1 = ttk.Frame(opts)
        o1.pack(fill="x")
        ttk.Checkbutton(o1, text="窗口置顶", variable=self.top_var, command=self._on_top).pack(side="left")
        ttk.Checkbutton(o1, text="监听剪贴板", variable=self.watch_var, command=self._on_watch).pack(side="left", padx=10)
        ttk.Checkbutton(o1, text="中英智能互译", variable=self.smart_var, command=self._retranslate).pack(side="left")
        ttk.Checkbutton(o1, text="双语对照", variable=self.bi_var, command=self._on_bilingual).pack(side="left", padx=10)
        ttk.Checkbutton(o1, text="显示原文", variable=self.show_src_var, command=self._on_show_src).pack(side="left")

        o2 = ttk.Frame(opts)
        o2.pack(fill="x", pady=(2, 0))
        ttk.Checkbutton(o2, text="指针取词", variable=self.pointer_var,
                        command=self._on_pointer_opt).pack(side="left")
        ttk.Checkbutton(o2, text="悬停取词", variable=self.hover_var,
                        command=self._on_pointer_opt).pack(side="left", padx=10)
        ttk.Button(o2, text="高级设置…", command=self.open_settings).pack(side="right")
        ttk.Button(o2, text="翻译历史…", command=self.open_history).pack(side="right", padx=(0, 6))
        self.fav_btn = ttk.Button(o2, text="☆ 收藏", command=self.favorite_current)
        self.fav_btn.pack(side="right", padx=(0, 6))
        ttk.Button(o2, text="生词本", command=self.open_vocab).pack(side="right", padx=(0, 6))

        self._build_settings_win()

        self._fit_rows = (top, eng_frame, btns, opts)

        self.hint = ttk.Label(root, text="", foreground="#5b6676", wraplength=560)
        self.hint.pack(anchor="w", fill="x", padx=12, pady=(6, 10))
        self.hint.bind("<Configure>", lambda e: self.hint.configure(wraplength=max(200, e.width - 8)))

        root.attributes("-topmost", self.top_var.get())
        if not self.show_src_var.get():
            self.paned.forget(self.f1)
        else:
            self.src.focus_set()

    # ------------------------------------------------ 高级设置（按用途分类）
    def _build_settings_win(self):
        """高级设置窗口：创建后先隐藏，控件一直存在（托盘 / 快捷键随时可读写选项）。

        分类：常规 / 翻译 / 取词 / 托盘 / 离线与网络 / 关于。
        和主窗口共用同一批变量，两边的勾选永远同步。
        """
        win = tk.Toplevel(self.root)
        win.withdraw()
        win.title("高级设置")
        win.geometry("640x580")
        win.minsize(600, 520)
        win.protocol("WM_DELETE_WINDOW", self.close_settings)
        win.bind("<Escape>", lambda e: self.close_settings())
        try:
            if IS_WIN:
                win.iconbitmap(resource_path("app.ico"))
        except Exception:
            pass
        self.settings_win = win

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        self.settings_nb = nb
        self.settings_tabs = {}

        def tab(key, title):
            f = ttk.Frame(nb, padding=14)
            nb.add(f, text=title)
            self.settings_tabs[key] = f
            return f

        def check(parent, text, var, cmd, note=None):
            cb = ttk.Checkbutton(parent, text=text, variable=var, command=cmd)
            cb.pack(anchor="w", pady=(6, 0))
            if note:
                ttk.Label(parent, text=note, foreground="#5b6676", wraplength=500,
                          justify="left").pack(anchor="w", padx=(26, 0))
            return cb

        # 常规
        f = tab("general", "常规")
        check(f, "窗口置顶", self.top_var, self._on_top, "翻译窗口始终显示在其他窗口上面。")
        if IS_WIN:
            check(f, "开机自启（最小化到托盘）", self.auto_var, self._on_autostart,
                  "登录 Windows 后自动运行，并直接收进托盘，不打扰你。")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Label(row, text="点窗口右上角 ×：").pack(side="left")
        self.close_cb = ttk.Combobox(row, values=list(CLOSE_NAMES.values()), state="readonly", width=10)
        self.close_cb.set(CLOSE_NAMES.get(self.cfg.get("close_action", "tray"), "隐藏到托盘"))
        self.close_cb.pack(side="left")
        self.close_cb.bind("<<ComboboxSelected>>", lambda e: self._save())
        ttk.Label(f, text="选「隐藏到托盘」时程序继续在后台运行，快捷键和取词照常可用；"
                          "没有托盘图标（被安全软件拦截）时会改为最小化。",
                  foreground="#5b6676", wraplength=500, justify="left").pack(anchor="w", padx=(0, 0), pady=(2, 0))
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Label(row, text="界面字号：").pack(side="left")
        sp = ttk.Spinbox(row, from_=10, to=18, increment=1, width=5,
                         textvariable=self.font_size_var, command=self._on_font_size)
        sp.pack(side="left")
        sp.bind("<Return>", lambda e: self._on_font_size())
        sp.bind("<FocusOut>", lambda e: self._on_font_size())
        ttk.Label(row, text="（10 ~ 18，改完立刻生效：原文 / 译文框、气泡 / 小窗口都跟着变）",
                  foreground="#5b6676").pack(side="left", padx=6)

        # 翻译
        f = tab("translate", "翻译")
        check(f, "中英智能互译", self.smart_var, self._retranslate,
              "检测到中文就译成英文，检测到其他语言译成中文。")
        check(f, "双语对照", self.bi_var, self._on_bilingual, "译文按句与原文逐句对照显示。")
        check(f, "显示原文", self.show_src_var, self._on_show_src, "主窗口里显示 / 隐藏上方的原文输入框。")
        check(f, "合并断行（粘贴 PDF / 文档时用）", self.reflow_var, self._retranslate,
              "把 PDF、网页里被硬换行切断的句子接起来再翻译，翻得更通顺。")
        check(f, "断网 / 在线引擎不可用时，自动改用离线翻译", self.auto_off_var, self._on_auto_offline,
              "需要先装好对应的离线语言包（见「离线与网络」）。")
        check(f, "翻译完成后自动复制译文到剪贴板", self.auto_copy_var, self._save,
              "只对主窗口的翻译生效（气泡 / 小窗口 / 悬停取词 / 截图翻译不自动复制），"
              "复制后剪贴板监听不会把它当成新复制再翻一遍。")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Label(row, text="朗读语速：").pack(side="left")
        sp = ttk.Spinbox(row, from_=-10, to=10, increment=1, width=5,
                         textvariable=self.tts_rate_var, command=self._on_tts_rate)
        sp.pack(side="left")
        sp.bind("<Return>", lambda e: self._on_tts_rate())
        sp.bind("<FocusOut>", lambda e: self._on_tts_rate())
        ttk.Label(row, text="（-10 最慢 ~ 10 最快，0 是默认语速；朗读只在 Windows 上可用）",
                  foreground="#5b6676").pack(side="left", padx=6)

        # 取词
        f = tab("grab", "取词")
        check(f, "监听剪贴板", self.watch_var, self._on_watch, "复制文字后自动翻译并显示主窗口。")
        self.pointer_check_btn = check(
            f, "指针取词（%s）" % self.hotkey_pointer_label, self.pointer_var, self._on_pointer_opt,
            "把鼠标放在文字上按快捷键，取到指针处的文字并翻译（按钮、菜单上的字也能取）。")
        check(f, "悬停取词（鼠标停住自动取词）", self.hover_var, self._on_pointer_opt,
              "鼠标在文字、按钮、菜单上停住后自动取词；鼠标压在本程序的原文 / 译文框或弹窗上时不触发。")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Label(row, text="取词范围：").pack(side="left")
        self.scope_cb = ttk.Combobox(row, values=list(SCOPE_NAMES.values()), state="readonly", width=8)
        self.scope_cb.set(SCOPE_NAMES[self.cfg.get("pointer_scope", "word")])
        self.scope_cb.pack(side="left")
        self.scope_cb.bind("<<ComboboxSelected>>", lambda e: self._on_pointer_opt())
        ttk.Label(row, text="（悬停取词和指针取词共用）", foreground="#5b6676").pack(side="left", padx=6)
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(10, 0))
        ttk.Label(row, text="悬停等待：").pack(side="left")
        sp = ttk.Spinbox(row, from_=300, to=3000, increment=100, width=7,
                         textvariable=self.hover_ms_var, command=self._on_hover_ms)
        sp.pack(side="left")
        sp.bind("<Return>", lambda e: self._on_hover_ms())
        sp.bind("<FocusOut>", lambda e: self._on_hover_ms())
        ttk.Label(row, text="毫秒（300 ~ 3000，鼠标停住多久后自动取词）", foreground="#5b6676").pack(side="left", padx=6)

        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Label(row, text="取词结果显示：").pack(side="left")
        self.popup_cb = ttk.Combobox(row, values=list(POPUP_NAMES.values()), state="readonly", width=24)
        self.popup_cb.set(POPUP_NAMES.get(self.cfg.get("popup_mode", "bubble"), POPUP_NAMES["bubble"]))
        self.popup_cb.pack(side="left")
        self.popup_cb.bind("<<ComboboxSelected>>", lambda e: self._on_popup_opt())
        ttk.Label(f, text="气泡：出现在指针旁，移开就消失；小窗口：固定大小、一直跟着指针走；"
                          "不弹窗：不显示任何弹窗，译文写进主窗口和历史。",
                  foreground="#5b6676", wraplength=540, justify="left").pack(anchor="w", pady=(2, 0))
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(8, 0))
        ttk.Label(row, text="小窗口大小：宽").pack(side="left")
        self.mini_w_var = tk.IntVar(value=int(self.cfg.get("mini_w", 320)))
        self.mini_h_var = tk.IntVar(value=int(self.cfg.get("mini_h", 110)))
        for var, key, unit in ((self.mini_w_var, "mini_w", "　高"), (self.mini_h_var, "mini_h", "")):
            lo, hi, _dv = MINI_SIZE[key]
            sp = ttk.Spinbox(row, from_=lo, to=hi, increment=10, width=5, textvariable=var,
                             command=self._on_mini_size)
            sp.pack(side="left", padx=(2, 0))
            sp.bind("<Return>", lambda e: self._on_mini_size())
            sp.bind("<FocusOut>", lambda e: self._on_mini_size())
            if unit:
                ttk.Label(row, text=unit).pack(side="left", padx=(8, 0))
        ttk.Label(row, text="像素（宽 160~800，高 60~500）", foreground="#5b6676").pack(side="left", padx=6)
        ttk.Button(row, text="预览", command=self._preview_mini).pack(side="left")

        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Label(row, text="截图翻译结果：").pack(side="left")
        self.shot_cb = ttk.Combobox(row, values=list(SHOT_NAMES.values()), state="readonly", width=12)
        self.shot_cb.set(SHOT_NAMES.get(self.cfg.get("shot_mode", "overlay"), SHOT_NAMES["overlay"]))
        self.shot_cb.pack(side="left")
        self.shot_cb.bind("<<ComboboxSelected>>", lambda e: self._save())
        ttk.Label(row, text="（Ctrl+Alt+S 框选后，译文直接盖在截图的原文位置上）", foreground="#5b6676").pack(side="left", padx=6)

        # 历史
        f = tab("history", "历史")
        check(f, "自动保存翻译记录", self.history_on_var, self._on_history_opt,
              "每次翻译成功都存下原文和译文（主窗口、指针取词、悬停取词、截图翻译都存）。"
              "只存在本机 history.db 里，不上传。")
        check(f, "相同原文直接用已保存的译文（翻译记忆）", self.history_reuse_var, self._on_history_opt,
              "原文和语言都相同时不再联网，立刻出结果，也能在断网时重复使用；"
              "想换个译法时在主窗口里改一下原文再翻。")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(12, 0))
        ttk.Label(row, text="最多保存：").pack(side="left")
        sp = ttk.Spinbox(row, from_=100, to=20000, increment=100, width=7,
                         textvariable=self.history_max_var, command=self._on_history_opt)
        sp.pack(side="left")
        sp.bind("<Return>", lambda e: self._on_history_opt())
        sp.bind("<FocusOut>", lambda e: self._on_history_opt())
        ttk.Label(row, text="条（超出时自动删最旧的；收藏的不会被删）", foreground="#5b6676").pack(side="left", padx=6)
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Button(row, text="打开翻译历史…", command=self.open_history).pack(side="left")
        ttk.Button(row, text="导出全部…", command=lambda: self._hist_export(None)).pack(side="left", padx=8)
        ttk.Button(row, text="清空历史（保留收藏）", command=self._hist_clear).pack(side="left")
        self.hist_info = ttk.Label(f, text="", foreground="#5b6676")
        self.hist_info.pack(anchor="w", pady=(10, 0))
        self._hist_update_info()

        # 托盘
        f = tab("tray", "托盘")
        check(f, "第一次隐藏到托盘时提示一次", self.tray_tip_var, self._save,
              "只在第一次弹出气泡，告诉你程序没退出、去哪里找回。")
        ttk.Label(f, text="托盘图标右键菜单：", font=self.ui_font).pack(anchor="w", pady=(16, 2))
        ttk.Label(f, text="显示主窗口 / 截图翻译 / 翻译剪贴板内容\n"
                          "指针取词、悬停取词、取词范围（可直接开关、切换）\n"
                          "监听剪贴板、窗口置顶、断网自动离线、开机自启\n"
                          "高级设置 / 网络检查 / 离线语言包 / 退出",
                  foreground="#5b6676", justify="left").pack(anchor="w", padx=(12, 0))
        ttk.Label(f, text="单击托盘图标显示主窗口。", foreground="#5b6676").pack(anchor="w", pady=(8, 0))

        # 离线与网络
        f = tab("offline", "离线与网络")
        ttk.Label(f, text="离线语言包让你在没有网络时也能翻译；网络检查帮你判断是哪个翻译引擎连不上。",
                  foreground="#5b6676", wraplength=500, justify="left").pack(anchor="w")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Button(row, text="网络检查", command=self.open_netcheck).pack(side="left")
        ttk.Button(row, text="离线语言包…", command=self._show_offline_packs).pack(side="left", padx=8)
        ttk.Label(f, text="「断网时自动改用离线翻译」的开关在「翻译」页。",
                  foreground="#5b6676").pack(anchor="w", pady=(10, 0))

        # 关于
        f = tab("about", "快捷键与关于")
        ttk.Label(f, text="%s v%s" % (APP_TITLE, __version__), font=self.ui_font).pack(anchor="w")
        self.about_hotkey_label = ttk.Label(f, text="", justify="left")
        self.about_hotkey_label.pack(anchor="w", pady=(10, 0))
        self._refresh_hotkey_labels()

        ttk.Label(f, text="自定义全局快捷键（和别的软件冲突时可以在这里改）：",
                  font=self.ui_font).pack(anchor="w", pady=(16, 2))
        self.hotkey_main_var = tk.StringVar(value=self.hotkey_main_label)
        self.hotkey_pointer_var = tk.StringVar(value=self.hotkey_pointer_label)
        self.hotkey_shot_var = tk.StringVar(value=self.hotkey_shot_label)
        self.hotkey_replace_var = tk.StringVar(value=self.hotkey_replace_label)
        for text, var, presets in (
                ("翻译选中的文字：", self.hotkey_main_var,
                 ["Ctrl+Alt+T", "Ctrl+Shift+T", "Alt+Shift+T", "Ctrl+Alt+Q", "Ctrl+Shift+Q", "Win+Alt+T"]),
                ("指针取词：", self.hotkey_pointer_var,
                 ["Ctrl+Alt+D", "Ctrl+Shift+D", "Alt+Shift+D", "Ctrl+Alt+W", "Ctrl+Shift+W", "Win+Alt+D"]),
                ("截图翻译：", self.hotkey_shot_var,
                 ["Ctrl+Alt+S", "Ctrl+Shift+S", "Alt+Shift+S", "Ctrl+Alt+A", "Ctrl+Shift+A", "Win+Alt+S"]),
                ("翻译并替换原文：", self.hotkey_replace_var,
                 ["Ctrl+Alt+R", "Ctrl+Shift+R", "Alt+Shift+R", "Ctrl+Alt+Y", "Ctrl+Shift+Y", "Win+Alt+R"])):
            row = ttk.Frame(f)
            row.pack(anchor="w", pady=(4, 0))
            ttk.Label(row, text=text, width=16).pack(side="left")
            ttk.Combobox(row, textvariable=var, values=presets, width=16).pack(side="left")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(10, 0))
        ttk.Button(row, text="保存快捷键", command=self._save_hotkeys).pack(side="left")
        ttk.Label(row, text="保存后重启程序生效（热键注册只在启动时做一次）。",
                  foreground="#5b6676").pack(side="left", padx=8)

        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(bar, text="恢复默认设置", command=self._reset_settings).pack(side="left")
        ttk.Button(bar, text="关闭", command=self.close_settings).pack(side="right")

    def open_settings(self, tab=None):
        win = self.settings_win
        if tab in self.settings_tabs:
            self.settings_nb.select(self.settings_tabs[tab])
        win.deiconify()
        win.lift()
        win.attributes("-topmost", True)
        if not self.top_var.get():
            win.after(300, lambda: win.attributes("-topmost", False))
        win.focus_force()

    def close_settings(self):
        self.settings_win.withdraw()

    def _on_popup_opt(self):
        self._save()
        if self.cfg.get("popup_mode") != "mini":
            self.mini.close()
        if self.cfg.get("popup_mode") != "bubble":
            self.bubble.close()

    def _on_mini_size(self):
        for var, key in ((self.mini_w_var, "mini_w"), (self.mini_h_var, "mini_h")):
            lo, hi, dv = MINI_SIZE[key]
            try:
                v = int(var.get())
            except Exception:
                v = self.cfg.get(key, dv)
            v = max(lo, min(v, hi))
            var.set(v)
            self.cfg[key] = v
        self._save()
        if self.mini.alive():                       # 正显示着的小窗口立刻按新大小重建
            self._preview_mini()

    def _preview_mini(self):
        """用示例文字显示一次小窗口，方便调大小。"""
        self.mini.show(self.root.winfo_pointerxy(), "Hello world   English → 中文",
                       "你好，世界。这是「跟随指针的小窗口」预览，调整宽高后再点一次预览看效果。"
                       "它会跟着鼠标走，几秒后自动消失。")

    def _on_hover_ms(self):
        try:
            v = int(self.hover_ms_var.get())
        except Exception:
            v = self.cfg.get("hover_ms", 800)
        v = max(300, min(v, 3000))
        self.hover_ms_var.set(v)
        self.cfg["hover_ms"] = v
        self.hover_fired = False
        self._save()

    def _refresh_hotkey_labels(self):
        """把界面上所有写快捷键的地方按当前配置刷新（关于页、取词页、托盘快照）。"""
        try:
            self.about_hotkey_label.configure(
                text="%s　翻译选中的文字\n%s　指针取词（指针处的单词 / 整行 / 整段）\n"
                     "%s　截图翻译（框选屏幕任意区域）\n%s　翻译并替换原文（选中文字翻完直接替换回原处）\nEsc　隐藏窗口 / 关闭气泡"
                     % (self.hotkey_main_label, self.hotkey_pointer_label,
                        self.hotkey_shot_label, self.hotkey_replace_label))
        except Exception:
            pass
        try:
            self.pointer_check_btn.configure(text="指针取词（%s）" % self.hotkey_pointer_label)
        except Exception:
            pass
        self._refresh_tray_state()

    def _save_hotkeys(self):
        """保存自定义全局快捷键：非法或重复的组合不保存，弹错并恢复成原来的值。

        不当场重新注册——热键只在启动时注册一次，改完重启生效（这是诚实、
        安全的做法：注册失败不会在运行中途把正在用的热键弄丢）。
        """
        vals = {}
        for key, var in (("hotkey_main", self.hotkey_main_var),
                         ("hotkey_pointer", self.hotkey_pointer_var),
                         ("hotkey_shot", self.hotkey_shot_var),
                         ("hotkey_replace", self.hotkey_replace_var)):
            vals[key] = var.get().strip()
        seen = set()
        for key, spec in vals.items():
            try:
                parse_hotkey(spec)
                norm = spec.strip().lower()
            except ValueError as e:
                messagebox.showerror("快捷键无效", "「%s」无效：%s\n已恢复成原来的值。" % (spec, e),
                                     parent=self.settings_win)
                self._revert_hotkey_vars()
                return False
            if norm in seen:
                messagebox.showerror("快捷键重复", "「%s」和另一个快捷键重复了，请换一个组合。\n已恢复成原来的值。" % spec,
                                     parent=self.settings_win)
                self._revert_hotkey_vars()
                return False
            seen.add(norm)
        for key, spec in vals.items():
            self.cfg[key] = spec.strip().lower()
        self._revert_hotkey_vars()          # 输入框按规范化后的显示文字回填
        self._save()
        self._refresh_hotkey_labels()
        self.status.configure(text="快捷键已保存，重启程序后生效")
        return True

    def _revert_hotkey_vars(self):
        """把快捷键输入框恢复成当前配置（规范化后的显示文字）。"""
        try:
            self.hotkey_main_var.set(self.hotkey_main_label)
            self.hotkey_pointer_var.set(self.hotkey_pointer_label)
            self.hotkey_shot_var.set(self.hotkey_shot_label)
            self.hotkey_replace_var.set(self.hotkey_replace_label)
        except Exception:
            pass

    def _on_font_size(self):
        """界面字号 Spinbox：钳制 10~18，改完立刻应用并保存。"""
        try:
            v = int(self.font_size_var.get())
        except Exception:
            v = self.cfg.get("font_size", 11)
        v = max(10, min(v, 18))
        self.font_size_var.set(v)
        self.cfg["font_size"] = v
        self._apply_font_size()
        self._save()

    def _apply_font_size(self):
        """把当前字号应用到原文 / 译文框、词典区，以及正显示的气泡 / 小窗口。"""
        size = int(self.cfg.get("font_size", 11))
        fam = getattr(self, "_font_family", self.font[0])
        self.font = (fam, size)
        self.ui_font = (fam, max(8, size - 1))
        for w in (getattr(self, "src", None), getattr(self, "dst", None)):
            try:
                if w is not None:
                    w.configure(font=self.font)
            except Exception:
                pass
        try:
            self.dict_label.configure(font=self.ui_font)
        except Exception:
            pass
        for pop, head_font in ((self.bubble, self.ui_font), (self.mini, (fam, 8))):
            try:
                if pop.alive():
                    pop.head.configure(font=head_font)
                    pop.body.configure(font=self.font)
                    pop.foot.configure(font=(fam, 8))
            except Exception:
                pass

    def _on_tts_rate(self):
        try:
            v = int(self.tts_rate_var.get())
        except Exception:
            v = self.cfg.get("tts_rate", 0)
        v = max(-10, min(v, 10))
        self.tts_rate_var.set(v)
        self.cfg["tts_rate"] = v
        self._save()

    def _reset_settings(self):
        if not messagebox.askyesno("恢复默认设置", "把高级设置里的选项恢复成默认值？\n（不影响开机自启、翻译引擎和语言）",
                                   parent=self.settings_win):
            return
        d = DEFAULTS
        self.top_var.set(d["top"]); self.watch_var.set(d["watch"]); self.smart_var.set(d["smart"])
        self.bi_var.set(d["bilingual"]); self.reflow_var.set(d["reflow"]); self.show_src_var.set(d["show_src"])
        self.auto_off_var.set(d["auto_offline"]); self.pointer_var.set(d["pointer"]); self.hover_var.set(d["hover"])
        self.scope_cb.set(SCOPE_NAMES[d["pointer_scope"]])
        self.hover_ms_var.set(d["hover_ms"]); self.cfg["hover_ms"] = d["hover_ms"]
        self.close_cb.set(CLOSE_NAMES[d["close_action"]]); self.tray_tip_var.set(d["tray_tip"])
        self.history_on_var.set(d["history_on"]); self.history_reuse_var.set(d["history_reuse"])
        self.history_max_var.set(d["history_max"]); self.cfg["history_max"] = d["history_max"]
        self.history.max_items = d["history_max"]
        self.popup_cb.set(POPUP_NAMES[d["popup_mode"]]); self.shot_cb.set(SHOT_NAMES[d["shot_mode"]])
        self.mini_w_var.set(d["mini_w"]); self.mini_h_var.set(d["mini_h"])
        self.cfg["mini_w"], self.cfg["mini_h"] = d["mini_w"], d["mini_h"]
        # v2.5：朗读语速、自动复制、自定义快捷键也恢复默认
        self.tts_rate_var.set(d["tts_rate"]); self.cfg["tts_rate"] = d["tts_rate"]
        self.auto_copy_var.set(d["auto_copy"]); self.cfg["auto_copy"] = d["auto_copy"]
        for k in HOTKEY_KEYS:
            self.cfg[k] = d[k]
        self._revert_hotkey_vars()
        self._refresh_hotkey_labels()
        # v2.6：界面字号也恢复默认并立刻应用
        self.font_size_var.set(d["font_size"]); self.cfg["font_size"] = d["font_size"]
        self._apply_font_size()
        self._on_top(); self._on_auto_offline(); self._on_pointer_opt()
        self._on_show_src(); self._on_bilingual()
        self._retranslate()                       # 里面会 _save()

    # ------------------------------------------------ 翻译记录 / 收藏
    def _on_history_opt(self):
        try:
            v = max(100, min(int(self.history_max_var.get()), 20000))
        except Exception:
            v = self.cfg.get("history_max", 2000)
        self.history_max_var.set(v)
        self.cfg["history_max"] = v
        self.history.max_items = v
        self.cfg["history_on"] = self.history_on_var.get()
        self.cfg["history_reuse"] = self.history_reuse_var.get()
        self._save()
        self._hist_update_info()

    def _hist_update_info(self):
        try:
            self.hist_info.configure(text="已保存 %d 条（其中收藏 %d 条）　位置：%s" % (
                self.history.count(), self.history.count(True), HISTORY_PATH))
        except Exception:
            pass

    def _hist_reuse_main(self, my, text, sl, tl):
        """翻译记忆：开着、且原文 + 语言都和已存记录一样，就直接出结果（不联网）。"""
        if not (self.cfg.get("history_reuse") and self.cfg.get("history_on", True)):
            return False
        hit = self.history.find(text, sl, tl)
        if not hit:
            return False
        self._from_hist = my
        det, target = hit["sl"] or sl, hit["tl"] or tl
        self.q.put(("result", my, True, ([(text, hit["dst"])], det, target, False)))
        return True

    def _hist_save_main(self, my, det, target, engine):
        req = self._req
        if not (self.cfg.get("history_on", True) and req and req[0] == my):
            return
        dst = self.plain_result()
        if dst:
            self.history.add(req[1], dst, det, target, engine, req[4], req[2], req[3])

    def favorite_current(self):
        """收藏 / 取消收藏当前这条翻译（没存历史时也会存下来并标收藏）。"""
        req = self._req
        src = (req[1] if req else self.src.get("1.0", "end")).strip()
        dst = self.plain_result()
        if not src or not dst:
            self.status.configure(text="还没有可收藏的译文")
            return
        sl, tl = (req[2], req[3]) if req else self._codes()
        row = self.history.find(src, sl, tl)
        if row and row["fav"]:
            self.history.set_fav(row["id"], False)
            self.status.configure(text="已取消收藏")
        else:
            det = self.detected or sl
            if self.history.add(src, dst, det, tl, self.engine.get(), req[4] if req else "main",
                                sl, tl, fav=True):
                self.status.configure(text="已收藏 ★")
            else:
                self.status.configure(text="收藏失败（无法写入 %s）" % HISTORY_PATH)
        self._hist_update_info()
        self._hist_refresh()

    # ---- 历史窗口
    def open_history(self, fav_only=None, word_only=None):
        if self.hist_win is None or not self.hist_win.winfo_exists():
            self._hist_build()
        if fav_only is not None:
            self.hist_fav.set(bool(fav_only))
        if word_only is not None:
            self.hist_word_only.set(bool(word_only))
        self._hist_refresh()
        win = self.hist_win
        win.deiconify()
        win.lift()
        win.attributes("-topmost", True)
        if not self.top_var.get():
            win.after(300, lambda: win.attributes("-topmost", False))

    def _hist_build(self):
        win = tk.Toplevel(self.root)
        win.title("翻译历史")
        win.geometry("780x540")
        win.minsize(640, 420)
        win.protocol("WM_DELETE_WINDOW", win.withdraw)
        win.bind("<Escape>", lambda e: win.withdraw())
        try:
            if IS_WIN:
                win.iconbitmap(resource_path("app.ico"))
        except Exception:
            pass
        self.hist_win = win
        self.hist_rows = {}
        self._hist_timer = None

        top = ttk.Frame(win)
        top.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(top, text="搜索").pack(side="left")
        self.hist_q = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self.hist_q)
        ent.pack(side="left", fill="x", expand=True, padx=6)
        self.hist_fav = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="只看收藏 ★", variable=self.hist_fav, command=self._hist_refresh).pack(side="left")
        self.hist_word_only = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="只看单词", variable=self.hist_word_only,
                        command=self._hist_refresh).pack(side="left")
        self.hist_count = ttk.Label(top, text="", foreground="#5b6676")
        self.hist_count.pack(side="right", padx=(8, 0))
        self.hist_q.trace_add("write", lambda *a: self._hist_search_later())
        ent.focus_set()

        mid = ttk.PanedWindow(win, orient="vertical")
        mid.pack(fill="both", expand=True, padx=10, pady=4)
        box = ttk.Frame(mid)
        cols = ("time", "src", "dst", "lang", "fav")
        tv = ttk.Treeview(box, columns=cols, show="headings", selectmode="extended", height=10)
        for c, t, w, a in (("time", "时间", 118, "w"), ("src", "原文", 230, "w"), ("dst", "译文", 230, "w"),
                           ("lang", "语言", 90, "w"), ("fav", "★", 34, "center")):
            tv.heading(c, text=t)
            tv.column(c, width=w, anchor=a, stretch=(c in ("src", "dst")))
        sb = ttk.Scrollbar(box, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tv.pack(side="left", fill="both", expand=True)
        self.hist_tv = tv
        mid.add(box, weight=3)
        det = ttk.Frame(mid)
        self.hist_detail = tk.Text(det, height=7, wrap="word", font=self.font, state="disabled",
                                   relief="solid", borderwidth=1)
        self.hist_detail.tag_configure("head", foreground="#5b6676")
        dsb = ttk.Scrollbar(det, orient="vertical", command=self.hist_detail.yview)
        self.hist_detail.configure(yscrollcommand=dsb.set)
        dsb.pack(side="right", fill="y")
        self.hist_detail.pack(side="left", fill="both", expand=True)
        mid.add(det, weight=2)
        tv.bind("<<TreeviewSelect>>", lambda e: self._hist_on_select())
        tv.bind("<Double-1>", lambda e: self._hist_load())
        tv.bind("<Delete>", lambda e: self._hist_delete())
        tv.bind("<Control-c>", lambda e: self._hist_copy())

        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=10, pady=(4, 10))
        for text, cmd in (("载入到主窗口", self._hist_load), ("复制译文", self._hist_copy),
                          ("朗读译文", self._hist_speak),
                          ("收藏 / 取消", self._hist_toggle_fav), ("删除", self._hist_delete),
                          ("导出…", lambda: self._hist_export(self._hist_selected_rows() or None)),
                          ("清空…", self._hist_clear)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="关闭", command=win.withdraw).pack(side="right")

    def _hist_search_later(self):
        if self._hist_timer:
            self.root.after_cancel(self._hist_timer)
        self._hist_timer = self.root.after(200, self._hist_refresh)

    @staticmethod
    def _one_line(t, n=60):
        t = " ".join((t or "").split())
        return t if len(t) <= n else t[:n] + "…"

    def open_vocab(self):
        """生词本：直接打开只看单词的历史窗口（复用历史记录，不另建表）。

        做法参考了 ScreenLookup（github.com/chaixshot/ScreenLookup，MIT）
        的点词存生词与 Pot（github.com/pot-app/pot-desktop）的生词本导出：
        只借鉴功能思路——本项目不另建生词表，单词就是历史里原文为单个词的记录。
        """
        self.open_history(word_only=True)

    def _hist_refresh(self):
        if self.hist_win is None or not self.hist_win.winfo_exists():
            return
        keep = set(self.hist_tv.selection())
        rows = self.history.search(self.hist_q.get(), self.hist_fav.get(), limit=1000)
        if getattr(self, "hist_word_only", None) is not None and self.hist_word_only.get():
            rows = [r for r in rows if is_word_entry(r["src"])]
        self.hist_rows = {str(r["id"]): r for r in rows}
        self.hist_tv.delete(*self.hist_tv.get_children())
        for r in rows:
            self.hist_tv.insert("", "end", iid=str(r["id"]), values=(
                time.strftime("%m-%d %H:%M", time.localtime(r["ts"])),
                self._one_line(r["src"]), self._one_line(r["dst"]),
                "%s→%s" % (r["sl"] or "?", r["tl"] or "?"), "★" if r["fav"] else ""))
        for iid in keep & set(self.hist_rows):
            self.hist_tv.selection_add(iid)
        total = self.history.count()
        self.hist_count.configure(text="显示 %d / 共 %d 条" % (len(rows), total))
        self._hist_on_select()

    def _hist_selected_rows(self):
        return [self.hist_rows[i] for i in self.hist_tv.selection() if i in self.hist_rows]

    def _hist_on_select(self):
        rows = self._hist_selected_rows()
        t = self.hist_detail
        t.configure(state="normal")
        t.delete("1.0", "end")
        if len(rows) == 1:
            r = rows[0]
            t.insert("end", "%s　%s → %s　%s　%s%s　用过 %d 次\n\n" % (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"])), r["sl"] or "?", r["tl"] or "?",
                r["engine"], history_store.KIND_NAMES.get(r["kind"], r["kind"]),
                "　★" if r["fav"] else "", r["count"]), "head")
            t.insert("end", r["src"] + "\n\n")
            t.insert("end", r["dst"])
        elif rows:
            t.insert("end", "已选 %d 条" % len(rows), "head")
        t.configure(state="disabled")

    def _hist_load(self):
        rows = self._hist_selected_rows()
        if not rows:
            return
        r = rows[0]
        self.show_window()
        self._set_src(r["src"])
        self.seq += 1                                  # 作废还在路上的翻译
        self.pairs = [(r["src"], r["dst"])]
        self.detected = r["sl"] or ""
        self._req = (self.seq, r["src"], r["req_sl"], r["req_tl"], r["kind"])
        self.render()
        self.status.configure(text="%s → %s · 来自历史记录" % (
            lang_name(r["sl"]) if r["sl"] else "?", lang_name(r["tl"]) if r["tl"] else "?"))

    def _hist_copy(self):
        rows = self._hist_selected_rows()
        if rows:
            text = "\n\n".join(r["dst"] for r in rows)
            self._set_clip(text)
            self.last_clip = text
            self.hist_count.configure(text="已复制译文")

    def _hist_speak(self):
        """朗读选中记录的译文（用该记录的目标语言；没选中就不做任何事）。"""
        rows = self._hist_selected_rows()
        if not rows:
            return
        r = rows[0]
        if not (r.get("dst") or "").strip():
            return
        self.speak_text(r["dst"], r.get("tl") or self.cfg.get("tl", "zh-CN"))

    def _hist_toggle_fav(self):
        rows = self._hist_selected_rows()
        if not rows:
            return
        new = not all(r["fav"] for r in rows)
        for r in rows:
            self.history.set_fav(r["id"], new)
        self._hist_refresh()
        self._hist_update_info()

    def _hist_delete(self):
        rows = self._hist_selected_rows()
        if not rows:
            return
        if not messagebox.askyesno("删除记录", "删除选中的 %d 条记录？" % len(rows), parent=self.hist_win):
            return
        self.history.delete([r["id"] for r in rows])
        self._hist_refresh()
        self._hist_update_info()

    def _hist_clear(self):
        parent = self.hist_win if (self.hist_win is not None and self.hist_win.winfo_exists()
                                   and self.hist_win.winfo_viewable()) else self.settings_win
        n, nfav = self.history.count(), self.history.count(True)
        if n - nfav <= 0:
            messagebox.showinfo("清空历史", "没有可清空的记录（收藏的会保留）。", parent=parent)
            return
        if not messagebox.askyesno("清空历史", "清空 %d 条未收藏的记录？\n（%d 条收藏会保留）" % (n - nfav, nfav),
                                   parent=parent):
            return
        self.history.clear(keep_fav=True)
        self._hist_refresh()
        self._hist_update_info()

    def _hist_export(self, rows=None):
        parent = self.hist_win if (self.hist_win is not None and self.hist_win.winfo_exists()
                                   and self.hist_win.winfo_viewable()) else self.settings_win
        path = filedialog.asksaveasfilename(
            parent=parent, title="导出翻译记录", defaultextension=".csv",
            initialfile="翻译记录-%s" % time.strftime("%Y%m%d"),
            filetypes=[("CSV（Excel 可打开）", "*.csv"), ("文本", "*.txt"), ("JSON", "*.json")])
        if not path:
            return
        try:
            n = self.history.export(path, rows)
            messagebox.showinfo("导出翻译记录", "已导出 %d 条：\n%s" % (n, path), parent=parent)
        except Exception as e:
            messagebox.showerror("导出翻译记录", "导出失败：%s" % e, parent=parent)

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
            return "没有取到文字。请先选中文字，再按 %s。" % self.hotkey_pointer_label
        if not self.grab_plan:
            return "终端窗口里请先选中文字，再按 %s。" % self.hotkey_main_label
        if self.grab_plan == ["copy"]:
            return ("指针下不是可选文字（光标不是「I」形）。\n"
                    "请把指针放到文字上；或先选中文字，再按 %s。" % self.hotkey_main_label)
        return "没有取到文字。这个位置的文字可能不可选（图片、按钮等）。"

    def _pointer_translate(self, text, xy):
        self.bseq += 1
        my = self.bseq
        mode = self.cfg.get("popup_mode", "bubble")
        if not text:
            if mode == "main":
                self.status.configure(text=self._pointer_empty_msg())
            else:
                self._popup().show(xy, "指针取词", self._pointer_empty_msg(), error=True)
            return
        text = text[:1000]
        sl, tl = self._codes()
        kind = self.grab_mode if self.grab_mode in ("pointer", "hover") else "pointer"
        if mode == "main":
            # 不弹窗：直接把取到的字交给主窗口翻译（不显示 / 不抢焦点），结果进历史
            self._set_src(text)
            self._kind_hint = kind
            self.translate_now()
            return
        head = text.replace("\n", " ")
        head = head if len(head) <= 60 else head[:60] + "…"
        self._popup().show(xy, head, "翻译中…", lang=tl)
        if self.cfg.get("history_reuse") and self.cfg.get("history_on", True):
            hit = self.history.find(text, sl, tl)
            if hit:
                self.q.put(("bubble", my, True, hit["dst"],
                            "%s → %s · 来自历史记录" % (lang_name(hit["sl"] or sl), lang_name(hit["tl"] or tl)), text,
                            hit["tl"] or tl))
                return
        threading.Thread(target=self._bubble_worker,
                         args=(my, text, sl, tl, self.smart_var.get(), self.engine.get(), kind),
                         daemon=True).start()

    def _bubble_worker(self, my, text, sl, tl, smart, engine, kind="pointer"):
        try:
            out, det, target = translate(text, sl, tl, smart, engine, cancelled=lambda: my != self.bseq)
            if self.cfg.get("history_on", True):
                self.history.add(text, out, det, target, engine, kind, sl, tl)      # 失败只返回 None，不影响气泡
            self.q.put(("bubble", my, True, out, "%s → %s" % (lang_name(det), lang_name(target)), text, target))
        except Exception as e:      # noqa: BLE001
            if my != self.bseq:
                return
            if isinstance(e, offline_engine.OfflineError):
                msg = str(e)
            elif netcheck.is_connectivity_error(e):
                msg = "网络不通，翻译失败。可在主窗口点「网络检查」，或把引擎切到「离线」。"
            else:
                msg = "翻译失败：%s" % e
            self.q.put(("bubble", my, False, msg[:300], "", text, tl))

    def _popup(self):
        """当前取词结果用哪个弹窗：气泡 or 跟随指针的小窗口。"""
        return self.mini if self.cfg.get("popup_mode") == "mini" else self.bubble

    def _on_bubble(self, my, ok, out, route, text, lang=None):
        pop = self._popup()
        if my != self.bseq:
            return
        if self.cfg.get("popup_mode") == "main":
            return
        if not pop.alive():
            return
        head = text.replace("\n", " ")
        head = head if len(head) <= 40 else head[:40] + "…"
        pop.update("%s   %s" % (head, route) if ok else head, out, error=not ok, lang=lang)

    # ------------------------------------------------ 悬停取词 / 截图翻译
    def _ocr_lang(self):
        try:
            sl, _tl = self._codes()
        except Exception:
            return None
        return None if sl == "auto" else sl

    def _hover_blocked(self, pos):
        """鼠标正压在本程序自己的「译文 / 原文 / 历史详情」文本框、弹窗或截图译文层上时不取词，
        避免自己取自己、越翻越多。本程序的按钮、标签、菜单文字照常能取。"""
        try:
            ov = self.shot_overlay
            if ov is not None and ov.winfo_exists():
                return True
            w = self.root.winfo_containing(pos[0], pos[1])
        except Exception:
            return False
        if w is None:
            return False
        if w in (self.src, self.dst, getattr(self, "hist_detail", None)):
            return True
        try:
            top = w.winfo_toplevel()
            return top in (self.bubble.win, self.mini.win)
        except Exception:
            return False

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
        if self._hover_blocked(pos):
            self.hover_last = None
            return
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
        self.mini.hide_for_capture()            # 小窗口别被截进 OCR
        scope = SCOPE_CODES.get(self.scope_cb.get(), "word")     # 在 Tk 线程里读，别在 worker 里碰 Tk
        threading.Thread(target=self._hover_worker, args=(pos, scope), daemon=True).start()

    # 各范围截光标周围多大一块去 OCR：单词一小块就够，整行要横向更宽，整段要纵向更高
    _OCR_BOX = {"word": (420, 110), "line": (900, 90), "paragraph": (900, 560)}

    def _ocr_pick(self, pos, scope):
        """截光标周围一块屏幕，用系统 OCR 取光标处的单词 / 整行 / 整段；取不到返回 None。

        在工作线程里调用（不碰 Tk；屏幕尺寸只在 screen_bounds 取不到时才问 Tk）。
        """
        if not ocr_win.ocr_available():
            return None
        bounds = screen_bounds()
        if bounds is None:
            bounds = (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        bw, bh = self._OCR_BOX.get(scope, self._OCR_BOX["word"])
        x, y, w, h = screen_win.clamp_region(pos[0] - bw // 2, pos[1] - bh // 2, bw, bh, bounds)
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = os.path.join(DATA_DIR, "hover.bmp")
        if self.cfg.get("popup_mode") == "mini":
            time.sleep(0.07)                    # 等隐藏小窗口的重绘完成再截屏
        # 按钮 / 菜单这类小号界面字，放大 2 倍后系统 OCR 才认得出；整段区域大，不放大
        scale = 2 if scope in ("word", "line") else 1
        if scale > 1:
            screen_win.capture_file(tmp, x, y, w, h, scale=scale)
        else:
            screen_win.capture_file(tmp, x, y, w, h)
        try:
            rx, ry = (pos[0] - x) * scale, (pos[1] - y) * scale
            if scope in ("line", "paragraph"):
                lines = ocr_win.ocr_lines(tmp, lang=self._ocr_lang())
                return ocr_win.pick_text_at(lines, rx, ry, scope)
            words = ocr_win.ocr_words(tmp, lang=self._ocr_lang())
            return ocr_win.pick_word_at(words, rx, ry)
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass

    def _hover_worker(self, pos, scope="word"):
        # 先走截图 OCR：认出光标处的单词 / 整行 / 整段。这条路不依赖软件本身
        # 是否支持选词，图片 / 游戏 / 扫描 PDF 里也能用。
        word, ibeam = None, False
        try:
            word = self._ocr_pick(pos, scope)
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
            if self.cfg.get("shot_mode", "overlay") == "overlay":
                self._shot_overlay_worker(rect, xy, tmp)
                return
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

    def _shot_overlay_worker(self, rect, xy, tmp):
        """截图 → OCR 行 → 按段翻译 → 交给界面线程把译文盖在截图上。"""
        x, y, w, h = rect
        cw, ch, bgra = screen_win.capture_region(x, y, w, h)
        screen_win.save_bmp(tmp, cw, ch, bgra)
        try:
            lines = ocr_win.ocr_lines(tmp, lang=self._ocr_lang())
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass
        if not lines:
            self.q.put(("shot_ocr", True, "", xy))        # 没认出字：走原来的提示
            return
        sl, tl = self._codes()
        smart, engine = self.smart_var.get(), self.engine.get()
        groups = ocr_win.group_paragraphs(lines)
        texts = [ocr_win.join_lines([lines[k]["text"] for k in idxs]) for idxs in groups]
        det_box = {"det": sl, "target": tl}

        def one(t):
            try:
                out, det, target = translate(t, sl, tl, smart, engine, cancelled=lambda: False)
                det_box["det"], det_box["target"] = det, target
                return out, True
            except Exception as e:      # noqa: BLE001  一段失败不影响其余段
                return "（翻译失败：%s）" % str(e)[:60], False

        with ThreadPoolExecutor(WORKERS) as ex:
            results = list(ex.map(one, texts))
        boxes = []
        for idxs, src_t, (dst_t, ok) in zip(groups, texts, results):
            bx, by, bw, bh = ocr_win.paragraph_box(lines, idxs)
            bg = screen_win.sample_bg(cw, ch, bgra, bx, by, bw, bh)
            boxes.append({"x": bx, "y": by, "w": bw, "h": bh, "src": src_t, "dst": dst_t, "ok": ok,
                          "bg": bg, "fg": screen_win.text_color_for(bg)})
        png = screen_win.bgra_to_png(cw, ch, bgra)
        self.q.put(("shot_overlay", rect, png, boxes, det_box["det"], det_box["target"], engine))

    # ---- 截图翻译：译文盖在截图上
    def _close_shot_overlay(self):
        ov = self.shot_overlay
        self.shot_overlay = None
        if ov is not None:
            try:
                ov.destroy()
            except Exception:
                pass

    def _show_shot_overlay(self, rect, png, boxes, det, target, engine):
        """在原来框选的位置开一个无边框置顶窗：底图是截图，每一段原文上盖一块「背景色 + 译文」。

        左键点一下复制全部译文；右键 / Esc 关闭。译文比原文长时，盖块向下延伸。"""
        self._close_shot_overlay()
        x, y, w, h = rect
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        try:
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        canvas = tk.Canvas(win, width=w, height=h, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        img = tk.PhotoImage(data=base64.b64encode(png))
        canvas.create_image(0, 0, image=img, anchor="nw")
        win._img = img                                   # 引用要留着，否则图被回收
        family = self.font[0] if isinstance(self.font, (tuple, list)) else "Microsoft YaHei UI"
        pad = 2
        for b in boxes:
            bx, by, bw, bh = b["x"], b["y"], max(b["w"], 24), b["h"]
            rid = canvas.create_rectangle(bx - pad, by - pad, bx + bw + pad, by + bh + pad,
                                          fill=b["bg"], outline="")
            size = max(8, min(26, int(bh * 0.8)))
            nl = max(1, b["src"].count("\n") + 1)
            tid = None
            while True:
                tid = canvas.create_text(bx, by, text=b["dst"], anchor="nw", width=bw,
                                         font=(family, -size), fill=b["fg"] if b["ok"] else "#d92d20")
                bb = canvas.bbox(tid)
                if size <= 9 or (bb and bb[3] - bb[1] <= bh + 2 * pad):
                    break
                canvas.delete(tid)
                size -= 1
            bb = canvas.bbox(tid)
            if bb and bb[3] + pad > by + bh + pad:        # 放不下：把盖块向下延伸，别露出下面的原文
                canvas.coords(rid, bx - pad, by - pad, bx + bw + pad, min(h, bb[3] + pad))
        tip = canvas.create_text(w - 6, h - 4, anchor="se", text="点击复制译文 · 右键 / Esc 关闭",
                                 font=(family, -11), fill="#ffffff")
        tb = canvas.bbox(tip)
        if tb:
            bgid = canvas.create_rectangle(tb[0] - 4, tb[1] - 2, tb[2] + 4, tb[3] + 2, fill="#1f2937", outline="")
            canvas.tag_lower(bgid, tip)
        full = "\n".join(b["dst"] for b in boxes)
        src_full = "\n".join(b["src"] for b in boxes)

        def copy_all(_e=None):
            self._set_clip(full)
            self.last_clip = full
            self.status.configure(text="已复制截图译文")
            self._close_shot_overlay()

        canvas.bind("<Button-1>", copy_all)
        canvas.bind("<Button-3>", lambda e: self._close_shot_overlay())
        win.bind("<Escape>", lambda e: self._close_shot_overlay())
        self.shot_overlay = win
        try:
            win.focus_force()
        except Exception:
            pass
        # 同步到主窗口（不弹出来）：想对照 / 复制时随时能看，也存进历史
        self._set_src(src_full[:MAX_LEN])
        self.seq += 1
        self.pairs = [(b["src"], b["dst"]) for b in boxes if b["ok"]]
        self.detected = det
        self.render()
        self.status.configure(text="截图翻译：%s → %s · %s · %d 段" % (
            lang_name(det), lang_name(target), engine, len(boxes)))
        if self.cfg.get("history_on", True) and any(b["ok"] for b in boxes):
            sl, tl = self._codes()
            self.history.add(src_full, "\n".join(b["dst"] for b in boxes if b["ok"]),
                             det, target, engine, "screenshot", sl, tl)

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
        self._kind_hint = "screenshot"
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
            pointer_scope=SCOPE_CODES.get(self.scope_cb.get(), "word"),
            close_action=CLOSE_CODES.get(self.close_cb.get(), "tray"),
            popup_mode=POPUP_CODES.get(self.popup_cb.get(), "bubble"),
            shot_mode=SHOT_CODES.get(self.shot_cb.get(), "overlay"),
            tray_tip=self.tray_tip_var.get(),
            history_on=self.history_on_var.get(), history_reuse=self.history_reuse_var.get(),
            history_max=self.cfg.get("history_max", 2000),
            auto_copy=self.auto_copy_var.get(), tts_rate=self.cfg.get("tts_rate", 0),
            font_size=self.cfg.get("font_size", 11))
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = CONFIG_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, ensure_ascii=False, indent=1)
            os.replace(tmp, CONFIG_PATH)
        except Exception:
            pass
        self._update_engine_hint()
        self._refresh_tray_state()

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
        self._refresh_tray_state()

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
        self._hide_dict()
        self.status.configure(text="")
        self.src.focus_set()

    def copy_result(self):
        text = self.plain_result()
        if text:
            self._set_clip(text)
            self.last_clip = text
            self.status.configure(text="已复制译文")

    def copy_source(self):
        """复制原文：把原文框的文字放进剪贴板，并记下 last_clip，
        免得剪贴板监听把它当成别处新复制的文字、又翻一遍。"""
        text = self.src.get("1.0", "end").strip()
        if text:
            self._set_clip(text)
            self.last_clip = text
            self.status.configure(text="已复制原文")

    def copy_bilingual(self):
        """复制双语对照，返回复制的文字（没内容返回 ""）。

        格式：双语对照开着时按段逐行「原文行 / 译文行」（和译文框里显示的
        顺序一致，段与段之间空一行）；没开时是「原文全文 + 空行 + 译文全文」。
        """
        pairs = [(s, d) for s, d in self.pairs if s or d]
        src = self.src.get("1.0", "end").strip()
        dst = self.plain_result()
        if not src and not dst:
            return ""
        if self.bi_var.get() and pairs:
            parts = []
            for s, d in pairs:
                if not s and not d:
                    parts.append("")
                elif s and d:
                    parts.append(s + "\n" + d)
                else:
                    parts.append(s or d)
            text = "\n\n".join(parts).strip()
        else:
            text = (src + "\n\n" + dst).strip() if src and dst else (src or dst)
        self._set_clip(text)
        self.last_clip = text
        self.status.configure(text="已复制双语对照" if self.bi_var.get() else "已复制原文+译文")
        return text

    # ---- 朗读发音（Windows 自带语音；非 Windows 只报状态，不做任何事） ----
    def speak_text(self, text, lang_code=None):
        """朗读一段文字：正在读同一段时再调一次就停掉（切换开关）。

        lang_code 是这段文字的语言（如 "zh-CN" / "en"），没给就用当前目标语言。
        非 Windows 时状态栏明说不可用，返回 False；成功开始朗读返回 True。
        """
        text = (text or "").strip()
        if not text:
            return False
        if tts_win is None or not tts_win.is_available():
            self.status.configure(text="朗读只在 Windows 上可用")
            return False
        lang = lang_code or self.cfg.get("tl", "zh-CN")
        try:
            if tts_win.is_speaking():
                tts_win.stop()
                self._tts_kind = None
                self.status.configure(text="已停止朗读")
                return True
            ok = tts_win.speak(text, lang, rate=int(self.cfg.get("tts_rate", 0)))
        except Exception:
            ok = False
        if ok:
            self.status.configure(text="正在朗读…（再点一次停止）")
        else:
            self.status.configure(text="朗读失败：本机可能没有该语言的语音（设置 → 语言 → 添加语言）")
        return bool(ok)

    def speak_source(self):
        """朗读原文：语言用检测到的原文语种（没检测到就用源语言选择）。"""
        text = self.src.get("1.0", "end").strip()
        if not text:
            return False
        sl, _tl = self._codes()
        lang = self.detected or (sl if sl != "auto" else "en")
        if tts_win is not None and tts_win.is_speaking() and self._tts_kind == "src":
            tts_win.stop()
            self._tts_kind = None
            self.status.configure(text="已停止朗读")
            return True
        ok = self.speak_text(text, lang)
        if ok:
            self._tts_kind = "src"
        return ok

    def speak_result(self):
        """朗读译文：语言用当前目标语言。"""
        text = self.plain_result()
        if not text:
            return False
        if tts_win is not None and tts_win.is_speaking() and self._tts_kind == "dst":
            tts_win.stop()
            self._tts_kind = None
            self.status.configure(text="已停止朗读")
            return True
        ok = self.speak_text(text, self.cfg.get("tl", "zh-CN"))
        if ok:
            self._tts_kind = "dst"
        return ok

    # ---- v2.6 词典区（只对 Google 引擎、单个词或短词组显示） ----
    def _hide_dict(self):
        try:
            if self.dict_frame.winfo_ismapped():
                self.dict_frame.pack_forget()
        except Exception:
            pass

    def _update_dict_area(self):
        """主窗口翻译成功后，按当前请求决定词典区显不显示。

        只显示一种情况：Google 引擎 + 输入是单个词或短词组 + 上次 Google
        响应里真有词典或 transliteration。解析不到就整块隐藏，不报错、
        不显示空框。transliteration 只取响应里真有的字段，绝不自己编拼音。
        """
        req = self._req
        if not req or req[4] != "main":
            self._hide_dict()
            return
        _my, src, sl, tl, _kind = req
        if self.engine.get() != "Google" or not is_dict_candidate(src):
            self._hide_dict()
            return
        raw = None
        if (_LAST_GOOGLE.get("text") == src and _LAST_GOOGLE.get("sl") == sl
                and _LAST_GOOGLE.get("tl") == tl):
            raw = _LAST_GOOGLE.get("data")
        parsed = parse_dict(raw) if raw is not None else {"entries": [], "translit": ""}
        if not parsed["entries"] and not parsed["translit"]:
            self._hide_dict()
            return
        lines = ["词典："]
        for e in parsed["entries"]:
            lines.append("%s：%s" % (e["pos"], "；".join(e["meanings"])))
        if parsed["translit"]:
            spoken = self.detected or sl
            label = "拼音：" if base(spoken) == "zh" else "读音："
            lines.append("%s%s" % (label, parsed["translit"]))
        self.dict_label.configure(text="\n".join(lines))
        if not self.dict_frame.winfo_ismapped():
            self.dict_frame.pack(fill="x", pady=(0, 2))

    # ---- v2.6 文档翻译（.txt / .md / .srt） ----
    def _translate_doc_file(self):
        path = filedialog.askopenfilename(
            title="选择要翻译的文档",
            filetypes=[("文档", "*.txt *.md *.srt"), ("文本", "*.txt"),
                       ("Markdown", "*.md"), ("字幕", "*.srt")])
        if not path:
            return
        if not doc_translate.supported_doc_ext(path):
            self.status.configure(text="只支持 .txt / .md / .srt 文档")
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
        except Exception as e:
            self.status.configure(text="打不开文档：%s" % e)
            return
        if not text.strip():
            self.status.configure(text="文档是空的")
            return
        self._doc_path = path
        self.status.configure(text="正在翻译文档…")
        # 语言/引擎/选项在 Tk 线程里读好再传进去：worker 线程里不能碰 Tk 控件。
        sl, tl = self._codes()
        threading.Thread(target=self._doc_worker,
                         args=(path, text, sl, tl, self.engine.get(),
                               self.smart_var.get(), self.reflow_var.get()),
                         daemon=True).start()

    def _doc_worker(self, path, text, sl, tl, engine, smart, reflow):
        """文档翻译（后台线程）：.srt 只翻正文，.txt/.md 按段落翻整篇。"""
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".srt":
                blocks = doc_translate.srt_parse(text)
                if not blocks:
                    self.q.put(("doc_done", False, "没有解析到字幕块"))
                    return
                src_texts = [b["text"] for b in blocks]
                first, det, target = translate(src_texts[0], sl, tl, smart, engine,
                                               cancelled=lambda: False)
                outs = [first]
                for i, t in enumerate(src_texts[1:], start=2):
                    self.q.put(("doc_prog", i, len(blocks)))
                    outs.append(translate_unit(t, det, target, engine,
                                               cancelled=lambda: False))
                pairs = list(zip(src_texts, outs))
                for b, o in zip(blocks, outs):
                    b["text"] = o
                out_text = doc_translate.srt_rebuild(blocks)
            else:
                pairs, det, target = translate_doc(
                    text, sl, tl, smart, reflow, engine,
                    progress=lambda d, n: self.q.put(("doc_prog", d, n)),
                    cancelled=lambda: False)
                out_text = "\n".join(d for _, d in pairs)
            self.q.put(("doc_done", True, (out_text, det, target, text, pairs, sl, tl)))
        except Exception as e:      # noqa: BLE001
            self.q.put(("doc_done", False, str(e)[:300]))

    def _on_doc_done(self, ok, payload):
        if not ok:
            self.status.configure(text="文档翻译失败：%s" % payload)
            return
        out_text, det, target, src_text, pairs, sl, tl = payload
        path = getattr(self, "_doc_path", "")
        # 译文载入主窗口（前部）+ 存历史（kind="doc"，原文/译文各存前 2000 字，
        # 免得整篇大文档把 history.db 撑大）。
        self.show_window()
        self.seq += 1
        self.pairs, self.detected = pairs, det
        self._req = (self.seq, src_text[:MAX_LEN], sl, tl, "doc")
        self._set_src(src_text[:MAX_LEN])
        self.render()
        self.history.add(src_text[:2000], out_text[:2000], det, target,
                         self.engine.get(), "doc", sl, tl)
        self._hist_update_info()
        # 保存路径：默认原文旁加 -译文 后缀；用户取消也不丢结果（已在主窗口里）。
        saved = ""
        if path:
            base, ext = os.path.splitext(path)
            save = filedialog.asksaveasfilename(
                title="保存译文", initialdir=os.path.dirname(path) or ".",
                initialfile=os.path.basename(base + "-译文" + ext),
                defaultextension=ext,
                filetypes=[("文档", "*" + ext), ("所有文件", "*.*")])
            if save:
                try:
                    with open(save, "w", encoding="utf-8") as f:
                        f.write(out_text)
                    saved = save
                except Exception as e:      # noqa: BLE001
                    self.status.configure(text="文档已翻好，但保存失败：%s" % e)
                    return
        self.status.configure(
            text="%s → %s · 文档翻译完成%s" % (lang_name(det), lang_name(target),
                                              "，已保存到 %s" % saved if saved else "（未保存到文件，译文在主窗口里）"))

    # ---- v2.6 图片文件翻译（Windows 系统 OCR，复用 ocr_win） ----
    def _translate_image_file(self):
        path = filedialog.askopenfilename(
            title="选择要翻译的图片",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.tif *.tiff"),
                       ("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg"),
                       ("BMP", "*.bmp"), ("TIFF", "*.tif *.tiff")])
        if not path:
            return
        if not doc_translate.supported_image_ext(path):
            self.status.configure(text="只支持 .png / .jpg / .jpeg / .bmp / .tif 图片")
            return
        if not IS_WIN:
            self.status.configure(text="图片翻译只在 Windows 上可用（需要系统 OCR）")
            return
        if not ocr_win.ocr_available():
            self.status.configure(text="图片翻译需要 Windows 系统 OCR（winocr.ps1 缺失或没有 PowerShell 5.1）")
            return
        self.status.configure(text="正在识别图片文字…")
        # OCR 语言在 Tk 线程里读好再传进去：worker 线程里不能碰 Tk 控件。
        threading.Thread(target=self._image_worker, args=(path, self._ocr_lang()),
                         daemon=True).start()

    def _image_worker(self, path, lang):
        """图片 OCR（后台线程）：认出的文字交给主窗口翻译，kind="image"。"""
        try:
            text = ocr_win.ocr_image(path, lang=lang)
        except Exception as e:      # noqa: BLE001
            self.q.put(("image_ocr", False, str(e)[:300], path))
            return
        self.q.put(("image_ocr", True, (text or "").strip(), path))

    def _on_image_ocr(self, ok, text, path):
        if not ok:
            self.status.configure(text="图片识别失败：%s" % text)
            return
        if not text:
            self.status.configure(text="图片里没有认出文字")
            return
        self._kind_hint = "image"
        self._set_src(text[:MAX_LEN])
        self.show_window()
        self.translate_now()

    # ---- v2.6 语音输入（Windows 自带语音识别，15 秒超时） ----
    def _stt_lang(self):
        """语音识别用的语言：说的是原文，所以用源语言；自动检测时按目标语言反推
        （目标是英文就默认说中文，否则默认说英文），识别错了也能在原文框里改。"""
        sl, tl = self._codes()
        if sl != "auto":
            return sl
        return "zh-CN" if base(tl) == "en" else "en"

    def start_voice_input(self):
        if getattr(self, "_stt_busy", False):
            self.status.configure(text="正在听…请说话")
            return
        if not IS_WIN or stt_win is None or not stt_win.is_available():
            self.status.configure(text="语音输入只在 Windows 上可用")
            return
        self._stt_busy = True
        self.status.configure(text="正在听，请说话（15 秒内）…")
        # 识别语言在 Tk 线程里读好再传进去：worker 线程里不能碰 Tk 控件。
        threading.Thread(target=self._stt_worker, args=(self._stt_lang(),),
                         daemon=True).start()

    def _stt_worker(self, lang):
        try:
            status, text = stt_win.recognize(lang)
        except Exception as e:      # noqa: BLE001
            status, text = "error", str(e)[:200]
        self.q.put(("stt_done", status, text))

    def _on_stt_done(self, status, text):
        self._stt_busy = False
        if status == "ok" and (text or "").strip():
            self._set_src(text.strip()[:MAX_LEN])
            self.show_window()
            self.translate_now()
        elif status == "timeout":
            self.status.configure(text="语音输入超时（15 秒内没听到说话）")
        elif status == "unavailable":
            self.status.configure(text="语音输入只在 Windows 上可用")
        else:
            self.status.configure(text="语音输入失败：%s" % (text or "请检查麦克风"))

    # ---- v2.6 翻译并替换原文（Replace as you go） ----
    def _on_replace_hotkey(self):
        """Ctrl+Alt+R：记住当前前台窗口 → 复制选中文字 → 翻译 → 粘贴替换。

        做法参考了 QTranslate（qtranslate-app.web.app，Ctrl+Shift+T 原地替换）
        的功能思路，安全护栏是本项目自己的：只在 Windows 上；终端窗口不做
        替换；粘贴前校验前台窗口还是刚才那个，变了就只把译文留在剪贴板。
        """
        if not IS_WIN:
            self.status.configure(text="翻译并替换只在 Windows 上可用")
            return
        if self.grabbing:
            return
        if foreground_is_terminal_win():
            self.status.configure(text="终端窗口里不支持翻译并替换（Ctrl+V 在终端里不是粘贴）")
            return
        self._replace_hwnd = foreground_window_win()
        self.grab_mode = "replace"
        self.grabbing = True
        self.old_clip = self._get_clip()
        self.root.clipboard_clear()
        self._seq0 = clip_seq_win()
        threading.Thread(target=self._copy_selection, daemon=True).start()

    def _translate_replace(self, text):
        self.seq += 1
        my = self.seq
        sl, tl = self._codes()
        engine = self.engine.get()
        self._req = (my, text, sl, tl, "replace")
        if self._hist_reuse_main(my, text, sl, tl):
            return
        self.status.configure(text="正在翻译并替换…")
        threading.Thread(
            target=self._worker,
            args=(my, text, sl, tl, self.smart_var.get(),
                  self.reflow_var.get(), engine),
            daemon=True).start()

    def _do_replace(self):
        """翻译并替换的最后一步：按 replace_decision 决定粘贴还是只留剪贴板。

        失败时译文仍在剪贴板里，不丢结果；窗口句柄拿不到时按「窗口变了」处理。
        """
        dst = self.plain_result()
        if not dst:
            self.status.configure(text="翻译并替换失败：没有得到译文")
            return
        hwnd0 = getattr(self, "_replace_hwnd", 0)
        try:
            same = bool(hwnd0) and foreground_window_win() == hwnd0
        except Exception:
            same = False
        try:
            terminal = foreground_is_terminal_win()
        except Exception:
            terminal = True
        action = replace_decision(IS_WIN, same, terminal)
        self._set_clip(dst)
        self.last_clip = dst
        if action == "paste":
            try:
                focus_window_win(hwnd0)
                time.sleep(0.15)
                send_paste_win()
            except Exception:
                pass
            self.status.configure(text="已把选中文字替换为译文")
        elif action == "clipboard-only":
            self.status.configure(text="前台窗口已变，只把译文放进了剪贴板（按 Ctrl+V 粘贴）")
        elif action == "skip-terminal":
            self.status.configure(text="终端窗口里不支持翻译并替换，译文已放进剪贴板")
        else:
            self.status.configure(text="翻译并替换只在 Windows 上可用，译文已放进剪贴板")

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
        self._hide_dict()
        if not text:
            self.pairs = []
            self.render()
            self.status.configure(text="")
            return
        sl, tl = self._codes()
        engine = self.engine.get()
        self.truncated = len(text) > MAX_LEN
        kind, self._kind_hint = self._kind_hint, "main"
        self._req = (my, text[:MAX_LEN], sl, tl, kind)
        if self._hist_reuse_main(my, text[:MAX_LEN], sl, tl):
            return
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
            if tts_win is not None:
                tts_win.stop()          # 正在朗读就停掉，别留一个 powershell 在后台读
        except Exception:
            pass
        try:
            if getattr(self, "tray", None) is not None:
                self.tray.stop()
        except Exception:
            pass
        try:
            self.bubble.close()
            self.mini.close()
            self._close_shot_overlay()
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
        main_l, pointer_l, shot_l = self.hotkey_main_label, self.hotkey_pointer_label, self.hotkey_shot_label
        replace_l = self.hotkey_replace_label
        ok_text = ("选中文字后按 %s 翻译；指针放在文字上按 %s 就地取词；按 %s 截图翻译；按 %s 翻译并替换原文；Esc 隐藏到托盘"
                   % (main_l, pointer_l, shot_l, replace_l)) if IS_WIN else \
                  ("选中文字后按 %s 翻译，或按 %s 在指针旁显示译文；Esc 隐藏窗口" % (main_l, pointer_l))
        if IS_WIN:
            try:
                specs = {k: self.cfg.get(k, DEFAULT_HOTKEYS[k]) for k in HOTKEY_KEYS}
                ok = start_hotkey_win(self.q, specs)
                pok = getattr(start_hotkey_win, "pointer_ok", False)
                sok = getattr(start_hotkey_win, "shot_ok", False)
                rok = getattr(start_hotkey_win, "replace_ok", False)
                missing = []
                if not ok:
                    missing.append(main_l)
                if not pok:
                    missing.append(pointer_l)
                if not sok:
                    missing.append(shot_l)
                if not rok:
                    missing.append(replace_l)
                if not missing:
                    self.hint.configure(text=ok_text)
                else:
                    self.hint.configure(text="%s 已被其他程序占用，不可用；其余快捷键仍可用（高级设置 → 快捷键与关于里可改）" % " / ".join(missing))
            except Exception as e:
                self.hint.configure(text="全局快捷键启动失败：%s" % e)
            return
        if keyboard is None:
            self.hint.configure(text="未安装 pynput，全局快捷键不可用（pip install pynput）")
            return
        try:
            specs = {k: self.cfg.get(k, DEFAULT_HOTKEYS[k]) for k in HOTKEY_KEYS}
            self.hk = keyboard.GlobalHotKeys({pynput_spec(specs["hotkey_main"]): lambda: self.q.put(("hotkey", 1)),
                                              pynput_spec(specs["hotkey_pointer"]): lambda: self.q.put(("hotkey", 2)),
                                              pynput_spec(specs["hotkey_shot"]): lambda: self.q.put(("hotkey", 3)),
                                              pynput_spec(specs["hotkey_replace"]): lambda: self.q.put(("hotkey", 4))})
            self.hk.daemon = True
            self.hk.start()
            self.hint.configure(text=ok_text)
        except Exception as e:
            self.hint.configure(text="全局快捷键启动失败：%s" % e)

    def _on_hotkey(self, which=1):
        if which == 3:
            self.start_screenshot()
            return
        if which == 4:
            self._on_replace_hotkey()
            return
        if self.grabbing:
            return
        pointer = (which == 2)
        if pointer and not self.pointer_var.get():
            return
        self.grab_mode = "pointer" if pointer else "main"
        if pointer:
            self.mini.hide_for_capture()
            self.grab_xy = self.root.winfo_pointerxy()
            self.grab_scope = SCOPE_CODES.get(self.scope_cb.get(), "word")
            self.grab_plan = []
        self.grabbing = True
        self.old_clip = self._get_clip()
        self.root.clipboard_clear()
        self._seq0 = clip_seq_win() if IS_WIN else 0
        threading.Thread(target=self._copy_selection, daemon=True).start()

    def _pointer_grab_win(self):
        """指针取词（Windows）：整行 / 整段先 OCR；单词在「I」形光标处双击选词再 Ctrl+C，
        复制不到（按钮、菜单等选不中的文字）就改用 OCR。"""
        self._pointer_text = None
        if not wait_keys_up_win((0x10, 0x11, 0x12, 0x44)):
            return                                    # 快捷键没松开，宁可不取也不乱点
        no_ocr, self._no_ocr = getattr(self, "_no_ocr", False), False
        if self.grab_scope in ("line", "paragraph") and not no_ocr:
            # 整行 / 整段：先用截图 OCR 取，不依赖软件支持选词、也不会点击任何东西；
            # OCR 没取到才退回三击选中。
            try:
                self._pointer_text = self._ocr_pick(self.grab_xy, self.grab_scope)
            except Exception:
                self._pointer_text = None
            if self._pointer_text:
                return
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
        if not no_ocr and self.grab_scope not in ("line", "paragraph") and clip_seq_win() == self._seq0:
            # 按钮、菜单、标签这类「选不中」的文字：光标不是「I」形，复制不到任何东西 ——
            # 改用截屏 OCR 取指针处的单词（不点击，不会误触按钮）。
            try:
                self._pointer_text = self._ocr_pick(self.grab_xy, self.grab_scope)
            except Exception:
                self._pointer_text = None

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
        if self.grab_mode == "pointer" and getattr(self, "_pointer_text", None):
            text, self._pointer_text = self._pointer_text, None      # OCR 取到的整行 / 整段
        self._set_clip(self.old_clip)
        self.last_clip = self.old_clip
        self.grabbing = False
        if self.grab_mode == "pointer":
            self._pointer_translate(text.strip(), self.grab_xy)      # 气泡就地显示，不打开主窗口
            return
        if self.grab_mode == "replace":
            if text.strip():
                self._translate_replace(text.strip()[:MAX_LEN])
            else:
                self.status.configure(text="没有检测到选中的文字")
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
                elif kind == "tray_cmd":
                    self._on_tray_cmd(msg[1])
                elif kind == "shot_overlay":
                    self._show_shot_overlay(*msg[1:])
                elif kind == "shot_ocr":
                    self._on_shot_ocr(msg[1], msg[2], msg[3])
                elif kind == "doc_prog":
                    self.status.configure(text="正在翻译文档 %d/%d" % (msg[1], msg[2]))
                elif kind == "doc_done":
                    self._on_doc_done(msg[1], msg[2])
                elif kind == "image_ocr":
                    self._on_image_ocr(msg[1], msg[2], msg[3])
                elif kind == "stt_done":
                    self._on_stt_done(msg[1], msg[2])
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
                        self._no_ocr = True         # 刚 OCR 过没取到，别再 OCR 一遍
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
                        # v2.6 翻译并替换：不写主窗口、不自动复制，只存历史 + 粘贴/留剪贴板
                        req = self._req
                        if req and req[0] == my and req[4] == "replace":
                            self._hist_save_main(my, det, target, "离线" if fb else self.engine.get())
                            self._do_replace()
                            continue
                        self.render()
                        n = sum(1 for s, _ in pairs if s)
                        extra = "（%d 段）" % n if n > 1 else ""
                        eng = self.engine.get()
                        warn = " · 已截断至 %d 字" % MAX_LEN if getattr(self, "truncated", False) else ""
                        if fb and eng != "离线":
                            warn += " · 在线不可用，已自动改用离线"
                        if my == self._from_hist:
                            warn += " · 来自历史记录"
                        else:
                            self._hist_save_main(my, det, target, "离线" if fb else eng)
                        self.status.configure(
                            text="%s → %s%s · %s%s" % (lang_name(det), lang_name(target), extra, eng, warn))
                        # v2.5 自动复制：只对主窗口的翻译生效（_req[4] == "main"）。
                        # 气泡 / 小窗口 / 悬停 / 截图不走这里（它们的 kind 是 pointer/hover/shot，
                        # 或直接走 _bubble_worker），所以不会误复制。last_clip 是护栏：
                        # 复制完立刻记下，剪贴板监听（_watch_clip）就不会把它当成新复制再翻一遍。
                        req = self._req
                        if (self.cfg.get("auto_copy") and req and req[0] == my
                                and req[4] == "main" and self.plain_result()):
                            text = self.plain_result()
                            self._set_clip(text)
                            self.last_clip = text
                            self.status.configure(text=self.status.cget("text") + " · 已复制")
                        self._update_dict_area()
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
