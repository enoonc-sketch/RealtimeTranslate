"""网络检查 + 在线失败自动回退离线 + 熔断 的测试（网络全部模拟）。"""
import os, sys, socket, ssl, tempfile, time, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netcheck as nc, offline_engine as oe
import desktop_translator as dt
from make_fake_model import make_pkg

fails = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

# ---- explain_error
U = urllib.error.URLError
cases = [
    (U(socket.gaierror(-2, "x")), "DNS"), (U(socket.timeout("timed out")), "超时"),
    (U(ssl.SSLCertVerificationError("CERTIFICATE_VERIFY_FAILED")), "证书"),
    (U(ConnectionRefusedError()), "拒绝"), (U(ConnectionResetError()), "重置"),
    (urllib.error.HTTPError("u", 429, "x", {}, None), "429"), (urllib.error.HTTPError("u", 407, "x", {}, None), "代理"),
    (urllib.error.HTTPError("u", 503, "x", {}, None), "服务端"),
]
for exc, kw in cases:
    check("explain %s" % kw, kw in nc.explain_error(exc)[0])
check("connectivity: URLError yes / HTTP 429 no",
      nc.is_connectivity_error(U("x")) and not nc.is_connectivity_error(urllib.error.HTTPError("u", 429, "x", {}, None)))
check("mask proxy creds", nc.mask_proxy("http://bob:pw@10.0.0.1:8080") == "http://***@10.0.0.1:8080")

# ---- recommend
def C(key, ok, ms=100): return nc.Check(key, key, ok, ms if ok else None)
R = nc.recommend
check("both ok -> fastest", R([C("net", True), C("google", True, 300), C("ms", True, 100), C("offline", None)]).engine == "微软")
check("only ms -> 微软 (warn)", (lambda r: r.engine == "微软" and r.level == "warn")(R([C("net", True), C("google", False), C("ms", True), C("offline", None)])))
check("only offline -> 离线", R([C("net", True), C("google", False), C("ms", False), C("offline", True)]).engine == "离线")
r = R([C("net", False), C("google", False), C("ms", False), C("offline", None)])
check("nothing -> None/bad, mentions 无法联网", r.engine is None and r.level == "bad" and "无法联网" in r.message)
r = R([C("net", True), C("google", False), C("ms", False), C("offline", None)])
check("net ok but engines blocked -> distinct message", r.engine is None and "拦截" in r.message)

# ---- run_all with fake engines: failure classification + timeout doesn't hang
nc.check_connectivity = lambda: nc.Check("net", "基础联网（外网 TCP 直连）", True, 20)
nc.check_dns = lambda: nc.Check("dns", "DNS 解析", True)
def slow(): time.sleep(5)
seen = []
t0 = time.time()
checks, reco = nc.run_all(lambda: (_ for _ in ()).throw(U(socket.timeout("timed out"))), lambda: "你好",
                          {"runtime": False}, on_item=seen.append)
by = {c.key: c for c in checks}
check("run_all: google timeout classified, ms ok", by["google"].ok is False and "超时" in by["google"].detail and by["ms"].ok)
check("run_all: recommends 微软 + callback per item", reco.engine == "微软" and len(seen) == 6)
t0 = time.time()
c = nc.check_engine("g", "G", slow, timeout=1)
check("check_engine times out without blocking", time.time() - t0 < 2 and c.ok is False)
check("report text", "结论：" in nc.format_report(checks, reco, "H") and "✘ Google 翻译" in nc.format_report(checks, reco))

# ---- fallback to offline + circuit breaker + no cache pollution
tmp = tempfile.mkdtemp()
en = ["hello world this is a test", "good morning everyone"] * 8; zh = ["你好世界这是一个测试", "大家早上好"] * 8
make_pkg(tmp, "en", "zh", en + zh); make_pkg(tmp, "zh", "en", zh + en, seed=1)
dt.OFFLINE = oe.Engine([(tmp, "测试")])
dt.AUTO_OFFLINE = True
calls = {"g": 0}
def dead(text, sl, tl, attempts=3, timeout=12):
    calls["g"] += 1; raise U(socket.gaierror(-2, "no dns"))
dt.g_translate = dead
dt.CACHE.clear(); dt.reset_online_state()
n0 = dt.fallback_count()
out, det = dt.cached("Hello world", "auto", "zh-CN", "Google")
check("online dead -> offline result returned", isinstance(out, str) and dt.fallback_count() == n0 + 1)
check("fallback result NOT cached", ("Hello world", "auto", "zh-CN", "Google") not in dt.CACHE)
g_before = calls["g"]
for i in range(5): dt.cached("Good morning %d" % i, "auto", "zh-CN", "Google")
check("circuit breaker: no more online attempts while down", calls["g"] == g_before)
dt.reset_online_state()
dt.cached("Another one", "auto", "zh-CN", "Google")
check("reset -> online retried", calls["g"] == g_before + 1)

# recovery: online works again -> real result cached
dt.g_translate = lambda t, sl, tl, attempts=3, timeout=12: ("在线:" + t, "en")
dt.reset_online_state(); dt.CACHE.clear()
out, _ = dt.cached("Hello again", "auto", "zh-CN", "Google")
check("recovery uses online + caches", out == "在线:Hello again" and ("Hello again", "auto", "zh-CN", "Google") in dt.CACHE)

# toggle off -> error surfaces
dt.g_translate = dead; dt.AUTO_OFFLINE = False; dt.reset_online_state(); dt.CACHE.clear()
try:
    dt.cached("Hello", "auto", "zh-CN", "Google"); check("auto-offline off -> raises", False)
except Exception:
    check("auto-offline off -> raises", True)
# no pack for the pair -> original network error (not a confusing offline one)
dt.AUTO_OFFLINE = True; dt.reset_online_state()
try:
    dt.cached("Hello", "auto", "ja", "Google"); check("no pack for pair -> original error", False)
except U:
    check("no pack for pair -> original error", True)
# 429 is not a connectivity failure -> breaker stays closed
def r429(text, sl, tl, attempts=3, timeout=12): raise urllib.error.HTTPError("u", 429, "x", {}, None)
dt.g_translate = r429; dt.ms_translate = lambda *a, **k: (_ for _ in ()).throw(urllib.error.HTTPError("u", 429, "x", {}, None))
dt.reset_online_state()
try: dt.cached("zzz", "auto", "zh-CN", "Google")
except Exception: pass
check("429 does not open breaker", dt._state["down_until"] == 0.0)

# offline engine explicit + selftest
dt.CACHE.clear()
check("engine=离线 works", isinstance(dt.cached("Hello world", "en", "zh-CN", "离线")[0], str))
dt.DATA_DIR = tempfile.mkdtemp()
rc = dt.run_selftest()
rep = open(os.path.join(dt.DATA_DIR, "selftest.txt"), encoding="utf-8").read()
check("selftest passes + lists pairs", rc == 0 and "en→zh" in rep and "结果：通过" in rep)
print("\nFAILED:", fails if fails else "none"); sys.exit(1 if fails else 0)
