"""v2.15.3 取词：文字清洗、悬停过滤、去重。纯逻辑，任何系统都能跑。"""
import os, re, ast, time, types
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(BASE, "desktop_translator.py"), encoding="utf-8").read()
ocr = open(os.path.join(BASE, "ocr_win.py"), encoding="utf-8").read()
o = {}; exec(ocr[ocr.index("def _is_cjk"):ocr.index("def join_lines")], o)
ns = {"re": re, "time": time, "ocr_win": types.SimpleNamespace(_is_cjk=o["_is_cjk"])}
exec(src[src.index("_ZERO_WIDTH = "):src.index("def pointer_plan")], ns)
N, H, D = ns["normalize_grab_text"], ns["hover_worth_translating"], ns["HoverDedupe"]
assert N("transla-\ntion engine") == "translation engine"
assert N("hello\nworld") == "hello world" and N("你好\n世界") == "你好世界"
assert N("a\n\nb") == "a\nb" and N("he\u200bllo  \t x") == "hello x"
assert not H("12,345") and not H("https://a.com") and not H("a@b.com") and not H("a")
assert H("字") and H("Hello")
d = D(); assert not d.seen("x", (0, 0), 0) and d.seen("x", (10, 10), 1) and not d.seen("x", (10, 10), 9)
print("PASS test_grab_v2153")
