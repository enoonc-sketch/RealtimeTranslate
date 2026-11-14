"""语言包在线下载：索引（含缓存回退）、选版本、镜像替换、下载/取消/拦截页、安装、缺哪些包。本地假服务器，不联网。"""
import json, os, sys, tempfile, threading, zipfile, http.server, functools
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import offline_engine as oe, pack_downloader as pd
from make_fake_model import make_pkg

tmp = tempfile.mkdtemp(); srv = os.path.join(tmp, "srv"); os.makedirs(srv)
en = ["hello world this is a test", "good morning everyone"] * 8; zh = ["你好世界这是一个测试", "大家早上好"] * 8
def arch(src_root, name, out):
    with zipfile.ZipFile(out, "w") as z:
        for rt, _, fs in os.walk(os.path.join(src_root, name)):
            for f in fs: z.write(os.path.join(rt, f), os.path.relpath(os.path.join(rt, f), src_root))
mk = os.path.join(tmp, "mk")
make_pkg(mk, "en", "zh", en + zh); arch(mk, "translate-en_zh-1_0", os.path.join(srv, "en_zh.argosmodel"))
make_pkg(mk, "zh", "en", zh + en, seed=1); arch(mk, "translate-zh_en-1_0", os.path.join(srv, "zh_en.argosmodel"))
open(os.path.join(srv, "blocked.argosmodel"), "w").write("<html>拦截页</html>")
open(os.path.join(srv, "big.argosmodel"), "wb").write(b"x" * 3_000_000)

import random, re
rng = random.Random(1)
with zipfile.ZipFile(os.path.join(srv, "big.zip"), "w", zipfile.ZIP_STORED) as z:
    z.writestr("a.bin", bytes(rng.getrandbits(8) for _ in range(3_000_000)))
BIG = open(os.path.join(srv, "big.zip"), "rb").read()
REQS, FLAKY_DONE = [], []
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        name = self.path.lstrip("/")
        if name not in ("big.zip", "flaky.zip", "norange.zip"):
            return super().do_GET()
        rng_h = self.headers.get("Range")
        REQS.append((name, rng_h))
        start = 0
        if rng_h and name != "norange.zip":
            start = int(re.match(r"bytes=(\d+)-", rng_h).group(1))
            if start >= len(BIG):
                self.send_response(416); self.end_headers(); return
            self.send_response(206)
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, len(BIG) - 1, len(BIG)))
        else:
            self.send_response(200)
        body = BIG[start:]
        self.send_header("Content-Length", str(len(body))); self.end_headers()
        if name == "flaky.zip" and not FLAKY_DONE:       # 第一次传到 40% 就掐断连接
            FLAKY_DONE.append(1)
            self.wfile.write(body[: int(len(body) * 0.4)]); self.wfile.flush(); self.close_connection = True
            self.connection.shutdown(2); return
        self.wfile.write(body)
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=srv))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d/" % httpd.server_port
dead = "http://127.0.0.1:1/"
index = [
    {"type": "translate", "from_code": "en", "to_code": "zh", "package_version": "1.0", "links": [dead + "x.argosmodel", B + "en_zh.argosmodel"]},
    {"type": "translate", "from_code": "en", "to_code": "zh", "package_version": "1.9", "links": [B + "en_zh.argosmodel"]},
    {"type": "translate", "from_code": "zh", "to_code": "en", "package_version": "1.0", "links": [B + "blocked.argosmodel", B + "zh_en.argosmodel"]},
    {"type": "translate", "from_code": "ja", "to_code": "en", "package_version": "1.1", "links": [B + "blocked.argosmodel"]},
    {"type": "translate", "from_code": "en", "to_code": "ja", "package_version": "1.1", "links": [B + "blocked.argosmodel"]},
    {"type": "sbd", "from_code": "en", "to_code": "en", "package_version": "9", "links": [B + "x"]},
    {"type": "translate", "from_code": "xx", "to_code": "yy", "package_version": "1", "links": []},
]
open(os.path.join(srv, "index.json"), "w").write(json.dumps(index))
res = []
def ok(n, c): print(("PASS " if c else "FAIL ") + n); res.append(bool(c))

# 索引：第一个源挂了，第二个成功；写缓存
cache = os.path.join(tmp, "data", "idx.json")
data, note, stale = pd.fetch_index(cache, urls=[dead + "i.json", B + "index.json"], timeout=3)
ok("index falls through dead url", len(data) == 7 and not stale and os.path.isfile(cache))
data2, note2, stale2 = pd.fetch_index(cache, urls=[dead + "i.json"], timeout=3)
ok("all urls dead -> stale cache", stale2 and "旧列表" in note2 and len(data2) == 7)
try: pd.fetch_index(os.path.join(tmp, "none.json"), urls=[dead + "i.json"], timeout=3); ok("no cache raises", False)
except oe.OfflineError as e: ok("no cache raises clear error", "无法获取语言包列表" in str(e))

best = pd.best_by_pair(data)
ok("best picks highest version, skips sbd/no-links", best[("en", "zh")]["package_version"] == "1.9" and ("xx", "yy") not in best and ("en", "en") not in best)
ok("apply_replace", pd.apply_replace("https://argos-net.com/a", "argos-net.com=mirror.cn") == "https://mirror.cn/a" and pd.apply_replace("u", "") == "u" and pd.apply_replace("u", "bad") == "u")

# 下载 / 取消 / 拦截页
dest = os.path.join(tmp, "dl", "a.argosmodel"); seen = []
pd.download(B + "en_zh.argosmodel", dest, lambda d, t: seen.append((d, t)))
ok("download reports progress and total", seen and seen[-1][0] == seen[-1][1] > 0 and zipfile.is_zipfile(dest))
try: pd.download(B + "big.argosmodel", os.path.join(tmp, "dl", "b"), cancelled=lambda: True); ok("cancel", False)
except pd.Cancelled: ok("cancel raises Cancelled", True)
try: pd.download(B + "blocked.argosmodel", os.path.join(tmp, "dl", "c")); ok("blocked page rejected", False)
except oe.OfflineError as e: ok("blocked page rejected", "不是有效的语言包" in str(e))

# ---- 断点续传 ----
dl = os.path.join(tmp, "dl2"); got = [0]
def prog(d, t): got[0] = d
try: pd.download(B + "big.zip", os.path.join(dl, "big.zip"), prog, cancelled=lambda: got[0] >= 500_000)
except pd.Cancelled: pass
part = os.path.join(dl, "big.zip.part")
ok("cancel keeps .part for resume", os.path.isfile(part) and 0 < os.path.getsize(part) < len(BIG))
REQS.clear(); seen2 = []
pd.download(B + "big.zip", os.path.join(dl, "big.zip"), lambda d, t: seen2.append((d, t)))
ok("resume sends Range and gets the rest", REQS and REQS[0][1] and REQS[0][1].startswith("bytes=") and open(os.path.join(dl, "big.zip"), "rb").read() == BIG)
ok("resume progress counts earlier bytes (total = full size)", seen2[0][0] > 500_000 and seen2[-1] == (len(BIG), len(BIG)))
ok(".part removed after success", not os.path.exists(part))

# 传输中途被掐断：自动重试并续传，调用方无感
REQS.clear()
pd.download(B + "flaky.zip", os.path.join(dl, "flaky.zip"), backoff=0.05)
ok("mid-stream drop auto-retries with Range", len(REQS) == 2 and REQS[1][1] and open(os.path.join(dl, "flaky.zip"), "rb").read() == BIG)

# 服务器不支持 Range（返回 200 整包）：丢弃旧 .part 重新下，结果仍然正确
open(os.path.join(dl, "norange.zip.part"), "wb").write(b"junk" * 1000)
pd.download(B + "norange.zip", os.path.join(dl, "norange.zip"))
ok("server ignoring Range -> restart cleanly", open(os.path.join(dl, "norange.zip"), "rb").read() == BIG)

# 连不上：不重试，立刻抛错（让上层换下一个链接）
import time as _t; t0 = _t.time()
try: pd.download(dead + "x.zip", os.path.join(dl, "x.zip"), timeout=3)
except Exception: ok("unreachable fails fast (no retry delay)", _t.time() - t0 < 2.5)

# 磁盘空间不足
import collections
_real = pd.shutil.disk_usage
pd.shutil.disk_usage = lambda p: collections.namedtuple("u", "total used free")(10, 9, 1000)
try: pd.download(B + "big.zip", os.path.join(dl, "nospace.zip")); ok("disk check", False)
except oe.OfflineError as e: ok("disk space shortage reported in MB", "磁盘空间不足" in str(e) and "MB" in str(e))
pd.shutil.disk_usage = _real
ok("no junk .part created by rejected download", not os.path.exists(os.path.join(dl, "nospace.zip")))

# 索引缓存：未过期直接用（不联网）；过期才联网
d3, n3, st3 = pd.fetch_index(cache, urls=[dead + "i.json"], timeout=3, max_age=3600)
ok("fresh cache used without network", "保存的列表" in n3 and not st3 and len(d3) == 7)
d4, n4, st4 = pd.fetch_index(cache, urls=[dead + "i.json"], timeout=3, max_age=0.0001)
ok("expired cache -> network -> stale fallback", st4)

# 整包下载安装：zh→en 第一个链接是拦截页，应自动换第二个
models, work = os.path.join(tmp, "models"), os.path.join(tmp, "work")
pkg = pd.download_pack(best[("zh", "en")], models, work)
ok("download_pack falls to 2nd link + installs", pkg.from_code == "zh" and pkg.usable and not os.listdir(work))
try: pd.download_pack(best[("ja", "en")], models, work); ok("all links bad", False)
except oe.OfflineError as e: ok("all links bad -> clear error", "下载失败" in str(e))

# 引擎能用，状态与缺口计算
eng = oe.Engine([(models, "用户导入")])
ok("engine sees downloaded pack", eng.pairs() == [("zh", "en")])
ok("status 已安装 / 未安装", pd.status_of(("zh", "en"), best[("zh", "en")], eng) == "已安装" and pd.status_of(("en", "zh"), best[("en", "zh")], eng) == "未安装")
upd = dict(best[("zh", "en")], package_version="2.0")
ok("status 可更新", pd.status_of(("zh", "en"), upd, eng) == "可更新")
ok("missing: direct available", pd.missing_for(eng, "en", "zh", best) == [("en", "zh")])
ok("missing: already possible", pd.missing_for(eng, "zh", "en", best) == [])
ok("missing: via English needs 2 legs", pd.missing_for(eng, "ja", "zh", best) == [("ja", "en"), ("en", "zh")])
ok("missing: impossible -> None", pd.missing_for(eng, "ja", "ko", best) is None)
httpd.shutdown()
print("ALL OK" if all(res) else "FAILED"); sys.exit(0 if all(res) else 1)
