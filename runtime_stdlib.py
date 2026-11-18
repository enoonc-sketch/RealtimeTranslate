"""标准版 exe 的「运行库用得到的标准库」清单（v2.13）。

背景：标准版 exe 里没有 ctranslate2 / sentencepiece / numpy，它们是用户在程序里点一下才下载到
%APPDATA% 再加载的。PyInstaller 只会打包「程序自己」import 到的标准库，所以运行库一 import
就可能报 No module named 'xxx'。2.12.0 的清单是在 Linux 上实测的，漏掉了 ctranslate2 的
Windows 专属分支用到的 glob（ctranslate2/__init__.py：if sys.platform == "win32": import glob）。

这里用「真的 import 一遍」的写法把它们全部列出来：PyInstaller 做静态分析时会因此把这些模块
收进 exe，不依赖 .spec 里的 hiddenimports 清单是否写全（两处都写，双保险）。
每个都包 try/except，缺哪个都不影响程序启动。
"""
import importlib

# Windows 专属 / 容易漏的放最前面；其余是 numpy / sentencepiece / ctranslate2 / yaml 常见依赖
NEEDED = [
    "glob", "fnmatch", "ctypes", "ctypes.util", "ctypes.wintypes", "importlib.resources",
    "importlib.metadata", "importlib.util", "importlib.machinery", "pathlib", "zipfile", "shutil",
    "tempfile", "platform", "secrets", "hmac", "hashlib", "random", "struct", "pickle", "copyreg",
    "weakref", "gc", "inspect", "dis", "ast", "textwrap", "pprint", "difflib", "string", "re",
    "warnings", "contextlib", "functools", "itertools", "collections", "collections.abc",
    "operator", "numbers", "decimal", "fractions", "statistics", "math", "cmath", "bisect",
    "heapq", "array", "queue", "threading", "concurrent.futures", "multiprocessing", "asyncio",
    "subprocess", "signal", "selectors", "socket", "ssl", "logging", "logging.handlers",
    "json", "csv", "base64", "binascii", "codecs", "locale", "datetime", "calendar", "time",
    "typing", "types", "enum", "abc", "io", "os", "sys", "stat", "errno", "copy", "traceback",
    "linecache", "tokenize", "token", "keyword", "reprlib", "uuid", "getpass", "shlex",
    "sysconfig", "zlib", "lzma", "bz2", "gzip", "tarfile", "sqlite3", "unicodedata",
    "urllib.request", "urllib.parse", "urllib.error", "http.client", "email.utils", "ipaddress",
    "quopri", "argparse", "configparser", "mmap", "opcode",
]

LOADED, MISSING = [], []


def preload():
    """真的 import 一遍（供自检用）；返回 (成功列表, 失败列表)。"""
    LOADED.clear()
    MISSING.clear()
    for name in NEEDED:
        try:
            importlib.import_module(name)
            LOADED.append(name)
        except Exception:      # noqa: BLE001
            MISSING.append(name)
    return list(LOADED), list(MISSING)


# ↓ 下面这一长串「静态 import」是给 PyInstaller 的分析器看的，运行时几乎零开销（都已在 sys.modules 里或很轻）
try:                                            # noqa: E401
    import glob, fnmatch, secrets, hmac, difflib, pprint, uuid, getpass, shlex, sysconfig        # noqa: F401,E401
    import gzip, tarfile, mmap, argparse, configparser, decimal, fractions, statistics, cmath    # noqa: F401,E401
    import ctypes.util, concurrent.futures, logging.handlers, multiprocessing, unicodedata       # noqa: F401,E401
except Exception:      # noqa: BLE001
    pass
