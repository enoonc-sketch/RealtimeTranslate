"""离线运行库在线安装：选轮子、安装/校验/路径安全/取消续传/回滚/激活。本地假 PyPI，不联网。"""
import hashlib, io, json, os, random, sys, tempfile, threading, zipfile, http.server, functools
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import offline_engine as oe, pack_downloader as pd, runtime_installer as ri

tmp = tempfile.mkdtemp(); srv = os.path.join(tmp, "srv"); os.makedirs(os.path.join(srv, "pypi")); os.makedirs(os.path.join(srv, "whl"))
tag = ri.py_tag(); LX = "manylinux_2_17_x86_64.manylinux2014_x86_64"
def wheel(name, files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for n, data in files.items(): z.writestr(n, data)
    return buf.getvalue()
rng = random.Random(3); BIGDATA = bytes(rng.getrandbits(8) for _ in range(3_000_000))
files = {}                                   # filename -> bytes
def add(pkg, ver, py, abi, plat, content, **extra):
    fn = "%s-%s-%s-%s-%s.whl" % (pkg, ver, py, abi, plat); files[fn] = content
    d = dict(packagetype="bdist_wheel", filename=fn, url=B + "whl/" + fn, size=len(content),
             digests={"sha256": hashlib.sha256(content).hexdigest()}); d.update(extra); return d
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/whl/"):
            data = files.get(self.path[5:])
            if data is None: self.send_response(404); self.end_headers(); return
            rh = self.headers.get("Range")
            start = int(rh.split("=")[1].rstrip("-")) if rh else 0
            self.send_response(206 if rh else 200)
            if rh: self.send_header("Content-Range", "bytes %d-%d/%d" % (start, len(data) - 1, len(data)))
            self.send_header("Content-Length", str(len(data) - start)); self.end_headers(); self.wfile.write(data[start:]); return
        return super().do_GET()
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=srv))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d/" % httpd.server_port
INDEX = B + "pypi/%s/json"

def publish(pkg, releases):
    json.dump({"releases": releases}, open(os.path.join(srv, "pypi", pkg + ".json"), "w"))
    os.makedirs(os.path.join(srv, "pypi", pkg), exist_ok=True)
    os.replace(os.path.join(srv, "pypi", pkg + ".json"), os.path.join(srv, "pypi", pkg, "json"))
def good(pkg, ver="1.0", extra=None):
    f = {pkg + "/__init__.py": "VERSION = %r\n" % ver, pkg + "/tests/test_x.py": "x", pkg + "/data.bin": "d" * 1000}
    f.update(extra or {}); return f
for pkg in ri.PKGS:
    publish(pkg, {
        "1.0": [add(pkg, "1.0", tag, tag, LX, wheel(pkg, good(pkg, "1.0")))],
        "2.0": [add(pkg, "2.0", tag, tag, LX, wheel(pkg, good(pkg, "2.0"))),
                add(pkg, "2.0", tag, tag, "win_amd64", wheel(pkg, good(pkg, "x"))),          # 别的系统：不能选
                add(pkg, "2.0", tag, tag, "musllinux_1_2_x86_64", wheel(pkg, good(pkg, "x")))],
        "3.0rc1": [add(pkg, "3.0rc1", tag, tag, LX, wheel(pkg, good(pkg, "x")))],              # 预发布：不能选
        "4.0": [add(pkg, "4.0", "cp27", "cp27m", LX, wheel(pkg, good(pkg, "x")))],              # Python 不匹配：不能选
        "5.0": [add(pkg, "5.0", tag, tag, LX, wheel(pkg, good(pkg, "x")), yanked=True)],        # 被撤回：不能选
    })
res = []
def ok(n, c): print(("PASS " if c else "FAIL ") + n); res.append(bool(c))

# ---- 选轮子 ----
d = json.load(open(os.path.join(srv, "pypi", "numpy", "json")))
w = ri.pick_wheel(d, tag)
ok("pick: highest compatible (skips other OS / musl / rc / wrong python / yanked)", w and w["version"] == "2.0" and LX in w["filename"])
ok("pick: abi3 wheel for older cpXY accepted", ri._wheel_ok("x-1-cp39-abi3-%s.whl" % LX, "cp312") and not ri._wheel_ok("x-1-cp313-abi3-%s.whl" % LX, "cp312"))
ok("pick: pure-python wheel (none-any) is not accepted for compiled platform filter", not ri._wheel_ok("x-1-py3-none-any.whl", tag))
ok("pick: nothing matches -> None", ri.pick_wheel({"releases": {"1.0": []}}, tag) is None)
ok("apply_replace multi pairs", pd.apply_replace("https://pypi.org/a files.pythonhosted.org", "pypi.org=m1.cn;files.pythonhosted.org=m2.cn") == "https://m1.cn/a m2.cn")

# ---- 安装 ----
rt = os.path.join(tmp, "rt"); prog = []
v = ri.install(rt, progress=lambda *a: prog.append(a), index=INDEX)
site = os.path.join(rt, "site")
ok("install returns picked versions", v == {p: "2.0" for p in ri.PKGS})
ok("files extracted, tests/ skipped", all(os.path.isfile(os.path.join(site, p, "__init__.py")) for p in ri.PKGS) and not os.path.exists(os.path.join(site, "numpy", "tests")))
ok("manifest + installed()", ri.installed(rt) == v and ri.installed(rt, "cp27") is None)
ok("downloads and staging cleaned", not os.path.exists(os.path.join(rt, "_downloads")) and not os.path.exists(os.path.join(rt, "_new")))
ok("progress covers all 4 packages", {a[0] for a in prog} == {0, 1, 2, 3} and all(a[1] == 4 for a in prog))
# 激活
before = list(sys.path); ok("activate adds site once", ri.activate(rt) and ri.activate(rt) and sys.path.count(site) == 1)
sys.path[:] = before
ok("activate without install -> False", not ri.activate(os.path.join(tmp, "nothing")))
# 重装：旧版本被整体替换（新版本号、不残留旧文件）
open(os.path.join(site, "numpy", "stale.txt"), "w").write("old")
ri.install(rt, index=INDEX)
ok("reinstall replaces site atomically (stale file gone)", not os.path.exists(os.path.join(site, "numpy", "stale.txt")) and os.path.isdir(site) and not os.path.exists(site + ".old"))

# ---- 失败路径 ----
def fresh(): return os.path.join(tempfile.mkdtemp(), "rt")
# 校验失败
bad = good("numpy"); okw = add("numpy", "9.0", tag, tag, LX, wheel("numpy", bad))
files[okw["filename"]] = wheel("numpy", good("numpy", "tampered"))                      # 内容与索引里的 sha256 不符
rel = json.load(open(os.path.join(srv, "pypi", "numpy", "json"))); rel["releases"]["9.0"] = [okw]
json.dump(rel, open(os.path.join(srv, "pypi", "numpy", "json"), "w"))
r2 = fresh()
try: ri.install(r2, index=INDEX); ok("sha mismatch rejected", False)
except oe.OfflineError as e:
    ok("sha mismatch rejected, nothing installed, staging cleaned", "校验失败" in str(e) and not os.path.isdir(os.path.join(r2, "site")) and not os.path.exists(os.path.join(r2, "_new")))
rel["releases"].pop("9.0"); json.dump(rel, open(os.path.join(srv, "pypi", "numpy", "json"), "w"))
# zip-slip
evil = add("pyyaml", "9.0", tag, tag, LX, wheel("pyyaml", {"pyyaml/__init__.py": "", "../../evil.txt": "pwn"}))
rel = json.load(open(os.path.join(srv, "pypi", "pyyaml", "json"))); rel["releases"]["9.0"] = [evil]
json.dump(rel, open(os.path.join(srv, "pypi", "pyyaml", "json"), "w"))
r3 = fresh()
try: ri.install(r3, index=INDEX); ok("zip-slip rejected", False)
except oe.OfflineError as e: ok("zip-slip rejected, no file escaped", "非法路径" in str(e) and not os.path.exists(os.path.join(os.path.dirname(r3), "evil.txt")) and not os.path.exists(os.path.join(r3, "evil.txt")))
rel["releases"].pop("9.0"); json.dump(rel, open(os.path.join(srv, "pypi", "pyyaml", "json"), "w"))
# 没有匹配的轮子
try: ri.install(fresh(), tag="cp20", index=INDEX); ok("no matching wheel", False)
except oe.OfflineError as e: ok("no matching wheel -> clear message", "没有适合当前程序" in str(e))
# 连不上索引
try: ri.install(fresh(), index="http://127.0.0.1:1/%s/json"); ok("unreachable PyPI", False)
except oe.OfflineError as e: ok("unreachable PyPI -> clear message mentions mirror", "无法从 PyPI 查询" in str(e) and "镜像" in str(e))
# 取消 → 回滚；再装 → 续传
big = add("ctranslate2", "7.0", tag, tag, LX, wheel("ctranslate2", {"ctranslate2/__init__.py": "", "ctranslate2/big.bin": BIGDATA}))
rel = json.load(open(os.path.join(srv, "pypi", "ctranslate2", "json"))); rel["releases"]["7.0"] = [big]
json.dump(rel, open(os.path.join(srv, "pypi", "ctranslate2", "json"), "w"))
r4 = fresh(); got = [0]
def pg(i, n, fn, d, t):
    if "ctranslate2" in fn: got[0] = d
try: ri.install(r4, index=INDEX, progress=pg, cancelled=lambda: got[0] >= 400_000); ok("cancel", False)
except pd.Cancelled: ok("cancel mid-download rolls back staging, keeps partial", not os.path.isdir(os.path.join(r4, "site")) and not os.path.exists(os.path.join(r4, "_new"))
                        and any(f.endswith(".part") for f in os.listdir(os.path.join(r4, "_downloads"))))
v4 = ri.install(r4, index=INDEX)
ok("retry resumes and completes", v4["ctranslate2"] == "7.0" and os.path.getsize(os.path.join(r4, "site", "ctranslate2", "big.bin")) == len(BIGDATA))
# 32 位 / 不支持系统
real = ri.struct.calcsize; ri.struct.calcsize = lambda f: 4
try: ri.install(fresh(), index=INDEX); ok("32-bit refused", False)
except oe.OfflineError as e: ok("32-bit refused with reason", "32 位" in str(e))
ri.struct.calcsize = real
httpd.shutdown()
print("ALL OK" if all(res) else "FAILED"); sys.exit(0 if all(res) else 1)
