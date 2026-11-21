"""v2.15.4 常用翻译软件功能 + 输入翻译：纯逻辑（不需要界面 / 网络）。"""
import os, re, sys, random
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
import translator_tools as tt
res = []
def ok(n, c): print(("PASS " if c else "FAIL ") + n); res.append(bool(c))
ok("split identifier", tt.split_identifier("parseHTTPResponse_v2") == ["parse", "http", "response", "v", "2"])
ok("to_case", tt.to_case("user login count", "camel") == "userLoginCount" and tt.to_case("userLoginCount", "snake") == "user_login_count"
   and tt.to_case("a b", "constant") == "A_B" and tt.to_case("get id", "pascal") == "GetId" and tt.to_case("x y", "kebab") == "x-y")
ok("looks_like_identifier", tt.looks_like_identifier("user id") and not tt.looks_like_identifier("中文"))
ok("clean_text", tt.clean_text("Hello \u201cw\u201d\n\n\n\n12\nPage 3 of 9\n\u7b2c 4 \u9875\n- 5 -\nnext\u3000line") == 'Hello "w"\n\nnext line')
ok("clean line numbers", tt.clean_text("1  def f():\n2     return 1", True) == "def f():\nreturn 1")
ok("compare plan", tt.compare_plan(["\u81ea\u52a8", "Google", "DeepL", "Lingva"], lambda e: e != "DeepL") == ["Google", "Lingva"])
cr = tt.CompareResult(["A", "B", "C"]); cr.add("B", True, "x y", 1); cr.add("A", True, "xy", 2); cr.add("C", False, "e", 3)
ok("compare result", cr.finished() and [e for e, *_ in cr.done] == ["B", "A", "C"] and sorted(cr.agreement()) == ["A", "B"])
ok("deepl formality", tt.deepl_formality("formal") == "prefer_more" and tt.deepl_formality("default") is None)
it = tt.InputTranslator(); r = None
for ch in "hello world   ":
    r = it.feed(ch) or r
ok("input: space x3 -> replace", r == {"kind": "replace", "text": "hello world", "erase": 14})
it = tt.InputTranslator(is_sensitive=lambda t: "password" in t); r = None
for ch in "password=abc   ":
    r = it.feed(ch) or r
ok("input: sensitive skipped", r is None)
it = tt.InputTranslator("f9")
for ch in "good morning   ":
    it.feed(ch)
ok("input: f9", it.trigger()["text"] == "good morning")
it = tt.InputTranslator(); [it.feed(c) for c in "abc\n"]; ok("input: enter clears", it.buf == "")
random.seed(5); bad = 0
for _ in range(5000):
    it = tt.InputTranslator(random.choice(["space3", "f9"]))
    try:
        for c in "".join(random.choice("ab \u4e2d\b\n\x1b.") for _ in range(random.randint(0, 60))):
            x = it.feed(c)
            if x:
                assert x["erase"] >= len(x["text"])
        it.trigger()
    except Exception:
        bad += 1
ok("input fuzz", bad == 0)
src = open(os.path.join(BASE, "desktop_translator.py"), encoding="utf-8").read()
ok("F9 forwarded by hook", "vk == 0x78" in src)
ok("backspaces capped", "min(int(n), 400)" in src)
ok("clipboard restored after input replace", "self._set_clip(old)" in src)
ok("tray has compare + input", '"id": "compare"' in src and '"id": "input"' in src)
assert all(res)
