#!/usr/bin/env python3
"""
实时翻译 — 桌面独立版 v2.15，Windows / macOS / Linux(X11)

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
 15. v2.7：健壮性审计（worker 线程不再碰 Tk 控件、网络检查与离线预热
     失败写崩溃日志、OCR/TTS/语音的 PowerShell 全都不弹黑窗）、检查更新
     （GitHub Releases，手动 + 每天启动时静默一次，绝不自动下载安装）、
     .docx 文档翻译（标准库 zipfile，样式图片原样保留）、自定义术语表
     （专有名词按固定译文翻）、生词本导出 Anki（.tsv）、深色外观（默认浅色，
     可选）、悬停取词 2 秒缓存（指针不动不再重复 OCR）、Ctrl+Enter 立即翻译
 16. v2.8：术语表 JSON 导入 / 导出、粘贴图片翻译（剪贴板图片 → 系统 OCR，
     Ctrl+Shift+V）、历史搜索框（按原文或译文筛，可和只看单词 / 只看收藏
     一起用）、单实例（Windows 互斥体，非 Windows 用文件锁；已有实例在
     跑就唤起它）、设置导出 / 导入（JSON，导入前先全量校验）、PDF 翻译
     （标准库提取正文，输出是 -译文.txt；扫描版 PDF 请用截图翻译）、
     状态栏显示原文 / 译文字数
 17. v2.10：整窗翻译（Ctrl+Alt+W，指针下的整个菜单 / 窗口一次翻完）、
     「点 ×」可选最小化到任务栏、点「–」可选收进托盘、卸载时询问是否删除数据库、
     大文件卡死修复（后台读取 / 解析、可取消、线性合并断行、译文框只显示前一部分、
     PDF 防压缩炸弹、文件大小上限）
 18. v2.11：悬停整窗翻译（鼠标停住就整窗翻，同一窗口只翻一次）、文档翻译前预估耗时
     （段数 ≥2000 或预估 ≥60 秒才先问）、实时刷新（每隔几秒重翻同一窗口，译文层点击穿透）
 19. v2.12：诊断信息一键复制（版本号 / 系统 / DPI / OCR / 各热键注册状态）、看门狗
     （界面线程卡死自动记各线程调用栈）、整窗翻译按窗口记忆缓存（同一菜单秒出）、
     整窗结果导出 CSV 对照表、译文层点一块加入术语表
 20. v2.14 打字检测翻译（默认关闭）：在别的软件里打字时也能检测翻译。
     主触发是打字过程中：每打完一个词（空格 / 标点 / 回车分隔）就立即翻译
     刚打完的词/句；正在打的当前词每多打一个字符就用约 250 毫秒防抖跟进，
     同一气泡内实时更新译文；停顿 1 秒只作兜底。Windows 用标准库 ctypes
     低级键盘钩子 WH_KEYBOARD_LL，macOS / Linux 用 pynput。缓冲只放内存，
     密码框 / 终端 / 敏感内容不翻，关闭时立即停钩子、清空缓冲。
 21. v2.15 打字检测翻译改为专业版功能：免费版保留 v2.14 全部其他功能；
     打字检测翻译需激活码（离线验证，见 license.py）或 7 天试用。
     未激活时开关置灰、托盘点一下弹激活框；激活状态只存本机 config.json，
     不随“导出设置”带出去（见 settings_io）。
"""
import base64
import collections
import csv
import hashlib
import itertools
import html
import json
import webbrowser
import math
import os
import platform
import queue
import re
import socket
import sys
import threading
import time
import traceback
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
import glossary
import update_check
import pdf_translate
import clip_image
import settings_io
import pet_catalog
import pet_state
try:                                   # v2.14：桌面小宠物。整个模块出任何问题都只是没有宠物，不影响翻译
    import pet_win
except Exception:                      # pragma: no cover
    pet_win = None
import single_instance
import typing_detect
import text_detect
import translator_tools
import license
import ui_platform
import tempfile
import zlib

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
CLIP_LABEL = "Ctrl+Shift+V"
PYNPUT_CLIP = "<ctrl>+<shift>+v"
WINDOW_LABEL = "Ctrl+Alt+W"           # v2.10 整窗翻译
# 默认全局快捷键（配置键名 → 默认组合；用户可在高级设置里改，保存后重启生效）
DEFAULT_HOTKEYS = {"hotkey_main": "ctrl+alt+t", "hotkey_pointer": "ctrl+alt+d",
                   "hotkey_shot": "ctrl+alt+s", "hotkey_replace": "ctrl+alt+r",
                   "hotkey_clip": "ctrl+shift+v", "hotkey_window": "ctrl+alt+w"}
HOTKEY_KEYS = ("hotkey_main", "hotkey_pointer", "hotkey_shot", "hotkey_replace", "hotkey_clip",
               "hotkey_window")
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


def format_status_counts(src_len, dst_len):
    """状态栏字数（纯函数，v2.8）：\"原文 128 字 · 译文 96 字\"。"""
    return "原文 %d 字 · 译文 %d 字" % (int(src_len), int(dst_len))


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
    """校验配置里的六个快捷键：非法或重复的逐个回落到默认值，绝不抛异常。

    返回新的 dict（只含 HOTKEY_KEYS 里的六个键）。
    重复按主窗口 → 指针取词 → 截图翻译 → 翻译并替换 → 粘贴图片翻译的顺序判定：
    先出现的保留，后出现的回默认。
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
# 打字检测翻译的范围：只分“单词 / 整句”两种（取词范围的整行/整段不适用）
TYPING_SCOPE_NAMES = {"word": "单词", "sentence": "整句"}
TYPING_SCOPE_CODES = {v: k for k, v in TYPING_SCOPE_NAMES.items()}
POPUP_NAMES = {"bubble": "气泡弹窗", "mini": "跟随指针的小窗口", "main": "不弹窗（结果只写入主窗口）"}  # 取词结果怎么显示
POPUP_CODES = {v: k for k, v in POPUP_NAMES.items()}
SHOT_NAMES = {"overlay": "盖在截图上", "main": "显示在主窗口"}                                  # 截图翻译结果怎么显示
SHOT_CODES = {v: k for k, v in SHOT_NAMES.items()}
MINI_SIZE = {"mini_w": (160, 800, 320), "mini_h": (60, 500, 110)}   # 小窗口宽 / 高：(最小, 最大, 默认)
CLOSE_NAMES = {"tray": "隐藏到托盘", "taskbar": "最小化到任务栏", "quit": "直接退出"}      # 点窗口 × 时（v2.10 加「最小化到任务栏」）
CLOSE_CODES = {v: k for k, v in CLOSE_NAMES.items()}
MINIMIZE_NAMES = {"taskbar": "留在任务栏", "tray": "收进托盘"}        # 点窗口 – 最小化时（v2.10）
MINIMIZE_CODES = {v: k for k, v in MINIMIZE_NAMES.items()}
__version__ = "2.15.8"
APP_TITLE = "实时翻译"
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
WATCHDOG_LOG = os.path.join(DATA_DIR, "watchdog.log")   # v2.12：看门狗记界面卡死时的各线程调用栈
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
# v2.15.4：新增内置免费引擎（都无需 Key）：Lingva（Google 镜像，国内常可直连）、MyMemory；
# 「自动」= 按顺序试 Google → 微软 → Lingva → MyMemory，哪个先通用哪个，并记住上次成功的。
ONLINE_ENGINES = ["自动", "Google", "微软", "Lingva", "MyMemory", "DeepL", "百度", "有道"]
# v2.15.4：需要自备 Key 的引擎（Key 在「高级设置 → 翻译 → 需要 Key 的引擎」里填，盘上 DPAPI 加密）
KEY_ENGINES = {"DeepL": ("deepl_key",), "百度": ("baidu_appid", "baidu_key"), "有道": ("youdao_appid", "youdao_key")}
SECRET_KEYS = ("proxy_pass", "deepl_key", "baidu_key", "youdao_key")      # 存盘加密、不导出、不导入
INPUT_TRIGGER_CODES = {v: k for k, v in translator_tools.INPUT_TRIGGERS.items()}
STYLE_CODES = {v: k for k, v in translator_tools.STYLES.items()}
ENGINE_KEY_FIELDS = ("deepl_key", "baidu_appid", "baidu_key", "youdao_appid", "youdao_key")
ENGINES = ONLINE_ENGINES + (["离线"] if offline_engine.runtime_present() else [])
ENGINE_HINTS = {
    "自动": "依次尝试 Google → 微软 → Lingva → MyMemory，优先用上次成功的",
    "Lingva": "Google 翻译的开源镜像，免费无需 Key；国内常可直连",
    "MyMemory": "免费无需 Key，每天约 5000 字额度；单次最多 500 字",
    "DeepL": "需要 DeepL API Key（免费版每月 50 万字）",
    "百度": "需要百度翻译开放平台 APPID + 密钥（标准版每月 5 万字免费）",
    "有道": "需要有道智云应用 ID + 应用密钥",
}
DEFAULTS = {
    "pet_mode": "minimized", "pet_id": "cat", "pet_bubble": True, "cute_theme": False, "apple_theme": True,
    "sl": "auto", "tl": "zh-CN", "top": True, "watch": False, "smart": True,
    "bilingual": False, "reflow": True, "show_src": True, "geometry": "480x760",
    "engine": "Google", "auto_offline": True,
    "pointer": True, "pointer_scope": "word", "pack_mirror": "",
    "hover": True, "hover_ms": 800, "hover_need_ctrl": False, "grab_spinner": True, "input_translate": False, "input_trigger": "space3", "translate_style": "default", "compare_engines": [], "settings_tab": "general", "settings_geometry": "",
    # v2.14 打字检测翻译：默认全部关（typing 开关、停顿毫秒、范围）
    "typing": False, "typing_pause_ms": 1000, "typing_scope": "word",
    # v2.15 授权：打字检测翻译是专业版功能。license_* 只存本机 config.json，
    # 照 proxy_pass 的模式不进 settings_io 白名单、不随设置导出/导入。
    "license_key": "", "license_status": "free", "license_trial_start": 0,
    "license_machines": [],
    "close_action": "taskbar", "tray_tip": True, "minimize_action": "taskbar",   # v2.13：点 × 默认最小化到任务栏
    "hover_window": False, "live_interval": 5,      # v2.11：悬停整窗翻译、实时刷新间隔（秒）
    # L-05：最短 5 秒——2~3 秒一轮高频 OCR 会把窗口卡住、CPU 占满。
    "history_on": True, "history_max": 2000, "history_reuse": False,
    # H-01：剪贴板监听开启时的外发提醒是否已显示过（只提醒一次）。
    "clip_warn_shown": False,
    "popup_mode": "bubble", "mini_w": 320, "mini_h": 110, "shot_mode": "overlay",
    # v2.5：朗读语速（-10~10，默认 0）、自动复制译文（默认关）、自定义全局快捷键
    "tts_rate": 0, "auto_copy": False,
    "hotkey_main": "ctrl+alt+t", "hotkey_pointer": "ctrl+alt+d", "hotkey_shot": "ctrl+alt+s",
    "hotkey_replace": "ctrl+alt+r", "hotkey_clip": "ctrl+shift+v",
    "hotkey_window": "ctrl+alt+w",      # v2.10：整窗翻译
    # v2.6：界面字号（10~18，默认 11）
    "font_size": 11,
    # v2.7：深色外观（默认浅色）、术语表（默认空）、每天自动检查更新（默认开）、上次检查日期
    "dark_mode": False, "glossary": [], "update_auto": True, "update_last_check": "",
    # v2.9：在线翻译引擎代理（默认不用；勾上才走代理。密码只存本机，设置导出不带出）
    "proxy_enabled": False, "proxy_host": "", "proxy_port": 0,
    "proxy_user": "", "proxy_pass": "",
    # v2.15.4：需要 Key 的引擎（DeepL / 百度 / 有道）。密钥存盘时 DPAPI 加密，不随设置导出 / 导入。
    "deepl_key": "", "baidu_appid": "", "baidu_key": "", "youdao_appid": "", "youdao_key": "",
    # v2.9：朗读语音（空 = 系统默认语音；下拉框里选的是 Windows 已安装语音的名字）
    "tts_voice": "",
}


def _read_capped(resp, limit):
    """读 HTTP 响应并限流：真实响应支持 read(n)；某些桩对象只定义了无参 read()，
    遇 TypeError 时退回无参读再截断（上限照样守住）。"""
    try:
        data = resp.read(limit)
    except TypeError:
        data = resp.read()
    return data[:limit]


def _rotate_log(path, max_bytes=5 * 1024 * 1024):
    """M-06：日志超过 max_bytes 就轮转（改名 .1，只留一份旧的），
    防止 crash.log / watchdog 日志无限增长。"""
    try:
        if os.path.getsize(path) > max_bytes:
            bak = path + ".1"
            try:
                os.remove(bak)
            except OSError:
                pass
            os.replace(path, bak)
    except OSError:
        pass


# H-01：剪贴板内容像不像敏感信息 —— 是就不要自动翻译、不要存历史、不要放进输入框。
# v2.15.5：规则搬到 text_detect.py（和打字检测共用一份），新增银行卡号（Luhn 校验）、JWT /
# AWS / GitHub / Slack / Google 密钥、Bearer 令牌、私钥、带密码的连接串、"验证码是 123456" 等。
def is_sensitive_clip(text):
    """H-01：剪贴板内容像不像敏感信息。纯函数，便于测试。"""
    return text_detect.is_sensitive(text)


def _dpapi_protect(plaintext):
    """M-04：Windows DPAPI 加密（本用户本机才能解开），返回 "dpapi:<base64>"。
    非 Windows / 加密失败返回 None（调用方回落明文）。"""
    if not sys.platform.startswith("win") or not plaintext:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        class _DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

        data = plaintext.encode("utf-8")
        in_blob = _DATA_BLOB(len(data), (ctypes.c_ubyte * len(data)).from_buffer_copy(data))
        out_blob = _DATA_BLOB()
        if not crypt32.CryptProtectData(ctypes.byref(in_blob), None, None, None, None,
                                       0x1, ctypes.byref(out_blob)):  # CRYPTPROTECT_UI_FORBIDDEN
            return None
        try:
            enc = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)
        return "dpapi:" + base64.b64encode(enc).decode("ascii")
    except Exception:      # noqa: BLE001
        return None


def _dpapi_unprotect(stored):
    """M-04：解开 _dpapi_protect 加密的值。不是 dpapi: 前缀的旧明文原样返回
    （兼容老版本 config.json）；解不开返回 None。"""
    if not isinstance(stored, str) or not stored:
        return stored
    if not stored.startswith("dpapi:"):
        return stored  # 旧版明文：兼容，存盘时再加密
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes
        from ctypes import wintypes
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        class _DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

        raw = base64.b64decode(stored[6:])
        in_blob = _DATA_BLOB(len(raw), (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw))
        out_blob = _DATA_BLOB()
        if not crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None,
                                         0x1, ctypes.byref(out_blob)):  # CRYPTPROTECT_UI_FORBIDDEN
            return None
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData).decode("utf-8")
        finally:
            kernel32.LocalFree(out_blob.pbData)
    except Exception:      # noqa: BLE001
        return None


def _foreground_is_password_field_win():
    """M-03：当前前台窗口的焦点控件是不是密码框（ES_PASSWORD 样式）。
    是就返回 True —— 翻译并替换 / 复制选中时不该碰密码框里的内容。
    非 Windows 返回 False。"""
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32

        class _GUITHREADINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD),
                        ("flags", wintypes.DWORD),
                        ("hwndActive", wintypes.HWND),
                        ("hwndFocus", wintypes.HWND),
                        ("hwndCapture", wintypes.HWND),
                        ("hwndMenuOwner", wintypes.HWND),
                        ("hwndMoveSize", wintypes.HWND),
                        ("hwndCaret", wintypes.HWND),
                        ("rcCaret", wintypes.RECT)]

        user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(_GUITHREADINFO)]
        user32.GetGUIThreadInfo.restype = wintypes.BOOL
        info = _GUITHREADINFO()
        info.cbSize = ctypes.sizeof(_GUITHREADINFO)
        if not user32.GetGUIThreadInfo(0, ctypes.byref(info)):
            return False
        hwnd = info.hwndFocus
        if not hwnd:
            return False
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = wintypes.LONG
        style = user32.GetWindowLongW(hwnd, -16)  # GWL_STYLE
        return bool(style & 0x20)  # ES_PASSWORD
    except Exception:      # noqa: BLE001
        return False


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


# ---------------------------------------------------------------- 外观主题（v2.7 深色外观，可选，默认浅色）
# 浅色是今天的样子（不改任何默认值）；深色只在用户勾选后才用。
# 对比度：正文 #f5f5f7 / #2c2c2e ≈ 13.5:1，灰字 #a1a1a6 / #2c2c2e ≈ 5.6:1，
# 都过了 WCAG AA 的 4.5:1（test_dark_mode.py 里会算一遍）。
THEME_LIGHT = {"bg": "#f0f0f0", "fg": "#000000", "gray": "#5b6676",
               "text_bg": "#ffffff", "text_fg": "#000000",
               "bubble_bg": "#fffdf6", "bubble_fg": "#111111",
               "bubble_gray": "#6b7380", "bubble_foot": "#9aa3b2",
               "border": "#c9ced6", "error": "#b42318"}
THEME_DARK = {"bg": "#1c1c1e", "fg": "#f5f5f7", "gray": "#a1a1a6",
              "text_bg": "#2c2c2e", "text_fg": "#f5f5f7",
              "bubble_bg": "#2c2c2e", "bubble_fg": "#f5f5f7",
              "bubble_gray": "#a1a1a6", "bubble_foot": "#8e8e93",
              "border": "#48484a", "error": "#ff6961"}


# v2.14 萌系配色（粉彩）：只在勾选后用；深色优先。对比度同样过 WCAG AA（test_pet.py 里会算）。
THEME_CUTE = {"bg": "#f6f3fb", "fg": "#3d303b", "gray": "#6b5e69",
              "text_bg": "#ffffff", "text_fg": "#3d303b",
              "bubble_bg": "#fff3ea", "bubble_fg": "#3d303b",
              "bubble_gray": "#6f5f6c", "bubble_foot": "#a8929f",
              "border": "#e3d9ee", "error": "#c2364f"}
_CUTE = False


def set_cute(on):
    global _CUTE
    _CUTE = bool(on)


def theme_colors(dark):
    if dark:
        return dict(THEME_DARK)
    return dict(THEME_CUTE if _CUTE else THEME_LIGHT)


def _lum(hexcolor):
    hexcolor = hexcolor.lstrip("#")
    r, g, b = (int(hexcolor[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = f(r), f(g), f(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg, bg):
    """两色的 WCAG 对比度（>= 4.5:1 才算正文可读）。"""
    l1, l2 = sorted((_lum(fg), _lum(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


# ---------------------------------------------------------------- 翻译核心
CACHE = collections.OrderedDict()
CACHE_MAX = 800
_cache_lock = threading.Lock()


def _is_rate_limit(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (429, 503)
    s = str(exc).lower()
    return "429" in s or "too many requests" in s


# ---- 在线翻译引擎的代理（v2.9.0） ----
_PROXY = {"url": None}


def proxy_url(cfg):
    """按配置拼出代理 URL；没启用 / 没配主机端口 / 端口非法 → None（不走代理）。

    纯函数，便于测试。账号密码做 URL 编码后拼进 URL；密码只存本机
    config.json，设置导出时不带出（见 settings_io 的说明）。
    """
    cfg = cfg or {}
    if not cfg.get("proxy_enabled"):
        return None
    host = str(cfg.get("proxy_host") or "").strip()
    if not host:
        return None
    try:
        port = int(cfg.get("proxy_port"))
    except Exception:
        return None
    if not 1 <= port <= 65535:
        return None
    auth = ""
    user = str(cfg.get("proxy_user") or "").strip()
    if user:
        auth = urllib.parse.quote(user, safe="")
        pw = str(cfg.get("proxy_pass") or "")
        if pw:
            auth += ":" + urllib.parse.quote(pw, safe="")
        auth += "@"
    return "http://%s%s:%d" % (auth, host, port)


def set_proxy_url(url):
    """设置在线引擎用的代理（None / 空串 = 不用代理）。"""
    _PROXY["url"] = url or None


def get_proxy_url():
    return _PROXY["url"]


def _urlopen(req, timeout=None):
    """在线引擎的统一出口：配了代理就走代理 opener，没配就和原来一样走 urlopen。

    只影响 Google / 微软在线翻译引擎；检查更新、语言包下载、网络检查
    不走这里（不在本次代理范围）。
    """
    url = _PROXY["url"]
    if not url:
        return urllib.request.urlopen(req, timeout=timeout)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": url, "https": url}))
    return opener.open(req, timeout=timeout)


def g_translate_full(text, sl, tl, attempts=3, timeout=12, deadline=None):
    """Google 翻译（带原始 JSON）：返回 (译文, 检测到的源语言, 原始响应)。

    原始响应存在 _LAST_GOOGLE 里，供词典区解析 data[1] 的词典与
    data[0] 的 transliteration（拼音/读音）用；只在 Google 引擎、
    单个词或短词组时才读它。

    deadline（B-4）：单调时钟上的总截止点；None 时先看调用链上 _online
    在本线程里设好的共享预算（_tl.online_deadline），没有再按
    ONLINE_TOTAL_TIMEOUT 现算。每次尝试的 socket 超时取 min(timeout,
    剩余预算），预算耗尽直接抛 TimeoutError（do_translate 会把它当连通性
    故障：进 30 秒熔断 + 离线回退）。
    """
    if deadline is None:
        deadline = getattr(_tl, "online_deadline", None) or (time.monotonic() + ONLINE_TOTAL_TIMEOUT)
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
        if time.monotonic() >= deadline:
            raise TimeoutError("在线翻译总耗时超过 %.0f 秒上限，已停止等待" % ONLINE_TOTAL_TIMEOUT)
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            # 单次尝试也不许超过剩余预算
            attempt_timeout = min(timeout, max(0.05, deadline - time.monotonic()))
            with _urlopen(req, timeout=attempt_timeout) as r:
                # 稳定性：响应限流 4 MB —— 免费端点偶尔会返回超大内容，不全读进内存。
                data = json.loads(_read_capped(r, 4 << 20).decode("utf-8"))
            out = "".join((seg[0] or "") for seg in (data[0] or []) if seg)
            det = data[2] if len(data) > 2 and data[2] else sl
            _LAST_GOOGLE.update(text=text, sl=sl, tl=tl, data=data)
            return out, det, data
        except Exception as e:
            last = e
            if isinstance(e, TimeoutError) and time.monotonic() >= deadline:
                raise TimeoutError("在线翻译总耗时超过 %.0f 秒上限，已停止等待" % ONLINE_TOTAL_TIMEOUT)
            if attempt + 1 >= attempts:
                break
            if _is_rate_limit(e):
                time.sleep(min(1.2 * (attempt + 1), max(0.0, deadline - time.monotonic())))
            else:
                time.sleep(min(0.4, max(0.0, deadline - time.monotonic())))
    raise last


_LAST_GOOGLE = {"text": None, "sl": None, "tl": None, "data": None}


def g_translate(text, sl, tl, attempts=3, timeout=12, deadline=None):
    out, det, _data = g_translate_full(text, sl, tl, attempts, timeout, deadline)
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
    """输入是不是值得查词典的单个词或短词组：去空白后 <=20 字符、1~3 个词、无换行、
    中间没有句子标点；网址 / 数字 / 敏感内容不查；汉字连写最多 6 个字。"""
    return text_detect.is_dict_candidate(text)


def is_word_entry(src):
    """一条历史记录的原文是不是单词：单个词、无空格、1~30 字符、含字母，
    不是网址 / 邮箱 / 路径 / 敏感内容（生词本用）。"""
    return text_detect.is_word_entry(src)


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


class HoverCache:
    """悬停取词的 OCR 结果缓存（纯逻辑，便于测试）。

    指针静止时悬停每 100ms 检查一次，但 OCR 不该每次都重跑：
    同一个范围 + 同一个 8px 位置格 + 2 秒内，直接用上次的 OCR 结果。
    指针移出格子、换了范围、超过 2 秒都算失效。缓存的是 OCR 认出的
    词（也可能是 None——该位置没认出字，2 秒内也不再重跑）。
    """
    _MISS = object()

    def __init__(self, ttl=2.0, bucket=8):
        self.ttl, self.bucket = ttl, bucket
        self._store = {}

    def _key(self, pos, scope):
        return (scope, int(pos[0]) // self.bucket, int(pos[1]) // self.bucket)

    def get(self, pos, scope, now=None):
        now = time.time() if now is None else now
        ent = self._store.get(self._key(pos, scope))
        if ent is None or now - ent[0] > self.ttl:
            return self._MISS, None
        return True, ent[1]

    def put(self, pos, scope, value, now=None):
        now = time.time() if now is None else now
        self._store[self._key(pos, scope)] = (now, value)

    def clear(self):
        self._store.clear()


# ---------------------------------------------------------------- v2.12 诊断信息
_HOTKEY_CN = {"hotkey_main": "翻译选中的文字", "hotkey_pointer": "指针取词",
              "hotkey_shot": "截图翻译", "hotkey_replace": "翻译并替换原文",
              "hotkey_clip": "粘贴图片翻译", "hotkey_window": "整窗翻译"}


def os_version_text():
    """操作系统版本（一行纯文本；任何平台都不抛异常）。"""
    try:
        if IS_WIN:
            return "Windows %s %s" % (platform.release(), platform.version())
        return "%s %s" % (platform.system(), platform.release())
    except Exception:
        return "不可用"


def dpi_scale_text():
    """主显示器 DPI 缩放（如 "150%"；非 Windows / 取不到时写"不可用"，不崩）。"""
    if not IS_WIN:
        return "不可用（非 Windows）"
    try:
        import ctypes
        try:
            dpi = ctypes.windll.user32.GetDpiForSystem()
        except Exception:
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)     # LOGPIXELSX
            ctypes.windll.user32.ReleaseDC(0, hdc)
        if dpi and dpi > 0:
            return "%d%%" % round(dpi * 100 / 96)
    except Exception:
        pass
    return "不可用"


def build_diag_text(info):
    """把诊断信息 dict 拼成可粘贴的纯文本。

    info 的键：version / python / os / dpi / ocr / hotkeys（[(中文名, 组合键, 状态)]）。
    缺哪个键就写"不可用"，从不抛异常——诊断本身不能成为新的崩溃源。
    """
    info = info or {}
    hotkeys = info.get("hotkeys") or []
    lines = ["实时翻译 诊断信息",
             "应用版本：实时翻译 v%s" % (info.get("version") or "不可用"),
             "Python：%s" % (info.get("python") or "不可用"),
             "操作系统：%s" % (info.get("os") or "不可用"),
             "DPI 缩放：%s" % (info.get("dpi") or "不可用"),
             "OCR：%s" % (info.get("ocr") or "不可用"),
             "热键："]
    if not hotkeys:
        lines.append("  （无热键状态）")
    for item in hotkeys:
        try:
            name, spec, status = item[0], item[1], item[2]
        except Exception:
            continue
        lines.append("  %s %s：%s" % (name, spec, status))
    return "\n".join(lines)


def collect_diag_info(app):
    """从运行中的 App 收集诊断信息（每项探测都单独 try，缺失写"不可用"）。

    热键状态来自 _start_hotkey 启动时记下的注册结果（见 _hotkey_status）：
    已注册 / 未注册（被占用）/ 不可用（还没启动或该平台不支持）。
    """
    try:
        ocr = "可用" if ocr_win.ocr_available() else "不可用（未找到 PowerShell / OCR 组件）"
    except Exception:
        ocr = "不可用"
    status = getattr(app, "_hotkey_status", None) or {}
    hotkeys = []
    cfg = getattr(app, "cfg", {}) or {}
    for key in HOTKEY_KEYS:
        spec = cfg.get(key, DEFAULT_HOTKEYS[key])
        label = hotkey_label(spec)
        if key not in status:
            st = "不可用"
        elif status[key]:
            st = "已注册"
        else:
            st = "未注册（被占用）"
        hotkeys.append((_HOTKEY_CN.get(key, key), label, st))
    return {"version": __version__,
            "python": sys.version.split()[0] if sys.version else "不可用",
            "os": os_version_text(),
            "dpi": dpi_scale_text(),
            "ocr": ocr,
            "hotkeys": hotkeys}


# ---------------------------------------------------------------- v2.12 看门狗
class Watchdog:
    """界面线程卡死自动记调用栈（crash.log 只记异常，这里补"没崩但卡住"的情况）。

    界面线程（Tk 主循环）每轮 _poll 都调 beat() 更新心跳；本线程每 interval 秒
    检查一次，心跳超过 threshold 秒没更新就判定卡死，用 sys._current_frames()
    把当时所有线程的调用栈写进 watchdog.log。一次卡死只记一次，恢复后复位，
    卡死期间不刷屏。开销：每秒一次时间比较 + 一次浮点赋值，可忽略。
    beat()/check_once() 都可单独测，不依赖 Tk。
    """

    def __init__(self, log_path, threshold=5.0, interval=1.0):
        self.log_path = log_path
        self.threshold = threshold
        self.interval = interval
        self._last_beat = time.time()
        self._reported = False
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def beat(self):
        with self._lock:
            self._last_beat = time.time()

    def start(self):
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="watchdog")
        self._thread.start()

    def stop(self):
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=2.0)
        self._thread = None

    def _loop(self):
        while not self._stop.wait(self.interval):
            try:
                self.check_once()
            except Exception:
                pass

    def check_once(self, now=None):
        now = time.time() if now is None else now
        with self._lock:
            last = self._last_beat
        if now - last > self.threshold:
            if not self._reported:
                self._reported = True
                self._dump(now - last)
        else:
            self._reported = False

    def _dump(self, stalled_for):
        try:
            frames = sys._current_frames()
            head = ("[%s] WATCHDOG v%s 界面线程超过 %.1f 秒无响应，当前各线程调用栈：\n"
                    % (time.strftime("%Y-%m-%d %H:%M:%S"), __version__, stalled_for))
            parts = [head]
            for tid, frame in sorted(frames.items()):
                th = None
                for t in threading.enumerate():
                    if t.ident == tid:
                        th = t
                        break
                name = th.name if th is not None else "?"
                parts.append("线程 %s (id=%s):\n" % (name, tid))
                parts.extend(traceback.format_stack(frame))
                parts.append("\n")
            parent = os.path.dirname(self.log_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            _rotate_log(self.log_path)     # M-06：超过 5 MB 先轮转，不无限增长
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write("".join(parts) + "\n")
        except Exception:
            pass


# ---------------------------------------------------------------- v2.12 整窗翻译按窗口记忆缓存
class WindowShotCache:
    """整窗翻译的 OCR + 译文缓存（只放内存，不落盘；上限 50 条 LRU）。

    键 = 窗口范围 + 整图 BGRA 字节的 SHA256（取前 32 位 hex）：工业软件界面
    文字基本固定，同一菜单每次截到的像素是字节级相同的，精确哈希命中可靠；
    刻意不用下采样/模糊哈希——长得像的两个菜单绝不能互相串结果。
    命中时跳过 OCR 与翻译、直接出上次的结果；像素或范围变了就重新识别。
    """

    def __init__(self, max_items=50):
        self.max_items = max_items
        self._store = collections.OrderedDict()

    @staticmethod
    def key(rect, bgra):
        blob = (bgra or b"") + ("%d,%d,%d,%d" % (rect[0], rect[1], rect[2], rect[3])).encode()
        return hashlib.sha256(blob).hexdigest()[:32]

    def get(self, rect, bgra):
        k = self.key(rect, bgra)
        msg = self._store.get(k)
        if msg is None:
            return None
        self._store.move_to_end(k)
        return msg

    def put(self, rect, bgra, msg):
        k = self.key(rect, bgra)
        self._store[k] = msg
        self._store.move_to_end(k)
        while len(self._store) > self.max_items:
            self._store.popitem(last=False)

    def __len__(self):
        return len(self._store)


def export_window_pairs_csv(pairs, path):
    """把整窗翻译的 (原文, 译文) 写成 CSV 对照表：UTF-8 带 BOM（Excel 直接打开
    不乱码），列头 原文/译文。含逗号 / 换行 / 中文的字段由 csv 模块自动加引号，
    不会断行。返回写出的行数（不含列头）。"""
    rows = [[str(s or ""), str(d or "")] for s, d in (pairs or [])]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["原文", "译文"])
        w.writerows(rows)
    return len(rows)


def overlay_block_at(boxes, x, y):
    """译文层上 (x, y) 点落在第几块译文上（没有返回 None）。"""
    for i, b in enumerate(boxes or []):
        try:
            if b["x"] <= x < b["x"] + b["w"] and b["y"] <= y < b["y"] + b["h"]:
                return i
        except Exception:
            continue
    return None


_ms_token = {"value": "", "ts": 0.0}
_ms_lock = threading.Lock()
MS_AUTH = "https://edge.microsoft.com/translate/auth"
MS_API = "https://api-edge.cognitive.microsofttranslator.com/translate"
_UA_EDGE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0"
)
# Edge token 格式校验已按用户决定去掉（2026-11-21）：拿到什么 token 就用
# 什么，不再因格式拒绝；代理返回拦截页内容时，微软端点会报 401/403，走正常
# 重试/报错。只保留空值这一事实性检查（什么都没拿到就没法调接口）。
def _ms_get_token(force=False, timeout=10):
    """Edge 翻译端点需要一个免费的短期 token（约 10 分钟有效），缓存复用。
    timeout（B-4）：取 token 的单次上限，调用方会按在线总预算再压小。"""
    with _ms_lock:
        if not force and _ms_token["value"] and time.time() - _ms_token["ts"] < 480:
            return _ms_token["value"]
        req = urllib.request.Request(MS_AUTH, headers={"User-Agent": _UA_EDGE})
        try:
            with _urlopen(req, timeout=timeout) as r:
                # 稳定性：token 响应限流 64KB —— 正常 token 只有几百字节。
                tok = _read_capped(r, 64 << 10).decode("utf-8").strip()
        except urllib.error.HTTPError as e:
            # 微软免费取 token 的接口已下线（直连也返回 404），不是代理拦截；
            # 下线是既定事实，重试也不会好，直接报明，不再含糊成“疑似被拦截”。
            if e.code == 404:
                raise ValueError("微软免费取 token 的接口已返回 404，该接口已下线，不是代理拦截；"
                                 "微软引擎暂时不可用，请改用 Google 或离线")
            raise
        if not tok:
            raise ValueError("Edge token 为空，未拿到 token")
        _ms_token.update(value=tok, ts=time.time())
        return tok


def ms_translate(text, sl, tl, attempts=3, timeout=15, deadline=None):
    """微软 Edge 免费翻译端点（无需自备 Key，token 自动获取并缓存）。

    deadline（B-4）：与 g_translate_full 同款总预算；None 时先看调用链上
    _online 在本线程里设好的共享预算，没有再按 ONLINE_TOTAL_TIMEOUT 现算。
    取 token 与每次 POST 都不许超过剩余预算。
    """
    if deadline is None:
        deadline = getattr(_tl, "online_deadline", None) or (time.monotonic() + ONLINE_TOTAL_TIMEOUT)
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
        if time.monotonic() >= deadline:
            raise TimeoutError("在线翻译总耗时超过 %.0f 秒上限，已停止等待" % ONLINE_TOTAL_TIMEOUT)
        try:
            # 取 token 也受总预算约束（微软接口已下线时这里 404 会立刻抛，不等）
            token_timeout = min(10, max(0.05, deadline - time.monotonic()))
            headers = {
                "Content-Type": "application/json; charset=UTF-8",
                "User-Agent": _UA_EDGE,
                "Authorization": "Bearer " + _ms_get_token(
                    force=attempt > 0 and _is_auth_error(last), timeout=token_timeout),
            }
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            attempt_timeout = min(timeout, max(0.05, deadline - time.monotonic()))
            with _urlopen(req, timeout=attempt_timeout) as r:
                # 稳定性：响应限流 4 MB —— 正常翻译响应只有几 KB。
                data = json.loads(_read_capped(r, 4 << 20).decode("utf-8"))
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
            # 微软接口已下线是既定事实，重试也不会好，直接报，不白等三轮。
            if "接口已下线" in str(e):
                raise
            if isinstance(e, TimeoutError) and time.monotonic() >= deadline:
                raise TimeoutError("在线翻译总耗时超过 %.0f 秒上限，已停止等待" % ONLINE_TOTAL_TIMEOUT)
            if attempt + 1 < attempts:
                time.sleep(min(0.6 * (attempt + 1), max(0.0, deadline - time.monotonic())))
    raise last


LINGVA_HOSTS = ["https://lingva.ml", "https://lingva.lunar.icu", "https://translate.plausibility.cloud"]
MYMEMORY_API = "https://api.mymemory.translated.net/get"


def _budget(deadline, timeout):
    if deadline is None:
        deadline = getattr(_tl, "online_deadline", None) or (time.monotonic() + ONLINE_TOTAL_TIMEOUT)
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError("在线翻译总耗时超过 %.0f 秒上限，已停止等待" % ONLINE_TOTAL_TIMEOUT)
    return deadline, min(timeout, max(0.05, left))


def lingva_code(code):
    """Lingva 用 Google 的语言代码；繁体 zh_HANT、简体 zh。"""
    c = (code or "auto")
    if c == "zh-CN":
        return "zh"
    if c == "zh-TW":
        return "zh_HANT"
    return c


def lingva_translate(text, sl, tl, timeout=8, deadline=None):
    """Lingva（Google 翻译开源前端）：GET /api/v1/{sl}/{tl}/{text}。多个公共实例依次试。"""
    last = None
    for host in LINGVA_HOSTS:
        deadline, t = _budget(deadline, timeout)
        url = "%s/api/v1/%s/%s/%s" % (host, urllib.parse.quote(lingva_code(sl)),
                                      urllib.parse.quote(lingva_code(tl)), urllib.parse.quote(text, safe=""))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA_EDGE, "Accept": "application/json"})
            with _urlopen(req, timeout=t) as r:
                data = json.loads(_read_capped(r, 2 << 20).decode("utf-8"))
            out = (data.get("translation") or "") if isinstance(data, dict) else ""
            if not out:
                raise RuntimeError("Lingva 返回为空")
            det = ((data.get("info") or {}).get("detectedSource") or sl) if isinstance(data, dict) else sl
            det = {"zh": "zh-CN", "zh_HANT": "zh-TW"}.get(det, det)
            return out, det
        except Exception as e:      # noqa: BLE001
            last = e
            if isinstance(e, TimeoutError) and "总耗时" in str(e):
                raise
    raise last or RuntimeError("Lingva 不可用")


def mymemory_translate(text, sl, tl, timeout=8, deadline=None):
    """MyMemory 免费接口：GET ?q=&langpair=en|zh-CN。不支持自动检测，auto 时按文字脚本猜。
    单次最多 500 字节左右，超长交给上层 split_long（这里再按 450 字切一次保险）。"""
    src = text_detect.detect_lang(text).lang if sl == "auto" else sl      # 繁体识别为 zh-TW
    src = {"zh": "zh-CN"}.get(src, src)
    if len(text) > 450:
        parts = [text[i:i + 450] for i in range(0, len(text), 450)]
        outs = [mymemory_translate(p, src, tl, timeout, deadline)[0] for p in parts]
        return _join(outs, tl), src
    deadline, t = _budget(deadline, timeout)
    url = "%s?q=%s&langpair=%s|%s" % (MYMEMORY_API, urllib.parse.quote(text),
                                      urllib.parse.quote(src), urllib.parse.quote(tl))
    req = urllib.request.Request(url, headers={"User-Agent": _UA_EDGE})
    with _urlopen(req, timeout=t) as r:
        data = json.loads(_read_capped(r, 2 << 20).decode("utf-8"))
    status = int(data.get("responseStatus") or 200) if isinstance(data, dict) else 500
    out = ((data.get("responseData") or {}).get("translatedText") or "") if isinstance(data, dict) else ""
    if status == 429 or "MYMEMORY WARNING" in out.upper():
        raise urllib.error.HTTPError(url, 429, "MyMemory 今日免费额度已用完", None, None)
    if status != 200 or not out:
        raise RuntimeError("MyMemory 返回错误（%s）：%s" % (status, str(data.get("responseDetails", ""))[:80]))
    return html.unescape(out), src


# ---------------------------------------------------------------- v2.15.4 需要 Key 的引擎
_ENGINE_KEYS = {k: "" for k in ENGINE_KEY_FIELDS}


class EngineKeyError(RuntimeError):
    """没填 Key / Key 无效 / 额度用完 —— 不是网络问题，不进熔断、不该被当成断网。"""


def set_engine_keys(cfg):
    for k in ENGINE_KEY_FIELDS:
        _ENGINE_KEYS[k] = str((cfg or {}).get(k) or "").strip()
    _ENGINE_KEYS["_style"] = str((cfg or {}).get("translate_style") or "default")


def engine_configured(name):
    return all(_ENGINE_KEYS.get(k) for k in KEY_ENGINES.get(name, ()))


def _need_keys(name):
    if not engine_configured(name):
        raise EngineKeyError("「%s」引擎还没填 Key：请到「高级设置 → 翻译 → 需要 Key 的引擎」里填写。" % name)


def deepl_lang(code, target=False):
    c = (code or "auto")
    if c == "auto":
        return None
    if c == "zh-CN":
        return "ZH-HANS" if target else "ZH"
    if c == "zh-TW":
        return "ZH-HANT" if target else "ZH"
    if target and c == "en":
        return "EN-US"
    if target and c == "pt":
        return "PT-BR"
    return base(c).upper()


def deepl_translate(text, sl, tl, timeout=10, deadline=None):
    _need_keys("DeepL")
    key = _ENGINE_KEYS["deepl_key"]
    host = "https://api-free.deepl.com" if key.endswith(":fx") else "https://api.deepl.com"
    deadline, t = _budget(deadline, timeout)
    form = {"text": text, "target_lang": deepl_lang(tl, True)}
    fm = translator_tools.deepl_formality(_ENGINE_KEYS.get("_style", "default"))
    if fm:
        form["formality"] = fm          # v2.15.4 译文风格：只有部分目标语言支持，不支持时 DeepL 忽略 prefer_*
    src = deepl_lang(sl)
    if src:
        form["source_lang"] = src
    req = urllib.request.Request(host + "/v2/translate", data=urllib.parse.urlencode(form).encode("utf-8"),
                                 headers={"Authorization": "DeepL-Auth-Key " + key,
                                          "Content-Type": "application/x-www-form-urlencoded",
                                          "User-Agent": "RealtimeTranslate/" + __version__})
    try:
        with _urlopen(req, timeout=t) as r:
            data = json.loads(_read_capped(r, 2 << 20).decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise EngineKeyError("DeepL Key 无效（HTTP %d）：请检查 Key 是否填对；免费版 Key 以 :fx 结尾。" % e.code)
        if e.code == 456:
            raise EngineKeyError("DeepL 本月额度已用完（HTTP 456）。")
        raise
    tr = (data.get("translations") or [{}])[0] if isinstance(data, dict) else {}
    out = tr.get("text") or ""
    if not out:
        raise RuntimeError("DeepL 返回为空")
    det = (tr.get("detected_source_language") or sl or "auto").lower()
    det = {"zh": "zh-CN"}.get(det, det)
    return out, det


BAIDU_CODE = {"zh-CN": "zh", "zh-TW": "cht", "ja": "jp", "ko": "kor", "fr": "fra", "es": "spa",
              "ar": "ara", "vi": "vie", "sv": "swe", "auto": "auto"}
BAIDU_BACK = {v: k for k, v in BAIDU_CODE.items()}
BAIDU_ERRORS = {"52001": "请求超时", "52002": "百度服务出错", "52003": "APPID 未授权或填错",
                "54000": "参数为空", "54001": "签名错误：密钥填错了", "54003": "请求太频繁（标准版每秒 1 次）",
                "54004": "账户余额不足", "54005": "长文本请求太频繁", "58000": "IP 不在白名单里",
                "58001": "不支持这个语种", "58002": "服务已关闭，请到百度翻译开放平台开通", "90107": "认证未通过或未生效"}


def baidu_sign(appid, q, salt, key):
    """百度翻译签名（纯函数）：md5(appid + q + salt + 密钥)。"""
    return hashlib.md5((appid + q + str(salt) + key).encode("utf-8")).hexdigest()


def baidu_translate(text, sl, tl, timeout=10, deadline=None):
    _need_keys("百度")
    appid, key = _ENGINE_KEYS["baidu_appid"], _ENGINE_KEYS["baidu_key"]
    deadline, t = _budget(deadline, timeout)
    salt = str(int(time.time() * 1000))
    form = {"q": text, "from": BAIDU_CODE.get(sl, base(sl)), "to": BAIDU_CODE.get(tl, base(tl)),
            "appid": appid, "salt": salt, "sign": baidu_sign(appid, text, salt, key)}
    req = urllib.request.Request("https://fanyi-api.baidu.com/api/trans/vip/translate",
                                 data=urllib.parse.urlencode(form).encode("utf-8"),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with _urlopen(req, timeout=t) as r:
        data = json.loads(_read_capped(r, 2 << 20).decode("utf-8"))
    code = str(data.get("error_code") or "") if isinstance(data, dict) else "x"
    if code and code != "52000":
        msg = "百度翻译：%s（错误码 %s）" % (BAIDU_ERRORS.get(code, data.get("error_msg", "未知错误")), code)
        if code == "54003":
            raise urllib.error.HTTPError("baidu", 429, msg, None, None)
        if code in ("52001", "52002"):
            raise RuntimeError(msg)
        raise EngineKeyError(msg)
    out = "\n".join(x.get("dst", "") for x in data.get("trans_result") or [])
    if not out:
        raise RuntimeError("百度翻译返回为空")
    det = data.get("from") or sl
    return out, BAIDU_BACK.get(det, det)


YOUDAO_CODE = {"zh-CN": "zh-CHS", "zh-TW": "zh-CHT", "auto": "auto"}
YOUDAO_ERRORS = {"101": "缺少必填参数", "102": "不支持的语言类型", "103": "翻译文本过长", "108": "应用 ID 无效",
                 "110": "没有绑定「文本翻译」服务", "111": "开发者账号无效", "113": "翻译内容为空",
                 "202": "签名错误：应用密钥填错了", "206": "时间戳无效（检查电脑时间）", "401": "账户已欠费",
                 "411": "访问太频繁", "412": "长请求太频繁"}


def youdao_input(q):
    """有道签名用的 input（纯函数）：长度 ≤ 20 原样；否则 前10字 + 长度 + 后10字。"""
    return q if len(q) <= 20 else q[:10] + str(len(q)) + q[-10:]


def youdao_sign(appid, q, salt, curtime, secret):
    return hashlib.sha256((appid + youdao_input(q) + salt + curtime + secret).encode("utf-8")).hexdigest()


def youdao_translate(text, sl, tl, timeout=10, deadline=None):
    _need_keys("有道")
    appid, secret = _ENGINE_KEYS["youdao_appid"], _ENGINE_KEYS["youdao_key"]
    deadline, t = _budget(deadline, timeout)
    salt, curtime = str(int(time.time() * 1000)), str(int(time.time()))
    form = {"q": text, "from": YOUDAO_CODE.get(sl, base(sl)), "to": YOUDAO_CODE.get(tl, base(tl)),
            "appKey": appid, "salt": salt, "sign": youdao_sign(appid, text, salt, curtime, secret),
            "signType": "v3", "curtime": curtime}
    req = urllib.request.Request("https://openapi.youdao.com/api", data=urllib.parse.urlencode(form).encode("utf-8"),
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with _urlopen(req, timeout=t) as r:
        data = json.loads(_read_capped(r, 2 << 20).decode("utf-8"))
    code = str(data.get("errorCode", "x")) if isinstance(data, dict) else "x"
    if code != "0":
        msg = "有道翻译：%s（错误码 %s）" % (YOUDAO_ERRORS.get(code, "未知错误"), code)
        if code in ("411", "412"):
            raise urllib.error.HTTPError("youdao", 429, msg, None, None)
        raise EngineKeyError(msg)
    out = "\n".join(data.get("translation") or [])
    if not out:
        raise RuntimeError("有道翻译返回为空")
    det = str(data.get("l") or "").split("2")[0] or sl
    return out, {"zh-CHS": "zh-CN", "zh-CHT": "zh-TW"}.get(det, det)


_AUTO_ORDER = ["Google", "微软", "Lingva", "MyMemory"]
_auto_state = {"last_ok": None}


def auto_order(last_ok=None, keyed=None):
    """「自动」引擎的尝试顺序（纯函数）：免费引擎在前，已填 Key 的引擎（keyed）排在后面兜底；
    上次成功的排第一。"""
    order = list(_AUTO_ORDER) + [k for k in (keyed or []) if k not in _AUTO_ORDER]
    if last_ok in order:
        order.remove(last_ok)
        order.insert(0, last_ok)
    return order


def _engine_call(name, text, sl, tl):
    if name == "Google":
        return g_translate(text, sl, tl, attempts=1)
    if name == "微软":
        return ms_translate(text, sl, tl, attempts=1)
    if name == "Lingva":
        return lingva_translate(text, sl, tl)
    if name == "MyMemory":
        return mymemory_translate(text, sl, tl)
    if name == "DeepL":
        return deepl_translate(text, sl, tl)
    if name == "百度":
        return baidu_translate(text, sl, tl)
    if name == "有道":
        return youdao_translate(text, sl, tl)
    raise ValueError("未知引擎：%s" % name)


def auto_translate(text, sl, tl):
    errs = []
    for name in auto_order(_auto_state["last_ok"], [k for k in KEY_ENGINES if engine_configured(k)]):
        try:
            out = _engine_call(name, text, sl, tl)
            _auto_state["last_ok"] = name
            return out
        except TimeoutError as e:
            if "总耗时" in str(e):
                raise
            errs.append("%s：%s" % (name, netcheck.explain_error(e)[0]))
        except Exception as e:      # noqa: BLE001
            errs.append("%s：%s" % (name, netcheck.explain_error(e)[0]))
    _auto_state["last_ok"] = None
    raise RuntimeError("所有在线引擎都失败了：\n" + "\n".join(errs))


def _is_auth_error(exc):
    return isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403)


def guess_lang(text):
    """语种粗判（仅供离线引擎的「自动检测」和 MyMemory 用），返回基础语言代码。
    v2.15.5：识别逻辑在 text_detect.detect_lang —— 假名 → 日语、谚文 → 韩语、
    纯汉字按简 / 繁 / 日语专有字分，拉丁字母按停用词 + 特征字母分英 / 西 / 法 / 德 / 意 / 葡 等；
    以前拉丁字母一律当英语、汉字一律当中文。"""
    return text_detect.guess_lang(text)


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
ONLINE_TOTAL_TIMEOUT = 10.0    # B-4：单次在线链路总时限（秒）——Google 重试 + 微软
# 回退共享这一个预算，到时直接停、走离线回退；代理拖沓时最坏也只等约 10 秒，
# 不再出现 3 次 × 12 秒超时 = 36 秒起的“点了半天没反应”。_DOWN_SECONDS 熔断不动。
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
    # B-4：整条在线链路（Google 重试 + 微软回退）共用一个总预算，到时即停，
    # 由 do_translate 接住 TimeoutError 进熔断、走离线回退。预算经线程本地变量
    # _tl.online_deadline 共享 —— 不改 g_translate/ms_translate 的调用签名，
    # 否则打桩替换它们的测试（test_core.py 的 fake_google）会被多出的关键字参数打断。
    _tl.online_deadline = time.monotonic() + ONLINE_TOTAL_TIMEOUT
    try:
        if engine == "微软":
            return ms_translate(text, sl, tl)
        if engine == "自动":
            return auto_translate(text, sl, tl)
        if engine == "Lingva":
            return lingva_translate(text, sl, tl)
        if engine == "MyMemory":
            return mymemory_translate(text, sl, tl)
        if engine in KEY_ENGINES:
            return _engine_call(engine, text, sl, tl)
        # Google 为主，限流时回退微软
        try:
            return g_translate(text, sl, tl)
        except Exception as e:
            if _is_rate_limit(e):
                try:
                    return ms_translate(text, sl, tl)
                except TimeoutError:
                    # B-4：总预算耗尽是连通性故障，原样抛出，让 do_translate 进熔断；
                    # 不要包进 RuntimeError，否则 is_connectivity_error 认不出来。
                    raise
                except Exception:
                    raise RuntimeError(
                        "Google 请求过于频繁（429），且微软端点也失败。\n"
                        "建议：稍等片刻，或切换到「微软 / 离线」引擎。\n"
                        "原始错误：%s" % e)
            raise
    finally:
        _tl.online_deadline = None


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
        if len(o) > limit:
            # v2.10：按下标切，不再 o = o[limit:] 反复复制剩余部分（超长单行 O(n²)，会卡死）
            for i in range(0, len(o), limit):
                final.append(o[i:i + limit])
        else:
            final.append(o)
    return final


def _join(parts, tl):
    sep = "" if base(tl) in ("zh", "ja", "th") else " "
    return sep.join(x.strip() for x in parts)


def translate_unit(unit, sl, tl, engine, cancelled=None):
    # 术语表（v2.7）：先把用户定的词换成占位符再翻，翻完换回固定译文。
    # 术语表为空时 protect/restore 都是原样返回，零开销、零行为变化。
    protected, mapping = glossary.protect(unit)
    parts = []
    for p in split_long(protected):
        if cancelled and cancelled():
            raise RuntimeError("cancelled")
        parts.append(cached(p, sl, tl, engine)[0])
    return glossary.restore(_join(parts, tl), mapping)


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


REFLOW_MAX = 1500        # 合并断行后一段最长多少字：再长就另起一段（v2.10）


def to_units(text, reflow):
    """拆成行；reflow 时把被硬换行打断的句子合并（保留标题、列表、空行）。

    v2.10：合并时用列表攒、最后一次性 join（以前每并一行就复制一遍整段，
    一个没有句号的大文件会退化成 O(n²) 并合并成一整块，卡死）；
    并给合并后的段长封顶（REFLOW_MAX），超过就另起一段。
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    cur, cur_len, last = None, 0, ""

    def close():
        nonlocal cur
        if cur is not None:
            out.append("".join(cur))
            cur = None

    for ln in lines:
        s = ln.strip()
        if not s:
            close()
            if out and out[-1] != "":
                out.append("")
            continue
        if (reflow and cur is not None and cur_len >= 45 and cur_len < REFLOW_MAX
                and last not in _END and not _BULLET.match(s)):
            glue = "" if (_cjk(last) and _cjk(s[0])) else " "
            cur.append(glue)
            cur.append(s)
            cur_len += len(glue) + len(s)
            last = s[-1]
        else:
            close()
            cur, cur_len, last = [s], len(s), s[-1]
    close()
    while out and out[-1] == "":
        out.pop()
    return out


DOC_BATCH = 64           # 文档翻译每批提交多少段给线程池
DOC_CONFIRM_SECS = 60    # 预估超过这么多秒（或下面的段数）就先问一句再翻（v2.11）
DOC_CONFIRM_SEGS = 2000
_SEC_PER_REQ_ONLINE = 0.5     # 在线引擎每个请求的经验耗时（秒），WORKERS 个并发
_SEC_PER_REQ_OFFLINE = 1.2    # 离线引擎每段的经验耗时（秒），按串行算


def estimate_doc_seconds(segs, chars, engine):
    """文档翻译预估耗时（秒，纯函数）：请求数 ≈ 段数 + 每 CHUNK 字多一个请求。
    只是量级估计：网速、引擎限流、CPU 都会影响，界面上写的是「约」。"""
    reqs = max(0, int(segs)) + max(0, int(chars)) // CHUNK
    if engine == "离线":
        return reqs * _SEC_PER_REQ_OFFLINE
    return reqs * _SEC_PER_REQ_ONLINE / WORKERS


def fmt_duration(sec):
    sec = max(0, int(sec))
    if sec < 60:
        return "约 %d 秒" % max(1, sec)
    if sec < 3600:
        return "约 %d 分钟" % math.ceil(sec / 60.0)
    return "约 %.1f 小时" % (sec / 3600.0)



def translate_many(texts, sl, tl, engine, progress=None, cancelled=None):
    """并发翻译一批文本，按原顺序返回译文列表（v2.10）。

    和旧的 ThreadPoolExecutor.map 相比：
    - 分批提交（DOC_BATCH 段一批），不再一次把几万个任务塞进线程池；
    - 任何一段失败 / 用户取消，其余排队的任务立刻快速退出，
      不会再傻等剩下每一段各自超时重试（那就是「点了没反应、像死机」）；
    - 优先把真正的错误（而不是「cancelled」）抛给调用方。
    """
    n = len(texts)
    results = [None] * n
    if not n:
        return results
    abort = threading.Event()
    counter = itertools.count(1)

    def work(i):
        if abort.is_set() or (cancelled and cancelled()):
            raise RuntimeError("cancelled")
        try:
            results[i] = translate_unit(texts[i], sl, tl, engine, cancelled)
        except BaseException:
            abort.set()
            raise
        if progress:
            progress(next(counter), n)

    with ThreadPoolExecutor(WORKERS) as ex:
        for start in range(0, n, DOC_BATCH):
            futs = [ex.submit(work, i) for i in range(start, min(n, start + DOC_BATCH))]
            first = None
            for f in futs:
                try:
                    f.result()
                except BaseException as e:      # noqa: BLE001
                    if first is None or (str(first) == "cancelled" and str(e) != "cancelled"):
                        first = e
            if first is not None:
                raise first
    return results


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
        sample, n = [], 0
        for t in texts:                 # 只取开头约 300 字做语言检测，不拼整篇
            sample.append(t)
            n += len(t) + 1
            if n >= 300:
                break
        det = cached(" ".join(sample)[:300], "auto", tl, engine)[1]
        src_lang = det
        if smart and base(det) == base(tl):
            target = alt_target(tl)
    outs = translate_many(texts, src_lang, target, engine, progress, cancelled)
    results = iter(outs)
    pairs = [("", "") if not u else (u, next(results)) for u in units]
    return pairs, det, target


# ---------------------------------------------------------------- Windows 全局热键
def start_hotkey_win(q, specs=None):
    """Windows 全局热键：注册六个组合键（主窗口 / 指针取词 / 截图翻译 /
    翻译并替换 / 粘贴图片翻译 / 整窗翻译）。

    specs 是 {"hotkey_main": "ctrl+alt+t", ...} 这类配置，不传（None）就用
    默认组合；非法组合逐个回落到默认，绝不抛异常。返回主窗口热键是否注册成功。
    """
    import ctypes
    import ctypes.wintypes
    user32 = ctypes.windll.user32
    ready, state = threading.Event(), {"ok": False, "pointer_ok": False, "shot_ok": False,
                                        "replace_ok": False, "clip_ok": False, "window_ok": False}
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
        names = ("ok", "pointer_ok", "shot_ok", "replace_ok", "clip_ok", "window_ok")
        for i, (mods, vk) in parsed.items():
            state[names[i - 1]] = bool(user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk))
        ready.set()
        if not (state["ok"] or state["pointer_ok"] or state["shot_ok"] or state["replace_ok"]
                or state["clip_ok"] or state["window_ok"]):
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
    start_hotkey_win.clip_ok = state["clip_ok"]
    start_hotkey_win.window_ok = state["window_ok"]
    return state["ok"]


# ---------------------------------------------------------------- 打字检测：Windows 键盘监听
# v2.15.6：钩子安装失败是 2.15.5 上报的 bug，本版修了三处硬伤并加了兜底：
#   1) SetWindowsHookExW / UnhookWindowsHookEx 从没设过 argtypes/restype，
#      ctypes 默认把 64 位钩子句柄截成 32 位 int 传回 / 传出；
#   2) hMod 传 None：部分机器 / 安全软件下 SetWindowsHookExW 直接报
#      ERROR_HOOK_NEEDS_HMOD（1428），改传 GetModuleHandleW(None)；
#   3) 原来只等 2 秒就判失败，失败也不说错误码。改成线程内重试 3 次、
#      用 Event 交握（最多等 5 秒）、失败时把 GetLastError 错误码带回队列；
#      钩子实在装不上时改用 GetAsyncKeyState 轮询兜底（start_typing_poll_win）。
_TYPING_HOOK_ERROR_TEXT = {
    5: "拒绝访问（5，可能被安全软件拦截）",
    87: "参数错误（87）",
    1428: "需要模块句柄（1428）",
    1429: "钩子已存在（1429）",
    1460: "安装超时（1460）",
}


def _typing_hook_error_text(code):
    """Win32 错误码 → 一句中文说明；未知码只报数字，不瞎猜原因。"""
    if code in _TYPING_HOOK_ERROR_TEXT:
        return _TYPING_HOOK_ERROR_TEXT[code]
    return "错误码 %s" % (code,) if code else "未知错误"


def _typing_win32_setup(user32, kernel32=None):
    """给真实 WinDLL 设好 argtypes/restype（64 位句柄不能截成 int）。
    传入 fake 对象（测试用）时设不上就跳过，不报错。"""
    import ctypes
    import ctypes.wintypes as wt
    try:
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        user32.GetKeyboardState.argtypes = [ctypes.POINTER(ctypes.c_ubyte)]
        user32.GetKeyboardState.restype = wt.BOOL
        user32.GetKeyboardLayout.argtypes = [wt.DWORD]
        user32.GetKeyboardLayout.restype = ctypes.c_void_p
        user32.ToUnicodeEx.argtypes = [ctypes.c_uint, ctypes.c_uint,
                                       ctypes.POINTER(ctypes.c_ubyte),
                                       ctypes.c_wchar_p, ctypes.c_int,
                                       ctypes.c_uint, ctypes.c_void_p]
        user32.ToUnicodeEx.restype = ctypes.c_int
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wt.WPARAM, wt.LPARAM]
        user32.CallNextHookEx.restype = wt.LPARAM
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p,
                                             ctypes.c_void_p, wt.DWORD]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        user32.UnhookWindowsHookEx.restype = wt.BOOL
        user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), ctypes.c_void_p,
                                       ctypes.c_uint, ctypes.c_uint]
        user32.GetMessageW.restype = wt.BOOL
        user32.PostThreadMessageW.argtypes = [wt.DWORD, ctypes.c_uint, wt.WPARAM, wt.LPARAM]
        user32.PostThreadMessageW.restype = wt.BOOL
        user32.GetCurrentThreadId.restype = wt.DWORD
    except (AttributeError, TypeError):
        pass
    if kernel32 is not None:
        try:
            kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        except (AttributeError, TypeError):
            pass


def _typing_modifiers_down(user32):
    """Ctrl / Alt / Win 任一按住（钩子与轮询共用）。"""
    return any(user32.GetAsyncKeyState(vk) & 0x8000 for vk in (0x11, 0x12, 0x5B, 0x5C))


def _typing_vk_to_char(user32, vk, scan):
    """虚拟键 → 字符（按当前键盘布局；转不出来返回 None。钩子与轮询共用）。"""
    import ctypes
    kb = (ctypes.c_ubyte * 256)()
    if not user32.GetKeyboardState(kb):
        return None
    buf = ctypes.create_unicode_buffer(8)
    n = user32.ToUnicodeEx(vk, scan, kb, buf, 8, 0, user32.GetKeyboardLayout(0))
    if n >= 1:
        return buf.value[:1]
    return None


def start_typing_hook_win(q, _win=None, _kernel=None):
    """Windows 打字检测翻译的低级键盘钩子（WH_KEYBOARD_LL，标准库 ctypes，
    不装第三方依赖）。只转发按键事件到队列，绝不在钩子回调里做翻译/弹窗/
    读配置：回调里只判断“是不是可打印字符 / 空格 / 回车 / 退格 / Esc”，
    修饰键组合（Ctrl/Alt/Win 按住时）一律不转发，注入的按键事件也不转发。
    返回 stop()；安装失败返回 None（并把错误码记在
    start_typing_hook_win.last_error、同时往队列发 ("typing_hook_error", 码)，
    调用方按码提示，绝不崩溃）。_win / _kernel 只供测试注入 fake user32。"""
    import ctypes
    import ctypes.wintypes as wt
    user32 = _win if _win is not None else ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = _kernel if _kernel is not None else ctypes.WinDLL("kernel32", use_last_error=True)
    _typing_win32_setup(user32, kernel32)
    WH_KEYBOARD_LL, WM_KEYDOWN, WM_SYSKEYDOWN = 13, 0x0100, 0x0104
    LLKHF_INJECTED = 0x10

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD),
                    ("flags", wt.DWORD), ("time", wt.DWORD),
                    ("dwExtraInfo", ctypes.c_void_p)]

    state = {"hook": None, "thread_id": 0, "stopped": False, "err": 0}
    ready = threading.Event()

    def _last_error():
        err = getattr(user32, "last_error", None)
        if err is None:
            try:
                err = ctypes.get_last_error()
            except Exception:
                err = 0
        return err or 0

    def _callback(n_code, w_param, l_param):
        try:
            if n_code >= 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if not (info.flags & LLKHF_INJECTED) and not _typing_modifiers_down(user32):
                    vk = info.vkCode
                    if vk == 0x20:
                        q.put(("typing_key", " ", vk))
                    elif vk == 0x0D:
                        q.put(("typing_key", "\n", vk))
                    elif vk == 0x08:
                        q.put(("typing_key", "\b", vk))
                    elif vk == 0x1B:
                        q.put(("typing_key", "\x1b", vk))
                    elif vk == 0x09:
                        q.put(("typing_key", "\t", vk))
                    elif vk == 0x78:                     # v2.15.4：F9 = 输入翻译的触发键
                        q.put(("typing_key", "\x00F9", vk))
                    else:
                        ch = _typing_vk_to_char(user32, vk, info.scanCode)
                        if ch:
                            q.put(("typing_key", ch, vk))
        except Exception:
            pass
        return user32.CallNextHookEx(state["hook"], n_code, w_param, l_param)

    # WINFUNCTYPE 只在 Windows 上有（stdcall）；Linux 单测用 CFUNCTYPE，
    # x86-64 下两者调用约定相同，只为让这段逻辑能在 Linux 上跑测试。
    _winfunctype = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
    HOOKPROC = _winfunctype(wt.LPARAM, ctypes.c_int, wt.WPARAM, wt.LPARAM)
    proc = HOOKPROC(_callback)
    state["_proc"] = proc  # 钩子回调绝不能被 GC 回收

    def loop():
        state["thread_id"] = user32.GetCurrentThreadId()
        try:
            hmod = kernel32.GetModuleHandleW(None)
        except Exception:
            hmod = None
        hook = None
        for _attempt in range(3):
            if state["stopped"]:
                break
            hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, proc, hmod, 0)
            if hook:
                break
            state["err"] = _last_error()
            time.sleep(0.2)
        if not hook:
            state["err"] = state["err"] or _last_error()
            q.put(("typing_hook_error", state["err"]))
            ready.set()
            return
        state["hook"] = hook
        ready.set()
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.UnhookWindowsHookEx(hook)
        state["hook"] = None

    threading.Thread(target=loop, daemon=True).start()
    ready.wait(5)
    if state["hook"] is None:
        start_typing_hook_win.last_error = state["err"]
        return None
    start_typing_hook_win.last_error = 0

    def stop():
        if state["stopped"]:
            return
        state["stopped"] = True
        try:
            if state["hook"] is not None:
                user32.UnhookWindowsHookEx(state["hook"])
        except Exception:
            pass
        try:
            if state["thread_id"]:
                user32.PostThreadMessageW(state["thread_id"], 0x0012, 0, 0)  # WM_QUIT
        except Exception:
            pass

    return stop


start_typing_hook_win.last_error = 0


# 轮询兜底要扫的虚拟键：退格 / Tab / 回车 / Esc / 空格 / F9 + 数字 + 字母 +
# 小键盘数字 + 常见标点键（修饰键本身不在里面）。
_TYPING_POLL_VKS = ((0x08, 0x09, 0x0D, 0x1B, 0x20, 0x78)
                    + tuple(range(0x30, 0x3A)) + tuple(range(0x41, 0x5B))
                    + tuple(range(0x60, 0x6A))
                    + (0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0,
                       0xDB, 0xDC, 0xDD, 0xDE, 0xE2))
_TYPING_POLL_SPECIAL = {0x08: "\b", 0x09: "\t", 0x0D: "\n",
                        0x1B: "\x1b", 0x20: " ", 0x78: "\x00F9"}


def start_typing_poll_win(q, _win=None, _interval=0.01):
    """轮询兜底：键盘钩子装不上时，用 GetAsyncKeyState 每 10ms 扫一遍按键，
    检测“按下边沿”后按钩子同样的规则转发（修饰键组合不转发）。
    认不出注入按键：替换粘贴期间按住 Ctrl/Alt 时不转发（和钩子一致）；
    替换用的退格注入会被当成真退格，但替换完成时会清空缓冲，影响有限。
    返回 stop()；线程起不来返回 None。_win 只供测试注入 fake user32。"""
    import ctypes
    user32 = _win if _win is not None else ctypes.WinDLL("user32", use_last_error=True)
    _typing_win32_setup(user32)
    state = {"stopped": False}
    prev = {}

    def loop():
        while not state["stopped"]:
            try:
                for vk in _TYPING_POLL_VKS:
                    down = bool(user32.GetAsyncKeyState(vk) & 0x8000)
                    was = prev.get(vk, False)
                    prev[vk] = down
                    if not down or was:
                        continue
                    if _typing_modifiers_down(user32):
                        continue
                    ch = _TYPING_POLL_SPECIAL.get(vk)
                    if ch is None:
                        ch = _typing_vk_to_char(user32, vk, 0)
                    if ch:
                        q.put(("typing_key", ch, vk))
            except Exception:
                pass
            time.sleep(_interval)

    try:
        threading.Thread(target=loop, daemon=True).start()
    except Exception:
        return None

    def stop():
        state["stopped"] = True

    return stop
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


def ctrl_down_win():
    try:
        import ctypes
        return bool(ctypes.windll.user32.GetAsyncKeyState(0x11) & 0x8000)
    except Exception:
        return False


def esc_pressed_win():
    """全局 Esc（气泡不抢焦点，窗口自己的 <Escape> 绑定收不到按键）。"""
    try:
        import ctypes
        return bool(ctypes.windll.user32.GetAsyncKeyState(0x1B) & 0x8000)
    except Exception:
        return False


def send_backspaces_win(n):
    """发 n 次退格（输入翻译：删掉刚打的那句话）。最多 400 次，防止误删太多。"""
    import ctypes
    u = ctypes.windll.user32
    for _ in range(max(0, min(int(n), 400))):
        u.keybd_event(0x08, 0, 0, 0)
        u.keybd_event(0x08, 0, 2, 0)
    time.sleep(0.02)


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


_ZERO_WIDTH = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"), None)


def normalize_grab_text(text):
    """v2.15.3 取词文字清洗（纯函数）：去零宽字符 / 软连字符，行内多空白压成一个，
    把硬换行断开的同一段重新接起来（英文行尾连字符直接拼，中文直接相连，其余加空格），
    空行保留为段落分隔。"""
    t = (text or "").translate(_ZERO_WIDTH).replace("\r\n", "\n").replace("\r", "\n")
    paras, cur = [], []
    for ln in t.split("\n"):
        ln = re.sub(r"[ \t\u00a0\u3000]+", " ", ln).strip()
        if ln:
            cur.append(ln)
        elif cur:
            paras.append(cur); cur = []
    if cur:
        paras.append(cur)
    out = []
    for lines in paras:
        s_ = ""
        for ln in lines:
            if not s_:
                s_ = ln
            elif s_.endswith("-") and s_[-2:-1].isalpha() and ln[:1].islower():
                s_ = s_[:-1] + ln
            elif ocr_win._is_cjk(s_[-1]) or ocr_win._is_cjk(ln[0]):
                s_ += ln
            else:
                s_ += " " + ln
        out.append(s_)
    return "\n".join(out)


def hover_worth_translating(word):
    """悬停取到的东西值不值得翻（纯函数）：纯数字 / 标点 / 网址 / 单个字母不翻，免得满屏乱弹。"""
    w = (word or "").strip()
    if not w:
        return False
    if not any(ch.isalpha() for ch in w):
        return False
    if re.match(r"^(https?://|www\.)", w, re.I) or re.match(r"^[\w.+-]+@[\w-]+\.[\w.]+$", w):
        return False
    if len(w) == 1 and w.isascii():
        return False
    return True


class HoverDedupe:
    """同一个词在附近刚翻过就不再弹（纯逻辑）：气泡关掉后指针还停在原词上，
    旧版会马上再取一次、再弹一次。"""

    def __init__(self, ttl=4.0, radius=40):
        self.ttl, self.radius = ttl, radius
        self.last = None            # (word, pos, t)

    def seen(self, word, pos, now=None):
        now = time.time() if now is None else now
        if self.last:
            w, p, t = self.last
            if (w == word and now - t < self.ttl
                    and abs(p[0] - pos[0]) <= self.radius and abs(p[1] - pos[1]) <= self.radius):
                return True
        self.last = (word, pos, now)
        return False


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
    window_label = snap.get("hotkey_window") or WINDOW_LABEL
    items = [
        {"id": "show", "label": "显示主窗口(&S)", "default": True},
        {"id": "shot", "label": "截图翻译(&C)　%s" % shot_label},
        {"id": "window", "label": "整窗翻译(&W)　%s" % window_label},
        {"id": "clip", "label": "翻译剪贴板内容(&V)"},
        {"id": "compare", "label": "多引擎对照剪贴板内容…"},
        {"id": "replace", "label": "翻译并替换原文(&R)　%s" % replace_label},
        {"sep": True},
        {"id": "pointer", "label": "指针取词　%s" % pointer_label, "checked": bool(snap.get("pointer"))},
        {"id": "hover", "label": "悬停取词", "checked": bool(snap.get("hover"))},
        {"id": "typing", "label": "打字检测翻译", "checked": bool(snap.get("typing"))},
        {"id": "input", "label": "输入翻译（打完替换成译文）", "checked": bool(snap.get("input"))},
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


def exclude_from_capture_win(win):
    """v2.15.3：让窗口不被截屏（Win10 2004+ 的 WDA_EXCLUDEFROMCAPTURE），
    并且鼠标穿透（点击直接落到下面的软件上）。取词提示用，不能被 OCR 截进去、也不能挡住双击。
    返回是否成功排除截屏；失败不抛异常。"""
    try:
        import ctypes
        u = ctypes.windll.user32
        u.GetParent.restype = ctypes.c_void_p
        u.GetParent.argtypes = [ctypes.c_void_p]
        hwnd = u.GetParent(win.winfo_id()) or win.winfo_id()
        GWL_EXSTYLE = -20
        WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = 0x80000, 0x20, 0x08000000, 0x80
        get = getattr(u, "GetWindowLongPtrW", u.GetWindowLongW)
        sett = getattr(u, "SetWindowLongPtrW", u.SetWindowLongW)
        get.restype = ctypes.c_ssize_t
        get.argtypes = [ctypes.c_void_p, ctypes.c_int]
        sett.restype = ctypes.c_ssize_t
        sett.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
        st = get(hwnd, GWL_EXSTYLE)
        sett(hwnd, GWL_EXSTYLE, st | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        u.SetWindowDisplayAffinity.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        return bool(u.SetWindowDisplayAffinity(hwnd, 0x11))
    except Exception:
        return False


def spinner_frames():
    """取词提示的动画帧（纯函数，便于测试）。"""
    return ["◐", "◓", "◑", "◒"]


def spinner_position(pointer, size, bounds, avoid=(0, 0)):
    """取词提示放在哪（纯函数）：默认指针右下；avoid=(半宽, 半高) 是 OCR 截图框，
    截屏排除不可用时就放到框外面，免得被截进去。放不下就翻到左 / 上。"""
    (x, y), (w, h) = pointer, size
    l, t, r, b = bounds
    ax, ay = avoid
    px, py = x + 16, y + max(18, ay + 6)
    if px + w > r - 4:
        px = x - w - 16
    if py + h > b - 4:
        py = y - max(18, ay + 6) - h
    return max(l + 4, min(px, r - w - 4)), max(t + 4, min(py, b - h - 4))


class GrabSpinner:
    """v2.15.3 取词加载提示：指针旁一个小胶囊「◐ 取词中…」。

    - 延迟 250ms 才出现：快的取词（缓存命中、复制秒回）不闪一下。
    - 不抢焦点、鼠标穿透、尽量不被截屏（WDA_EXCLUDEFROMCAPTURE），
      排除失败时摆到 OCR 截图框外面。
    - 结果 / 错误到了就收起；最多显示 8 秒防止残留。只在 Tk 线程里调用。
    """
    DELAY_MS, MAX_MS, TICK_MS = 250, 8000, 120

    def __init__(self, app):
        self.app = app
        self.win = None
        self.label = None
        self._job = None
        self._tick_job = None
        self._token = 0
        self._frame = 0
        self._t0 = 0.0
        self._text = "取词中…"
        self._xy = (0, 0)
        self._avoid = (0, 0)

    def enabled(self):
        return bool(self.app.cfg.get("grab_spinner", True))

    def visible(self):
        try:
            return self.win is not None and bool(self.win.winfo_exists()) and self.win.state() != "withdrawn"
        except Exception:
            return False

    def start(self, xy, text="取词中…", avoid=(0, 0)):
        if not self.enabled():
            return
        self.stop()
        self._token += 1
        tok = self._token
        self._xy, self._text, self._avoid = xy, text, avoid
        self._t0 = time.time()
        try:
            self._job = self.app.root.after(self.DELAY_MS, lambda: self._show(tok))
        except Exception:
            self._job = None

    def stop(self):
        self._token += 1
        for j in (self._job, self._tick_job):
            if j is not None:
                try:
                    self.app.root.after_cancel(j)
                except Exception:
                    pass
        self._job = self._tick_job = None
        if self.win is not None:
            try:
                self.win.withdraw()
            except Exception:
                self.win = None

    def _ensure(self):
        if self.win is not None:
            try:
                if self.win.winfo_exists():
                    return True
            except Exception:
                pass
        try:
            w = tk.Toplevel(self.app.root)
            w.withdraw()
            w.overrideredirect(True)
            try:
                w.attributes("-topmost", True)
                w.attributes("-alpha", 0.94)
            except tk.TclError:
                pass
            dark = bool(self.app.cfg.get("dark_mode", False))
            bg, fg, acc = ("#2c2c2e", "#f5f5f7", "#0a84ff") if dark else ("#1d1d1f", "#f5f5f7", "#2997ff")
            w.configure(background=bg)
            fam = getattr(self.app, "ui_font", ("TkDefaultFont", 10))[0]
            self.icon = tk.Label(w, text="◐", bg=bg, fg=acc, font=(fam, 10))
            self.label = tk.Label(w, text=self._text, bg=bg, fg=fg, font=(fam, 9))
            self.icon.pack(side="left", padx=(9, 3), pady=3)
            self.label.pack(side="left", padx=(0, 10), pady=3)
            self.win = w
            self._excluded = False
            return True
        except Exception:
            self.win = None
            return False

    def _show(self, tok):
        self._job = None
        if tok != self._token or not self._ensure():
            return
        w = self.win
        try:
            self.label.configure(text=self._text)
            w.update_idletasks()
            size = (w.winfo_reqwidth(), w.winfo_reqheight())
            bounds = screen_bounds() or (0, 0, w.winfo_screenwidth(), w.winfo_screenheight())
            avoid = (0, 0) if getattr(self, "_excluded", False) else self._avoid
            w.geometry("+%d+%d" % spinner_position(self._xy, size, bounds, avoid))
            w.deiconify()
            if IS_WIN:
                w.update_idletasks()
                self._excluded = exclude_from_capture_win(w)
                if not self._excluded:
                    w.geometry("+%d+%d" % spinner_position(self._xy, size, bounds, self._avoid))
        except Exception:
            return
        self._tick(tok)

    def _tick(self, tok):
        if tok != self._token or not self.visible():
            return
        if (time.time() - self._t0) * 1000 > self.MAX_MS:
            self.stop()
            return
        self._frame = (self._frame + 1) % 4
        try:
            self.icon.configure(text=spinner_frames()[self._frame])
            self._tick_job = self.app.root.after(self.TICK_MS, lambda: self._tick(tok))
        except Exception:
            self._tick_job = None


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


def find_uninstaller(exe_dir=None):
    """安装版的卸载程序路径（和 exe 同目录的 Uninstall.exe / unins000.exe）；免安装版返回 None。"""
    if exe_dir is None:
        if not FROZEN:
            return None
        exe_dir = os.path.dirname(sys.executable)
    for name in ("Uninstall.exe", "unins000.exe"):
        pth = os.path.join(exe_dir, name)
        if os.path.isfile(pth):
            return pth
    return None


def install_info_text():
    if not FROZEN:
        return "当前从源码运行，没有安装程序。数据在：%s" % DATA_DIR
    if find_uninstaller():
        return "安装位置：%s。卸载时会问你要不要删除翻译历史和设置（默认保留）。" % os.path.dirname(sys.executable)
    return "免安装版：直接删除程序文件夹即可；数据在 %s。" % DATA_DIR


def open_folder(path):
    try:
        os.makedirs(path, exist_ok=True)
        if IS_WIN:
            os.startfile(path)            # noqa: S606
        else:
            import subprocess
            subprocess.Popen(["open" if IS_MAC else "xdg-open", path])
        return True
    except Exception:
        return False


def log_crash(text):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        _rotate_log(CRASH_LOG)             # M-06：超过 5 MB 先轮转，不无限增长
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
        th = app.popup_colors()
        frame = tk.Frame(w, bg=th["bubble_bg"], highlightbackground=th["border"],
                         highlightthickness=1, padx=10, pady=7)
        frame.pack()
        self.head = tk.Label(frame, bg=th["bubble_bg"], fg=th["bubble_gray"],
                             font=app.ui_font, anchor="w", justify="left", wraplength=380)
        self.body = tk.Label(frame, bg=th["bubble_bg"], font=app.font, anchor="w",
                             justify="left", wraplength=380)
        self.foot = tk.Label(frame, bg=th["bubble_bg"], fg=th["bubble_foot"],
                             font=(app.ui_font[0], 8), anchor="w",
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
        th = self.app.popup_colors()
        self.head.configure(text=head)
        self.body.configure(text=body, fg=th["error"] if error else th["bubble_fg"])
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
    HIDE_TIMEOUT = 8.0       # v2.15.8：取词时藏起来最多等这么久（旧值 2 秒，比 OCR 冷启动还短，识别没回来窗口就没了）
    OFFSET = (16, 22)

    def __init__(self, app):
        self.app = app
        self.win = None
        self.t0 = 0.0
        self.hidden_at = None
        self._follow_id = None
        self.copy_text = ""
        self.speak_lang = None

    def alive(self):
        try:
            return self.win is not None and bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def _cancel_follow(self):
        fid, self._follow_id = self._follow_id, None
        if fid is not None:
            try:
                self.app.root.after_cancel(fid)
            except Exception:
                pass

    def close(self):
        self._cancel_follow()
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
        th = app.popup_colors()
        frame = tk.Frame(w, bg=th["bubble_bg"], highlightbackground=th["border"],
                         highlightthickness=1, width=W, height=H)
        frame.pack()
        frame.pack_propagate(False)                   # 固定大小：文字太长就裁掉，不撑大窗口
        self.head = tk.Label(frame, bg=th["bubble_bg"], fg=th["bubble_gray"],
                             font=(app.ui_font[0], 8), anchor="w", justify="left")
        self.body = tk.Label(frame, bg=th["bubble_bg"], font=app.font, anchor="nw",
                             justify="left", wraplength=max(60, W - 20))
        self.foot = tk.Label(frame, bg=th["bubble_bg"], fg=th["bubble_foot"],
                             font=(app.ui_font[0], 8), anchor="w",
                             text="点击复制译文 · 双击朗读译文 · 右键或 Esc 关闭")
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
        th = self.app.popup_colors()
        self.head.configure(text=head)
        self.body.configure(text=body, fg=th["error"] if error else th["bubble_fg"])
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

    def restore(self):
        """v2.15.8：取词后没有新结果（同一个词刚翻过、被去重）时，把藏起来的小窗口放回来，
        不然它会被藏 HIDE_TIMEOUT 秒后自己关掉，看起来就是「悬停取词没反应」。"""
        if self.alive() and self.hidden_at is not None:
            self.hidden_at = None
            try:
                self.win.deiconify()
            except tk.TclError:
                return
            self._follow()

    def hide_for_capture(self):
        """取词截屏前先藏起来（在 Tk 线程调用）。HIDE_TIMEOUT 秒内没新结果就自己关掉。"""
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
        self._cancel_follow()           # v2.15.8：只留一条跟随循环（以前每次 show 都再起一条，越叠越多）
        if not self.alive():
            return
        now = time.time()
        if now - self.t0 > self.MAX_SECONDS or (self.hidden_at is not None and now - self.hidden_at > self.HIDE_TIMEOUT):
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
        self._follow_id = self.app.root.after(self.FOLLOW_MS, self._follow)


class App:
    def __init__(self):
        self.cfg = self._load_cfg()
        set_proxy_url(proxy_url(self.cfg))   # v2.9：启动时按配置决定在线引擎走不走代理
        set_engine_keys(self.cfg)             # v2.15.4：DeepL / 百度 / 有道 的 Key
        # 首次运行（还没有配置文件）：状态栏给一句空态提示，告诉用户从哪开始
        self._first_run = not (os.path.exists(CONFIG_PATH)
                               or os.path.exists(OLD_CONFIG_PATH))
        self._hover_cache = HoverCache()
        self._hover_ocr_err = ""
        glossary.set_active(self.cfg.get("glossary", []))

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
        self.live_on = False                    # v2.11：实时刷新整窗翻译
        self._live_job = None
        self._live_busy = False
        self._live_rect = None
        self._live_crc = None
        self._live_msg = None
        self._hover_win_rect = None             # v2.11：悬停整窗翻译上一次翻的窗口范围
        self._window_cache = WindowShotCache()  # v2.12：整窗翻译按窗口记忆缓存（内存，50 条 LRU）
        self._hotkey_status = {}                # v2.12：启动时各热键的注册结果（诊断信息用）
        self._watchdog = None                   # v2.12：界面卡死看门狗（root 建好后启动）
        self._doc_busy = False                  # v2.10：文档翻译进行中（防重复点击）
        self._doc_cancel = threading.Event()    # v2.10：「取消翻译」
        # v2.14 打字检测翻译：缓冲只放内存，默认关闭；监听在 _start_typing 里按需启动
        self._typing_buffer = typing_detect.TypingBuffer(
            scope=self.cfg.get("typing_scope", "word"),
            pause_ms=self.cfg.get("typing_pause_ms", 1000))
        self._typing_seq = 0
        self._typing_stop = None                # Windows 钩子 / 轮询兜底的 stop()
        self._typing_poll_fallback = False      # v2.15.6：钩子装不上时改用轮询
        self._typing_listener = None            # pynput 监听器（macOS/Linux）
        self._typing_last_hwnd = None           # 前台窗口一切换就清空缓冲
        self._typing_bubble_active = False
        self._typing_mods = set()               # pynput 下按住的修饰键
        self._tts_kind = None          # 正在朗读的是原文（"src"）还是译文（"dst"），用于再点一次停止

        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        # v2.13：保存的窗口大小 / 位置先夹进当前屏幕（小屏笔记本、换显示器、导入别台电脑的设置都不会跑到屏幕外）
        _sw, _sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(ui_platform.clamp_geometry(self.cfg.get("geometry") or DEFAULTS["geometry"], _sw, _sh)
                           or DEFAULTS["geometry"])
        self.root.minsize(min(380, _sw - 40), min(360, _sh - 80))
        try:
            if IS_WIN:
                self.root.iconbitmap(resource_path("app.ico"))
        except Exception:
            pass
        self.root.report_callback_exception = self._on_tk_error
        self.bubble = Bubble(self)
        self.mini = MiniWin(self)
        self.spinner = GrabSpinner(self)
        self.shot_overlay = None
        self._build_ui()
        self._fit_min_width()
        self._orig_colors = self._snapshot_colors()
        self._apply_theme()
        if self._first_run:
            self.status.configure(text="在上方输入文字，或在任意软件里选中文字按 Ctrl+Alt+T 翻译")
        # M-11：离线运行库文件被改动时启动加载会被拒绝 —— 在状态栏提醒用户重新下载，
        # 而不是让离线引擎在后台悄悄不可用。
        if runtime_installer.LAST_VERIFY_ERROR:
            self.status.configure(text="离线组件校验失败：%s，请在「离线与网络」里重新下载组件。"
                                  % runtime_installer.LAST_VERIFY_ERROR)

        self.last_clip = self._get_clip()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Unmap>", self._on_unmap)
        self.root.bind("<Escape>", lambda e: (self.bubble.close(), self.mini.close(), self._close_shot_overlay(),
                                              self.hide_window()))
        self._watchdog = Watchdog(WATCHDOG_LOG)   # v2.12：界面线程卡死自动记调用栈
        self._watchdog.start()
        self._init_pet()
        self.root.after(100, self._poll)
        self.root.after(600, self._watch_clip)
        self.root.after(1500, self._warmup)
        self.root.after(5000, self._auto_update_check)
        self._start_hotkey()
        self._start_tray()
        self._start_typing()
        if "--minimized" in sys.argv:
            # v2.13.2：开机自启（--minimized）一律缩在任务栏，不管「点 ×」选的是什么。
            # 等窗口真正显示出来再最小化，启动瞬间调用 iconify 在 Windows 上有时不生效。
            self.root.after(300, self._start_minimized)

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
        # v2.14 打字检测翻译：默认关闭；停顿夹在 500–3000 毫秒；范围只认单词/整句
        cfg["typing"] = bool(cfg.get("typing", False))
        try:
            cfg["typing_pause_ms"] = int(cfg.get("typing_pause_ms", 1000))
        except Exception:
            cfg["typing_pause_ms"] = 1000
        cfg["typing_pause_ms"] = max(500, min(cfg["typing_pause_ms"], 3000))
        if cfg.get("typing_scope") not in TYPING_SCOPE_NAMES:
            cfg["typing_scope"] = "word"
        # v2.15 授权：坏的授权值一律回落免费版，绝不让坏配置让程序起不来
        if not isinstance(cfg.get("license_key"), str):
            cfg["license_key"] = ""
        if cfg.get("license_status") not in ("free", "trial", "pro"):
            cfg["license_status"] = "free"
        try:
            cfg["license_trial_start"] = float(cfg.get("license_trial_start") or 0)
        except Exception:
            cfg["license_trial_start"] = 0
        if not isinstance(cfg.get("license_machines"), list):
            cfg["license_machines"] = []
        cfg["license_machines"] = [m for m in cfg["license_machines"]
                                   if isinstance(m, str)]
        if cfg.get("close_action") not in CLOSE_NAMES:
            cfg["close_action"] = DEFAULTS["close_action"]
        # v2.13：旧版默认「点 × 隐藏到托盘」，窗口会从任务栏消失、很多人以为程序退出了。
        # 老配置里还是旧默认值的，一次性改成「最小化到任务栏」（设置里 / 主窗口勾选框随时可改回去，只迁移一次）。
        # v2.13.2：默认窗口改小（480x600），老配置里存的大窗口一次性重置成小窗口，之后用户自己拖多大都记住
        if not cfg.get("compact_migrated"):
            cfg["geometry"] = DEFAULTS["geometry"]
            cfg["compact_migrated"] = True
        if not cfg.get("close_taskbar_migrated"):
            if cfg.get("close_action") == "tray":
                cfg["close_action"] = "taskbar"
            cfg["close_taskbar_migrated"] = True
        cfg["hover_window"] = bool(cfg.get("hover_window", False))
        try:
            cfg["live_interval"] = max(5, min(int(cfg.get("live_interval", 5)), 30))
        except Exception:
            cfg["live_interval"] = 5
        if cfg.get("minimize_action") not in MINIMIZE_NAMES:
            cfg["minimize_action"] = "taskbar"
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
        if cfg.get("pack_mirror_preset") not in pack_downloader.MIRROR_PRESETS:
            cfg["pack_mirror_preset"] = pack_downloader.MIRROR_PRESETS[0]
        # v2.5：朗读语速钳制 -10..10、自动复制开关、快捷键非法/重复回默认
        try:
            cfg["tts_rate"] = int(cfg.get("tts_rate", 0))
        except Exception:
            cfg["tts_rate"] = 0
        cfg["tts_rate"] = max(-10, min(cfg["tts_rate"], 10))
        cfg["auto_copy"] = bool(cfg.get("auto_copy", False))
        cfg.update(validate_hotkey_cfg(cfg))
        # v2.7：深色外观、术语表、自动检查更新
        cfg["dark_mode"] = bool(cfg.get("dark_mode", False))
        # v2.14：萌系配色 + 桌面小宠物
        cfg["cute_theme"] = bool(cfg.get("cute_theme", False))
        cfg["apple_theme"] = bool(cfg.get("apple_theme", True))
        if cfg.get("pet_mode") not in pet_catalog.PET_MODES:
            cfg["pet_mode"] = "minimized"
        if cfg.get("pet_id") not in pet_catalog.pet_ids():
            cfg["pet_id"] = pet_catalog.DEFAULT_PET
        cfg["pet_bubble"] = bool(cfg.get("pet_bubble", True))
        for k in ("pet_x", "pet_y"):
            if not isinstance(cfg.get(k), int) or isinstance(cfg.get(k), bool) or abs(cfg[k]) > 20000:
                cfg.pop(k, None)
        cfg["glossary"] = glossary.sanitize_pairs(cfg.get("glossary", []))
        cfg["update_auto"] = bool(cfg.get("update_auto", True))
        if not isinstance(cfg.get("update_last_check"), str):
            cfg["update_last_check"] = ""
        # v2.6：界面字号钳制 10~18
        try:
            cfg["font_size"] = int(cfg.get("font_size", 11))
        except Exception:
            cfg["font_size"] = 11
        cfg["font_size"] = max(10, min(cfg["font_size"], 18))
        # v2.9：代理配置（端口非法回 0 = 没配）；朗读语音只认字符串
        cfg["proxy_enabled"] = bool(cfg.get("proxy_enabled", False))
        if not isinstance(cfg.get("proxy_host"), str):
            cfg["proxy_host"] = ""
        cfg["proxy_host"] = cfg["proxy_host"].strip()
        try:
            cfg["proxy_port"] = int(cfg.get("proxy_port", 0))
        except Exception:
            cfg["proxy_port"] = 0
        if not 0 <= cfg["proxy_port"] <= 65535:
            cfg["proxy_port"] = 0
        if not isinstance(cfg.get("proxy_user"), str):
            cfg["proxy_user"] = ""
        if not isinstance(cfg.get("proxy_pass"), str):
            cfg["proxy_pass"] = ""
        # M-04：代理密码在盘上是 DPAPI 加密的 —— 读入后解开，内存里保持明文；
        # 旧版明文直接兼容；解不开（换了用户/机器）就清空，不让坏值进代理。
        for sk in ENGINE_KEY_FIELDS:
            if not isinstance(cfg.get(sk), str):
                cfg[sk] = ""
        for sk in SECRET_KEYS:                      # v2.15.4：引擎密钥和代理密码同款加密
            if cfg.get(sk):
                dec = _dpapi_unprotect(cfg[sk])
                cfg[sk] = dec if isinstance(dec, str) else ""
        if not isinstance(cfg.get("tts_voice"), str):
            cfg["tts_voice"] = ""
        if not re.match(r"^\d+x\d+([+-]-?\d+[+-]-?\d+)?$", str(cfg.get("geometry", ""))):
            cfg["geometry"] = DEFAULTS["geometry"]
        return cfg

    def _on_tk_error(self, exc, val, tb):
        import traceback
        text = "".join(traceback.format_exception(exc, val, tb))
        log_crash(text)
        self.status.configure(text="发生内部错误，详见 %s" % CRASH_LOG)

    def _tray_alive(self):
        return getattr(self, "tray", None) is not None and self.tray.is_running()

    def _hide_to_tray(self, tip=True):
        """藏到托盘（withdraw，任务栏不留窗口，点托盘图标找回）。没有托盘返回 False。"""
        if not self._tray_alive():
            return False
        self.root.withdraw()
        if tip and self.cfg.get("tray_tip", True) and not self.cfg.get("tray_tip_shown"):
            # 第一次隐藏时弹一次气泡，告诉用户程序没退出、在哪找回
            self.cfg["tray_tip_shown"] = True
            try:
                self.tray.notify(APP_TITLE, "已隐藏到托盘。单击托盘图标显示窗口，右键可切换取词选项或退出。")
            except Exception:
                pass                # 气泡只是提示，失败不能影响隐藏窗口
            self._save()
        return True

    def hide_window(self, tip=True):
        # v2.10：「点 ×」选了「最小化到任务栏」→ 直接最小化，窗口留在任务栏；
        # 否则有托盘时隐藏到托盘；没托盘时才最小化——旧版 withdraw 后没有托盘图标，
        # 窗口就找不回来了。
        if self.cfg.get("close_action", "taskbar") == "taskbar":
            self.root.iconify()
        elif not self._hide_to_tray(tip):
            self.root.iconify()

    def _start_minimized(self):
        try:
            self.root.iconify()
        except Exception:
            pass

    def minimize_to_taskbar(self):
        """v2.13：主窗口「— 最小化」按钮：无条件缩到任务栏（点任务栏图标还原），
        不受「点 ×」「点 – 最小化」设置影响；同时收起气泡 / 小窗口 / 设置窗口，免得它们留在桌面上。"""
        try:
            self.bubble.close()
            self.mini.close()
            self.settings_win.withdraw()
        except Exception:
            pass
        try:
            self.root.iconify()
        except Exception:
            pass

    def _on_close_taskbar(self):
        """主窗口「点 × 最小化到任务栏」勾选框：勾上 = 点 × 缩到任务栏；取消 = 回到隐藏到托盘。"""
        self.close_cb.set(CLOSE_NAMES["taskbar" if self.close_taskbar_var.get() else "tray"])
        self._save()

    def _sync_close_taskbar(self):
        try:
            self.close_taskbar_var.set(CLOSE_CODES.get(self.close_cb.get(), "tray") == "taskbar")
        except Exception:
            pass

    def _on_unmap(self, e):
        """点标题栏「–」最小化时：设置里选了「收进托盘」就把窗口藏进托盘（默认留在任务栏）。"""
        if e.widget is not self.root or self.cfg.get("minimize_action", "taskbar") != "tray":
            return
        self.root.after(30, self._minimize_to_tray)

    def _minimize_to_tray(self):
        try:
            if self.root.state() == "iconic" and self._tray_alive():
                self._hide_to_tray(tip=True)
        except Exception:
            pass

    def _on_close(self):
        # 点 ×：按「高级设置 → 常规」里的选择：直接退出 / 最小化到任务栏 / 隐藏到托盘
        # （真正退出走托盘右键菜单 / 主界面「退出」按钮）
        if self.cfg.get("close_action", "taskbar") == "quit":
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

    @property
    def hotkey_window_label(self):
        try:
            return hotkey_label(self.cfg.get("hotkey_window", DEFAULT_HOTKEYS["hotkey_window"]))
        except ValueError:
            return WINDOW_LABEL

    @property
    def hotkey_clip_label(self):
        try:
            return hotkey_label(self.cfg.get("hotkey_clip", DEFAULT_HOTKEYS["hotkey_clip"]))
        except ValueError:
            return CLIP_LABEL

    def _refresh_tray_state(self):
        """把当前选项拍成快照给托盘菜单读（托盘线程不能碰 Tk），并更新托盘提示文字。"""
        try:
            self._tray_snap = {
                "top": self.top_var.get(), "watch": self.watch_var.get(),
                "pointer": self.pointer_var.get(), "hover": self.hover_var.get(),
                "typing": self.typing_var.get(),
                "input": bool(self.cfg.get("input_translate", False)),
                "scope": SCOPE_CODES.get(self.scope_cb.get(), "word"),
                "auto_off": self.auto_off_var.get(),
                "history_on": self.history_on_var.get(),
                "autostart": self.auto_var.get() if hasattr(self, "auto_var") else False,
                "hotkey_main": self.hotkey_main_label,
                "hotkey_pointer": self.hotkey_pointer_label,
                "hotkey_shot": self.hotkey_shot_label,
                "hotkey_replace": self.hotkey_replace_label,
                "hotkey_clip": self.hotkey_clip_label,
                "hotkey_window": self.hotkey_window_label,
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
                   "typing": ("typing_var", "_on_typing_opt"),
                   "input": ("input_var", "_on_input_opt"),
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
        elif cid == "compare":
            self.show_window()
            self.open_compare(self._get_clip())
        elif cid == "window":
            # 从托盘菜单点的时候指针在任务栏上：给 3 秒把指针移到目标菜单 / 窗口
            self.window_translate(delay_ms=3000)
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
        # v2.13：按钮 / 选项行现在会自动折行，最小宽度只要放得下「最宽的那一个控件」和两个下拉框行，
        # 不再被一整排按钮撑到 900 像素（小屏放不下）。
        try:
            self.root.update_idletasks()
            top, eng_frame = self._fit_rows[0], self._fit_rows[1]
            need = max([top.winfo_reqwidth(), eng_frame.winfo_reqwidth()]
                       + [f.min_width() for f in self._flows]) + 2 * 12 + 4
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            min_w = min(max(380, need), sw - 40)
            self.root.minsize(min_w, min(360, sh - 80))
            m = re.match(r"^(\d+)x(\d+)(.*)$", str(self.root.geometry()))
            if m and int(m.group(1)) < min_w:
                self.root.geometry("%dx%d%s" % (min_w, int(m.group(2)), m.group(3)))
            for f in self._flows:
                f.relayout()
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
        # v2.13：字体按「本机实际装了哪个」挑（Windows 雅黑 / macOS 苹方 / Linux 思源·文泉驿…），
        # 不再写死名字；ttk 主题、表格行高按系统和字号适配
        fam, base_size = ui_platform.ui_family(self.root), ui_platform.base_size()
        if self.cfg.get("apple_theme", True):
            fam = ui_platform.pick_family(self.root, ui_platform.APPLE_FONT_CANDIDATES[ui_platform.os_key()], fallback=fam)
        self._mono_family = ui_platform.mono_family(self.root)
        # v2.6 界面字号：默认 11（设置 → 常规里 10~18 可调，改完立刻生效）
        size = int(self.cfg.get("font_size", 11))
        self._font_family = fam
        font = (fam, size)
        ui_font = (fam, max(8, size - 1))

        self.font, self.ui_font = font, ui_font
        root = self.root
        style = ttk.Style()
        ui_platform.pick_theme(style)
        ui_platform.apply_styles(root, fam, size)

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
            eng_frame, values=ENGINES, state="readonly", width=11)
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

        ttk.Label(f1, text="原文", style="Title.TLabel").pack(anchor="w", pady=(4, 0))
        box, self.src = self._text_with_scroll(f1, height=3, font=font, undo=True)
        box.pack(fill="both", expand=True, pady=(2, 6))
        self.src.bind("<<Modified>>", self._on_modified)
        self.src.bind("<Control-Return>", self._on_ctrl_enter)   # Ctrl+Enter 立即翻译，不用等 0.35 秒

        row = ttk.Frame(f2)
        row.pack(fill="x")
        ttk.Label(row, text="译文", style="Title.TLabel").pack(side="left")
        self.status = ttk.Label(row, text="", foreground="#5b6676")
        self.status.pack(side="right")
        box2, self.dst = self._text_with_scroll(f2, height=3, font=font, state="disabled")
        box2.pack(fill="both", expand=True, pady=(2, 6))
        self.dst.tag_configure("src", foreground="#6b7380")
        # v2.6 词典区：平时隐藏；只有 Google 引擎、单个词或短词组且响应里真有
        # 词典/注音时才显示（见 _update_dict_area）。
        self.dict_frame = ttk.Frame(f2)
        self.dict_label = ttk.Label(self.dict_frame, text="", foreground="#5b6676",
                                    font=ui_font, wraplength=560, justify="left")
        self.dict_label.pack(fill="x")

        # —— 按钮 ——
        btns = ui_platform.FlowFrame(root)           # v2.13：放不下自动折行，不再把右边的按钮裁掉
        btns.pack(fill="x", padx=12, pady=(2, 0))
        B = lambda text, cmd: btns.add(ttk.Button(btns, text=text, command=cmd))      # noqa: E731
        btns.add(ttk.Button(btns, text="复制译文", command=self.copy_result, style="Accent.TButton"))
        B("复制原文", self.copy_source)
        B("🔊 原文", self.speak_source)
        B("🔊 译文", self.speak_result)
        B("清空", self.clear)
        B("网络检查", self.open_netcheck)
        B("离线语言包…", self._show_offline_packs)
        B("导入语言包…", self._import_packs)
        B("⚖ 多引擎对照", self.open_compare)
        B("Aa 命名格式", self.open_case_tool)
        B("🧹 去格式", self.clean_source)
        B("截图翻译", self.start_screenshot)
        B("翻译文档…", self._translate_doc_file)
        B("翻译图片…", self._translate_image_file)
        B("粘贴图片翻译", self._translate_clipboard_image)
        B("🎤 语音输入", self.start_voice_input)
        B("—  最小化", self.minimize_to_taskbar)      # v2.13：一键最小化到任务栏（不受「关闭 ×」设置影响）
        B("退出", self.quit)
        # v2.11：整窗翻译 / 实时刷新 / 悬停整窗等进阶功能放在「高级设置 → 取词」，主窗口保持简洁；
        # 这一行平时是空的，只在文档翻译进行中显示「取消翻译」。
        btns2 = ttk.Frame(root)
        btns2.pack(fill="x", padx=12)
        self.doc_cancel_btn = ttk.Button(btns2, text="取消翻译", command=self._cancel_doc)
        self.live_var = tk.BooleanVar(value=False)
        self.live_int_var = tk.StringVar(value=str(self.cfg.get("live_interval", 5)))

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
        # v2.14 打字检测翻译（默认关闭；开关/停顿/范围，见高级设置 → 取词）
        self.typing_var = tk.BooleanVar(value=bool(self.cfg.get("typing", False)))
        self.typing_pause_var = tk.IntVar(value=int(self.cfg.get("typing_pause_ms", 1000)))
        self.typing_scope_var = tk.StringVar(
            value=TYPING_SCOPE_NAMES.get(self.cfg.get("typing_scope", "word"), "单词"))
        self._hover_dedupe = HoverDedupe()
        self.spinner_var = tk.BooleanVar(value=bool(self.cfg.get("grab_spinner", True)))
        self.hover_mod_var = tk.BooleanVar(value=bool(self.cfg.get("hover_need_ctrl", False)))
        self.hover_win_var = tk.BooleanVar(value=bool(self.cfg.get("hover_window", False)))
        self.tray_tip_var = tk.BooleanVar(value=bool(self.cfg.get("tray_tip", True)))
        self.history_on_var = tk.BooleanVar(value=bool(self.cfg.get("history_on", True)))
        self.history_reuse_var = tk.BooleanVar(value=bool(self.cfg.get("history_reuse", False)))
        self.history_max_var = tk.IntVar(value=int(self.cfg.get("history_max", 2000)))
        self.tts_rate_var = tk.IntVar(value=int(self.cfg.get("tts_rate", 0)))
        self.tts_voice_var = tk.StringVar(value=self.cfg.get("tts_voice", "") or "")
        self.tts_voice_names = []       # 下拉框里显示的语音名（v2.9，Windows 才有内容）
        self.proxy_enabled_var = tk.BooleanVar(value=bool(self.cfg.get("proxy_enabled", False)))
        self.proxy_host_var = tk.StringVar(value=self.cfg.get("proxy_host", ""))
        self.proxy_port_var = tk.StringVar(
            value=str(self.cfg.get("proxy_port", 0)) if self.cfg.get("proxy_port") else "")
        self.proxy_user_var = tk.StringVar(value=self.cfg.get("proxy_user", ""))
        self.proxy_pass_var = tk.StringVar(value=self.cfg.get("proxy_pass", ""))
        self.auto_copy_var = tk.BooleanVar(value=bool(self.cfg.get("auto_copy", False)))
        self.font_size_var = tk.IntVar(value=int(self.cfg.get("font_size", 11)))
        self.dark_var = tk.BooleanVar(value=bool(self.cfg.get("dark_mode", False)))
        set_cute(self.cfg.get("cute_theme", False))
        self.cute_var = tk.BooleanVar(value=bool(self.cfg.get("cute_theme", False)))
        self.apple_var = tk.BooleanVar(value=bool(self.cfg.get("apple_theme", True)))
        self.pet_bubble_var = tk.BooleanVar(value=bool(self.cfg.get("pet_bubble", True)))
        self.update_auto_var = tk.BooleanVar(value=bool(self.cfg.get("update_auto", True)))
        self._stt_busy = False
        self._replace_hwnd = 0
        self._doc_path = ""
        self._doc_bytes = None

        opts = ttk.LabelFrame(root, text="常用", padding=(8, 4))
        opts.pack(fill="x", padx=12, pady=(8, 0))

        o1 = ui_platform.FlowFrame(opts)
        o1.pack(fill="x")
        o1.add(ttk.Checkbutton(o1, text="窗口置顶", variable=self.top_var, command=self._on_top))
        o1.add(ttk.Checkbutton(o1, text="监听剪贴板", variable=self.watch_var, command=self._on_watch))
        o1.add(ttk.Checkbutton(o1, text="中英智能互译", variable=self.smart_var, command=self._retranslate))
        o1.add(ttk.Checkbutton(o1, text="双语对照", variable=self.bi_var, command=self._on_bilingual))
        o1.add(ttk.Checkbutton(o1, text="显示原文", variable=self.show_src_var, command=self._on_show_src))
        # v2.13：点 × 时最小化到任务栏（和高级设置 → 常规里的下拉框同步；以前只藏在设置里，找不到）
        self.close_taskbar_var = tk.BooleanVar(value=self.cfg.get("close_action", "taskbar") == "taskbar")
        o1.add(ttk.Checkbutton(o1, text="点 × 最小化到任务栏", variable=self.close_taskbar_var,
                               command=self._on_close_taskbar))
        if IS_WIN:      # v2.13.2：开机自启放到主窗口，勾上后开机自动缩在任务栏
            o1.add(ttk.Checkbutton(o1, text="开机自动缩在任务栏", variable=self.auto_var,
                                   command=self._on_autostart))

        o2 = ui_platform.FlowFrame(opts)
        o2.pack(fill="x", pady=(2, 0))
        o2.add(ttk.Checkbutton(o2, text="指针取词", variable=self.pointer_var, command=self._on_pointer_opt))
        o2.add(ttk.Checkbutton(o2, text="悬停取词", variable=self.hover_var, command=self._on_pointer_opt))
        # v2.11：「跟随指针的小窗口」以前只能在高级设置的下拉框里选，这里放一个开关（和下拉框同步）
        self.mini_follow_var = tk.BooleanVar(value=self.cfg.get("popup_mode") == "mini")
        o2.add(ttk.Checkbutton(o2, text="小窗跟随指针", variable=self.mini_follow_var,
                               command=self._on_mini_follow))
        o2.add(ttk.Button(o2, text="生词本", command=self.open_vocab))
        self.fav_btn = ttk.Button(o2, text="☆ 收藏", command=self.favorite_current)
        o2.add(self.fav_btn)
        o2.add(ttk.Button(o2, text="翻译历史…", command=self.open_history))
        o2.add(ttk.Button(o2, text="高级设置…", command=self.open_settings))
        self._flows = (btns, o1, o2)

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
        ui_platform.fit_window(win, 660, 600, 440, 400, parent=self.root)     # v2.13：按屏幕收缩、居中
        win.protocol("WM_DELETE_WINDOW", self.close_settings)
        win.bind("<Escape>", lambda e: self.close_settings())
        try:
            if IS_WIN:
                win.iconbitmap(resource_path("app.ico"))
        except Exception:
            pass
        self.settings_win = win

        # v2.15.4：搜索设置（输入关键字，回车 / 选中结果就跳到那一页并高亮）
        sbar = ttk.Frame(win)
        sbar.pack(fill="x", padx=10, pady=(10, 0))
        ttk.Label(sbar, text="🔍").pack(side="left")
        self.settings_search_var = tk.StringVar()
        ent = ttk.Entry(sbar, textvariable=self.settings_search_var)
        ent.pack(side="left", fill="x", expand=True, padx=(4, 6))
        self.settings_search_entry = ent
        self.settings_search_hint = ttk.Label(sbar, text="搜索设置（Ctrl+F）", style="Note.TLabel")
        self.settings_search_hint.pack(side="left")
        self.settings_results = tk.Listbox(win, height=0, activestyle="none", relief="flat",
                                           highlightthickness=1, exportselection=False)
        self.settings_search_var.trace_add("write", lambda *_: self._settings_search())
        ent.bind("<Return>", lambda e: self._settings_search_go(0))
        ent.bind("<Down>", lambda e: (self.settings_results.focus_set(),
                                      self.settings_results.selection_set(0)) if self.settings_results.size() else None)
        ent.bind("<Escape>", lambda e: (self.settings_search_var.set(""), "break")[1])
        self.settings_results.bind("<Return>", lambda e: self._settings_search_go())
        self.settings_results.bind("<Double-Button-1>", lambda e: self._settings_search_go())
        self.settings_results.bind("<ButtonRelease-1>", lambda e: self._settings_search_go())
        win.bind("<Control-f>", lambda e: (ent.focus_set(), ent.select_range(0, "end")))
        self._settings_hits = []

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=10, pady=(8, 4))
        nb.enable_traversal()          # Ctrl+Tab / Ctrl+Shift+Tab 切页
        nb.bind("<<NotebookTabChanged>>", lambda e: self._remember_settings_tab())
        self.settings_nb = nb
        self.settings_tabs = {}

        def tab(key, title):
            # v2.13：每页放进可滚动容器——小屏 / 大字号 / 高缩放下内容比窗口高时可以滚，不再被截断
            sf = ui_platform.ScrollFrame(nb, padding=14)
            nb.add(sf, text=title)
            self.settings_tabs[key] = sf
            cur["tab"] = key
            return sf.body

        self._settings_index = []          # (tab_key, widget, 文字) 供搜索
        self._settings_deps = []           # (控件列表, 条件函数) 依赖关系置灰
        cur = {"tab": None}

        def section(parent, title, first=False):
            """分组小标题（苹果偏好设置式）：灰色粗体 + 细分隔线。"""
            if not first:
                ttk.Separator(parent).pack(fill="x", pady=(16, 6))
            lab = ttk.Label(parent, text=title, style="Section.TLabel")
            lab.pack(anchor="w", pady=(0 if first else 0, 2))
            self._settings_index.append((cur["tab"], lab, title))
            return lab

        def check(parent, text, var, cmd, note=None):
            cb = ttk.Checkbutton(parent, text=text, variable=var, command=cmd)
            cb.pack(anchor="w", pady=(6, 0))
            self._settings_index.append((cur["tab"], cb, text + " " + (note or "")))
            if note:
                lab = ttk.Label(parent, text=note, style="Note.TLabel", wraplength=500,
                                justify="left")
                lab.pack(anchor="w", padx=(26, 0))
                ui_platform.autowrap(lab, pad=60)
            return cb

        # 常规
        f = tab("general", "常规")
        section(f, "窗口", first=True)
        check(f, "窗口置顶", self.top_var, self._on_top, "翻译窗口始终显示在其他窗口上面。")
        if IS_WIN:
            check(f, "开机自启（自动缩在任务栏）", self.auto_var, self._on_autostart,
                  "登录 Windows 后自动运行，并直接缩在任务栏，点任务栏图标即可打开，不打扰你。")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Label(row, text="点窗口右上角 ×：").pack(side="left")
        self.close_cb = ttk.Combobox(row, values=list(CLOSE_NAMES.values()), state="readonly", width=10)
        self.close_cb.set(CLOSE_NAMES.get(self.cfg.get("close_action", "taskbar"), "最小化到任务栏"))
        self.close_cb.pack(side="left")
        self.close_cb.bind("<<ComboboxSelected>>", lambda e: (self._sync_close_taskbar(), self._save()))
        ttk.Label(f, text="选「隐藏到托盘」时程序继续在后台运行，快捷键和取词照常可用；"
                          "选「最小化到任务栏」时窗口缩到任务栏、点任务栏图标就能还原（Esc 也一样）；"
                          "没有托盘图标（被安全软件拦截）时「隐藏到托盘」会改为最小化。",
                  style="Note.TLabel", wraplength=500, justify="left").pack(anchor="w", padx=(0, 0), pady=(2, 0))
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(10, 0))
        ttk.Label(row, text="点窗口 – 最小化：").pack(side="left")
        self.min_cb = ttk.Combobox(row, values=list(MINIMIZE_NAMES.values()), state="readonly", width=10)
        self.min_cb.set(MINIMIZE_NAMES.get(self.cfg.get("minimize_action", "taskbar"), "留在任务栏"))
        self.min_cb.pack(side="left")
        self.min_cb.bind("<<ComboboxSelected>>", lambda e: self._save())
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Label(row, text="界面字号：").pack(side="left")
        sp = ttk.Spinbox(row, from_=10, to=18, increment=1, width=5,
                         textvariable=self.font_size_var, command=self._on_font_size)
        sp.pack(side="left")
        sp.bind("<Return>", lambda e: self._on_font_size())
        sp.bind("<FocusOut>", lambda e: self._on_font_size())
        ttk.Label(row, text="（10 ~ 18，改完立刻生效：原文 / 译文框、气泡 / 小窗口都跟着变）",
                  style="Note.TLabel").pack(side="left", padx=6)
        section(f, "外观")
        check(f, "深色外观", self.dark_var, self._on_dark_mode,
              "主窗口、设置、历史、气泡 / 小窗口换成深色；默认是浅色，不勾就是今天的样子。")
        check(f, "萌系配色（粉彩）", self.cute_var, self._on_cute_theme,
              "把浅色外观换成柔和的粉彩配色；和「深色外观」同时勾选时以深色为准。")
        check(f, "苹果风格（macOS 质感：浅灰底、白卡片、系统蓝按钮）", self.apple_var, self._on_apple_theme)
        # v2.14：桌面小宠物
        section(f, "桌面小宠物")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(10, 0))
        ttk.Label(row, text="桌面小宠物：").pack(side="left")
        self.pet_mode_cb = ttk.Combobox(row, state="readonly", width=18, values=list(pet_catalog.PET_MODES.values()))
        self.pet_mode_cb.set(pet_catalog.PET_MODES.get(self.cfg.get("pet_mode", "minimized"), ""))
        self.pet_mode_cb.pack(side="left")
        self.pet_mode_cb.bind("<<ComboboxSelected>>", lambda e: self._on_pet_opt())
        self.pet_cb = ttk.Combobox(row, state="readonly", width=12, values=[pet_catalog.pet_display(p) for p in pet_catalog.pet_ids()])
        self.pet_cb.set(pet_catalog.pet_display(self.cfg.get("pet_id", pet_catalog.DEFAULT_PET)))
        self.pet_cb.pack(side="left", padx=6)
        self.pet_cb.bind("<<ComboboxSelected>>", lambda e: self._on_pet_opt())
        check(f, "译好后用气泡显示译文（宠物显示时）", self.pet_bubble_var, self._on_pet_opt,
              "小宠物会跟着翻译状态变化：复制文字时惊讶、翻译中思考、译好开心、失败难过、久不用会睡着。"
              "点它打开翻译窗口，双击翻译剪贴板，右键换宠物。")
        section(f, "备份与迁移")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(6, 0))
        ttk.Button(row, text="导出设置…", command=self._export_settings).pack(side="left")
        ttk.Button(row, text="导入设置…", command=self._import_settings).pack(side="left", padx=6)
        ttk.Label(row, text="设置存成一个 JSON 文件（含术语表和自定义快捷键，不含任何密码）。导入前会先全量校验，有问题的不应用。",
                  style="Note.TLabel", wraplength=420, justify="left").pack(side="left", padx=8)

        # 翻译
        f = tab("translate", "翻译")
        section(f, "翻译方式", first=True)
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
        row.pack(anchor="w", pady=(10, 0))
        ttk.Label(row, text="译文风格：").pack(side="left")
        self.style_cb = ttk.Combobox(row, state="readonly", width=8, values=list(translator_tools.STYLES.values()))
        self.style_cb.set(translator_tools.STYLES.get(self.cfg.get("translate_style", "default"), "默认"))
        self.style_cb.pack(side="left")
        self.style_cb.bind("<<ComboboxSelected>>", lambda e: self._on_style())
        ttk.Label(row, text="（目前 DeepL 支持正式 / 口语；其他引擎不受影响）", style="Note.TLabel").pack(side="left", padx=6)

        section(f, "需要 Key 的引擎")
        ttk.Label(f, text="填好后在主窗口「引擎」里选它；也会作为「自动」模式的最后兜底。"
                          "Key 只存在本机（加密保存），导出设置时不带出。",
                  style="Note.TLabel", wraplength=520, justify="left").pack(anchor="w")
        self.key_vars = {k: tk.StringVar(value=self.cfg.get(k, "")) for k in ENGINE_KEY_FIELDS}
        self.key_status = {}
        for eng, fields, url in (
                ("DeepL", (("deepl_key", "API Key", True),), "https://www.deepl.com/pro-api"),
                ("百度", (("baidu_appid", "APPID", False), ("baidu_key", "密钥", True)), "https://fanyi-api.baidu.com/"),
                ("有道", (("youdao_appid", "应用 ID", False), ("youdao_key", "应用密钥", True)), "https://ai.youdao.com/")):
            row = ttk.Frame(f)
            row.pack(anchor="w", fill="x", pady=(6, 0))
            ttk.Label(row, text=eng, width=6, style="Title.TLabel").pack(side="left")
            for key, label, secret in fields:
                ttk.Label(row, text=label + "：").pack(side="left", padx=(6, 0))
                ttk.Entry(row, textvariable=self.key_vars[key], width=24 if len(fields) == 1 else 14,
                          show="•" if secret else "").pack(side="left")
            ttk.Button(row, text="测试", width=5, command=lambda e=eng: self._test_engine_key(e)).pack(side="left", padx=(8, 0))
            ttk.Button(row, text="申请…", width=6, command=lambda u=url: webbrowser.open(u)).pack(side="left", padx=(4, 0))
            st = ttk.Label(row, text="", style="Note.TLabel")
            st.pack(side="left", padx=6)
            self.key_status[eng] = st
            self._settings_index.append((cur["tab"], row, "%s Key 密钥 APPID 引擎" % eng))
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(6, 0))
        ttk.Button(row, text="保存 Key", command=self._save_engine_keys).pack(side="left")
        ttk.Button(row, text="清除全部 Key", command=self._clear_engine_keys).pack(side="left", padx=6)
        self._refresh_key_status()

        section(f, "朗读")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(6, 0))
        ttk.Label(row, text="朗读语速：").pack(side="left")
        sp = ttk.Spinbox(row, from_=-10, to=10, increment=1, width=5,
                         textvariable=self.tts_rate_var, command=self._on_tts_rate)
        sp.pack(side="left")
        sp.bind("<Return>", lambda e: self._on_tts_rate())
        sp.bind("<FocusOut>", lambda e: self._on_tts_rate())
        ttk.Label(row, text="（-10 最慢 ~ 10 最快，0 是默认语速；朗读只在 Windows 上可用）",
                  style="Note.TLabel").pack(side="left", padx=6)
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(10, 0))
        ttk.Label(row, text="朗读语音：").pack(side="left")
        self.tts_voice_cb = ttk.Combobox(row, textvariable=self.tts_voice_var,
                                         state="readonly", width=32)
        self.tts_voice_cb.pack(side="left")
        self.tts_voice_cb.bind("<<ComboboxSelected>>", lambda e: self._on_tts_voice())
        ttk.Label(row, text="（只在 Windows 上有；选了就记住，重启仍生效）",
                  style="Note.TLabel").pack(side="left", padx=6)
        section(f, "术语表")
        ttk.Label(f, text="专有名词按固定译文翻，每行一对，原文 = 译文：",
                  style="Note.TLabel").pack(anchor="w", pady=(2, 2))
        self.glossary_text = tk.Text(f, height=4, font=self.ui_font, wrap="none")
        self.glossary_text.pack(fill="x")
        self._refresh_glossary_text()
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(6, 0))
        ttk.Button(row, text="保存术语表", command=self._save_glossary).pack(side="left")
        ttk.Button(row, text="导入…", command=self._import_glossary).pack(side="left", padx=6)
        ttk.Button(row, text="导出…", command=self._export_glossary).pack(side="left")
        ttk.Label(row, text="最多 200 对，每词不超过 40 字；空着就是没有术语表，翻译和今天一样。导入会替换掉现在的术语表。",
                  style="Note.TLabel").pack(side="left", padx=8)

        # 取词
        f = tab("grab", "取词")
        section(f, "取词方式", first=True)
        check(f, "监听剪贴板", self.watch_var, self._on_watch, "复制文字后自动翻译并显示主窗口。")
        self.pointer_check_btn = check(
            f, "指针取词（%s）" % self.hotkey_pointer_label, self.pointer_var, self._on_pointer_opt,
            "把鼠标放在文字上按快捷键，取到指针处的文字并翻译（按钮、菜单上的字也能取）。")
        check(f, "悬停取词（鼠标停住自动取词）", self.hover_var, self._on_pointer_opt,
              "鼠标在文字、按钮、菜单上停住后自动取词；鼠标压在本程序的原文 / 译文框或弹窗上时不触发。")
        hover_deps = []
        hover_deps.append(check(f, "取词时在指针旁显示「取词中…」提示", self.spinner_var, self._on_spinner_opt,
              "识别 / 复制超过 0.25 秒才出现，结果一到就消失；不会被截进识别图，也不挡鼠标点击。"))
        hover_deps.append(check(f, "只在按住 Ctrl 时悬停取词", self.hover_mod_var, self._on_hover_mod,
              "开了以后鼠标随便停不会弹词，按住 Ctrl 再停住才取词；适合长时间阅读、不想被打扰。"))
        hover_deps.append(check(f, "悬停时翻译整个窗口（代替取词）", self.hover_win_var, self._on_pointer_opt,
              "开启「悬停取词」后，鼠标在菜单 / 窗口上停住就整窗翻译（用下面的悬停等待，最少 1.2 秒）；"
              "同一个窗口只翻一次，指针离开再回来才会重翻。"))
        hover_deps.pop(0)                   # 加载提示对指针取词也有用，不依赖悬停
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Label(row, text="取词范围：").pack(side="left")
        self.scope_cb = ttk.Combobox(row, values=list(SCOPE_NAMES.values()), state="readonly", width=8)
        self.scope_cb.set(SCOPE_NAMES[self.cfg.get("pointer_scope", "word")])
        self.scope_cb.pack(side="left")
        self.scope_cb.bind("<<ComboboxSelected>>", lambda e: self._on_pointer_opt())
        ttk.Label(row, text="（悬停取词和指针取词共用）", style="Note.TLabel").pack(side="left", padx=6)
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(10, 0))
        ttk.Label(row, text="悬停等待：").pack(side="left")
        sp = ttk.Spinbox(row, from_=300, to=3000, increment=100, width=7,
                         textvariable=self.hover_ms_var, command=self._on_hover_ms)
        sp.pack(side="left")
        hover_deps.append(sp)
        self._settings_deps.append((hover_deps, lambda: bool(self.hover_var.get())))
        sp.bind("<Return>", lambda e: self._on_hover_ms())
        sp.bind("<FocusOut>", lambda e: self._on_hover_ms())
        ttk.Label(row, text="毫秒（300 ~ 3000，鼠标停住多久后自动取词）", style="Note.TLabel").pack(side="left", padx=6)

        # —— v2.14 打字检测翻译：在别的软件里打字时自动翻译 ——
        section(f, "打字检测翻译")
        # v2.15：专业版功能。未激活且试用已用完时开关置灰，只能点「升级到专业版」。
        self.typing_check = check(f, "打字检测翻译（在别的软件里打字时自动翻译）", self.typing_var, self._on_typing_opt,
              "默认关闭。主触发是打字过程中：每打完一个词（空格 / 标点 / 回车分隔）就立即翻译"
              "刚打完的词/句；正在打的当前词每多打一个字符就用约 250 毫秒防抖跟进，同一气泡内"
              "实时更新译文；停顿 1 秒只作兜底。开启后重启生效；关闭时立即停监听、清空缓冲。"
              "密码框 / 终端窗口 / 敏感内容（验证码、身份证号、API 密钥等）不翻译，缓冲只放内存，"
              "绝不写盘、不写日志、不进历史。")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(8, 0))
        ttk.Button(row, text="升级到专业版…", command=self._show_license_dialog).pack(side="left")
        ttk.Label(row, text="专业版解锁打字检测翻译；首次可免费试用 7 天。",
                  style="Note.TLabel").pack(side="left", padx=6)
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(10, 0))
        ttk.Label(row, text="打字范围：").pack(side="left")
        self.typing_scope_cb = ttk.Combobox(row, values=list(TYPING_SCOPE_NAMES.values()),
                                            textvariable=self.typing_scope_var,
                                            state="readonly", width=8)
        self.typing_scope_cb.pack(side="left")
        self.typing_scope_cb.bind("<<ComboboxSelected>>", lambda e: self._on_typing_opt())
        ttk.Label(row, text="（单词：按词翻；整句：按句翻）", style="Note.TLabel").pack(side="left", padx=6)
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(10, 0))
        ttk.Label(row, text="停顿兜底：").pack(side="left")
        sp = ttk.Spinbox(row, from_=500, to=3000, increment=100, width=7,
                         textvariable=self.typing_pause_var, command=self._on_typing_pause)
        sp.pack(side="left")
        sp.bind("<Return>", lambda e: self._on_typing_pause())
        sp.bind("<FocusOut>", lambda e: self._on_typing_pause())
        ttk.Label(row, text="毫秒（500 ~ 3000，打完停住多久后兜底翻译；主触发是按词即翻，不等停顿）",
                  style="Note.TLabel").pack(side="left", padx=6)
        self.typing_status_label = ttk.Label(
            f, text=self._typing_status_text(), style="Note.TLabel", wraplength=540, justify="left")
        self.typing_status_label.pack(anchor="w", pady=(6, 0))

        # —— v2.11 整窗翻译（进阶）：整个菜单 / 对话框 / 软件窗口一次翻完 ——
        section(f, "输入翻译（打完一句，替换成译文）")
        self.input_var = tk.BooleanVar(value=bool(self.cfg.get("input_translate", False)))
        check(f, "输入翻译：在任意输入框里打一句，按触发键就把它替换成译文", self.input_var, self._on_input_opt,
              "适合聊天 / 写邮件时用母语打字、直接发出外语。只替换本句（回车或切换窗口后重新开始）；"
              "密码框 / 终端 / 敏感内容不翻。替换时会临时借用剪贴板，0.4 秒后还原。和打字检测共用一个键盘监听。")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(6, 0))
        ttk.Label(row, text="触发键：").pack(side="left")
        self.input_trigger_cb = ttk.Combobox(row, state="readonly", width=26,
                                             values=[v for k, v in translator_tools.INPUT_TRIGGERS.items() if k != "ctrl_enter"])
        self.input_trigger_cb.set(translator_tools.INPUT_TRIGGERS.get(self.cfg.get("input_trigger", "space3"),
                                                                     translator_tools.INPUT_TRIGGERS["space3"]))
        self.input_trigger_cb.pack(side="left")
        self.input_trigger_cb.bind("<<ComboboxSelected>>", lambda e: self._on_input_opt())
        ttk.Label(row, text="（中文输入法下请先上屏再按；Windows 以外只放进剪贴板）", style="Note.TLabel").pack(side="left", padx=6)

        section(f, "整窗翻译")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(6, 0))
        ttk.Button(row, text="整窗翻译（3 秒后翻指针下的窗口）",
                   command=lambda: self._settings_then(lambda: self.window_translate(delay_ms=3000))
                   ).pack(side="left")
        ttk.Label(row, text="或按 %s" % self.hotkey_window_label, style="Note.TLabel").pack(side="left", padx=8)
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(8, 0))
        ttk.Checkbutton(row, text="实时刷新", variable=self.live_var,
                        command=lambda: self._settings_then(self._on_live_toggle)).pack(side="left")
        lcb = ttk.Combobox(row, textvariable=self.live_int_var, values=["5", "10", "15", "30"], width=3)
        lcb.pack(side="left", padx=(8, 0))
        lcb.bind("<<ComboboxSelected>>", lambda e: self._on_live_interval())
        lcb.bind("<Return>", lambda e: self._on_live_interval())
        ttk.Label(row, text="秒（每隔几秒重新翻译）", style="Note.TLabel").pack(side="left", padx=6)
        ttk.Label(f, text="实时刷新：译文层点击穿透，可以照常操作下面的软件；再按整窗热键或取消勾选停止。",
                  style="Note.TLabel", wraplength=500, justify="left").pack(anchor="w", pady=(2, 0))

        section(f, "结果显示")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(6, 0))
        ttk.Label(row, text="取词结果显示：").pack(side="left")
        self.popup_cb = ttk.Combobox(row, values=list(POPUP_NAMES.values()), state="readonly", width=24)
        self.popup_cb.set(POPUP_NAMES.get(self.cfg.get("popup_mode", "bubble"), POPUP_NAMES["bubble"]))
        self.popup_cb.pack(side="left")
        self.popup_cb.bind("<<ComboboxSelected>>", lambda e: self._on_popup_opt())
        ttk.Label(f, text="气泡：出现在指针旁，移开就消失；小窗口：固定大小、一直跟着指针走；"
                          "不弹窗：不显示任何弹窗，译文写进主窗口和历史。",
                  style="Note.TLabel", wraplength=540, justify="left").pack(anchor="w", pady=(2, 0))
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(8, 0))
        ttk.Label(row, text="小窗口大小：宽").pack(side="left")
        self.mini_w_var = tk.IntVar(value=int(self.cfg.get("mini_w", 320)))
        self.mini_h_var = tk.IntVar(value=int(self.cfg.get("mini_h", 110)))
        mini_deps = []
        for var, key, unit in ((self.mini_w_var, "mini_w", "　高"), (self.mini_h_var, "mini_h", "")):
            lo, hi, _dv = MINI_SIZE[key]
            sp = ttk.Spinbox(row, from_=lo, to=hi, increment=10, width=5, textvariable=var,
                             command=self._on_mini_size)
            mini_deps.append(sp)
            sp.pack(side="left", padx=(2, 0))
            sp.bind("<Return>", lambda e: self._on_mini_size())
            sp.bind("<FocusOut>", lambda e: self._on_mini_size())
            if unit:
                ttk.Label(row, text=unit).pack(side="left", padx=(8, 0))
        ttk.Label(row, text="像素（宽 160~800，高 60~500）", style="Note.TLabel").pack(side="left", padx=6)
        ttk.Button(row, text="预览", command=self._preview_mini).pack(side="left")
        self._settings_deps.append((mini_deps, lambda: self.cfg.get("popup_mode", "bubble") == "mini"))

        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Label(row, text="截图翻译结果：").pack(side="left")
        self.shot_cb = ttk.Combobox(row, values=list(SHOT_NAMES.values()), state="readonly", width=12)
        self.shot_cb.set(SHOT_NAMES.get(self.cfg.get("shot_mode", "overlay"), SHOT_NAMES["overlay"]))
        self.shot_cb.pack(side="left")
        self.shot_cb.bind("<<ComboboxSelected>>", lambda e: self._save())
        ttk.Label(row, text="（Ctrl+Alt+S 框选后，译文直接盖在截图的原文位置上）", style="Note.TLabel").pack(side="left", padx=6)

        # 历史
        f = tab("history", "历史")
        section(f, "翻译记录", first=True)
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
        ttk.Label(row, text="条（超出时自动删最旧的；收藏的不会被删）", style="Note.TLabel").pack(side="left", padx=6)
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Button(row, text="打开翻译历史…", command=self.open_history).pack(side="left")
        ttk.Button(row, text="导出全部…", command=lambda: self._hist_export(None)).pack(side="left", padx=8)
        ttk.Button(row, text="清空历史（保留收藏）", command=self._hist_clear).pack(side="left")
        self.hist_info = ttk.Label(f, text="", style="Note.TLabel")
        self.hist_info.pack(anchor="w", pady=(10, 0))
        self._hist_update_info()

        # 托盘
        f = tab("tray", "托盘")
        section(f, "托盘", first=True)
        self.tray_state_label = ttk.Label(f, text="", style="Note.TLabel")
        self.tray_state_label.pack(anchor="w")
        check(f, "第一次隐藏到托盘时提示一次", self.tray_tip_var, self._save,
              "只在第一次弹出气泡，告诉你程序没退出、去哪里找回。")
        ttk.Label(f, text="托盘图标右键菜单：", font=self.ui_font).pack(anchor="w", pady=(16, 2))
        ttk.Label(f, text="显示主窗口 / 截图翻译 / 翻译剪贴板内容\n"
                          "指针取词、悬停取词、取词范围（可直接开关、切换）\n"
                          "监听剪贴板、窗口置顶、断网自动离线、开机自启\n"
                          "高级设置 / 网络检查 / 离线语言包 / 退出",
                  style="Note.TLabel", justify="left").pack(anchor="w", padx=(12, 0))
        ttk.Label(f, text="单击托盘图标显示主窗口。", style="Note.TLabel").pack(anchor="w", pady=(8, 0))

        # 离线与网络
        f = tab("offline", "离线与网络")
        section(f, "离线翻译与网络检查", first=True)
        ttk.Label(f, text="离线语言包让你在没有网络时也能翻译；网络检查帮你判断是哪个翻译引擎连不上。",
                  style="Note.TLabel", wraplength=500, justify="left").pack(anchor="w")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(14, 0))
        ttk.Button(row, text="网络检查", command=self.open_netcheck).pack(side="left")
        ttk.Button(row, text="离线语言包…", command=self._show_offline_packs).pack(side="left", padx=8)
        ttk.Label(f, text="「断网时自动改用离线翻译」的开关在「翻译」页。",
                  style="Note.TLabel").pack(anchor="w", pady=(10, 0))
        # v2.9：代理（只影响 Google / 微软在线翻译引擎）
        section(f, "代理（在线翻译引擎用）")
        check(f, "使用代理服务器", self.proxy_enabled_var, self._on_proxy,
              "公司 / 学校网络需要代理才能上网时勾上；不勾就和今天一样直连。")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(8, 0))
        ttk.Label(row, text="地址：").pack(side="left")
        proxy_deps = [ttk.Entry(row, textvariable=self.proxy_host_var, width=24)]
        proxy_deps[-1].pack(side="left")
        ttk.Label(row, text="端口：").pack(side="left", padx=(8, 0))
        proxy_deps.append(ttk.Entry(row, textvariable=self.proxy_port_var, width=7))
        proxy_deps[-1].pack(side="left")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(6, 0))
        ttk.Label(row, text="账号：").pack(side="left")
        proxy_deps.append(ttk.Entry(row, textvariable=self.proxy_user_var, width=16))
        proxy_deps[-1].pack(side="left")
        ttk.Label(row, text="密码：").pack(side="left", padx=(8, 0))
        proxy_deps.append(ttk.Entry(row, textvariable=self.proxy_pass_var, width=16, show="*"))
        proxy_deps[-1].pack(side="left")
        self._settings_deps.append((proxy_deps, lambda: bool(self.proxy_enabled_var.get())))
        ttk.Button(row, text="保存", command=self._on_proxy).pack(side="left", padx=8)
        ttk.Label(f, text="只影响 Google / 微软在线翻译引擎；离线翻译、检查更新、语言包下载不走这个代理。"
                          "密码只存本机，导出设置时不带出。",
                  style="Note.TLabel", wraplength=500, justify="left").pack(anchor="w", pady=(4, 0))

        # 关于
        f = tab("about", "快捷键与关于")
        section(f, "关于", first=True)
        ttk.Label(f, text="%s v%s" % (APP_TITLE, __version__), font=self.ui_font).pack(anchor="w")
        self.about_hotkey_label = ttk.Label(f, text="", justify="left")
        self.about_hotkey_label.pack(anchor="w", pady=(10, 0))
        self._refresh_hotkey_labels()

        section(f, "自定义全局快捷键")
        ttk.Label(f, text="和别的软件冲突时可以在这里改：", style="Note.TLabel").pack(anchor="w", pady=(0, 2))
        self.hotkey_main_var = tk.StringVar(value=self.hotkey_main_label)
        self.hotkey_pointer_var = tk.StringVar(value=self.hotkey_pointer_label)
        self.hotkey_shot_var = tk.StringVar(value=self.hotkey_shot_label)
        self.hotkey_replace_var = tk.StringVar(value=self.hotkey_replace_label)
        self.hotkey_clip_var = tk.StringVar(value=self.hotkey_clip_label)
        self.hotkey_window_var = tk.StringVar(value=self.hotkey_window_label)
        for text, var, presets in (
                ("翻译选中的文字：", self.hotkey_main_var,
                 ["Ctrl+Alt+T", "Ctrl+Shift+T", "Alt+Shift+T", "Ctrl+Alt+Q", "Ctrl+Shift+Q", "Win+Alt+T"]),
                ("指针取词：", self.hotkey_pointer_var,
                 ["Ctrl+Alt+D", "Ctrl+Shift+D", "Alt+Shift+D", "Ctrl+Alt+P", "Ctrl+Shift+P", "Win+Alt+D"]),
                ("截图翻译：", self.hotkey_shot_var,
                 ["Ctrl+Alt+S", "Ctrl+Shift+S", "Alt+Shift+S", "Ctrl+Alt+A", "Ctrl+Shift+A", "Win+Alt+S"]),
                ("翻译并替换原文：", self.hotkey_replace_var,
                 ["Ctrl+Alt+R", "Ctrl+Shift+R", "Alt+Shift+R", "Ctrl+Alt+Y", "Ctrl+Shift+Y", "Win+Alt+R"]),
                ("粘贴图片翻译：", self.hotkey_clip_var,
                 ["Ctrl+Shift+V", "Ctrl+Alt+V", "Alt+Shift+V", "Ctrl+Shift+B", "Win+Alt+V"]),
                ("整窗翻译：", self.hotkey_window_var,
                 ["Ctrl+Alt+W", "Ctrl+Shift+W", "Alt+Shift+W", "Ctrl+Alt+M", "Win+Alt+W"])):
            row = ttk.Frame(f)
            row.pack(anchor="w", pady=(4, 0))
            ttk.Label(row, text=text, width=16).pack(side="left")
            ttk.Combobox(row, textvariable=var, values=presets, width=16).pack(side="left")
        row = ttk.Frame(f)
        row.pack(anchor="w", pady=(10, 0))
        ttk.Button(row, text="保存快捷键", command=self._save_hotkeys).pack(side="left")
        ttk.Label(row, text="保存后重启程序生效（热键注册只在启动时做一次）。",
                  style="Note.TLabel").pack(side="left", padx=8)
        section(f, "更新")
        row = ttk.Frame(f)
        row.pack(anchor="w")
        ttk.Button(row, text="检查更新", command=self._check_update_manual).pack(side="left")
        self.update_label = ttk.Label(row, text="当前版本 v%s" % __version__,
                                      style="Note.TLabel")
        self.update_label.pack(side="left", padx=8)
        check(f, "每天启动时自动检查更新", self.update_auto_var, self._save,
              "每天只查一次；有新版才告诉你，从不自动下载、从不自动安装。")
        section(f, "安装与卸载")
        row = ttk.Frame(f)
        row.pack(anchor="w")
        self.uninst_btn = ttk.Button(row, text="卸载程序…", command=self._run_uninstaller)
        self.uninst_btn.pack(side="left")
        ttk.Button(row, text="打开数据文件夹", command=lambda: open_folder(DATA_DIR)).pack(side="left", padx=6)
        ttk.Label(row, text=install_info_text(), style="Note.TLabel", wraplength=420,
                  justify="left").pack(side="left", padx=8)
        if not find_uninstaller():
            self.uninst_btn.state(["disabled"])
        section(f, "诊断信息")
        row = ttk.Frame(f)
        row.pack(anchor="w")
        ttk.Button(row, text="复制诊断信息", command=self._copy_diag_info).pack(side="left")
        ttk.Label(row, text="一键复制版本号、系统版本、DPI 缩放、OCR 是否可用和各热键注册状态；"
                            "报「某个热键没反应」时直接把这段贴出来定位，不用来回问。",
                  style="Note.TLabel", wraplength=420, justify="left").pack(side="left", padx=8)

        bar = ttk.Frame(win)
        bar.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(bar, text="恢复默认设置", command=self._reset_settings).pack(side="left")
        ttk.Button(bar, text="关闭", command=self.close_settings, style="Accent.TButton").pack(side="right")
        ttk.Label(bar, text="勾选项改完立即生效；带「保存」按钮的（术语表 / 代理 / 快捷键）要点保存。",
                  style="Note.TLabel").pack(side="left", padx=10)
        # 标签页文字也进搜索索引
        for key, sf in self.settings_tabs.items():
            self._settings_index.append((key, None, nb.tab(sf, "text")))
        self._refresh_settings_deps()

    # ------------------------------------------------ v2.15.4 高级设置：搜索 / 依赖置灰 / 记住页签
    @staticmethod
    def _settings_match(index, query, limit=12):
        """纯函数：在 [(tab, widget, text)] 里找含所有关键字（空格分隔、不区分大小写）的项。"""
        q = [w for w in (query or "").lower().split() if w]
        if not q:
            return []
        out = []
        for item in index:
            t = (item[2] or "").lower()
            if all(w in t for w in q):
                out.append(item)
                if len(out) >= limit:
                    break
        return out

    def _settings_search(self):
        lb = self.settings_results
        q = self.settings_search_var.get()
        self._settings_hits = self._settings_match(self._settings_index, q)
        lb.delete(0, "end")
        names = {k: self.settings_nb.tab(sf, "text") for k, sf in self.settings_tabs.items()}
        for key, _w, text in self._settings_hits:
            first = text.split("  ")[0].split("（")[0].strip()
            first = first if len(first) <= 34 else first[:34] + "…"
            lb.insert("end", "%s  ›  %s" % (names.get(key, ""), first))
        if self._settings_hits:
            lb.configure(height=min(6, len(self._settings_hits)))
            if not lb.winfo_ismapped():
                lb.pack(fill="x", padx=10, pady=(4, 0), before=self.settings_nb)
            self.settings_search_hint.configure(text="%d 项" % len(self._settings_hits))
        else:
            lb.pack_forget()
            self.settings_search_hint.configure(text="没有找到" if q.strip() else "搜索设置（Ctrl+F）")

    def _settings_search_go(self, idx=None):
        lb = self.settings_results
        if idx is None:
            sel = lb.curselection()
            idx = sel[0] if sel else 0
        if not (0 <= idx < len(self._settings_hits)):
            return
        key, w, _t = self._settings_hits[idx]
        if key in self.settings_tabs:
            self.settings_nb.select(self.settings_tabs[key])
        if w is not None:
            self.root.after(60, lambda: self._settings_flash(key, w))

    def _settings_flash(self, key, w):
        """滚到目标控件并闪一下（ttk 控件切到 focus 态 + 前景色短暂变蓝）。"""
        sf = self.settings_tabs.get(key)
        try:
            sf.update_idletasks()
            total = max(1, sf.body.winfo_height())
            y = w.winfo_rooty() - sf.body.winfo_rooty()
            sf.canvas.yview_moveto(max(0.0, (y - 40) / float(total)))
        except Exception:
            pass
        try:
            w.focus_set()
        except Exception:
            pass
        try:
            st = w.cget("style") or ""
            w.configure(style="Found." + (st.split(".")[-1] if st else w.winfo_class()))
            self.root.after(1200, lambda: w.configure(style=st))
        except Exception:
            pass

    def _refresh_settings_deps(self):
        """依赖关系：没开悬停取词时悬停相关选项置灰；不用代理时代理输入框置灰；
        不是小窗口模式时小窗口大小置灰。"""
        for widgets, cond in getattr(self, "_settings_deps", []):
            try:
                on = bool(cond())
            except Exception:
                on = True
            for w in widgets:
                try:
                    w.state(["!disabled"] if on else ["disabled"])
                except Exception:
                    pass
        try:
            lab = getattr(self, "tray_state_label", None)
            if lab is not None:
                lab.configure(text="托盘状态：" + ("✅ 运行中" if self._tray_alive() else
                              "❌ 没有托盘图标（详细原因见 %TEMP%\\RealtimeTranslate_tray.log）"))
        except Exception:
            pass

    def _remember_settings_tab(self):
        try:
            cur = self.settings_nb.select()
            for k, sf in self.settings_tabs.items():
                if str(sf) == cur:
                    self.cfg["settings_tab"] = k
        except Exception:
            pass

    def open_settings(self, tab=None):
        win = self.settings_win
        self._refresh_tts_voices()   # 打开设置时才枚举已安装语音，不拖慢启动
        self._refresh_typing_ui()    # v2.15：每次打开设置都按授权状态刷新打字检测开关
        if tab is None:
            tab = self.cfg.get("settings_tab")        # v2.15.4：回到上次看的那一页
        if tab in self.settings_tabs:
            self.settings_nb.select(self.settings_tabs[tab])
        g = ui_platform.clamp_geometry(self.cfg.get("settings_geometry") or "", win.winfo_screenwidth(),
                                       win.winfo_screenheight()) if self.cfg.get("settings_geometry") else None
        if g:
            try:
                win.geometry(g)
            except Exception:
                pass
        self._refresh_settings_deps()
        win.deiconify()
        win.lift()
        win.attributes("-topmost", True)
        if not self.top_var.get():
            win.after(300, lambda: win.attributes("-topmost", False))
        win.focus_force()

    def _settings_then(self, fn):
        """从高级设置里点整窗翻译 / 实时刷新：先收起设置窗口（别挡住目标），再执行。"""
        try:
            self.settings_win.withdraw()
        except Exception:
            pass
        fn()

    def close_settings(self):
        try:
            self.cfg["settings_geometry"] = self.settings_win.geometry()
            self._remember_settings_tab()
            self.settings_search_var.set("")
            self._save()
        except Exception:
            pass
        self.settings_win.withdraw()

    def _on_mini_follow(self):
        """主窗口的「小窗跟随指针」开关：开 = 取词结果用跟随指针的小窗口，关 = 气泡。"""
        self.popup_cb.set(POPUP_NAMES["mini" if self.mini_follow_var.get() else "bubble"])
        self._on_popup_opt()

    def _on_popup_opt(self):
        self.root.after(0, self._refresh_settings_deps)
        self._save()
        if hasattr(self, "mini_follow_var"):
            self.mini_follow_var.set(self.cfg.get("popup_mode") == "mini")
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
                     "%s　截图翻译（框选屏幕任意区域）\n%s　翻译并替换原文（选中文字翻完直接替换回原处）\n"
                     "%s　粘贴图片翻译（剪贴板里的图片 → 系统 OCR → 翻译）\n"
                     "%s　整窗翻译（指针放在菜单 / 窗口上，整个窗口一次翻完）\nEsc　隐藏窗口 / 关闭气泡"
                     % (self.hotkey_main_label, self.hotkey_pointer_label,
                        self.hotkey_shot_label, self.hotkey_replace_label, self.hotkey_clip_label,
                        self.hotkey_window_label))
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
                         ("hotkey_replace", self.hotkey_replace_var),
                         ("hotkey_clip", self.hotkey_clip_var),
                         ("hotkey_window", self.hotkey_window_var)):
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
            self.hotkey_clip_var.set(self.hotkey_clip_label)
            self.hotkey_window_var.set(self.hotkey_window_label)
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
        try:                                    # v2.13：表格行高 / 按钮字体跟着字号走，按钮行重新折行
            ui_platform.apply_styles(self.root, fam, size)
            if self.cfg.get("apple_theme", True):
                self._apply_theme()
            self._fit_min_width()
        except Exception:
            pass
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

    def _refresh_tts_voices(self):
        """朗读语音下拉框：列 Windows 已安装的语音（v2.9）。

        下拉框显示的是语音名；「系统默认语音」一项对应配置里的空串。
        非 Windows 上 tts_win.list_voices() 返回 []，下拉框只留
        「系统默认语音」一项；本机没有语音时也一样，绝不报错。
        """
        names = []
        try:
            if tts_win is not None:
                names = [v.get("name", "") for v in tts_win.list_voices()
                         if v.get("name")]
        except Exception:
            names = []
        self.tts_voice_names = names
        cur = (self.cfg.get("tts_voice", "") or "").strip()
        self.tts_voice_cb["values"] = ["系统默认语音"] + names
        self.tts_voice_var.set(cur if cur in names else "系统默认语音")

    def _on_tts_voice(self):
        """朗读语音改了就保存（下拉框显示「系统默认语音」时存空串）。"""
        v = self.tts_voice_var.get().strip()
        self.cfg["tts_voice"] = "" if v == "系统默认语音" else v
        self._save()

    # ------------------------------------------------ v2.15.4 需要 Key 的引擎
    def _save_engine_keys(self, quiet=False):
        for k, v in self.key_vars.items():
            self.cfg[k] = v.get().strip()
        set_engine_keys(self.cfg)
        self._save()
        self._refresh_key_status()
        if not quiet:
            self.status.configure(text="引擎 Key 已保存")

    def _clear_engine_keys(self):
        if not messagebox.askyesno("清除 Key", "清除 DeepL / 百度 / 有道 的全部 Key？", parent=self.settings_win):
            return
        for v in self.key_vars.values():
            v.set("")
        self._save_engine_keys(quiet=True)
        if self.engine.get() in KEY_ENGINES:
            self.engine.set("自动")
            self._save()

    def _refresh_key_status(self):
        for eng, lab in getattr(self, "key_status", {}).items():
            try:
                lab.configure(text="已填写" if engine_configured(eng) else "未填写")
            except Exception:
                pass

    def _test_engine_key(self, eng):
        """先保存，再用 hello 试翻一次；在后台线程里跑，结果回到 Tk 线程显示。"""
        self._save_engine_keys(quiet=True)
        lab = self.key_status.get(eng)
        if not engine_configured(eng):
            lab.configure(text="❌ 还没填完")
            return
        lab.configure(text="测试中…")

        def job():
            try:
                _tl.online_deadline = time.monotonic() + 12
                out = _engine_call(eng, "hello", "en", "zh-CN")[0]
                msg = "✅ 可用：hello → %s" % out[:16]
            except Exception as e:      # noqa: BLE001
                msg = "❌ " + (str(e) if isinstance(e, EngineKeyError) else netcheck.explain_error(e)[0])[:60]
            finally:
                _tl.online_deadline = None
            self.q.put(("key_test", eng, msg))
        threading.Thread(target=job, daemon=True).start()

    def _on_proxy(self):
        self.root.after(0, self._refresh_settings_deps)
        """代理设置改了就保存并立刻生效（不用重启）。"""
        try:
            port = int((self.proxy_port_var.get() or "").strip() or 0)
        except Exception:
            port = 0
        self.cfg["proxy_enabled"] = bool(self.proxy_enabled_var.get())
        self.cfg["proxy_host"] = self.proxy_host_var.get().strip()
        self.cfg["proxy_port"] = max(0, min(port, 65535))
        self.cfg["proxy_user"] = self.proxy_user_var.get().strip()
        self.cfg["proxy_pass"] = self.proxy_pass_var.get()
        self.proxy_port_var.set(str(self.cfg["proxy_port"])
                                if self.cfg["proxy_port"] else "")
        self._save()

    # ------------------------------------------------ v2.7 深色外观
    def popup_colors(self):
        """气泡 / 小窗口用的颜色（深色时跟主题走，浅色就是原来的米白）。"""
        return theme_colors(bool(self.cfg.get("dark_mode", False)))

    def _snapshot_colors(self):
        """记下浅色下各文本框的原始颜色：切回浅色时按原样恢复。"""
        snap = {}
        for name in ("src", "dst"):
            w = getattr(self, name, None)
            if w is not None:
                try:
                    snap[name] = (w.cget("background"), w.cget("foreground"),
                                  w.cget("insertbackground"))
                except Exception:
                    pass
        try:
            snap["root_bg"] = self.root.cget("background")
        except Exception:
            pass
        return snap

    # ------------------------------------------------ v2.14 桌面小宠物 / 萌系配色
    def _main_visible(self):
        try:
            return self.root.state() == "normal" and bool(self.root.winfo_viewable())
        except Exception:
            return True

    def _init_pet(self):
        """建桌面小宠物。任何失败都只是没有宠物，不影响翻译。"""
        self.pet = None
        self.pet_error = ""
        if pet_win is None:
            return
        try:
            pets_dir = resource_path("pets")
            hooks = {
                "show_main": self.show_window,
                "translate_clip": lambda: self._on_tray_cmd("clip"),
                "shot": lambda: self.q.put(("tray_shot",)),
                "quit": self.quit,
                "main_visible": self._main_visible,
                "get_theme": lambda: theme_colors(bool(self.cfg.get("dark_mode", False))),
                "save": self._save,
            }
            self.pet = pet_win.PetWindow(self.root, pets_dir, self.cfg, hooks)
            self.pet.start()
        except Exception as e:
            self.pet = None
            self.pet_error = str(e)

    def _pet_event(self, kind, text="", bubble=True):
        p = getattr(self, "pet", None)
        if p is not None:
            try:
                p.event(kind, text, bubble)
            except Exception:
                pass

    def _pet_msg(self, msg):
        """把程序里的消息翻成宠物的动作（只读，不改任何消息、不影响原有处理）。"""
        if getattr(self, "pet", None) is None:
            return
        try:
            kind = msg[0]
            if kind in ("hotkey", "copied"):
                self._pet_event("curious")
            elif kind == "progress":
                _, my, done, total = msg
                if my == self.seq:
                    self._pet_event("busy", "翻译中 %d/%d" % (done, total))
            elif kind == "result":
                _, my, ok, payload = msg
                if my != self.seq:
                    return
                if ok:
                    self._pet_event("done", " ".join(d for _, d in payload[0] if d))
                else:
                    self._pet_event("fail", pet_state.short_text(str(payload).split("\n")[0], 36))
            elif kind == "bubble":                    # 指针/悬停翻译：自己有弹窗，宠物只做表情
                if msg[1] == self.bseq:
                    self._pet_event("done" if msg[2] else "fail", "", bubble=False)
            elif kind == "doc_prog":
                self._pet_event("busy", "文档翻译中…")
            elif kind == "doc_done":
                self._pet_event("done" if msg[1] else "fail", "文档翻译好啦" if msg[1] else "文档翻译失败")
            elif kind in ("shot_ocr", "image_ocr", "hover_ocr"):
                self._pet_event("busy", "识别中…")
            elif kind == "dl_done":
                self._pet_event("done", "下载好啦")
        except Exception:
            pass

    def _on_pet_opt(self):
        rev = {v: k for k, v in pet_catalog.PET_MODES.items()}
        mode = rev.get(self.pet_mode_cb.get(), "minimized")
        pid = pet_catalog.pet_ids()[self.pet_cb.current()] if self.pet_cb.current() >= 0 else pet_catalog.DEFAULT_PET
        self.cfg.update(pet_mode=mode, pet_id=pid, pet_bubble=self.pet_bubble_var.get())
        self._save()
        p = getattr(self, "pet", None)
        if p is None and pet_win is not None and mode != "off":
            self._init_pet()
        elif p is not None:
            p.refresh_pet()
            if not self.pet_bubble_var.get():
                p.bubble.hide()

    def _on_spinner_opt(self):
        self.cfg["grab_spinner"] = bool(self.spinner_var.get())
        if not self.cfg["grab_spinner"]:
            self.spinner.stop()
        self._save()

    def _on_hover_mod(self):
        self.cfg["hover_need_ctrl"] = bool(self.hover_mod_var.get())
        self.hover_last = None
        self._save()

    def _on_apple_theme(self):
        self.cfg["apple_theme"] = self.apple_var.get()
        if not self.apple_var.get():
            try:                         # 关掉后回到系统原生主题
                ui_platform.pick_theme(ttk.Style())
                ui_platform.apply_styles(self.root, self._font_family, int(self.cfg.get("font_size", 11)))
            except Exception:
                pass
        self._apply_theme()
        self._save()

    def _on_cute_theme(self):
        self.cfg["cute_theme"] = self.cute_var.get()
        set_cute(self.cute_var.get())
        self._apply_theme()
        self._save()

    def _on_dark_mode(self):
        self.cfg["dark_mode"] = self.dark_var.get()
        self._apply_theme()
        self._save()

    def _apply_apple_theme(self, dark):
        """v2.15.1 苹果风格：整套 ttk 换成 clam 自定义样式，文本框变白色卡片。成功返回 True。"""
        try:
            fam = getattr(self, "_font_family", None) or ui_platform.ui_family(self.root)
            size = int(self.cfg.get("font_size", 11))
            p = ui_platform.apply_apple_style(self.root, fam, size, dark)
        except Exception:
            return False
        try:
            self.root.configure(background=p["bg"])
        except Exception:
            pass
        for name in ("src", "dst", "hist_detail", "net_txt"):
            w = getattr(self, name, None)
            if w is not None:
                ui_platform.style_text_apple(w, p)
        lb = getattr(self, "settings_results", None)
        if lb is not None:
            try:
                lb.configure(background=p["card"], foreground=p["fg"], selectbackground=p["accent"],
                             selectforeground=p["accent_fg"], highlightbackground=p["border"],
                             highlightcolor=p["accent"], borderwidth=0)
            except Exception:
                pass
        gt = getattr(self, "glossary_text", None)
        if gt is not None:
            ui_platform.style_text_apple(gt, p)
        try:
            self.dst.tag_configure("src", foreground=p["gray"])
        except Exception:
            pass
        for w in (getattr(self, "status", None), getattr(self, "hint", None),
                  getattr(self, "engine_hint", None), getattr(self, "dict_label", None)):
            try:
                if w is not None:
                    w.configure(foreground=p["gray"])
            except Exception:
                pass
        th = theme_colors(dark)
        bub = {"bubble_bg": p["card"], "bubble_fg": p["fg"], "bubble_gray": p["gray"],
               "bubble_foot": p["gray"]}
        for pop in (getattr(self, "bubble", None), getattr(self, "mini", None)):
            try:
                if pop is not None and pop.alive():
                    pop._fill(pop.head.cget("text"), pop.body.cget("text"), False)
                    for wd, key in ((pop.head, "bubble_gray"), (pop.body, "bubble_fg"),
                                    (pop.foot, "bubble_foot")):
                        wd.configure(background=bub["bubble_bg"], foreground=bub[key])
            except Exception:
                pass
        try:
            self._fit_min_width()
        except Exception:
            pass
        try:
            self.render()
        except Exception:
            pass
        return True

    def _apply_theme(self):
        """应用当前外观：深色 / 浅色。

        覆盖：主窗口原文/译文框、状态栏与提示字、设置/历史/网络检查里的
        文本框、气泡与小窗口（下次弹出时按新主题画；正显示着的也立刻换色）。
        不覆盖：截图翻译的盖图层（它画在截图上，颜色由截图本身决定）、
        托盘图标与托盘菜单（Windows 原生菜单）、ttk 按钮与下拉框在 Windows
        原生主题（vista）下保持系统样式——这是 Tk 在 Windows 上的限制，
        强行换肤会让按钮错位，所以只换能安全换的部分。
        """
        dark = bool(self.cfg.get("dark_mode", False))
        th = theme_colors(dark)
        if self.cfg.get("apple_theme", True) and not (self.cfg.get("cute_theme") and not dark):
            if self._apply_apple_theme(dark):
                return
        try:
            ui_platform.configure_common_labels(ttk.Style(), getattr(self, "_font_family", "TkDefaultFont"),
                                                int(self.cfg.get("font_size", 11)),
                                                gray=th["gray"] if dark else "#5b6676")
            for s_ in ("Note.TLabel", "Section.TLabel"):
                ttk.Style().configure(s_, background=th["bg"])
        except Exception:
            pass
        try:
            self.root.configure(background=th["bg"])
        except Exception:
            pass
        try:
            style = ttk.Style()
            style.configure("TFrame", background=th["bg"])
            style.configure("TLabel", background=th["bg"], foreground=th["fg"])
            style.configure("TLabelframe", background=th["bg"], foreground=th["fg"])
            style.configure("TLabelframe.Label", background=th["bg"], foreground=th["fg"])
            style.configure("TNotebook", background=th["bg"])
            style.configure("TNotebook.Tab", background=th["bg"], foreground=th["fg"])
        except Exception:
            pass
        for name in ("src", "dst"):
            w = getattr(self, name, None)
            if w is None:
                continue
            try:
                if dark:
                    w.configure(background=th["text_bg"], foreground=th["text_fg"],
                                insertbackground=th["text_fg"])
                else:
                    orig = self._orig_colors.get(name)
                    if orig:
                        w.configure(background=orig[0], foreground=orig[1],
                                    insertbackground=orig[2])
            except Exception:
                pass
        try:
            self.dst.tag_configure("src", foreground=th["gray"])
        except Exception:
            pass
        for w in (getattr(self, "status", None), getattr(self, "hint", None),
                  getattr(self, "engine_hint", None)):
            try:
                if w is not None:
                    w.configure(foreground=th["gray"] if dark else "#5b6676")
            except Exception:
                pass
        for w in (getattr(self, "hist_detail", None), getattr(self, "net_txt", None)):
            try:
                if w is not None:
                    if dark:
                        w.configure(background=th["text_bg"], foreground=th["text_fg"],
                                    insertbackground=th["text_fg"])
                    else:
                        w.configure(background="#ffffff", foreground="#000000",
                                    insertbackground="#000000")
            except Exception:
                pass
        if getattr(self, "dict_label", None) is not None:
            try:
                self.dict_label.configure(foreground=th["fg"] if dark else "#000000")
            except Exception:
                pass
        for pop in (self.bubble, self.mini):
            try:
                if pop.alive():
                    pop._fill(pop.head.cget("text"), pop.body.cget("text"), False)
                    for wd, key in ((pop.head, "bubble_gray"), (pop.body, "bubble_fg"),
                                    (pop.foot, "bubble_foot")):
                        wd.configure(background=th["bubble_bg"], foreground=th[key])
            except Exception:
                pass
        try:
            self.render()
        except Exception:
            pass

    # ------------------------------------------------ v2.7 术语表
    @staticmethod
    def _parse_glossary_text(text):
        """术语表编辑框的文本 -> [[原文, 译文], ...]：每行一对，分隔符是 = 或 Tab。"""
        pairs = []
        for ln in (text or "").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            if "=" in ln:
                src, dst = ln.split("=", 1)
            elif "\t" in ln:
                src, dst = ln.split("\t", 1)
            else:
                continue
            pairs.append([src.strip(), dst.strip()])
        return pairs

    def _refresh_glossary_text(self):
        try:
            self.glossary_text.delete("1.0", "end")
            for src, dst in self.cfg.get("glossary", []):
                self.glossary_text.insert("end", "%s = %s\n" % (src, dst))
        except Exception:
            pass

    def _save_glossary(self):
        pairs = glossary.sanitize_pairs(
            self._parse_glossary_text(self.glossary_text.get("1.0", "end")))
        self.cfg["glossary"] = pairs
        glossary.set_active(pairs)
        self._refresh_glossary_text()
        self._save()
        self.status.configure(text="术语表已保存（%d 对）" % len(pairs))

    def _import_glossary(self):
        """术语表 JSON 导入（v2.8）：导入会替换掉现在的术语表。"""
        path = filedialog.askopenfilename(
            title="导入术语表", filetypes=[("JSON", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            # 稳定性：术语表文件超过 1 MB 直接拒绝，不全读进内存。
            if os.path.getsize(path) > 1 << 20:
                messagebox.showerror("导入术语表", "文件太大（超过 1 MB），已拒绝",
                                     parent=self.settings_win)
                return
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
        except Exception as e:      # noqa: BLE001
            messagebox.showerror("导入术语表", "打不开文件：%s" % e, parent=self.settings_win)
            return
        pairs, skipped, err = glossary.load_glossary_json(text)
        if err:
            messagebox.showerror("导入术语表", "文件不对：%s" % err, parent=self.settings_win)
            return
        self.cfg["glossary"] = pairs
        glossary.set_active(pairs)
        self._refresh_glossary_text()
        self._save()
        self.status.configure(text="术语表已导入 %d 对%s" % (
            len(pairs), "，跳过 %d 条重复/非法" % skipped if skipped else ""))

    def _export_glossary(self):
        """术语表 JSON 导出（v2.8）。"""
        path = filedialog.asksaveasfilename(
            title="导出术语表", initialfile="glossary.json", defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(glossary.dump_glossary_json(self.cfg.get("glossary", [])))
        except Exception as e:      # noqa: BLE001
            messagebox.showerror("导出术语表", "保存失败：%s" % e, parent=self.settings_win)
            return
        self.status.configure(text="术语表已导出 %d 对到 %s" % (
            len(self.cfg.get("glossary", [])), path))

    # ------------------------------------------------ v2.12 诊断信息 / 术语沉淀 / 对照表导出
    def _run_uninstaller(self):
        u = find_uninstaller()
        if not u:
            messagebox.showinfo("卸载", install_info_text(), parent=self.settings_win)
            return
        if not messagebox.askyesno("卸载", "确定要卸载%s吗？\n程序会先退出，然后打开卸载向导。" % APP_TITLE,
                                   parent=self.settings_win):
            return
        try:
            os.startfile(u)               # noqa: S606  卸载向导会自己请求管理员权限
        except Exception as e:
            messagebox.showerror("卸载", "无法启动卸载程序：%s" % e, parent=self.settings_win)
            return
        self.root.after(300, self.quit)   # 退出，释放互斥体和 exe 文件锁

    def _copy_diag_info(self):
        """设置 → 关于里的「复制诊断信息」：版本号、系统版本、DPI 缩放、OCR 是否可用、
        各热键注册状态，一键进剪贴板。任何一项探测失败都只写"不可用"，不弹窗、不崩。"""
        try:
            text = build_diag_text(collect_diag_info(self))
            self._set_clip(text)
            self.last_clip = text
            self.status.configure(text="诊断信息已复制到剪贴板")
        except Exception as e:      # noqa: BLE001  诊断本身绝不能拖垮主流程
            try:
                self.status.configure(text="诊断信息复制失败：%s" % str(e)[:60])
            except Exception:
                pass

    def add_glossary_pair(self, src, dst):
        """把一对原文→译文加进术语表（复用 glossary.py 的清洗与上限）。

        已有的不重复加；太长（>40 字）或为空的拒绝。成功返回 True 并保存设置，
        失败返回 False（调用方自行写状态栏，不弹窗）。"""
        src, dst = (src or "").strip(), (dst or "").strip()
        if not src or not dst:
            return False
        pairs = list(self.cfg.get("glossary", []))
        if any(s == src for s, _ in pairs):
            return False
        clean = glossary.sanitize_pairs(pairs + [[src, dst]])
        if [src, dst] not in clean:
            return False
        self.cfg["glossary"] = clean
        glossary.set_active(clean)
        try:
            self._refresh_glossary_text()
        except Exception:
            pass
        self._save()
        self.status.configure(text="已加入术语表：%s = %s" % (src, dst))
        return True

    def _export_shot_csv(self, pairs=None):
        """把整窗翻译的 (原文, 译文) 导出成 CSV 对照表（UTF-8 带 BOM，Excel 直接打开）。

        pairs 默认取最近一次整窗/截图翻译的段；取消时只写状态栏，不弹窗。"""
        if pairs is None:
            pairs = list(getattr(self, "pairs", []) or [])
        if not pairs:
            self.status.configure(text="没有可导出的整窗翻译结果")
            return
        path = filedialog.asksaveasfilename(
            title="导出对照表", initialfile="window-translate.csv", defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("所有文件", "*.*")])
        if not path:
            self.status.configure(text="已取消导出对照表")
            return
        try:
            n = export_window_pairs_csv(pairs, path)
        except Exception as e:      # noqa: BLE001  导出失败只写状态栏，不弹窗、不崩
            self.status.configure(text="导出对照表失败：%s" % str(e)[:60])
            return
        self.status.configure(text="对照表已导出 %d 行到 %s" % (n, path))

    # ------------------------------------------------ v2.7 检查更新
    def _check_update_manual(self):
        """设置页「检查更新」：一定查一次，结果写在设置页与状态栏。"""
        try:
            self.update_label.configure(text="正在检查…")
        except Exception:
            pass
        threading.Thread(target=self._update_worker, args=(True,), daemon=True).start()

    def _auto_update_check(self):
        """启动后静默检查一次：每天只查一次；没新版、查不到都不打扰。"""
        if not self.cfg.get("update_auto", True):
            return
        today = time.strftime("%Y-%m-%d")
        if self.cfg.get("update_last_check", "") == today:
            return
        threading.Thread(target=self._update_worker, args=(False,), daemon=True).start()

    def _update_worker(self, manual):
        try:
            status, tag = update_check.check(__version__)
        except Exception as e:      # noqa: BLE001
            status, tag = "error", str(e)[:200]
        self.q.put(("update_result", status, tag, manual))

    def _on_update_result(self, status, tag, manual):
        today = time.strftime("%Y-%m-%d")
        if status == "newer":
            self.cfg["update_last_check"] = today
            self._save()
            msg = "发现新版本 %s（当前 v%s），去下载？" % (tag, __version__)
            self.status.configure(text="发现新版本 %s" % tag)
            try:
                self.update_label.configure(text="发现新版本 %s" % tag)
            except Exception:
                pass
            if messagebox.askyesno("发现新版本", msg + "\n\n只打开下载页，不会自动下载或安装。",
                                   parent=self.root):
                import webbrowser
                webbrowser.open(update_check.RELEASES_URL)
        elif status == "same":
            self.cfg["update_last_check"] = today
            self._save()
            if manual:
                self.status.configure(text="已是最新版本 v%s" % __version__)
                try:
                    self.update_label.configure(text="已是最新版本 v%s" % __version__)
                except Exception:
                    pass
        elif status == "older":
            self.cfg["update_last_check"] = today
            self._save()
            if manual:
                self.status.configure(text="当前版本比已发布的更新（开发版）")
        else:  # error：静默——断网时不弹窗，手动查才在状态栏说一句
            if manual:
                self.status.configure(text="检查更新失败（网络问题），稍后再试")
                try:
                    self.update_label.configure(text="检查失败：%s" % tag)
                except Exception:
                    pass

    def _on_ctrl_enter(self, _e=None):
        """Ctrl+Enter：不等 0.35 秒防抖，立刻翻译。"""
        self.translate_now()
        return "break"

    def _export_settings(self):
        """设置导出（v2.8）：JSON 文件，含配置 + 术语表 + 自定义快捷键，不含密码。"""
        path = filedialog.asksaveasfilename(
            title="导出设置", initialfile="realtime-translate-settings.json",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(settings_io.export_settings(self.cfg))
        except Exception as e:      # noqa: BLE001
            messagebox.showerror("导出设置", "保存失败：%s" % e, parent=self.settings_win)
            return
        self.status.configure(text="设置已导出到 %s" % path)

    def _import_settings(self):
        """设置导入（v2.8）：先全量校验，失败或类型不对的项一律不应用，绝不半应用。"""
        path = filedialog.askopenfilename(
            title="导入设置", filetypes=[("JSON", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            # 稳定性：设置文件超过 1 MB 直接拒绝，不全读进内存。
            if os.path.getsize(path) > 1 << 20:
                messagebox.showerror("导入设置", "文件太大（超过 1 MB），已拒绝",
                                     parent=self.settings_win)
                return
            with open(path, "r", encoding="utf-8-sig") as f:
                text = f.read()
        except Exception as e:      # noqa: BLE001
            messagebox.showerror("导入设置", "打不开文件：%s" % e, parent=self.settings_win)
            return
        cfg, ignored, err = settings_io.import_settings(text, DEFAULTS)
        if err:
            messagebox.showerror("导入设置", "文件不对：%s\n没有应用任何设置。" % err,
                                 parent=self.settings_win)
            return
        # H-04：导入文件要改网络出口（镜像域名 / 代理）时，先把变化列给用户确认，
        # 不同意则整份设置都不导入。proxy_pass 永远不被导入（见 settings_io）。
        changes = settings_io.sensitive_import_changes(text, self.cfg, DEFAULTS)
        if changes:
            def _fmt(v):
                return "(空)" if v in ("", None) else str(v)
            detail = "\n".join("  %s：%s → %s" % (k, _fmt(a), _fmt(b)) for k, a, b in changes)
            ok = messagebox.askyesno(
                "导入设置 — 网络出口将改变",
                "这份设置文件要改动以下网络相关项（改了等于改了程序的网络出口，"
                "流量可能被引到别的服务器）：\n\n%s\n\n确定应用吗？不同意则整份设置都不导入。"
                % detail,
                parent=self.settings_win)
            if not ok:
                self.status.configure(text="已取消导入设置（网络出口未改动）")
                return
        self._apply_cfg_to_ui(cfg)
        self.status.configure(text="设置已导入%s" % (
            "，忽略了 %d 个未知 / 错误的项" % ignored if ignored else ""))

    def _apply_cfg_to_ui(self, cfg):
        """把一份已校验的配置应用到界面（v2.8 设置导入用）。

        cfg 一定是 settings_io.import_settings 返回的完整配置（以 DEFAULTS
        为底）。语言 / 引擎只认已知值，否则保持现状；其余项按 _reset_settings
        的同一套写法回填，再保存一次。
        """
        d = cfg
        # v2.15：授权状态只存本机 —— 导入设置绝不能把已激活的专业版冲回免费版
        #（import_settings 返回的 d 以 DEFAULTS 为底，license_* 都是空值）。
        lic = {k: self.cfg.get(k) for k in license.LICENSE_KEYS}
        self.cfg.update(d)
        self.cfg.update(lic)
        if d.get("sl") == "auto" or d.get("sl") in LANGS:
            self.sl.set(AUTO if d["sl"] == "auto" else lang_name(d["sl"]))
        if d.get("tl") in LANGS:
            self.tl.set(lang_name(d["tl"]))
        if d.get("engine") in ENGINES:
            self.engine.set(d["engine"])
        self.top_var.set(d["top"]); self.watch_var.set(d["watch"]); self.smart_var.set(d["smart"])
        self.bi_var.set(d["bilingual"]); self.reflow_var.set(d["reflow"]); self.show_src_var.set(d["show_src"])
        self.auto_off_var.set(d["auto_offline"]); self.pointer_var.set(d["pointer"]); self.hover_var.set(d["hover"])
        self.scope_cb.set(SCOPE_NAMES[d["pointer_scope"]])
        self.hover_ms_var.set(d["hover_ms"]); self.cfg["hover_ms"] = d["hover_ms"]
        self.hover_win_var.set(d.get("hover_window", False))
        # v2.14 打字检测翻译（设置导入时同步回填）
        self.typing_var.set(d.get("typing", False))
        self.typing_pause_var.set(d.get("typing_pause_ms", 1000))
        self.typing_scope_var.set(TYPING_SCOPE_NAMES.get(d.get("typing_scope", "word"), "单词"))
        self.cfg["typing_pause_ms"] = d.get("typing_pause_ms", 1000)
        self.cfg["typing_scope"] = d.get("typing_scope", "word")
        if getattr(self, "_typing_buffer", None) is not None:
            self._typing_buffer.set_scope(self.cfg["typing_scope"])
            self._typing_buffer.set_pause_ms(self.cfg["typing_pause_ms"])
        self.live_int_var.set(str(d.get("live_interval", 5))); self.cfg["live_interval"] = d.get("live_interval", 5)
        self.close_cb.set(CLOSE_NAMES.get(d["close_action"], CLOSE_NAMES["taskbar"])); self._sync_close_taskbar()
        self.min_cb.set(MINIMIZE_NAMES.get(d.get("minimize_action"), MINIMIZE_NAMES["taskbar"]))
        self.tray_tip_var.set(d["tray_tip"])
        self.history_on_var.set(d["history_on"]); self.history_reuse_var.set(d["history_reuse"])
        self.history_max_var.set(d["history_max"]); self.cfg["history_max"] = d["history_max"]
        self.history.max_items = d["history_max"]
        self.popup_cb.set(POPUP_NAMES[d["popup_mode"]]); self.shot_cb.set(SHOT_NAMES[d["shot_mode"]])
        self.mini_follow_var.set(d["popup_mode"] == "mini")
        self.mini_w_var.set(d["mini_w"]); self.mini_h_var.set(d["mini_h"])
        self.cfg["mini_w"], self.cfg["mini_h"] = d["mini_w"], d["mini_h"]
        self.tts_rate_var.set(d["tts_rate"]); self.cfg["tts_rate"] = d["tts_rate"]
        self.cfg["tts_voice"] = d["tts_voice"]; self._refresh_tts_voices()
        self.proxy_enabled_var.set(d["proxy_enabled"])
        self.proxy_host_var.set(d["proxy_host"])
        self.proxy_port_var.set(str(d["proxy_port"]) if d["proxy_port"] else "")
        self.proxy_user_var.set(d["proxy_user"])
        self.proxy_pass_var.set(d["proxy_pass"])
        self.auto_copy_var.set(d["auto_copy"]); self.cfg["auto_copy"] = d["auto_copy"]
        for k in HOTKEY_KEYS:
            self.cfg[k] = d[k]
        self._revert_hotkey_vars()
        self._refresh_hotkey_labels()
        self.font_size_var.set(d["font_size"]); self.cfg["font_size"] = d["font_size"]
        self._apply_font_size()
        self.dark_var.set(d["dark_mode"]); self.cfg["dark_mode"] = d["dark_mode"]
        self._apply_theme()
        self.cfg["glossary"] = list(d["glossary"])
        glossary.set_active(self.cfg["glossary"])
        self._refresh_glossary_text()
        self.update_auto_var.set(d["update_auto"]); self.cfg["update_auto"] = d["update_auto"]
        self._save()
        self._on_top(); self._on_auto_offline(); self._on_pointer_opt()
        self._on_typing_opt()
        self._on_show_src(); self._on_bilingual()

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
        self.hover_win_var.set(d.get("hover_window", False))
        # v2.14 打字检测翻译也恢复默认（关、1000 毫秒、单词）
        self.typing_var.set(d.get("typing", False))
        self.typing_pause_var.set(d.get("typing_pause_ms", 1000))
        self.typing_scope_var.set(TYPING_SCOPE_NAMES.get(d.get("typing_scope", "word"), "单词"))
        self.cfg["typing_pause_ms"] = d.get("typing_pause_ms", 1000)
        self.cfg["typing_scope"] = d.get("typing_scope", "word")
        if getattr(self, "_typing_buffer", None) is not None:
            self._typing_buffer.set_scope(self.cfg["typing_scope"])
            self._typing_buffer.set_pause_ms(self.cfg["typing_pause_ms"])
        self.live_int_var.set(str(d.get("live_interval", 5))); self.cfg["live_interval"] = d.get("live_interval", 5)
        self.close_cb.set(CLOSE_NAMES.get(d["close_action"], CLOSE_NAMES["taskbar"])); self._sync_close_taskbar()
        self.min_cb.set(MINIMIZE_NAMES.get(d.get("minimize_action"), MINIMIZE_NAMES["taskbar"]))
        self.tray_tip_var.set(d["tray_tip"])
        self.history_on_var.set(d["history_on"]); self.history_reuse_var.set(d["history_reuse"])
        self.history_max_var.set(d["history_max"]); self.cfg["history_max"] = d["history_max"]
        self.history.max_items = d["history_max"]
        self.popup_cb.set(POPUP_NAMES[d["popup_mode"]]); self.shot_cb.set(SHOT_NAMES[d["shot_mode"]])
        self.mini_follow_var.set(d["popup_mode"] == "mini")
        self.mini_w_var.set(d["mini_w"]); self.mini_h_var.set(d["mini_h"])
        self.cfg["mini_w"], self.cfg["mini_h"] = d["mini_w"], d["mini_h"]
        # v2.5：朗读语速、自动复制、自定义快捷键也恢复默认
        self.tts_rate_var.set(d["tts_rate"]); self.cfg["tts_rate"] = d["tts_rate"]
        # v2.9：朗读语音、代理也恢复默认
        for k in ("proxy_enabled", "proxy_host", "proxy_port", "proxy_user",
                  "proxy_pass", "tts_voice"):
            self.cfg[k] = d[k]
        self._refresh_tts_voices()
        self.proxy_enabled_var.set(d["proxy_enabled"])
        self.proxy_host_var.set(d["proxy_host"])
        self.proxy_port_var.set(str(d["proxy_port"]) if d["proxy_port"] else "")
        self.proxy_user_var.set(d["proxy_user"])
        self.proxy_pass_var.set(d["proxy_pass"])
        self.auto_copy_var.set(d["auto_copy"]); self.cfg["auto_copy"] = d["auto_copy"]
        for k in HOTKEY_KEYS:
            self.cfg[k] = d[k]
        self._revert_hotkey_vars()
        self._refresh_hotkey_labels()
        # v2.6：界面字号也恢复默认并立刻应用
        self.font_size_var.set(d["font_size"]); self.cfg["font_size"] = d["font_size"]
        self._apply_font_size()
        # v2.7：深色外观、术语表、自动检查更新也恢复默认
        self.dark_var.set(d["dark_mode"]); self.cfg["dark_mode"] = d["dark_mode"]
        self._apply_theme()
        self.cfg["glossary"] = list(d["glossary"])
        glossary.set_active(self.cfg["glossary"])
        self._refresh_glossary_text()
        self.update_auto_var.set(d["update_auto"]); self.cfg["update_auto"] = d["update_auto"]
        self._on_top(); self._on_auto_offline(); self._on_pointer_opt()
        self._on_typing_opt()
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
        ui_platform.fit_window(win, 800, 560, 520, 380, parent=self.root)
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
        ttk.Label(top, text="搜索原文或译文…").pack(side="left")
        self.hist_q = tk.StringVar()
        ent = ttk.Entry(top, textvariable=self.hist_q)
        ent.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="✕", width=2,
                   command=lambda: self.hist_q.set("")).pack(side="left")
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
        # v2.8：搜索由纯函数 filter_history 在内存里筛（整个 query 当一个子串，
        # 大小写不敏感），再和「只看收藏」「只看单词」叠加；SQL 只按收藏筛。
        rows = self.history.search("", self.hist_fav.get(), limit=1000)
        rows = history_store.filter_history(rows, self.hist_q.get())
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
            filetypes=[("CSV（Excel 可打开）", "*.csv"), ("Markdown（按日期分组）", "*.md"),
                       ("文本", "*.txt"), ("JSON", "*.json"),
                       ("Anki（只导单词 .tsv）", "*.tsv")])
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
        elif eng in KEY_ENGINES and not engine_configured(eng):
            self.engine_hint.configure(text="还没填 Key：高级设置 → 翻译 → 需要 Key 的引擎")
        elif eng in ENGINE_HINTS:
            last = _auto_state.get("last_ok") if eng == "自动" else None
            self.engine_hint.configure(text=ENGINE_HINTS[eng] + ("（当前：%s）" % last if last else ""))
        else:
            self.engine_hint.configure(text="Google 免费端点" + ("" if offline_engine.runtime_present() else " · 点「离线语言包…」可下载离线组件"))

    # ------------------------------------------------ 在线安装离线翻译组件（标准版）
    @staticmethod
    def _rt_preset_label(replace):
        """镜像替换串属于哪个预设（下拉框显示用）；手动填的返回 ''（不属于任何预设）。"""
        for label, val in runtime_installer.MIRROR_PRESETS:
            if val == (replace or ""):
                return label
        return ""

    def _rt_preset_selected(self, _event=None):
        for label, val in runtime_installer.MIRROR_PRESETS:
            if label == self.rt_mirror_preset.get():
                self.rt_mirror.set(val)
                return

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
        ui_platform.fit_window(win, 640, 270, 420, 240, parent=self.root)
        win.transient(self.root)
        self.rt_win = win
        self.rt_busy, self.rt_cancel = True, False
        self._rt_closed = False          # 2.15.8：用户在取消中强行关了窗口就记下来，后台装完不再弹对话框
        self._rt_speed = {"label": None, "t": 0.0, "done": 0, "v": 0.0}
        _l = ttk.Label(win, text="正在下载离线翻译组件（numpy、ctranslate2 等）。下载中途断网可再次点击，会接着下。",
                       wraplength=580)
        _l.pack(anchor="w", padx=12, pady=(14, 6))
        ui_platform.autowrap(_l)
        self.rt_bar = ttk.Progressbar(win, mode="determinate", maximum=100)
        self.rt_bar.pack(fill="x", padx=12)
        self.rt_msg = ttk.Label(win, text="正在连接 PyPI …", foreground="#5b6676", wraplength=580)
        self.rt_msg.pack(anchor="w", padx=12, pady=(4, 6))
        ui_platform.autowrap(self.rt_msg)
        mrow = ttk.Frame(win)
        mrow.pack(fill="x", padx=12)
        ttk.Label(mrow, text="镜像").pack(side="left")
        self.rt_mirror_preset = tk.StringVar(value=self._rt_preset_label(self.cfg.get("pack_mirror", "")))
        _preset = ttk.Combobox(mrow, textvariable=self.rt_mirror_preset, state="readonly",
                               values=[label for label, _ in runtime_installer.MIRROR_PRESETS], width=38)
        _preset.pack(side="left", padx=(6, 0))
        _preset.bind("<<ComboboxSelected>>", self._rt_preset_selected)
        self.rt_mirror = tk.StringVar(value=self.cfg.get("pack_mirror", ""))
        _entry = ttk.Entry(mrow, textvariable=self.rt_mirror)
        _entry.pack(side="left", fill="x", expand=True, padx=6)
        _entry.bind("<KeyRelease>",
                    lambda _e: self.rt_mirror_preset.set(self._rt_preset_label(self.rt_mirror.get())))
        ttk.Label(win, text="下载慢时选个镜像（只换轮子下载地址，查询仍走 PyPI）；也可手动填，如 files.pythonhosted.org=镜像域名",
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
        self._rt_closed = False
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
                    cancelled=lambda: self.rt_cancel,
                    status=lambda s: self.q.put(("rt_prog", -1, 0, s, 0, 0)))
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
            if self.rt_cancel:
                # 2.15.8：已经在取消中了，再点一次（或点右上角 ×）就直接关窗口，
                # 不用干等后台线程；后台是 daemon 线程，随程序退出结束；装完不再弹对话框。
                self._rt_closed = True
                if self._rt_alive():
                    self.rt_win.destroy()
            else:
                self.rt_cancel = True
                self.rt_msg.configure(text="正在取消…（已下载的部分会保留）")
                self.rt_btn.configure(text="关闭")
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
            if getattr(self, "_rt_closed", False):
                return          # 2.15.8：用户在取消中强行关了窗口，别再自动弹语言包对话框
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
        # 布局修复（2026-11-21）：表格 height=10 时会把底下按钮行顶出 440 高的
        # 默认窗口，用户点不到「导入语言包…」。表格改矮、窗口加高，按钮固定可见。
        ui_platform.fit_window(win, 680, 520, 460, 420, parent=self.root)
        win.transient(self.root)
        self.pack_win = win
        _l = ttk.Label(win, text="离线翻译使用 Argos 语言包（.argosmodel），在本机运行，不联网、不上传文字。",
                       wraplength=520)
        _l.pack(anchor="w", padx=12, pady=(12, 4))
        ui_platform.autowrap(_l)
        cols = ("pair", "ver", "src", "state")
        tv = ttk.Treeview(win, columns=cols, show="headings", height=6)
        for c, t, w in (("pair", "翻译方向", 120), ("ver", "版本", 70), ("src", "来源", 90), ("state", "状态", 220)):
            tv.heading(c, text=t)
            tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True, padx=12, pady=4)
        self.pack_tv = tv
        self.pack_msg = ttk.Label(win, text="", foreground="#5b6676", wraplength=520)
        self.pack_msg.pack(anchor="w", padx=12)
        ui_platform.autowrap(self.pack_msg)
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
        # 既可从离线语言包对话框点，也可从主窗口直接点：对话框没打开时，
        # 文件选择框挂到主窗口，进度和结果走主窗口状态栏，不依赖 pack_win。
        pack_win = getattr(self, "pack_win", None)
        parent = pack_win if (pack_win is not None and pack_win.winfo_exists()) else self.root
        paths = filedialog.askopenfilenames(
            parent=parent, title="选择语言包",
            filetypes=[("Argos 语言包", "*.argosmodel *.zip"), ("所有文件", "*.*")])
        if not paths:
            return
        if parent is pack_win:
            self.pack_msg.configure(text="正在导入，请稍候…（语言包较大时需要几秒）")
        else:
            self.status.configure(text="正在导入语言包，请稍候…（语言包较大时需要几秒）")

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
        if ok:
            msg_ok = "已导入：" + "、".join(ok) + "。"
        else:
            msg_ok = ""
        if getattr(self, "pack_win", None) and self.pack_win.winfo_exists():
            msg = msg_ok
            if bad:
                msg += "\n失败：\n" + "\n".join(bad)
            self.pack_msg.configure(text=msg or "")
        else:
            # 从主窗口直接导入：结果走主窗口状态栏，失败再弹窗报明原因。
            if bad:
                self.status.configure(text="导入语言包失败：" + "；".join(bad))
                messagebox.showerror("导入语言包", "失败：\n" + "\n".join(bad),
                                     parent=self.root)
            elif ok:
                self.status.configure(text=msg_ok)
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
        ui_platform.fit_window(win, 720, 580, 480, 400, parent=self.root)
        win.transient(self.root)
        self.dl_win = win
        self.dl_best = {}
        self.dl_iid = {}
        self.dl_note = ttk.Label(win, text="正在获取语言包列表…", foreground="#5b6676", wraplength=660)
        self.dl_note.pack(anchor="w", padx=12, pady=(12, 4))
        ui_platform.autowrap(self.dl_note)

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

        # 镜像预设（2026-11-21）：主站被拦时不用自己拼域名，选一个预设就行；
        # “自动”会按主站 → 官方镜像 → R2 依次尝试，某个不通自动换下一个。
        # 预设里的站都经实测（见 pack_downloader.MIRROR_PRESETS）：前两个是 Argos
        # 官方，R2 是旧官方地址；索引列表另有 jsDelivr 与两个第三方 GitHub 加速站。
        prow2 = ttk.Frame(win)
        prow2.pack(fill="x", padx=12, pady=(0, 6), side="bottom")
        ttk.Label(prow2, text="镜像预设").pack(side="left")
        self.dl_mirror_preset = tk.StringVar(value=self.cfg.get("pack_mirror_preset", pack_downloader.MIRROR_PRESETS[0]))
        ttk.Combobox(prow2, textvariable=self.dl_mirror_preset, state="readonly",
                     values=pack_downloader.MIRROR_PRESETS).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Label(prow2, text="自动会换镜像，不用手动填", foreground="#8a93a2").pack(side="left")

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
        # 未钉死语言对的二次确认已按用户决定去掉（2026-11-21）：不再因语言对
        # 没有内置哈希校验信息而弹窗拦截，直接下载。
        # H-04：镜像域名不在内置白名单里时，保存前请用户确认一次 ——
        # 自定义镜像意味着语言包从用户指定的服务器下载。
        if mirror:
            hosts = []
            for pair in re.split(r"[;；]", mirror):
                if "=" in pair:
                    hosts.append(pair.split("=", 1)[1].strip().split("/")[0].split(":")[0].lower())
                elif pair.strip():
                    hosts.append(pair.strip().split("/")[0].split(":")[0].lower())
            untrusted = [h for h in hosts
                         if h and not pack_downloader.is_trusted_mirror_host(h)]
            if untrusted:
                if not messagebox.askyesno(
                        "下载语言包 — 自定义镜像",
                        "镜像域名 %s 不在程序内置的已知可信域名里。\n\n"
                        "语言包将从该镜像下载。确定使用这个镜像吗？" % "、".join(untrusted),
                        parent=self.root):
                    self.dl_prog.configure(text="已取消下载（未确认自定义镜像）")
                    return
        self.dl_busy, self.dl_cancel = True, False
        self._dl_speed = {"label": None, "t": 0.0, "done": 0, "v": 0.0}
        self.dl_btn.configure(state="disabled")
        self.dl_stop.configure(state="normal")
        best, n = dict(self.dl_best), len(pairs)
        # 镜像预设：选了某个镜像就把它排到最前面；“自动”按主站 → 官方镜像 → R2 依次试。
        _preset = self.dl_mirror_preset.get() if hasattr(self, "dl_mirror_preset") else pack_downloader.MIRROR_PRESETS[0]
        preferred = pack_downloader.MIRROR_PRESETS.index(_preset) if _preset in pack_downloader.MIRROR_PRESETS else 0
        self.cfg["pack_mirror_preset"] = pack_downloader.MIRROR_PRESETS[preferred]
        self._save()
        self._dl_mirror_used = {}
        self._dl_mirror_current = None

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

                def _on_mirror(url, _pair=pair):
                    lab = pack_downloader.mirror_label(url)
                    self._dl_mirror_current = lab
                    self._dl_mirror_used[_pair] = lab

                try:
                    self._dl_mirror_current = None
                    self.q.put(("dl_prog", i, n, label, 0, 0))
                    pack_downloader.download_pack(best[pair], USER_MODELS_DIR, _dl_dir(), mirror,
                                                  progress=prog, cancelled=lambda: self.dl_cancel,
                                                  preferred_mirror=preferred, on_mirror=_on_mirror)
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
        if getattr(self, "_dl_mirror_current", None):
            txt += " · 当前镜像：" + self._dl_mirror_current
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
                _used = sorted(set(getattr(self, "_dl_mirror_used", {}).values()))
                if _used:
                    msg += "本次下载用过镜像：" + "、".join(_used) + "。"
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
            except Exception:      # noqa: BLE001  预热失败不能静默丢掉：写进崩溃日志
                import traceback
                log_crash("offline warmup failed:\n" + traceback.format_exc())
            finally:
                self._warming = False
        threading.Thread(target=job, daemon=True).start()

    # ------------------------------------------------ 指针取词
    def _on_pointer_opt(self):
        self.root.after(0, self._refresh_settings_deps)
        self.cfg["pointer_scope"] = SCOPE_CODES.get(self.scope_cb.get(), "word")
        self.cfg["hover"] = self.hover_var.get()
        self.cfg["hover_window"] = self.hover_win_var.get()
        self.hover_fired = False
        self._save()

    # ------------------------------------------------ 打字检测翻译（v2.14）
    # v2.15：打字检测翻译是专业版功能（免费版 / 7 天试用 / 专业版，见 license.py）
    def _license_state_text(self):
        """授权状态一句话（v2.15）：专业版 / 试用剩余天数 / 免费版。"""
        st = license.status_of(self.cfg)
        if st == "pro":
            return "专业版已激活"
        if st == "trial":
            return "试用中，剩余 %.1f 天" % license.trial_days_left(self.cfg)
        if license.trial_available(self.cfg):
            return "免费版（可免费试用 7 天）"
        return "免费版（试用已结束）"

    def _typing_status_text(self):
        """打字检测翻译的状态说明（高级设置 → 取词里显示）。"""
        lic = self._license_state_text()
        if not IS_WIN and keyboard is None:
            return "打字检测翻译：本机不可用——未安装 pynput（pip install pynput 后重启）。%s。" % lic
        if self.cfg.get("typing"):
            return ("打字检测翻译：已开启，重启后生效。主触发是打字过程中按词即翻，"
                    "停顿 %d 毫秒只作兜底；密码框 / 终端 / 敏感内容不翻译。%s。" % (self.cfg.get("typing_pause_ms", 1000), lic))
        return "打字检测翻译：已关闭（默认）。开启后在别的软件里打字时自动翻译。%s。" % lic

    def _refresh_typing_ui(self):
        """v2.15：按授权状态刷新打字检测开关（置灰 / 放开）与状态说明。
        试用还没用过：开关放开，点一下就开始 7 天试用；试用完又没买：置灰，
        只能点旁边的「升级到专业版」按钮。"""
        try:
            allowed = license.typing_allowed(self.cfg)
            trial_ok = license.trial_available(self.cfg)
            cb = getattr(self, "typing_check", None)
            if cb is not None:
                cb.configure(state="normal" if (allowed or trial_ok) else "disabled")
            if getattr(self, "typing_status_label", None) is not None:
                self.typing_status_label.configure(text=self._typing_status_text())
        except Exception:
            pass

    def _show_license_dialog(self):
        """v2.15：专业版激活框（高级设置 → 取词的「升级到专业版」按钮、
        托盘菜单点打字检测时也会弹到这里）。全程离线验证，不联网。"""
        self.show_window()
        try:
            win = tk.Toplevel(self.root)
        except Exception:
            return
        win.title("升级到专业版")
        ui_platform.fit_window(win, 480, 320, 480, 320, parent=self.root)
        try:
            if IS_WIN:
                win.iconbitmap(resource_path("app.ico"))
        except Exception:
            pass
        ttk.Label(win, text="打字检测翻译是专业版功能", font=(self._font_family, 11, "bold")).pack(
            anchor="w", padx=14, pady=(14, 4))
        ttk.Label(win, text="在别的软件里打字就自动翻译，不用选中、不用按快捷键。\n"
                            "免费版其他功能不受影响；买断制，一次购买终身使用。",
                  wraplength=440, justify="left").pack(anchor="w", padx=14)
        row = ttk.Frame(win)
        row.pack(fill="x", padx=14, pady=(12, 4))
        ttk.Label(row, text="激活码：").pack(side="left")
        code_var = tk.StringVar()
        ent = ttk.Entry(row, textvariable=code_var, width=26)
        ent.pack(side="left", fill="x", expand=True)
        ent.focus_set()
        msg = ttk.Label(win, text=self._license_state_text(), foreground="#5b6676",
                        wraplength=440, justify="left")
        msg.pack(anchor="w", padx=14, pady=(4, 0))

        def _do_activate():
            code = code_var.get().strip()
            if not code:
                msg.configure(text="请先输入激活码。")
                return
            ok, text, _info = license.activate(self.cfg, code)
            if not ok:
                msg.configure(text=text)
                return
            self._save()
            self._refresh_typing_ui()
            self._refresh_tray_state()
            msg.configure(text=text + "\n已解锁，打开打字检测开关后重启生效。")
            self.status.configure(text="专业版已激活，打字检测翻译已解锁")

        def _do_trial():
            if license.start_trial(self.cfg):
                self._save()
                self._refresh_typing_ui()
                self._refresh_tray_state()
                msg.configure(text="已开始 7 天免费试用。打开打字检测开关后重启生效。")
            else:
                msg.configure(text="试用已经用过了，请输入激活码升级到专业版。")

        btns = ttk.Frame(win)
        btns.pack(fill="x", padx=14, pady=(12, 0))
        ttk.Button(btns, text="激活", command=_do_activate).pack(side="left")
        if license.trial_available(self.cfg):
            ttk.Button(btns, text="开始 7 天免费试用", command=_do_trial).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="关闭", command=win.destroy).pack(side="right")
        win.bind("<Return>", lambda e: _do_activate())
        win.bind("<Escape>", lambda e: win.destroy())

    def _on_typing_opt(self):
        """打字检测翻译开关 / 范围改动：保存；关闭时立即停监听、清空缓冲
        （隐私优先）；开启后立即启动监听（v2.15.6：以前要重启才生效，
        钩子装不上时连重试的机会都没有）。
        v2.15：专业版功能 —— 未激活时打开开关先给 7 天试用（只给一次），
        试用用完又没买就弹激活框、开关打回去。"""
        self.cfg["typing_scope"] = TYPING_SCOPE_CODES.get(self.typing_scope_var.get(), "word")
        if self.typing_var.get() and not license.typing_allowed(self.cfg):
            if license.trial_available(self.cfg):
                license.start_trial(self.cfg)
            else:
                self.typing_var.set(False)
                self.cfg["typing"] = False
                self._save()
                self._refresh_typing_ui()
                self._show_license_dialog()
                return
        self.cfg["typing"] = self.typing_var.get()
        self._save()
        if not self.typing_var.get():
            self._stop_typing()
        else:
            self._start_typing()  # v2.15.6：打开立即启动（已在监听时内部直接返回）
        self._refresh_typing_ui()
        self._refresh_tray_state()

    def _on_typing_pause(self):
        """打字检测翻译的停顿兜底毫秒（500–3000），改完立刻保存并同步缓冲。"""
        try:
            v = int(self.typing_pause_var.get())
        except Exception:
            v = self.cfg.get("typing_pause_ms", 1000)
        v = max(500, min(v, 3000))
        self.typing_pause_var.set(v)
        self.cfg["typing_pause_ms"] = v
        buf = getattr(self, "_typing_buffer", None)
        if buf is not None:
            buf.set_pause_ms(v)
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
        try:
            self.spinner.stop()
        except Exception:
            pass
        self.bseq += 1
        my = self.bseq
        mode = self.cfg.get("popup_mode", "bubble")
        if not text:
            if mode == "main":
                self.status.configure(text=self._pointer_empty_msg())
            else:
                self._popup().show(xy, "指针取词", self._pointer_empty_msg(), error=True)
            return
        text = normalize_grab_text(text)[:1000]
        if not text:
            return
        if "\n" not in text and len(text.split()) == 1:
            text = ocr_win.clean_word(text)      # v2.15.2：单个词去掉两头标点，命中词典 / 缓存
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
            return top in (self.bubble.win, self.mini.win, getattr(self.spinner, "win", None))
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
        if self.cfg.get("hover_need_ctrl") and not ctrl_down_win():
            self.hover_last = None          # v2.15.3：只在按住 Ctrl 时悬停取词，平时不打扰
            return
        now = time.time()
        last = self.hover_last
        # v2.15.2：手抖 3px 以内不算移动，否则鼠标轻微晃动会一直重置计时、永远取不到词
        moved = last is None or abs(pos[0] - last[0]) > 3 or abs(pos[1] - last[1]) > 3
        if moved:
            self.hover_last, self.hover_since, self.hover_fired = pos, now, False
            return
        if self.hover_fired:
            return
        wait = self.cfg.get("hover_ms", 800)
        if self.hover_win_var.get():
            wait = max(wait, 1200)
        if (now - self.hover_since) * 1000 < wait:
            return
        self.hover_fired = True
        if self.hover_win_var.get():
            self._on_hover_window(pos)
        else:
            self._on_hover(pos)

    def _on_hover_err(self, err, pos):
        """悬停取词时 OCR 报错：状态栏写一句；同一种错误只弹一次气泡（别每次停住鼠标都弹）。"""
        err = (err or "").strip()
        if not err:
            return
        self.status.configure(text="悬停取词失败：%s" % err[:160])
        if err != getattr(self, "_hover_err_shown", None):
            self._hover_err_shown = err
            try:
                self._popup().show(pos, "悬停取词失败", err[:260], error=True)
            except Exception:
                pass

    def _on_hover(self, pos):
        self.grab_mode = "hover"
        self.grab_xy = pos
        self.mini.hide_for_capture()            # 小窗口别被截进 OCR
        scope = SCOPE_CODES.get(self.scope_cb.get(), "word")     # 在 Tk 线程里读，别在 worker 里碰 Tk
        bw, bh = self._OCR_BOX.get(scope, self._OCR_BOX["word"])
        self.spinner.start(pos, "识别中…", avoid=(bw // 2, bh // 2))
        lang = self._ocr_lang()
        bounds = screen_bounds() or (0, 0, self.root.winfo_screenwidth(),
                                     self.root.winfo_screenheight())
        threading.Thread(target=self._hover_worker, args=(pos, scope, lang, bounds),
                         daemon=True).start()

    # 各范围截光标周围多大一块去 OCR：单词一小块就够，整行要横向更宽，整段要纵向更高
    _OCR_BOX = {"word": (420, 110), "line": (900, 90), "paragraph": (900, 560)}

    def _ocr_pick(self, pos, scope, lang=None, bounds=None):
        """截光标周围一块屏幕，用系统 OCR 取光标处的单词 / 整行 / 整段；取不到返回 None。

        只在工作线程里调用，不碰 Tk：lang（OCR 语言）与 bounds（屏幕范围）
        必须由调用它的 Tk 线程在启动 worker 之前读好传进来（v2.7 修复：
        之前这里在 worker 线程里调 self._ocr_lang() → _codes() 读下拉框，
        以及 winfo_screenwidth()，Tk 控件不是线程安全的）。
        """
        if not ocr_win.ocr_available():
            raise ocr_win.OcrError("系统 OCR 不可用：Windows 需要 PowerShell 5.1 和 winocr.ps1；"
                                   "macOS / Linux 需要先安装 tesseract")
        bounds = bounds or screen_bounds() or (0, 0, 1920, 1080)
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
                lines = ocr_win.ocr_lines(tmp, lang=lang)
                return ocr_win.pick_text_at(lines, rx, ry, scope)
            words = ocr_win.ocr_words(tmp, lang=lang)
            return ocr_win.pick_word_at(words, rx, ry)
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass

    def _hover_worker(self, pos, scope="word", lang=None, bounds=None):
        # 先走截图 OCR：认出光标处的单词 / 整行 / 整段。这条路不依赖软件本身
        # 是否支持选词，图片 / 游戏 / 扫描 PDF 里也能用。
        # 2 秒缓存：指针静止时不再重复 OCR（见 HoverCache）。
        word, ibeam = None, False
        hit, cached = self._hover_cache.get(pos, scope)
        if hit is True:
            word = cached
        else:
            self._hover_ocr_err = ""            # v2.13：每次重新识别前清掉旧错误，免得「这里没字」被误报成 OCR 故障
            try:
                word = self._ocr_pick(pos, scope, lang, bounds)
            except Exception as e:      # noqa: BLE001  OCR 失败不报错、不弹状态，
                word = None              # 悬停是后台静默取词，失败就退回双击取词，
                self._hover_ocr_err = str(e)[:200]   # 原因记下来，方便查问题
            self._hover_cache.put(pos, scope, word)
            if hit is not True and word:
                self._hover_ocr_err = ""
                self._hover_err_shown = None
        if not word:
            try:
                ibeam = cursor_is_ibeam_win()
            except Exception:
                ibeam = False
        self.q.put(("hover_ocr", word, pos, ibeam))
        if not word and self._hover_ocr_err:
            # v2.13：OCR 本身出错（不是「这里没字」）时让用户看得到原因，不再一声不响
            self.q.put(("hover_err", self._hover_ocr_err, pos))

    def start_screenshot(self):
        """截图翻译：框选屏幕任意区域 → 系统 OCR 认字 → 翻译。"""
        if not IS_WIN:
            # v2.13：macOS / Linux 用 tesseract + 系统截图命令（只出文字，不盖在截图上）
            import ocr_backends
            if not ocr_win.ocr_available():
                self.status.configure(text="截图翻译需要先安装 tesseract（macOS: brew install tesseract tesseract-lang；"
                                           "Linux: sudo apt install tesseract-ocr tesseract-ocr-chi-sim）")
                return
            if not ocr_backends.capture_available():
                self.status.configure(text="没有可用的截图命令（macOS 自带 screencapture；Linux 请安装 grim / scrot / imagemagick）")
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
            # 语言/引擎/选项在 Tk 线程里读好再传进去：worker 线程里不能碰 Tk 控件。
            sl, tl = self._codes()
            threading.Thread(target=self._shot_worker,
                             args=(rect, xy, self._ocr_lang(), sl, tl,
                                   self.smart_var.get(), self.engine.get()),
                             daemon=True).start()

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

    def _shot_worker(self, rect, xy, lang=None, sl="auto", tl="zh-CN",
                     smart=True, engine="Google", ocr_scale=1, ui_mode=False, live=False):
        x, y, w, h = rect
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = os.path.join(DATA_DIR, "shot.bmp")
            time.sleep(0.15)      # 等框选层彻底消失，否则会把黑框也截进去
            import ocr_backends
            if not IS_WIN and ocr_backends.capture_available():
                png = os.path.join(DATA_DIR, "shot.png")
                try:
                    ocr_backends.capture_file(png, x, y, w, h)
                    text = ocr_win.ocr_image(png, lang=lang)
                finally:
                    try:
                        os.remove(png)
                    except Exception:
                        pass
                self.q.put(("shot_ocr", True, text.strip(), xy))
                return
            if live or self.cfg.get("shot_mode", "overlay") == "overlay":
                self._shot_overlay_worker(rect, xy, tmp, lang, sl, tl, smart, engine,
                                          ocr_scale=ocr_scale, ui_mode=ui_mode, live=live)
                return
            screen_win.capture_file(tmp, x, y, w, h, scale=ocr_scale)
            try:
                text = ocr_win.ocr_image(tmp, lang=lang)
            finally:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
            self.q.put(("shot_ocr", True, text.strip(), xy))
        except Exception as e:
            self.q.put(("shot_ocr", False, str(e)[:300], xy))

    def _shot_overlay_worker(self, rect, xy, tmp, lang=None, sl="auto",
                             tl="zh-CN", smart=True, engine="Google",
                             ocr_scale=1, ui_mode=False, live=False):
        """截图 → OCR 行 → 按段翻译 → 交给界面线程把译文盖在截图上。

        v2.10（整窗翻译）：ocr_scale > 1 时拿放大后的图去 OCR（菜单 / 按钮的小号字
        放大 2 倍才认得准），认出来的坐标再缩回原图尺寸，盖层仍用 1:1 的截图；
        ui_mode 时菜单项 / 按钮这类短行逐行翻，不并成一整句。"""
        x, y, w, h = rect
        cw, ch, bgra = screen_win.capture_region(x, y, w, h)
        if live:
            # 实时刷新：画面和上一轮完全一样就直接复用上次的译文层，不再 OCR / 翻译
            crc = zlib.crc32(bgra)
            if crc == self._live_crc and self._live_msg is not None:
                self.q.put(self._live_msg)
                return
            self._live_crc = crc
        # v2.12：整窗翻译按窗口记忆缓存——同一窗口、同一画面直接用上次的 OCR + 译文，
        # 不再 OCR / 翻译。键是窗口范围 + 整图 SHA256（精确哈希，不会把两个像的菜单串起来）。
        # 实时刷新走上面自己的 crc 判断，不再进这套缓存；截图模式（ui_mode=False）不缓存。
        _wcache = getattr(self, "_window_cache", None) if ui_mode and not live else None
        if _wcache is not None:
            try:
                _hit = _wcache.get(rect, bgra)
            except Exception:
                _hit = None
            if _hit is not None:
                self.q.put(_hit)
                return
        scale = ocr_scale if ocr_scale and ocr_scale > 1 else 1
        if scale > 1:
            sw, sh, sbgra = screen_win.capture_region(x, y, w, h, scale=scale)
            screen_win.save_bmp(tmp, sw, sh, sbgra)
            del sbgra
        else:
            screen_win.save_bmp(tmp, cw, ch, bgra)
        try:
            lines = ocr_win.ocr_lines(tmp, lang=lang)
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass
        if scale > 1:
            lines = [dict(ln, x=int(ln["x"] / scale), y=int(ln["y"] / scale),
                          w=max(1, int(round(ln["w"] / float(scale)))),
                          h=max(1, int(round(ln["h"] / float(scale))))) for ln in lines]
        if not lines:
            self.q.put(("shot_ocr", True, "", xy))        # 没认出字：走原来的提示
            return
        groups = ocr_win.group_ui_lines(lines) if ui_mode else ocr_win.group_paragraphs(lines)
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
        msg = ("shot_overlay", rect, png, boxes, det_box["det"], det_box["target"], engine, live)
        if _wcache is not None:          # v2.12：本次结果写进窗口记忆缓存（只放内存）
            try:
                _wcache.put(rect, bgra, msg)
            except Exception:
                pass
        if live:
            self._live_msg = msg
        self.q.put(msg)

    # ---- v2.10 整窗翻译：指针放在菜单 / 对话框 / 软件窗口上，整个窗口一次翻完
    def window_translate(self, delay_ms=0):
        """整窗翻译：不用框选。热键（默认 Ctrl+Alt+W）按下时，指针下面的整个
        顶层窗口——下拉菜单、右键菜单、对话框、整个软件界面——一次截下来，
        系统 OCR 识别后整窗翻译，译文盖在原位（v2.12 起：单击某一块加入术语表，
        双击复制全部，右键出菜单，Esc 关闭）。

        热键不会抢焦点，所以下拉菜单还开着的时候也能翻；delay_ms > 0 是给
        「从主窗口按钮 / 托盘菜单触发」用的：先等几秒，让你把指针移到目标上。"""
        if not IS_WIN:
            self.status.configure(text="整窗翻译只支持 Windows")
            return
        if getattr(self, "shot_win", None) is not None or self.grabbing:
            return
        if not ocr_win.ocr_available():
            self.status.configure(text="整窗翻译需要 Windows 系统 OCR（没找到 PowerShell / OCR 组件）")
            return
        if delay_ms > 0:
            self.bubble.close()
            self.mini.close()
            self.status.configure(text="%d 秒后翻译指针下的窗口，请把指针移到要翻译的菜单 / 窗口上…"
                                  % max(1, delay_ms // 1000))
            try:
                self.root.iconify()              # 别让本程序窗口挡在目标前面
            except Exception:
                pass
            self.root.after(delay_ms, self._window_translate_now)
            return
        self._window_translate_now()

    def _window_target(self, pos):
        """指针 pos 下要翻译的窗口范围（已夹到屏幕内）；找不到 / 太小返回 None 并写状态栏。"""
        rect = screen_win.window_rect_at(pos[0], pos[1], skip_pid=os.getpid())
        if rect is None:
            self.status.configure(text="没找到指针下的窗口：请把指针放在要翻译的菜单 / 窗口上再试")
            return None
        bounds = screen_bounds() or (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        rect = screen_win.clamp_region(rect[0], rect[1], rect[2], rect[3], bounds)
        if rect[2] < 20 or rect[3] < 20:
            self.status.configure(text="指针下的窗口太小，没法翻译")
            return None
        return rect

    def _start_window_worker(self, rect, pos, live=False):
        sl, tl = self._codes()
        # 菜单 / 对话框这类不大的窗口放大 2 倍再 OCR，小号界面字才认得准；整屏大窗口不放大（太慢）
        scale = 2 if rect[2] * rect[3] <= 1400000 else 1
        self.status.configure(text="正在识别并翻译整个窗口（%d×%d）…" % (rect[2], rect[3]))
        threading.Thread(target=self._shot_worker,
                         args=(rect, pos, self._ocr_lang(), sl, tl, self.smart_var.get(),
                               self.engine.get(), scale, True, live),
                         daemon=True).start()

    def _window_translate_now(self):
        self.bubble.close()
        self.mini.close()
        self._close_shot_overlay()
        pos = self.root.winfo_pointerxy()
        rect = self._window_target(pos)
        if rect is None:
            return
        self._start_window_worker(rect, pos)

    # ---- v2.11 悬停整窗翻译：鼠标在窗口上停住就整窗翻，同一个窗口只翻一次
    def _on_hover_window(self, pos):
        try:
            if self.root.winfo_containing(pos[0], pos[1]) is not None:
                return                      # 指针在本程序自己的窗口上：不翻
        except Exception:
            pass
        rect = screen_win.window_rect_at(pos[0], pos[1], skip_pid=os.getpid())
        if rect is None:
            return
        last = self._hover_win_rect
        if last is not None and last == rect:
            return                          # 还是刚翻过的那个窗口：不重复
        self._hover_win_rect = rect
        rect = self._window_target(pos)
        if rect is not None:
            self.mini.hide_for_capture()
            self._start_window_worker(rect, pos)

    # ---- v2.11 实时刷新：每隔几秒重新翻译同一个窗口，译文层点击穿透，可以照常操作软件
    def _on_live_interval(self):
        try:
            # L-05：实时刷新间隔最短 5 秒 —— 2~3 秒一轮高频 OCR 会把窗口卡住。
            v = max(5, min(int(self.live_int_var.get()), 30))
        except Exception:
            v = self.cfg.get("live_interval", 5)
        self.live_int_var.set(str(v))
        self.cfg["live_interval"] = v
        self._save()

    def _on_live_toggle(self):
        if self.live_var.get():
            if not IS_WIN:
                self.live_var.set(False)
                self.status.configure(text="实时刷新只支持 Windows")
                return
            self._on_live_interval()
            self.status.configure(text="3 秒后开始实时翻译指针下的窗口，请把指针移到目标上…")
            try:
                self.root.iconify()
            except Exception:
                pass
            self.root.after(3000, self.live_start)
        else:
            self.live_stop()

    def live_start(self):
        if not self.live_var.get() or self.live_on:
            return
        if not ocr_win.ocr_available():
            self.live_var.set(False)
            self.status.configure(text="实时刷新需要 Windows 系统 OCR（没找到 PowerShell / OCR 组件）")
            return
        self._close_shot_overlay()
        rect = self._window_target(self.root.winfo_pointerxy())
        if rect is None:
            self.live_var.set(False)
            return
        self.live_on, self._live_rect, self._live_busy = True, rect, False
        self._live_crc = self._live_msg = None
        self._live_tick()

    def live_stop(self):
        self.live_on = False
        self._live_busy = False
        self.live_var.set(False)
        if self._live_job is not None:
            try:
                self.root.after_cancel(self._live_job)
            except Exception:
                pass
            self._live_job = None
        self._close_shot_overlay()
        self.status.configure(text="已停止实时刷新")

    def _live_tick(self):
        self._live_job = None
        if not self.live_on:
            return
        if self._live_busy or getattr(self, "shot_win", None) is not None or self.grabbing:
            self._live_job = self.root.after(500, self._live_tick)
            return
        self._live_busy = True
        self._close_shot_overlay()          # 截图前先撤掉上一层译文，否则会把译文也截进去
        self._start_window_worker(self._live_rect, self.root.winfo_pointerxy(), live=True)

    def _live_done(self):
        """一轮翻译（成功 / 没认出字 / 出错）结束：隔 live_interval 秒再来一轮。"""
        self._live_busy = False
        if self.live_on and self._live_job is None:
            sec = max(5, int(self.cfg.get("live_interval", 5)))
            self._live_job = self.root.after(sec * 1000, self._live_tick)

    # ---- 截图翻译：译文盖在截图上
    def _close_shot_overlay(self):
        ov = self.shot_overlay
        self.shot_overlay = None
        if ov is not None:
            try:
                ov.destroy()
            except Exception:
                pass

    def _show_shot_overlay(self, rect, png, boxes, det, target, engine, live=False):
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
        family = self.font[0] if isinstance(self.font, (tuple, list)) else self._font_family
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
        tip = canvas.create_text(w - 6, h - 4, anchor="se",
                                 text=("实时刷新中 · 再按 %s 停止" % self.hotkey_window_label) if live
                                 else "点一块加入术语表 · 双击复制全部 · 右键更多 · Esc 关闭",
                                 font=(family, -11), fill="#ffffff")
        tb = canvas.bbox(tip)
        if tb:
            bgid = canvas.create_rectangle(tb[0] - 4, tb[1] - 2, tb[2] + 4, tb[3] + 2, fill="#1f2937", outline="")
            canvas.tag_lower(bgid, tip)
        full = "\n".join(b["dst"] for b in boxes)
        src_full = "\n".join(b["src"] for b in boxes)

        self._overlay_boxes = list(boxes)   # v2.12：当前译文层上的块（点一块加术语用）

        def copy_all(_e=None):
            self._set_clip(full)
            self.last_clip = full
            self.status.configure(text="已复制截图译文")
            self._close_shot_overlay()

        # v2.12 译文层交互（只在非实时刷新层生效；实时刷新层是点击穿透，本来就收不到点击）：
        #   单击某一块 → 把这块的原文→译文加入术语表；
        #   双击 → 复制全部译文（原来的"点一下复制全部"改到双击）；
        #   右键 → 菜单：导出对照表 (CSV) / 关闭。Esc 照常关闭。
        # 单击要等 250ms 再执行（等双击：双击到了就取消加术语、改复制全部），
        # 和气泡的单击/双击区分是同一套做法。
        self._overlay_click_after = None

        def _cancel_pending_click():
            if getattr(self, "_overlay_click_after", None) is not None:
                try:
                    self.root.after_cancel(self._overlay_click_after)
                except Exception:
                    pass
                self._overlay_click_after = None

        def on_click(e):
            idx = overlay_block_at(boxes, e.x, e.y)
            if idx is None:
                return
            _cancel_pending_click()

            def _add():
                self._overlay_click_after = None
                b = boxes[idx]
                try:
                    if not self.add_glossary_pair(b["src"], b["dst"]):
                        self.status.configure(text="已在术语表里：%s" % (b["src"] or "")[:30])
                except Exception:
                    pass

            self._overlay_click_after = self.root.after(250, _add)

        def on_double(e):
            _cancel_pending_click()
            copy_all()

        def on_right(e):
            _cancel_pending_click()
            menu = tk.Menu(win, tearoff=0)
            menu.add_command(label="导出对照表 (CSV)…",
                             command=lambda: self._export_shot_csv())
            menu.add_command(label="关闭", command=self._close_shot_overlay)
            self._overlay_menu = menu
            # 用 post() 而不用 tk_popup()：后者会阻塞事件循环等用户选完，
            # 前者只把菜单贴出来就返回，点别处或选完即消失，行为一样、测试也测得了
            menu.post(e.x_root, e.y_root)

        canvas.bind("<Button-1>", on_click)
        canvas.bind("<Double-Button-1>", on_double)
        canvas.bind("<Button-3>", on_right)
        win.bind("<Escape>", lambda e: self._close_shot_overlay())
        self.shot_overlay = win
        if live:
            # 点击穿透、不抢焦点：不挡下面的软件；不写主窗口、不存历史（每几秒一次会刷屏）
            win.update_idletasks()
            screen_win.make_click_through(win.winfo_id())
            self.status.configure(text="实时刷新中（每 %d 秒）：%s → %s · 再按 %s 或取消「实时刷新」停止"
                                  % (self.cfg.get("live_interval", 5), lang_name(det), lang_name(target),
                                     self.hotkey_window_label))
            self._live_done()
            return
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
        if self.live_on:                     # 实时刷新中：没认出字 / 出错就静默等下一轮
            if not ok:
                self.status.configure(text="实时刷新：本轮失败（%s），稍后重试" % text[:60])
            self._live_done()
            return
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
        ui_platform.fit_window(win, 620, 450, 420, 320, parent=self.root)
        win.transient(self.root)
        self.net_win = win
        box, self.net_txt = self._text_with_scroll(win, height=14, font=(self._mono_family, 10),
                                                  state="disabled")
        box.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        for tag, color in (("ok", "#15803d"), ("bad", "#b42318"), ("info", "#5b6676"), ("warn", "#b45309")):
            self.net_txt.tag_configure(tag, foreground=color)
        self.net_txt.tag_configure("head", font=(self._font_family, 10, "bold"))
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
            try:
                checks, reco = netcheck.run_all(
                    google_fn=lambda: g_translate("hello", "en", "zh-CN", attempts=1, timeout=8)[0],
                    ms_fn=lambda: ms_translate("hello", "en", "zh-CN", attempts=1, timeout=8)[0],
                    offline_info=info,
                    on_item=lambda c: self.q.put(("net_item", run, c)),
                    cancelled=lambda: run != self.net_run,
                    proxy_url=netcheck.effective_proxy(get_proxy_url()),
                    extra_engines=[("lingva", "Lingva", lambda: lingva_translate("hello", "en", "zh-CN", deadline=time.monotonic() + 12)[0]),
                                   ("mymemory", "MyMemory", lambda: mymemory_translate("hello", "en", "zh-CN", deadline=time.monotonic() + 12)[0])])   # v2.15.3：程序内自定义代理也检查端口
            except Exception as e:      # noqa: BLE001  检测本身崩了也不能让界面一直卡在「检测中」
                import traceback
                log_crash("netcheck failed:\n" + traceback.format_exc())
                checks, reco = [], netcheck.Recommendation(
                    None, "检测本身出错：%s" % e, "bad")
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

    def _geometry_to_save(self):
        """只在窗口是正常状态时记它的大小位置：最小化 / 藏起来时 Tk 可能报 1x1 或 -32000 的假坐标，
        存进去下次启动窗口就跑到屏幕外了。再夹一次进屏幕，保证存下来的永远是可见的。"""
        old = self.cfg.get("geometry") or DEFAULTS["geometry"]
        try:
            if self.root.state() != "normal":
                return old
            g = self.root.geometry()
            return ui_platform.clamp_geometry(g, self.root.winfo_screenwidth(),
                                              self.root.winfo_screenheight()) or old
        except Exception:
            return old

    def _save(self):
        sl, tl = self._codes()
        self.cfg.update(
            sl=sl, tl=tl, top=self.top_var.get(), watch=self.watch_var.get(),
            smart=self.smart_var.get(), bilingual=self.bi_var.get(),
            reflow=self.reflow_var.get(), show_src=self.show_src_var.get(),
            geometry=self._geometry_to_save(), engine=self.engine.get(),
            auto_offline=AUTO_OFFLINE, pointer=self.pointer_var.get(),
            hover=self.hover_var.get(), hover_ms=self.cfg.get("hover_ms", 800),
            typing=self.typing_var.get(),
            typing_pause_ms=self.cfg.get("typing_pause_ms", 1000),
            typing_scope=self.cfg.get("typing_scope", "word"),
            hover_window=self.hover_win_var.get(), live_interval=self.cfg.get("live_interval", 5),
            pointer_scope=SCOPE_CODES.get(self.scope_cb.get(), "word"),
            close_action=CLOSE_CODES.get(self.close_cb.get(), "taskbar"),
            minimize_action=MINIMIZE_CODES.get(self.min_cb.get(), "taskbar"),
            popup_mode=POPUP_CODES.get(self.popup_cb.get(), "bubble"),
            shot_mode=SHOT_CODES.get(self.shot_cb.get(), "overlay"),
            tray_tip=self.tray_tip_var.get(),
            history_on=self.history_on_var.get(), history_reuse=self.history_reuse_var.get(),
            history_max=self.cfg.get("history_max", 2000),
            auto_copy=self.auto_copy_var.get(), tts_rate=self.cfg.get("tts_rate", 0),
            font_size=self.cfg.get("font_size", 11),
            dark_mode=self.dark_var.get() if getattr(self, "dark_var", None) is not None
                      else self.cfg.get("dark_mode", False),
            glossary=self.cfg.get("glossary", []),
            update_auto=self.update_auto_var.get() if getattr(self, "update_auto_var", None) is not None
                        else self.cfg.get("update_auto", True),
            update_last_check=self.cfg.get("update_last_check", ""),
            proxy_enabled=self.cfg.get("proxy_enabled", False),
            proxy_host=self.cfg.get("proxy_host", ""),
            proxy_port=self.cfg.get("proxy_port", 0),
            proxy_user=self.cfg.get("proxy_user", ""),
            proxy_pass=self.cfg.get("proxy_pass", ""),
            tts_voice=self.cfg.get("tts_voice", ""))
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = CONFIG_PATH + ".tmp"
            # M-04：存盘前把代理密码换成 DPAPI 加密副本 —— 内存里的 self.cfg
            # 保持明文（代理还要用），盘上的 config.json 不再存明文密码。
            # 加密失败（非 Windows / DPAPI 不可用）时回落明文，不阻保存。
            to_save = dict(self.cfg)
            for sk in SECRET_KEYS:
                pw = to_save.get(sk) or ""
                if pw and not str(pw).startswith("dpapi:"):
                    enc = _dpapi_protect(pw)
                    if enc:
                        to_save[sk] = enc
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(to_save, f, ensure_ascii=False, indent=1)
            os.replace(tmp, CONFIG_PATH)
            # M-04/M-06：配置文件仅本用户可读（里面有代理账号密码）。
            try:
                os.chmod(CONFIG_PATH, 0o600)
            except OSError:
                pass
        except Exception:
            pass
        set_proxy_url(proxy_url(self.cfg))   # v2.9：保存后立刻按新配置决定走不走代理
        set_engine_keys(self.cfg)             # v2.15.4
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
            # H-01：监听剪贴板意味着复制的内容会发给在线翻译引擎并存入历史库 ——
            # 第一次开启时提醒一次（只提醒一次，之后不再打扰）。
            if not self.cfg.get("clip_warn_shown"):
                self.cfg["clip_warn_shown"] = True
                try:
                    messagebox.showinfo(
                        "监听剪贴板",
                        "已开启剪贴板监听。\n\n"
                        "开启后，你在任何地方复制的文字都会自动发给在线翻译引擎"
                        "（Google / 微软），并保存在本机历史库（%s）里。\n"
                        "复制验证码、密码、身份证号等敏感内容时请先关闭监听。"
                        % HISTORY_PATH,
                        parent=self.root)
                except Exception:
                    pass
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
        th = theme_colors(bool(self.cfg.get("dark_mode", False)))
        self.dst.configure(state="normal", foreground=th["error"])
        self.dst.delete("1.0", "end")
        self.dst.insert("1.0", text)
        self.dst.configure(state="disabled")

    def plain_result(self):
        return "\n".join(d for _, d in self.pairs).strip()

    RENDER_MAX_CHARS = 150000        # 译文框最多显示多少字；其余在内存里，复制 / 保存仍是全文

    def render(self):
        t = self.dst
        th = theme_colors(bool(self.cfg.get("dark_mode", False)))
        t.configure(state="normal", foreground=th["text_fg"])
        t.delete("1.0", "end")
        bi = self.bi_var.get()
        used, shown = 0, 0
        if not bi:
            # 一次 insert：几万段逐段 insert 会让 Tk 卡住几十秒（「未响应」）
            chunk = []
            for s_, d in self.pairs:
                line = "\n" if (not s_ and not d) else d + "\n"
                if used + len(line) > self.RENDER_MAX_CHARS:
                    break
                chunk.append(line)
                used += len(line)
                shown += 1
            t.insert("end", "".join(chunk))
        else:
            for s_, d in self.pairs:
                if not s_ and not d:
                    if used + 1 > self.RENDER_MAX_CHARS:
                        break
                    t.insert("end", "\n")
                    used += 1
                else:
                    if used + len(s_) + len(d) + 3 > self.RENDER_MAX_CHARS:
                        break
                    t.insert("end", s_ + "\n", "src")
                    t.insert("end", d + "\n\n")
                    used += len(s_) + len(d) + 3
                shown += 1
        if shown < len(self.pairs):
            t.insert("end", "\n……（窗口里只显示前 %d 段，后面还有 %d 段没有显示；"
                            "「复制译文」和保存的文件里是完整译文）\n" % (shown, len(self.pairs) - shown))
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
            ok = tts_win.speak(text, lang, rate=int(self.cfg.get("tts_rate", 0)),
                               voice=self.cfg.get("tts_voice") or None)
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
            self.dict_frame.pack(side="bottom", fill="x", pady=(0, 2))   # v2.13：先分配空间，窗口矮时不被译文框挤没

    # ---- v2.6 文档翻译（.txt / .md / .srt） ----
    def _translate_doc_file(self):
        if getattr(self, "_doc_busy", False):
            self.status.configure(text="已经有一份文档在翻译，可点「取消翻译」再选新的")
            return
        path = filedialog.askopenfilename(
            title="选择要翻译的文档",
            filetypes=[("文档", "*.txt *.md *.srt *.docx *.pdf"), ("文本", "*.txt"),
                       ("Markdown", "*.md"), ("字幕", "*.srt"),
                       ("Word 文档", "*.docx"), ("PDF", "*.pdf")])
        if not path:
            return
        ext = os.path.splitext(path)[1].lower()
        if ext != ".pdf" and not doc_translate.supported_doc_ext(path):
            self.status.configure(text="只支持 .txt / .md / .srt / .docx / .pdf 文档")
            return
        # v2.10：只在界面线程里做「看大小 + 问一句」，读文件、解析 docx / pdf 全部放后台线程。
        # 旧版在这里同步读整个文件并解析，大文件会让窗口「未响应」。
        try:
            size = os.path.getsize(path)
        except OSError as e:
            self.status.configure(text="打不开文档：%s" % e)
            return
        limit = doc_translate.size_limit_for(ext)
        if size > limit:
            self.status.configure(text="文件太大（%.1f MB），上限 %d MB，请拆成几份再翻译"
                                  % (size / 1048576.0, limit // 1048576))
            return
        self._doc_busy = True
        self._doc_cancel.clear()
        self.doc_cancel_btn.pack(side="left", pady=(4, 0))
        self.status.configure(text="正在读取文档…")
        self._doc_path = path
        # 语言/引擎/选项在 Tk 线程里读好再传进去：worker 线程里不能碰 Tk 控件。
        sl, tl = self._codes()
        threading.Thread(target=self._doc_worker,
                         args=(path, sl, tl, self.engine.get(),
                               self.smart_var.get(), self.reflow_var.get()),
                         daemon=True).start()

    def _doc_confirm(self, segs, chars, engine, cancelled):
        """（后台线程）估算耗时；不大就直接开翻，否则让界面线程问用户，等回答。"""
        secs = estimate_doc_seconds(segs, chars, engine)
        if segs < DOC_CONFIRM_SEGS and secs < DOC_CONFIRM_SECS:
            return True
        box = {"ev": threading.Event(), "ok": False}
        self.q.put(("doc_confirm", segs, chars, secs, box))
        while not box["ev"].wait(0.2):
            if cancelled():
                return False
        return box["ok"]

    def _on_doc_confirm(self, segs, chars, secs, box):
        try:
            box["ok"] = messagebox.askyesno(
                "翻译前确认", "这份文档约 %d 段、%d 字，预计%s（在线按每段一个请求估算，实际受网速和限流影响）。\n"
                              "翻译中可随时点「取消翻译」。现在开始吗？" % (segs, chars, fmt_duration(secs)),
                parent=self.root)
        finally:
            box["ev"].set()

    def _cancel_doc(self):
        """取消正在进行的文档翻译：后台线程下一段开始前就会退出。"""
        if getattr(self, "_doc_busy", False):
            self._doc_cancel.set()
            self.status.configure(text="正在取消文档翻译…")

    def _doc_finish_ui(self):
        self._doc_busy = False
        try:
            self.doc_cancel_btn.pack_forget()
        except Exception:
            pass

    def _doc_worker(self, path, sl, tl, engine, smart, reflow):
        """文档翻译（后台线程）：读文件 / 解析 → 翻译 → 把结果放进队列。

        .srt 只翻正文，.txt/.md/.pdf 按段落翻整篇，.docx 按段落翻并重建文件。
        所有重活（读文件、解析、翻译）都在这里，界面线程只收进度和结果。"""
        ext = os.path.splitext(path)[1].lower()
        cancelled = self._doc_cancel.is_set
        last = [0.0]
        t_start = [time.time()]

        def prog(d, n):
            # 进度节流：最多每 0.25 秒一条（旧版每段一条，几万段会把消息队列塞满）
            now = time.time()
            if d >= n or now - last[0] >= 0.25:
                last[0] = now
                eta = (now - t_start[0]) / d * (n - d) if d >= 5 else None   # 剩余时间
                self.q.put(("doc_prog", d, n, eta))

        def go(segs, chars):
            """翻之前先估时间：段数多或预计久就问用户，不想翻就当取消。"""
            ok_ = self._doc_confirm(segs, chars, engine, cancelled)
            t_start[0] = time.time()
            return ok_

        try:
            data = None
            if ext == ".pdf":
                text = pdf_translate.extract_pdf_text(path)
                if len(text.strip()) < pdf_translate.PDF_TRANSLATE_MIN_CHARS:
                    self.q.put(("doc_done", False,
                                "这个 PDF 几乎没有可提取的文字，可能是扫描件 / 图片型 PDF，"
                                "请改用截图翻译（框选后识别）"))
                    return
            elif ext == ".docx":
                with open(path, "rb") as f:
                    data = f.read()
                texts_docx = doc_translate.docx_paragraph_texts(doc_translate.docx_document_xml(data))
                text = "\n\n".join(texts_docx)
            else:
                text = doc_translate.read_text_file(path)
            if not text.strip():
                self.q.put(("doc_done", False, "文档是空的"))
                return
            if cancelled():
                raise RuntimeError("cancelled")
            self.q.put(("doc_prog", 0, 0))
            if ext == ".docx":
                texts = texts_docx
                idx = [i for i, t in enumerate(texts) if t.strip()]
                if not idx:
                    self.q.put(("doc_done", False, "文档里没有可翻译的文字"))
                    return
                if not go(len(idx), sum(len(texts[i]) for i in idx)):
                    raise RuntimeError("cancelled")
                first, det, target = translate(texts[idx[0]], sl, tl, smart, engine, cancelled=cancelled)
                outs = [""] * len(texts)
                outs[idx[0]] = first
                rest = idx[1:]
                for i, o in zip(rest, translate_many([texts[i] for i in rest], det, target, engine,
                                                     prog, cancelled)):
                    outs[i] = o
                pairs = [(t, o) for t, o in zip(texts, outs) if t.strip()]
                out_text = "\n".join(o for o in outs if o)
                out_bytes = doc_translate.docx_rebuild(data, outs)
                self.q.put(("doc_done", True, (out_text, det, target, text, pairs, sl, tl, out_bytes)))
                return
            if ext == ".srt":
                blocks = doc_translate.srt_parse(text)
                if not blocks:
                    self.q.put(("doc_done", False, "没有解析到字幕块"))
                    return
                src_texts = [b["text"] for b in blocks]
                if not go(len(src_texts), sum(len(t) for t in src_texts)):
                    raise RuntimeError("cancelled")
                first, det, target = translate(src_texts[0], sl, tl, smart, engine, cancelled=cancelled)
                outs = [first] + translate_many(src_texts[1:], det, target, engine, prog, cancelled)
                pairs = list(zip(src_texts, outs))
                for b, o in zip(blocks, outs):
                    b["text"] = o
                out_text = doc_translate.srt_rebuild(blocks)
            else:
                _units = [u for u in to_units(text, reflow) if u]
                if not go(len(_units), sum(len(u) for u in _units)):
                    raise RuntimeError("cancelled")
                del _units
                pairs, det, target = translate_doc(text, sl, tl, smart, reflow, engine,
                                                   progress=prog, cancelled=cancelled)
                out_text = "\n".join(d for _, d in pairs)
            self.q.put(("doc_done", True, (out_text, det, target, text, pairs, sl, tl)))
        except MemoryError:
            self.q.put(("doc_done", False, "内存不够，这个文件太大了，请拆成几份再翻译"))
        except Exception as e:      # noqa: BLE001
            if str(e) == "cancelled" or cancelled():
                self.q.put(("doc_done", False, "已取消文档翻译"))
            else:
                log_crash("doc_worker: %r" % (e,))
                self.q.put(("doc_done", False, str(e)[:300]))

    def _on_doc_done(self, ok, payload):
        self._doc_finish_ui()
        if not ok:
            self.status.configure(text=payload if payload.startswith("已取消") else "文档翻译失败：%s" % payload)
            return
        out_bytes = payload[7] if len(payload) > 7 else None
        out_text, det, target, src_text, pairs, sl, tl = payload[:7]
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
        # PDF 的译文是纯文本，保存成 -译文.txt（不写回 PDF）。
        saved = ""
        if path:
            base, ext = os.path.splitext(path)
            save_ext = ".txt" if ext.lower() == ".pdf" else ext
            save = filedialog.asksaveasfilename(
                title="保存译文", initialdir=os.path.dirname(path) or ".",
                initialfile=os.path.basename(base + "-译文" + save_ext),
                defaultextension=save_ext,
                filetypes=[("文档", "*" + save_ext), ("所有文件", "*.*")])
            if save:
                try:
                    if out_bytes is not None:
                        with open(save, "wb") as f:
                            f.write(out_bytes)
                    else:
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
        if not ocr_win.ocr_available():
            self.status.configure(text=("图片翻译需要 Windows 系统 OCR（winocr.ps1 缺失或没有 PowerShell 5.1）" if IS_WIN
                                        else "图片翻译需要先安装 tesseract（macOS: brew install tesseract tesseract-lang；"
                                             "Linux: sudo apt install tesseract-ocr tesseract-ocr-chi-sim）"))
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

    # ---- v2.8 粘贴图片翻译：剪贴板图片 → 临时 BMP → 系统 OCR → 翻译 ----
    def _translate_clipboard_image(self):
        if not IS_WIN:
            self.status.configure(text="粘贴图片翻译只在 Windows 上可用（需要系统 OCR）")
            return
        if not ocr_win.ocr_available():
            self.status.configure(text="粘贴图片翻译需要 Windows 系统 OCR（winocr.ps1 缺失或没有 PowerShell 5.1）")
            return
        try:
            dib = clip_image.get_clipboard_dib()
        except Exception:      # noqa: BLE001
            dib = None
        if not dib:
            self.status.configure(text="剪贴板里没有图片")
            return
        try:
            bmp = clip_image.dib_to_bmp(dib)
        except Exception as e:      # noqa: BLE001
            self.status.configure(text="剪贴板里的图片读不出来：%s" % e)
            return
        try:
            fd, tmp = tempfile.mkstemp(suffix=".bmp", prefix="rt_clip_")
            with os.fdopen(fd, "wb") as f:
                f.write(bmp)
        except Exception as e:      # noqa: BLE001
            self.status.configure(text="写临时图片失败：%s" % e)
            return
        self.status.configure(text="正在识别剪贴板图片文字…")
        # OCR 语言在 Tk 线程里读好再传进去：worker 线程里不能碰 Tk 控件。
        threading.Thread(target=self._clip_image_worker, args=(tmp, self._ocr_lang()),
                         daemon=True).start()

    def _clip_image_worker(self, path, lang):
        """剪贴板图片 OCR（后台线程）：认完删临时文件，结果走 image_ocr 复用图片翻译的后续。"""
        try:
            text = ocr_win.ocr_image(path, lang=lang)
        except Exception as e:      # noqa: BLE001
            self.q.put(("image_ocr", False, str(e)[:300], path))
        else:
            self.q.put(("image_ocr", True, (text or "").strip(), path))
        finally:
            try:
                os.remove(path)
            except Exception:      # noqa: BLE001
                pass

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
                time.sleep(0.05)
                # M-03：粘贴前再确认一次前台窗口还是原来的 —— 翻译这段时间里
                # 用户可能切走了窗口，贴错地方就把译文粘进了别的软件。
                if foreground_window_win() != hwnd0:
                    self.status.configure(text="前台窗口已变，只把译文放进了剪贴板（按 Ctrl+V 粘贴）")
                    return
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

    # ------------------------------------------------ v2.15.4 常用翻译软件功能
    def _compare_engines(self):
        want = [e for e in (self.cfg.get("compare_engines") or []) if e in ENGINES]
        base_list = want or ENGINES
        return translator_tools.compare_plan(
            base_list, lambda e: (e not in KEY_ENGINES or engine_configured(e))
            and (e != "离线" or offline_engine.runtime_present()), max_n=6 if want else 4)

    def open_compare(self, text=None):
        """多引擎对照：同一段原文同时交给几个引擎，结果按完成先后列出；点「用这个」写回主窗口。"""
        text = (text if text is not None else self.src.get("1.0", "end")).strip()
        if not text:
            text = self._get_clip().strip()
        if not text:
            self.status.configure(text="先在原文框里输入，或复制一段文字，再点「多引擎对照」")
            return
        text = text[:MAX_LEN]
        engines = self._compare_engines()
        if not engines:
            self.status.configure(text="没有可用的引擎")
            return
        w = getattr(self, "compare_win", None)
        if w is None or not w.winfo_exists():
            w = tk.Toplevel(self.root)
            w.title("多引擎对照")
            ui_platform.fit_window(w, 720, 520, 420, 300, parent=self.root)
            w.bind("<Escape>", lambda e: w.withdraw())
            self.compare_win = w
            top = ttk.Frame(w)
            top.pack(fill="x", padx=12, pady=(10, 4))
            self.compare_head = ttk.Label(top, text="", style="Note.TLabel", wraplength=640, justify="left")
            self.compare_head.pack(side="left", fill="x", expand=True)
            ttk.Button(top, text="选择引擎…", command=self._pick_compare_engines).pack(side="right")
            sf = ui_platform.ScrollFrame(w, padding=8)
            sf.pack(fill="both", expand=True, padx=4, pady=(0, 8))
            self.compare_body = sf.body
        for c in self.compare_body.winfo_children():
            c.destroy()
        sl, tl = self._codes()
        head = text.replace("\n", " ")
        self.compare_head.configure(text="原文：" + (head if len(head) <= 120 else head[:120] + "…"))
        self._compare_seq = getattr(self, "_compare_seq", 0) + 1
        my = self._compare_seq
        self._compare_res = translator_tools.CompareResult(engines)
        self._compare_rows = {}
        fam = getattr(self, "_font_family", "TkDefaultFont")
        for eng in engines:
            fr = ttk.Frame(self.compare_body)
            fr.pack(fill="x", pady=(0, 10))
            hd = ttk.Frame(fr)
            hd.pack(fill="x")
            ttk.Label(hd, text=eng, style="Section.TLabel").pack(side="left")
            meta = ttk.Label(hd, text="翻译中…", style="Note.TLabel")
            meta.pack(side="left", padx=8)
            use = ttk.Button(hd, text="用这个", width=7)
            use.pack(side="right")
            cp = ttk.Button(hd, text="复制", width=5)
            cp.pack(side="right", padx=4)
            body = tk.Text(fr, height=3, wrap="word", font=(fam, int(self.cfg.get("font_size", 11))),
                           relief="flat", borderwidth=0)
            body.pack(fill="x", pady=(2, 0))
            body.insert("1.0", "…")
            body.configure(state="disabled")
            if self.cfg.get("apple_theme", True):
                ui_platform.style_text_apple(body, ui_platform.apple_palette(bool(self.cfg.get("dark_mode"))))
            self._compare_rows[eng] = (meta, body, use, cp)
            for b in (use, cp):
                b.state(["disabled"])
            threading.Thread(target=self._compare_worker, args=(my, eng, text, sl, tl), daemon=True).start()
        w.deiconify()
        w.lift()

    def _compare_worker(self, my, eng, text, sl, tl):
        t0 = time.time()
        try:
            out, det, _target = translate(text, sl, tl, False, eng, cancelled=lambda: my != self._compare_seq)
            self.q.put(("compare", my, eng, True, out, (time.time() - t0) * 1000))
        except Exception as e:      # noqa: BLE001
            msg = str(e) if isinstance(e, (EngineKeyError, offline_engine.OfflineError)) else netcheck.explain_error(e)[0]
            self.q.put(("compare", my, eng, False, msg, (time.time() - t0) * 1000))

    def _on_compare(self, my, eng, ok, out, ms):
        if my != getattr(self, "_compare_seq", 0) or eng not in getattr(self, "_compare_rows", {}):
            return
        self._compare_res.add(eng, ok, out, ms)
        meta, body, use, cp = self._compare_rows[eng]
        order = len(self._compare_res.done)
        meta.configure(text=("#%d · %d ms" % (order, ms)) if ok else "失败")
        body.configure(state="normal")
        body.delete("1.0", "end")
        body.insert("1.0", out)
        lines = max(1, min(12, int(body.count("1.0", "end", "displaylines")[0]) if body.count("1.0", "end", "displaylines") else 3))
        body.configure(height=lines, state="disabled")
        if ok:
            use.configure(command=lambda o=out, e=eng: self._compare_use(o, e))
            cp.configure(command=lambda o=out: (self._set_clip(o), setattr(self, "last_clip", o),
                                                self.status.configure(text="已复制 %s 的译文" % eng)))
            use.state(["!disabled"]); cp.state(["!disabled"])
        if self._compare_res.finished():
            agree = self._compare_res.agreement()
            tail = ("　·　%s 译文一致" % "、".join(agree)) if len(agree) >= 2 else ""
            self.compare_head.configure(text=self.compare_head.cget("text").split("　·　")[0] + tail)

    def _compare_use(self, out, eng):
        self.pairs = [(self.src.get("1.0", "end").strip(), out)]
        try:
            self.render()
        except Exception:
            pass
        self._set_clip(out)
        self.last_clip = out
        self.status.configure(text="已采用 %s 的译文并复制" % eng)

    def _pick_compare_engines(self):
        win = tk.Toplevel(self.compare_win)
        win.title("对照哪些引擎")
        win.transient(self.compare_win)
        cur = set(self.cfg.get("compare_engines") or [])
        vs = {}
        for e in ENGINES:
            if e == "自动":
                continue
            v = tk.BooleanVar(value=(e in cur) if cur else e in self._compare_engines())
            usable = e not in KEY_ENGINES or engine_configured(e)
            cb = ttk.Checkbutton(win, text=e + ("" if usable else "（未填 Key）"), variable=v)
            cb.pack(anchor="w", padx=16, pady=2)
            if not usable:
                cb.state(["disabled"])
            vs[e] = v

        def done():
            self.cfg["compare_engines"] = [e for e, v in vs.items() if v.get()][:6]
            self._save()
            win.destroy()
            self.open_compare()
        ttk.Label(win, text="最多 6 个；一个都不选就自动挑 4 个。", style="Note.TLabel").pack(anchor="w", padx=16, pady=(6, 0))
        ttk.Button(win, text="确定", style="Accent.TButton", command=done).pack(pady=10)

    def open_case_tool(self):
        """命名格式：把原文（或译文）转成 camelCase / snake_case 等，点一下复制。
        中文原文先取当前译文（例如「用户登录次数」→ user login count → userLoginCount）。"""
        src = self.src.get("1.0", "end").strip()
        cand = src if translator_tools.looks_like_identifier(src) else self.plain_result()
        if not translator_tools.looks_like_identifier(cand or ""):
            self.status.configure(text="命名格式需要一个短的英文词组：先把中文译成英文，或直接输入英文")
            return
        menu = tk.Menu(self.root, tearoff=0)
        for name, val in translator_tools.all_cases(cand):
            menu.add_command(label="%s    %s" % (val, name),
                             command=lambda v=val: (self._set_clip(v), setattr(self, "last_clip", v),
                                                    self.status.configure(text="已复制 " + v)))
        try:
            x, y = self.root.winfo_pointerxy()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def clean_source(self):
        src = self.src.get("1.0", "end").strip()
        if not src:
            return
        out = translator_tools.clean_text(src, strip_line_numbers=True)
        if out != src:
            self._set_src(out)
            self.translate_now()
            self.status.configure(text="已去掉页码 / 行号 / 多余空行，并重新翻译")
        else:
            self.status.configure(text="没有需要清理的格式")

    def _on_style(self):
        self.cfg["translate_style"] = STYLE_CODES.get(self.style_cb.get(), "default")
        set_engine_keys(self.cfg)
        with _cache_lock:
            CACHE.clear()
        self._save()
        self.translate_now()

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
        self._pet_event("busy", "翻译中…")
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
            if offline_msg or isinstance(e, EngineKeyError):
                tip = ""                       # v2.15.4：Key 类错误本身就写清了原因和去哪改
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
            if getattr(self, "pet", None) is not None:
                self.pet.close()
        except Exception:
            pass
        try:                                      # v2.12：先停看门狗，别留后台线程
            if getattr(self, "_watchdog", None) is not None:
                self._watchdog.stop()
        except Exception:
            pass
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
            self._stop_typing()       # v2.14：退出时立即停打字监听、清空缓冲
        except Exception:
            pass
        self.live_on = False
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
        clip_l = self.hotkey_clip_label
        window_l = self.hotkey_window_label
        ok_text = ("选中文字后按 %s 翻译；指针放在文字上按 %s 就地取词；按 %s 截图翻译；按 %s 翻译并替换原文；"
                   "按 %s 翻译剪贴板里的图片；指针放在菜单 / 窗口上按 %s 整窗翻译；Esc 隐藏窗口"
                   % (main_l, pointer_l, shot_l, replace_l, clip_l, window_l)) if IS_WIN else \
                  ("选中文字后按 %s 翻译，或按 %s 在指针旁显示译文；Esc 隐藏窗口" % (main_l, pointer_l))
        if IS_WIN:
            try:
                specs = {k: self.cfg.get(k, DEFAULT_HOTKEYS[k]) for k in HOTKEY_KEYS}
                ok = start_hotkey_win(self.q, specs)
                pok = getattr(start_hotkey_win, "pointer_ok", False)
                sok = getattr(start_hotkey_win, "shot_ok", False)
                rok = getattr(start_hotkey_win, "replace_ok", False)
                cok = getattr(start_hotkey_win, "clip_ok", False)
                wok = getattr(start_hotkey_win, "window_ok", False)
                missing = []
                if not ok:
                    missing.append(main_l)
                if not pok:
                    missing.append(pointer_l)
                if not sok:
                    missing.append(shot_l)
                if not rok:
                    missing.append(replace_l)
                if not cok:
                    missing.append(clip_l)
                if not wok:
                    missing.append(window_l)
                # v2.12：记下各热键的注册结果，诊断信息里报（被占用的也写清楚）
                self._hotkey_status = {"hotkey_main": bool(ok), "hotkey_pointer": bool(pok),
                                       "hotkey_shot": bool(sok), "hotkey_replace": bool(rok),
                                       "hotkey_clip": bool(cok), "hotkey_window": bool(wok)}
                if not missing:
                    self.hint.configure(text=ok_text)
                else:
                    self.hint.configure(text="%s 已被其他程序占用，不可用；其余快捷键仍可用（高级设置 → 快捷键与关于里可改）" % " / ".join(missing))
            except Exception as e:
                self._hotkey_status = {k: False for k in HOTKEY_KEYS}
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
                                              pynput_spec(specs["hotkey_replace"]): lambda: self.q.put(("hotkey", 4)),
                                              pynput_spec(specs["hotkey_clip"]): lambda: self.q.put(("hotkey", 5)),
                                              pynput_spec(specs["hotkey_window"]): lambda: self.q.put(("hotkey", 6))})
            self.hk.daemon = True
            self.hk.start()
            self._hotkey_status = {k: True for k in HOTKEY_KEYS}   # v2.12：诊断信息用
            self.hint.configure(text=ok_text)
        except Exception as e:
            self._hotkey_status = {k: False for k in HOTKEY_KEYS}
            self.hint.configure(text="全局快捷键启动失败：%s" % e)

    # ------------------------------------------------ 打字检测翻译（v2.14）
    def _start_typing(self):
        """按配置启动打字检测监听（默认关闭）。Windows 用 ctypes 低级键盘钩子，
        macOS/Linux 用 pynput；缺 pynput 时功能不可用并在界面明确提示，绝不崩溃。
        开启后重启生效——这里只在启动时调一次，开关打开不立即启动。
        v2.15：专业版功能 —— 没激活、试用也过期时直接不启动钩子；开关
        状态不一致时（比如手改了配置文件）顺手把开关打回去，免得界面撒谎。"""
        if not (self.cfg.get("typing", False) or self.cfg.get("input_translate", False)):
            return
        if getattr(self, "_typing_stop", None) is not None or getattr(self, "_typing_listener", None) is not None:
            return  # v2.15.6：已经在监听，别重复装钩子
        if not license.typing_allowed(self.cfg):
            self.cfg["typing"] = False
            self.cfg["input_translate"] = False
            v = getattr(self, "typing_var", None)
            if v is not None:
                try:
                    v.set(False)
                except Exception:
                    pass
            return
        if IS_WIN:
            # v2.15.6：钩子装不上不再直接放弃 —— 先报真实错误码，再改用轮询兜底。
            stop = None
            try:
                stop = start_typing_hook_win(self.q)
            except Exception as e:
                self.status.configure(text="打字检测翻译：键盘钩子启动失败：%s" % e)
            if stop is None:
                err = getattr(start_typing_hook_win, "last_error", 0)
                try:
                    stop = start_typing_poll_win(self.q)
                except Exception:
                    stop = None
                if stop is not None:
                    self._typing_stop = stop
                    self._typing_poll_fallback = True
                    self.status.configure(text="打字检测翻译：键盘钩子安装失败（%s），已改用轮询监听" % _typing_hook_error_text(err))
                else:
                    self.status.configure(text="打字检测翻译：键盘钩子安装失败（%s），轮询监听也启动失败" % _typing_hook_error_text(err))
            else:
                self._typing_stop = stop
                self._typing_poll_fallback = False
            return
        if keyboard is None:
            self.status.configure(text="打字检测翻译：未安装 pynput，本机不可用（pip install pynput 后重启）")
            return
        try:
            mods = set()

            def _press(key):
                try:
                    if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r,
                               keyboard.Key.alt_l, keyboard.Key.alt_r,
                               keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                        mods.add(key)
                        return
                    if mods:
                        return      # 修饰键组合不捕获
                    ch = getattr(key, "char", None)
                    if ch:
                        self.q.put(("typing_key", ch))
                    elif key == keyboard.Key.space:
                        self.q.put(("typing_key", " "))
                    elif key == keyboard.Key.enter:
                        self.q.put(("typing_key", "\n"))
                    elif key == keyboard.Key.backspace:
                        self.q.put(("typing_key", "\b"))
                    elif key == keyboard.Key.esc:
                        self.q.put(("typing_key", "\x1b"))
                    elif key == keyboard.Key.tab:
                        self.q.put(("typing_key", "\t"))
                except Exception:
                    pass

            def _release(key):
                mods.discard(key)

            self._typing_mods = mods
            listener = keyboard.Listener(on_press=_press, on_release=_release)
            listener.daemon = True
            listener.start()
            self._typing_listener = listener
        except Exception as e:
            self._typing_listener = None
            self.status.configure(text="打字检测翻译：监听启动失败：%s" % e)

    def _stop_typing(self):
        """立即停打字监听、清空缓冲（关闭/退出时调用，隐私优先）。"""
        try:
            if self._typing_stop is not None:
                self._typing_stop()
        except Exception:
            pass
        self._typing_stop = None
        self._typing_poll_fallback = False
        try:
            if self._typing_listener is not None:
                self._typing_listener.stop()
        except Exception:
            pass
        self._typing_listener = None
        buf = getattr(self, "_typing_buffer", None)
        if buf is not None:
            buf.clear()
        self._typing_seq += 1       # 正在翻译的旧请求全部作废
        if getattr(self, "_typing_bubble_active", False):
            try:
                self.bubble.close()
                self.mini.close()
            except Exception:
                pass
            self._typing_bubble_active = False

    def _typing_suppressed(self):
        """当前按键该不该抑制：主窗口获得焦点 / 密码框 / 终端窗口。"""
        try:
            if self.root.focus_get() is not None:
                return True         # 主窗口内已有输入即译，避免双重触发
        except Exception:
            pass
        if IS_WIN:
            try:
                if _foreground_is_password_field_win():
                    return True
                if foreground_is_terminal_win():
                    return True
            except Exception:
                pass
        return False

    def _on_typing_key(self, ch):
        """键盘钩子/pynput 转发来的一个按键（在 Tk 线程里处理）。"""
        if not ch:
            return
        if self.cfg.get("input_translate", False):
            self._on_input_key(ch)
        if ch == "\x00F9" or not self.cfg.get("typing", False):
            return
        buf = self._typing_buffer
        if IS_WIN:
            hwnd = foreground_window_win()
            if self._typing_last_hwnd is None:
                self._typing_last_hwnd = hwnd
            elif hwnd != self._typing_last_hwnd:
                self._typing_last_hwnd = hwnd
                buf.clear()         # 前台窗口一切换就清空缓冲
        # B-3（已评估，不做）：pynput 路径没有窗口切换检测 —— pynput 本身不提供
        # 当前窗口 API；Linux 上要补需另装 python-xlib（只覆盖 X11）或调 xdotool
        # 外部命令（目标机器上一般没有），macOS 则要 pyobjc/AppKit。成本高于收益，
        # 且本软件面向 Windows（Windows 走上面原生分支，已有检测），故不硬上。
        if self._typing_suppressed():
            buf.set_suppressed(True)
            return
        buf.set_suppressed(False)
        ev = buf.feed(ch)
        if ev is not None and ev.get("kind") == "word":
            self._typing_request(ev["text"], ev["kind"])

    # ------------------------------------------------ v2.15.4 输入翻译（打字识别增强）
    def _input_tr(self):
        it = getattr(self, "_input_translator", None)
        trig = self.cfg.get("input_trigger", "space3")
        if it is None or it.trigger_kind != trig:
            it = translator_tools.InputTranslator(trig, is_sensitive=is_sensitive_clip)
            self._input_translator = it
        return it

    def _on_input_key(self, ch):
        """在别的软件里打一句话 → 连按 3 次空格（或 F9）→ 这句话被替换成译文。
        只在 Windows 上做替换（要注入退格和粘贴）；其他系统只把译文放进剪贴板。"""
        it = self._input_tr()
        if getattr(self, "_input_busy", False):
            return                                   # 正在替换：自己注入的按键不算（钩子已过滤注入事件，这里再保险）
        if IS_WIN:
            hwnd = foreground_window_win()
            if hwnd != getattr(self, "_input_hwnd", None):
                self._input_hwnd = hwnd
                it.clear()
        if self._typing_suppressed():
            it.clear()
            return
        ev = it.trigger() if ch == "\x00F9" else it.feed(ch)
        if ev:
            self._input_request(ev)

    def _input_request(self, ev):
        sl, tl = self._codes()
        self._input_busy = True
        self._input_seq = getattr(self, "_input_seq", 0) + 1
        my = self._input_seq
        try:
            self.spinner.start(self.root.winfo_pointerxy(), "输入翻译中…")
        except Exception:
            pass
        hwnd = foreground_window_win() if IS_WIN else 0

        def job():
            try:
                out, _det, _t = translate(ev["text"], sl, tl, self.smart_var.get(), self.engine.get())
                self.q.put(("input_done", my, True, out, ev, hwnd))
            except Exception as e:      # noqa: BLE001
                self.q.put(("input_done", my, False, str(e)[:200], ev, hwnd))
        threading.Thread(target=job, daemon=True).start()

    def _on_input_done(self, my, ok, out, ev, hwnd):
        try:
            self.spinner.stop()
        except Exception:
            pass
        if my != getattr(self, "_input_seq", 0):
            self._input_busy = False
            return
        if not ok or not out.strip():
            self._input_busy = False
            self.status.configure(text="输入翻译失败：%s" % out)
            return
        out = out.strip()
        if not IS_WIN or foreground_window_win() != hwnd or foreground_is_terminal_win():
            self._set_clip(out)
            self.last_clip = out
            self._input_busy = False
            self.status.configure(text="输入翻译：窗口已切换 / 非 Windows，译文已放进剪贴板（Ctrl+V 粘贴）")
            return
        old = self._get_clip()

        def do_replace():
            try:
                send_backspaces_win(ev["erase"])
                self._set_clip(out)
                self.root.update()
                time.sleep(0.03)
                send_paste_win()
            finally:
                # 粘贴完把剪贴板还给用户（等目标程序读完剪贴板）
                self.root.after(400, lambda: (self._set_clip(old), setattr(self, "last_clip", old),
                                              setattr(self, "_input_busy", False)))
        self.root.after(10, do_replace)
        if self.cfg.get("history_on", True) and not is_sensitive_clip(ev["text"]):
            try:
                sl, tl = self._codes()
                self.history.add(ev["text"], out, sl, tl, self.engine.get(), "input", sl, tl)
            except Exception:
                pass
        self.status.configure(text="输入翻译：已替换为译文")

    def _on_input_opt(self):
        self.cfg["input_translate"] = bool(self.input_var.get())
        self.cfg["input_trigger"] = INPUT_TRIGGER_CODES.get(self.input_trigger_cb.get(), "space3")
        if self.cfg["input_translate"] and not license.typing_allowed(self.cfg):
            if license.trial_available(self.cfg):
                license.start_trial(self.cfg)
            else:
                self.input_var.set(False)
                self.cfg["input_translate"] = False
                self._save()
                self._show_license_dialog()
                return
        self._input_translator = None
        self._save()
        hooked = getattr(self, "_typing_stop", None) is not None or getattr(self, "_typing_listener", None) is not None
        if self.cfg["input_translate"] and not hooked:
            self._start_typing()                     # 和打字检测共用一个键盘钩子
        if not (self.cfg["input_translate"] or self.cfg.get("typing")):
            self._stop_typing()
        self._refresh_tray_state()

    def _typing_tick(self):
        """每轮 _poll（约 100ms）调一次：当前词实时跟进 + 停顿兜底。"""
        if not self.cfg.get("typing", False):
            return
        buf = getattr(self, "_typing_buffer", None)
        if buf is None or buf.suppressed:
            return
        ev = buf.tick()
        if ev is not None:
            self._typing_request(ev["text"], ev["kind"])

    def _typing_request(self, text, kind):
        """发一次打字翻译请求：同一气泡内实时更新译文，不弹新气泡。
        敏感内容（is_sensitive_clip 二次把关）不翻、不存历史、不放输入框。"""
        text = (text or "").strip()
        if not text or not typing_detect.is_eligible(text):
            return
        if is_sensitive_clip(text):
            return
        sl, tl = self._codes()
        self._typing_seq += 1
        my = self._typing_seq
        self._typing_buffer.mark_translated(text)
        head = text if len(text) <= 60 else text[:60] + "…"
        try:
            xy = self.root.winfo_pointerxy()
        except Exception:
            xy = (0, 0)
        pop = self._popup()
        self._typing_bubble_active = True
        try:
            if pop.alive():
                # 气泡跟随光标：指针移远了才重定位，否则原地更新译文
                try:
                    ax, ay = pop.anchor
                    if math.hypot(xy[0] - ax, xy[1] - ay) > Bubble.MOVE_AWAY:
                        pop.show(xy, head, "翻译中…", lang=tl)
                    else:
                        pop.update(head, "翻译中…", lang=tl)
                except Exception:
                    pop.update(head, "翻译中…", lang=tl)
            else:
                pop.show(xy, head, "翻译中…", lang=tl)
        except Exception:
            return
        threading.Thread(target=self._typing_worker,
                         args=(my, text, sl, tl, self.smart_var.get(), self.engine.get(), kind),
                         daemon=True).start()

    def _typing_worker(self, my, text, sl, tl, smart, engine, kind="word"):
        """打字翻译的 worker：复用 translate()（引擎/语言/术语表/离线回落全复用），
        但绝不写历史——全局打字的内容不该进历史库。"""
        try:
            out, det, target = translate(text, sl, tl, smart, engine,
                                         cancelled=lambda: my != self._typing_seq)
            self.q.put(("typing_bubble", my, True, out,
                        "%s → %s" % (lang_name(det), lang_name(target)), text, target))
        except Exception as e:      # noqa: BLE001
            if my != self._typing_seq:
                return
            if isinstance(e, offline_engine.OfflineError):
                msg = str(e)
            elif netcheck.is_connectivity_error(e):
                msg = "网络不通，翻译失败。可在主窗口点「网络检查」，或把引擎切到「离线」。"
            else:
                msg = "翻译失败：%s" % e
            self.q.put(("typing_bubble", my, False, msg[:300], "", text, tl))

    def _on_typing_bubble(self, my, ok, out, route, text, lang=None):
        """打字翻译结果回来：同一气泡内更新（旧请求已被新请求作废的直接丢弃）。"""
        if my != self._typing_seq:
            return
        if self.cfg.get("popup_mode") == "main":
            return
        pop = self._popup()
        if not pop.alive():
            return
        head = text.replace("\n", " ")
        head = head if len(head) <= 40 else head[:40] + "…"
        pop.update("%s   %s" % (head, route) if ok else head, out, error=not ok, lang=lang)

    def _on_hotkey(self, which=1):
        if which == 3:
            self.start_screenshot()
            return
        if which == 4:
            self._on_replace_hotkey()
            return
        if which == 5:
            self._translate_clipboard_image()
            return
        if which == 6:
            if self.live_on:
                self.live_stop()
                return
            self.window_translate()
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
            bw, bh = self._OCR_BOX.get(self.grab_scope, self._OCR_BOX["word"])
            self.spinner.start(self.grab_xy, "取词中…", avoid=(bw // 2, bh // 2))
        # OCR 语言/屏幕范围在 Tk 线程里读好：_pointer_grab_win 在 worker 线程里，
        # 不能碰 Tk 控件（v2.7 修复，见 _ocr_pick）。
        self._grab_ocr_lang = self._ocr_lang()
        self._grab_bounds = screen_bounds() or (0, 0, self.root.winfo_screenwidth(),
                                                self.root.winfo_screenheight())
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
                self._pointer_text = self._ocr_pick(
                    self.grab_xy, self.grab_scope,
                    getattr(self, "_grab_ocr_lang", None),
                    getattr(self, "_grab_bounds", None))
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
                self._pointer_text = self._ocr_pick(
                    self.grab_xy, self.grab_scope,
                    getattr(self, "_grab_ocr_lang", None),
                    getattr(self, "_grab_bounds", None))
            except Exception:
                self._pointer_text = None

    def _copy_selection(self):
        try:
            if IS_WIN and self.grab_mode == "pointer":
                self._pointer_grab_win()
                return
            if IS_WIN:
                # M-03：焦点在密码框里时不模拟 Ctrl+C —— 密码不该进剪贴板。
                if _foreground_is_password_field_win():
                    self._grab_aborted = True
                    self.status.configure(text="当前是密码框，不复制")
                    return
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
        try:
            self.spinner.stop()
        except Exception:
            pass
        # M-03：密码框里按了取词热键 —— _copy_selection 已跳过复制，
        # 这里直接收尾，不翻译剪贴板里原来的旧内容。
        if getattr(self, "_grab_aborted", False):
            self._grab_aborted = False
            self.grabbing = False
            return
        try:
            text = self._get_clip()
            if self.grab_mode == "pointer" and getattr(self, "_pointer_text", None):
                text, self._pointer_text = self._pointer_text, None      # OCR 取到的整行 / 整段
        finally:
            # M-03：无论后面翻译成不成功，剪贴板一定要恢复成复制前的旧内容，
            # 不让刚复制的选中文字留在剪贴板里。
            try:
                self._set_clip(self.old_clip)
            except Exception:
                pass
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
                        # H-01：像验证码 / 身份证号 / API 密钥 / 密码的内容不自动翻译、
                        # 不存历史、不放进输入框，只在状态栏提示一次。
                        if is_sensitive_clip(clip):
                            self.status.configure(text="剪贴板内容疑似敏感信息（验证码 / 密码等），已跳过自动翻译")
                            return
                        # v2.15.5：网址 / 邮箱 / 文件路径 / 纯数字 / 纯符号翻了没意义，自动监听时跳过
                        # （想翻可以手动粘贴到输入框，或用取词热键）。
                        info = text_detect.analyze(clip)
                        if not info.translatable:
                            self.status.configure(text="剪贴板内容是%s，已跳过自动翻译" % (info.reason or "非文本"))
                            return
                        self._set_src(clip.strip()[:MAX_LEN])
                        self.show_window()
                        self.translate_now()
        finally:
            self.root.after(600, self._watch_clip)

    def _poll(self):
        try:
            for _drain in range(300):          # v2.10：每轮最多处理 300 条，别让一大波消息把界面堵死
                msg = self.q.get_nowait()
                kind = msg[0]
                self._pet_msg(msg)
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
                elif kind == "doc_confirm":
                    self._on_doc_confirm(*msg[1:])
                elif kind == "doc_prog":
                    if getattr(self, "_doc_busy", False):
                        if not msg[2]:
                            self.status.configure(text="文档已读入，正在估算耗时…")
                        else:
                            eta = msg[3] if len(msg) > 3 else None
                            self.status.configure(text="正在翻译文档 %d/%d%s" % (
                                msg[1], msg[2], "，剩余%s" % fmt_duration(eta) if eta is not None else ""))
                elif kind == "doc_done":
                    self._on_doc_done(msg[1], msg[2])
                elif kind == "image_ocr":
                    self._on_image_ocr(msg[1], msg[2], msg[3])
                elif kind == "stt_done":
                    self._on_stt_done(msg[1], msg[2])
                elif kind == "update_result":
                    self._on_update_result(msg[1], msg[2], msg[3])
                elif kind == "hover_ocr":
                    _, word, xy, ibeam = msg
                    if not (not word and ibeam):
                        self.spinner.stop()          # 退回双击取词时继续转，等复制结果
                    if word and not hover_worth_translating(word):
                        word, ibeam = None, False          # v2.15.3：数字 / 网址 / 标点不翻，也不退回双击
                    elif word and getattr(self, "_hover_dedupe", None) is not None and self._hover_dedupe.seen(word, xy):
                        word, ibeam = None, False          # 刚翻过同一个词：不重复弹
                        self.mini.restore()                # v2.15.8：取词时藏起来的小窗口放回来，别让它凭空消失
                    if word:
                        self._pointer_translate(word, xy)
                    elif ibeam:
                        # OCR 没认出，但光标是「I」形：退回双击取词
                        self.grab_mode = "pointer"
                        self.grab_xy = xy
                        self.grab_scope = SCOPE_CODES.get(self.scope_cb.get(), "word")
                        self.grab_plan = []
                        self._no_ocr = True         # 刚 OCR 过没取到，别再 OCR 一遍
                        self._grab_ocr_lang = self._ocr_lang()
                        self._grab_bounds = screen_bounds() or (
                            0, 0, self.root.winfo_screenwidth(),
                            self.root.winfo_screenheight())
                        self.grabbing = True
                        self.old_clip = self._get_clip()
                        self.root.clipboard_clear()
                        self._seq0 = clip_seq_win() if IS_WIN else 0
                        threading.Thread(target=self._copy_selection, daemon=True).start()
                elif kind == "input_done":
                    self._on_input_done(*msg[1:])
                elif kind == "compare":
                    self._on_compare(*msg[1:])
                elif kind == "key_test":
                    lab = self.key_status.get(msg[1])
                    if lab is not None:
                        lab.configure(text=msg[2])
                elif kind == "hover_err":
                    self.spinner.stop()
                    self._on_hover_err(msg[1], msg[2])
                elif kind == "bubble":
                    self._on_bubble(*msg[1:])
                elif kind == "typing_key":
                    self._on_typing_key(msg[1] if len(msg) > 1 else "")
                elif kind == "typing_bubble":
                    self._on_typing_bubble(*msg[1:])
                elif kind == "typing_hook_error":
                    # v2.15.6：已改用轮询兜底时别把状态栏盖回“已保持关闭”；
                    # 钩子线程是先报错、调用方后处理，所以这里只在确实没监听时才报。
                    if getattr(self, "_typing_stop", None) is None and getattr(self, "_typing_listener", None) is None:
                        code = msg[1] if len(msg) > 1 else 0
                        self.status.configure(text="打字检测翻译：键盘钩子安装失败（%s），已保持关闭" % _typing_hook_error_text(code))
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
                        # v2.8：状态栏末尾加原文 / 译文字数
                        counts = format_status_counts(sum(len(s) for s, _ in pairs),
                                                      sum(len(d) for _, d in pairs))
                        self.status.configure(
                            text="%s → %s%s · %s%s · %s" % (lang_name(det), lang_name(target), extra, eng, warn,
                                                            counts))
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
        self._typing_tick()       # v2.14：打字检测的实时跟进（防抖）与停顿兜底都在这里判
        if IS_WIN and esc_pressed_win():
            try:
                self.spinner.stop()
            except Exception:
                pass
            for pop in (getattr(self, "bubble", None), getattr(self, "mini", None)):
                try:
                    if pop is not None and pop.alive():
                        pop.close()
                        self.bseq += 1              # 正在翻的结果也作废，别关了又弹出来
                except Exception:
                    pass
        self._hover_check()
        try:                                      # v2.12：每轮 poll 都给看门狗打一次心跳
            if getattr(self, "_watchdog", None) is not None:
                self._watchdog.beat()
        except Exception:
            pass
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
    # v2.14：桌面小宠物的动画包要能打开（打包漏了 pets 目录会在这里直接报出来）
    try:
        import pet_pack
        bad = []
        for pid in pet_catalog.pet_ids():
            try:
                pet_pack.PetPack(pet_pack.pack_path(resource_path("pets"), pid))
            except pet_pack.PetPackError as e:
                bad.append("%s（%s）" % (pid, e))
        lines.append("小宠物动画包：%d 只，%s" % (len(pet_catalog.pet_ids()), ("损坏/缺失：" + "、".join(bad[:5])) if bad else "全部可用"))
        if bad:
            ok = False
    except Exception as e:      # noqa: BLE001
        ok = False
        lines.append("小宠物动画包检查出错：%s" % e)
    # v2.13：标准库完整性——标准版的离线运行库是运行时才下载的，它要用的标准库（如 glob）必须已打进 exe
    try:
        import runtime_stdlib
        loaded, missing = runtime_stdlib.preload()
        critical = [m for m in missing if m in ("glob", "ctypes", "importlib.resources", "zipfile", "pathlib",
                                                 "fnmatch", "shutil", "tempfile")]
        lines.append("标准库（运行库依赖）：%d 个可用，缺 %d 个%s" % (
            len(loaded), len(missing), ("：" + ", ".join(missing[:12])) if missing else ""))
        if critical:
            ok = False
            lines.append("  ✘ 关键标准库缺失：%s（离线组件会报 No module named）" % ", ".join(critical))
    except Exception as e:      # noqa: BLE001
        lines.append("标准库自检失败：%s" % e)
    # v2.13：系统 OCR 自检（只在 Windows）：对一张白图跑一遍 winocr.ps1，确认脚本能解析、WinRT 能加载
    if IS_WIN:
        try:
            probe = os.path.join(DATA_DIR, "ocr_selftest.bmp")
            os.makedirs(DATA_DIR, exist_ok=True)
            screen_win.save_bmp(probe, 64, 64, b"\xff\xff\xff\x00" * (64 * 64))
            try:
                ocr_win.ocr_lines(probe)
                lines.append("系统 OCR：脚本可运行（白图无文字，返回空属正常）")
            except ocr_win.OcrError as e:
                msg = str(e)
                lines.append("系统 OCR：%s" % msg)
                # v2.15.6：脚本被改动也算不通过 —— OCR 完全不可用，不能只记一行就放过去
                #（以前只有“解析失败 / 无法加载”才判失败，2.15.5 的误报就是这么从自检里漏过去的）。
                if "解析失败" in msg or "无法加载" in msg or "已被改动" in msg:
                    ok = False
            finally:
                try:
                    os.remove(probe)
                except Exception:
                    pass
        except Exception as e:      # noqa: BLE001
            lines.append("系统 OCR 自检出错：%s" % e)
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
    # v2.8 单实例：Windows 用命名互斥体，非 Windows 用文件锁；已有实例在跑
    # 就唤起它的主窗口并退出。检查本身绝不能阻止启动（single_instance 内部 fail-open）。
    # _single 必须留在 main 的局部变量里：App().run() 期间它一直活着，锁才一直占着。
    _single = single_instance.ensure_single_instance()
    if _single is None:
        return
    try:
        App().run()
    except Exception:
        import traceback
        log_crash(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
