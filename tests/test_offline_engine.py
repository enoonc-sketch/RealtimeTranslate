"""离线引擎测试（用随机权重的微型模型验证整条推理链路；译文是乱码，只验证流程）。
运行：python tests/test_offline_engine.py   需要 pip install ctranslate2 sentencepiece numpy"""
import os, shutil, sys, tempfile, zipfile, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import offline_engine as oe
from make_fake_model import make_pkg

fails = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

check("runtime_present", oe.runtime_present())
tmp = tempfile.mkdtemp()
bundled = os.path.join(tmp, "bundled"); user = os.path.join(tmp, "用户 数据", "models")   # 路径含中文和空格
en = ["hello world this is a test", "how are you today", "good morning everyone"] * 6
zh = ["你好世界这是一个测试", "你今天好吗", "大家早上好"] * 6
make_pkg(bundled, "en", "zh", en + zh)
make_pkg(bundled, "zh", "en", zh + en, seed=1)
eng = oe.Engine([(user, "用户"), (bundled, "内置")])
check("scan finds 2 packs", eng.pairs() == [("en", "zh"), ("zh", "en")])
check("available", eng.available())

# translate: batch of sentences, newlines preserved, CJK joined without spaces
out = eng.translate("Hello world. How are you?\n\nGood morning everyone.", "en", "zh")
print("   out(前60字):", repr(out[:60]))
check("newline structure kept", out.count("\n") == 2 and out.split("\n")[1] == "")
check("same-lang passthrough", eng.translate("abc", "en", "en") == "abc")
try:
    eng.translate("x", "en", "ja"); check("missing pair raises OfflineError", False)
except oe.OfflineError as e:
    check("missing pair raises OfflineError", "en → ja" in str(e) and "en→zh" in str(e))

# pivot through English: add ja->en only; zh->ja needs en->ja -> still missing; ja->zh = ja->en + en->zh
make_pkg(bundled, "ja", "en", ["こんにちは世界", "ありがとう"] * 10 + en, seed=2)
eng.reload()
check("pivot route ja->zh via en", [(p.from_code, p.to_code) for p in eng.route("ja", "zh")] == [("ja", "en"), ("en", "zh")])
o = eng.translate("こんにちは世界", "ja", "zh")
check("pivot translate runs", isinstance(o, str))

# cancel
try:
    eng.translate("Hello world.", "en", "zh", cancelled=lambda: True); check("cancel", False)
except RuntimeError as e:
    check("cancel", "cancelled" in str(e))

# sentence splitter
s = oe.split_sentences("Hi there. This is fine! 你好。再见！ Pi is 3.14 ok?")
check("split_sentences", s == ["Hi there.", "This is fine!", "你好。", "再见！", "Pi is 3.14 ok?"] or print(s))
long = ", ".join("word%d" % i for i in range(200))
check("long sentence wrapped <= MAX", all(len(x) <= oe.MAX_SENT_CHARS for x in oe.split_sentences(long)))

# install .argosmodel (zip) incl. zip-slip rejection
src = make_pkg(os.path.join(tmp, "src"), "en", "ja", en + ["こんにちは"] * 10, seed=3)
arc = os.path.join(tmp, "translate-en_ja-1_0.argosmodel")
with zipfile.ZipFile(arc, "w") as z:
    for r, _, fs in os.walk(src):
        for f in fs:
            full = os.path.join(r, f); z.write(full, os.path.relpath(full, os.path.dirname(src)))
pkg = oe.install_package(arc, user)
eng.reload()
check("install_package + reload", ("en", "ja") in eng.pairs() and pkg.usable)
check("installed pack translates", isinstance(eng.translate("Hello world.", "en", "ja"), str))
evil = os.path.join(tmp, "evil.argosmodel")
with zipfile.ZipFile(evil, "w") as z:
    z.writestr("p/metadata.json", "{}"); z.writestr("../../escape.txt", "x")
try:
    oe.install_package(evil, user); check("zip-slip rejected", False)
except oe.OfflineError:
    check("zip-slip rejected", not os.path.exists(os.path.join(tmp, "escape.txt")))
try:
    oe.install_package(os.path.join(HERE, "test_offline_engine.py"), user); check("non-zip rejected", False)
except oe.OfflineError as e:
    check("non-zip rejected", "不是有效的语言包" in str(e))

# version preference
make_pkg(user, "en", "zh", en + zh, seed=9)   # same version/dir name as bundled; user has priority
eng.reload()
check("user dir has priority on tie", eng._by_pair[("en", "zh")].source == "用户")

# LRU eviction doesn't break
oe.MAX_LOADED = 1
for a, b in (("en", "zh"), ("zh", "en"), ("en", "zh")):
    eng.translate("hello world", a, b)
check("LRU eviction ok", len(eng._loaded) == 1)

# thread safety
import threading
errs = []
def w():
    try:
        for _ in range(5): eng.translate("hello world. good morning everyone", "en", "zh")
    except Exception as e: errs.append(e)
ts = [threading.Thread(target=w) for _ in range(4)]; [t.start() for t in ts]; [t.join() for t in ts]
check("concurrent translate", not errs)
shutil.rmtree(tmp, ignore_errors=True)
print("\nFAILED:", fails if fails else "none"); sys.exit(1 if fails else 0)
