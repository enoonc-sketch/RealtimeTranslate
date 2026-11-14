import sys, threading, time, json, io, urllib.error
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import desktop_translator as dt

fails = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

calls = []
def fake_google(text, sl, tl):
    calls.append(len(text))
    det = "zh-CN" if any("\u4e00" <= c <= "\u9fff" for c in text) else "en"
    return "[%s>%s]%s" % (sl, tl, text[:5]), det
dt.g_translate = fake_google

# 1. long single paragraph is chunked (old code sent it in one request)
long_text = "".join("Sentence number %d is here. " % i for i in range(800))[:20000]   # one line, ~20000 chars, all unique
out, det, tgt = dt.translate(long_text, "auto", "zh-CN", True, "Google")
check("long single paragraph chunked <= CHUNK", max(calls) <= dt.CHUNK and len(calls) >= 10)

# 2. smart mode: zh text -> zh target flips to en
dt.CACHE.clear()
out, det, tgt = dt.translate("你好世界，这是测试。", "auto", "zh-CN", True, "Google")
check("smart flip zh->en", tgt == "en" and "[zh-CN>en]" in out)

# 3. doc translate keeps blank lines / order
dt.CACHE.clear()
doc = "Title\n\nFirst para line one\nsecond line.\n\n- item a\n- item b"
pairs, det, tgt = dt.translate_doc(doc, "auto", "zh-CN", True, True, "Google", lambda d, n: None, lambda: False)
check("doc pairs preserve blank line", ("", "") in pairs and len(pairs) == 7)

# 4. cancellation
dt.CACHE.clear()
try:
    dt.translate_doc("a\nb\nc\nd", "auto", "zh-CN", True, False, "Google", lambda d, n: None, lambda: True)
    check("cancel raises", False)
except RuntimeError as e:
    check("cancel raises", "cancelled" in str(e))

# 5. LRU + thread safety (old code could KeyError after CACHE.clear())
dt.CACHE.clear(); dt.CACHE_MAX = 50
errs = []
def hammer(i):
    try:
        for j in range(300):
            dt.cached("t%d" % ((i * 7 + j) % 200), "auto", "zh-CN", "Google")
    except Exception as e:
        errs.append(e)
ts = [threading.Thread(target=hammer, args=(i,)) for i in range(8)]
[t.start() for t in ts]; [t.join() for t in ts]
check("cache thread-safe, bounded", not errs and len(dt.CACHE) <= 50)
dt.CACHE_MAX = 800

# 6. rate-limit detection
h429 = urllib.error.HTTPError("u", 429, "Too Many", {}, None)
h500 = urllib.error.HTTPError("u", 500, "Server", {}, None)
check("429 detected", dt._is_rate_limit(h429))
check("500 not rate limit", not dt._is_rate_limit(h500))
check("'generate' text not rate limit", not dt._is_rate_limit(Exception("failed to generate")))

# 7. MS: token fetch, reuse, refresh on 401
seq = []
class R:
    def __init__(s, b): s.b = b
    def read(s): return s.b
    def __enter__(s): return s
    def __exit__(s, *a): pass
state = {"auth": 0, "tr": 0}
def fake_urlopen(req, timeout=0):
    url = req.full_url
    if url.startswith(dt.MS_AUTH):
        state["auth"] += 1
        return R(("tok%d" % state["auth"]).encode())
    state["tr"] += 1
    if state["tr"] == 1:
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)
    assert req.headers["Authorization"] == "Bearer tok2", req.headers
    return R(json.dumps([{"detectedLanguage": {"language": "zh-Hans"}, "translations": [{"text": "hello"}]}]).encode())
dt.urllib.request.urlopen = fake_urlopen
dt.time.sleep = lambda s: None
o, d = dt.ms_translate("你好", "auto", "en")
check("MS 401 -> token refresh -> ok", o == "hello" and d == "zh-CN" and state["auth"] == 2)

# 8. argos script guess
check("guess_lang", [dt.guess_lang(x) for x in ("こんにちは", "안녕하세요", "Привет", "你好", "hello")] == ["ja", "ko", "ru", "zh", "en"])

# 9. config sanitize
import os, tempfile
dt.CONFIG_PATH = os.path.join(tempfile.mkdtemp(), "c.json")
dt.OLD_CONFIG_PATH = dt.CONFIG_PATH + ".old"
json.dump({"engine": "bogus", "tl": "xx", "sl": "yy", "geometry": "garbage"}, open(dt.OLD_CONFIG_PATH, "w"))
c = dt.App._load_cfg()
check("old config migrated + sanitized", c["engine"] == "Google" and c["tl"] == "zh-CN" and c["sl"] == "auto" and c["geometry"] == dt.DEFAULTS["geometry"])

print("\nFAILED:", fails if fails else "none")
sys.exit(1 if fails else 0)
