"""v2.15.3 联通性：代理端口检测、整体超时、单项出错不拖垮报告。无需外网。"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import netcheck as nc
P = nc.parse_proxy_hostport
assert P("http://u:p@127.0.0.1:7890") == ("127.0.0.1", 7890) and P("127.0.0.1:1080") == ("127.0.0.1", 1080)
assert P("") is None
c = nc.check_proxy_alive("http://127.0.0.1:1")
assert c.ok is False and "代理软件" in c.hint
r = nc.recommend([nc.Check("net", "", True), nc.Check("proxy_alive", "", False, None, "x"),
                  nc.Check("google", "", False), nc.Check("ms", "", False), nc.Check("offline", "", None)])
assert r.level == "bad" and "代理" in r.message
nc.check_connectivity = lambda: nc.Check("net", "n", True, 5)
nc.check_dns = lambda: nc.Check("dns", "d", True)
def boom(): raise ValueError("x")
t0 = time.time()
checks, reco = nc.run_all(lambda: time.sleep(60), boom, {"runtime": False}, proxy_url="http://127.0.0.1:1", total_timeout=3)
assert time.time() - t0 < 5, "run_all must respect total_timeout"
keys = {c.key for c in checks}
assert "proxy_alive" in keys and "ms" in keys and "google" not in keys
assert nc.effective_proxy("http://a:1") == "http://a:1"
print("PASS test_netcheck_v2153")
