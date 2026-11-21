"""v2.15.4 内置引擎（模拟网络）+ 设置搜索。无需外网。"""
import os, sys, json, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import desktop_translator as dt
class R:
    def __init__(s, b): s.b = b
    def __enter__(s): return s
    def __exit__(s, *a): pass
    def read(s, n=-1): return s.b
def fake(req, timeout=None):
    u = req.full_url
    if "lingva.ml" in u: raise OSError("down")
    if "lingva" in u: return R(json.dumps({"translation": "你好", "info": {"detectedSource": "en"}}).encode())
    return R(json.dumps({"responseStatus": 200, "responseData": {"translatedText": "Tom &amp; 你好"}}).encode())
dt._urlopen = fake
dt._read_capped = lambda r, n: r.b
assert dt.lingva_translate("hello", "en", "zh-CN") == ("你好", "en")
assert dt.mymemory_translate("hi", "en", "zh-CN")[0] == "Tom & 你好"
assert dt.auto_order("Lingva")[0] == "Lingva"
def down(*a, **k): raise OSError("x")
dt.g_translate = down; dt.ms_translate = down
assert dt.auto_translate("hello", "en", "zh-CN") == ("你好", "en") and dt._auto_state["last_ok"] == "Lingva"
assert {"自动", "Lingva", "MyMemory"} <= set(dt.ENGINES)
M = dt.App._settings_match
idx = [("grab", 1, "悬停取词 鼠标停住"), ("offline", 2, "使用代理服务器")]
assert M(idx, "悬停 鼠标") == [idx[0]] and M(idx, "") == []
print("PASS test_engines_v2154")
