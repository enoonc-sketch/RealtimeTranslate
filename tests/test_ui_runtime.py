"""标准版界面流程：点「离线语言包…」→ 询问 → 下载组件 → 失败可重试 / 可取消 → 装好后无需重启，引擎出现「离线」并自动进入语言包下载。需 xvfb。"""
import hashlib, io, json, os, sys, tempfile, threading, time, zipfile, http.server, functools
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


import desktop_translator as dt, offline_engine as oe, pack_downloader as pd, runtime_installer as ri

tmp = tempfile.mkdtemp(); srv = os.path.join(tmp, "srv"); os.makedirs(os.path.join(srv, "whl"))
dt.DATA_DIR = os.path.join(tmp, "data"); dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json"); dt.HISTORY_PATH = os.path.join(dt.DATA_DIR, "history.db")
dt.USER_MODELS_DIR = os.path.join(dt.DATA_DIR, "models")
tag, LX = ri.py_tag(), "manylinux_2_17_x86_64"
files = {}
def whl(pkg):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z: z.writestr(pkg + "/__init__.py", "")
    fn = "%s-1.0-%s-%s-%s.whl" % (pkg, tag, tag, LX); files[fn] = buf.getvalue()
    return {"packagetype": "bdist_wheel", "filename": fn, "url": B + "whl/" + fn, "size": len(files[fn]),
            "digests": {"sha256": hashlib.sha256(files[fn]).hexdigest()}}
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/whl/"):
            d = files[self.path[5:]]; self.send_response(200); self.send_header("Content-Length", str(len(d))); self.end_headers(); self.wfile.write(d); return
        return super().do_GET()
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=srv))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d/" % httpd.server_port
for pkg in ri.PKGS:
    os.makedirs(os.path.join(srv, "pypi", pkg), exist_ok=True)
    json.dump({"releases": {"1.0": [whl(pkg)]}}, open(os.path.join(srv, "pypi", pkg, "json"), "w"))
ri.INDEX = B + "pypi/%s/json"
pd.INDEX_URLS[:] = ["http://127.0.0.1:1/index.json"]

# 模拟「标准版」：没有运行库，也没有「离线」引擎
present = [False]
oe.runtime_present = lambda: present[0]
dt.ENGINES[:] = ["Google", "微软"]
ri.verify_import = lambda: present.__setitem__(0, True)        # 装好后「能加载」
asked, info = [], []
ANS = [False]
dt.messagebox.askyesno = lambda *a, **k: (asked.append(a), ANS[0])[1]
dt.messagebox.showinfo = lambda *a, **k: info.append(a)
dt.OFFLINE = oe.Engine([(dt.USER_MODELS_DIR, "用户导入")])

app = dt.App(); r = app.root
def pump(sec, until=None):
    end = time.time() + sec
    while time.time() < end:
        r.update(); time.sleep(0.02)
        if until and until(): return True
    return bool(until and until())
res = []
def ok(n, c): print(("PASS " if c else "FAIL ") + n); res.append(bool(c))

ok("standard build: no 离线 engine, but 离线语言包 button exists", "离线" not in app.engine.cget("values") and any(
    str(w.cget("text")) == "离线语言包…" for w in _walk(r) if hasattr(w, "cget") and "text" in w.keys()))
# 1. 选「否」：什么都不发生
app._show_offline_packs(); pump(0.2)
ok("decline -> nothing downloaded/opened", asked and not getattr(app, "rt_win", None) and not ri.installed(dt._runtime_dir()))
ok("confirm text mentions size and location", "MB" in asked[0][1] and dt._runtime_dir() in asked[0][1])

# 2. 不支持的系统：只提示原因，不询问
real_sup = ri.supported; ri.supported = lambda: (False, "本系统请手动安装")
n_asked = len(asked); app._show_offline_packs(); ri.supported = real_sup
ok("unsupported OS -> reason shown, no prompt", info and "手动安装" in info[-1][1] and len(asked) == n_asked)

# 3. 失败：窗口保留、显示原因、可重试
real_inst = ri.install; ANS[0] = True
ri.install = lambda *a, **k: (_ for _ in ()).throw(oe.OfflineError("无法从 PyPI 查询 numpy：boom"))
app._show_offline_packs()
ok("failure keeps window, shows reason, retry enabled", pump(4, lambda: "失败" in app.rt_msg.cget("text")) and "boom" in app.rt_msg.cget("text")
   and str(app.rt_retry.cget("state")) == "normal" and app.rt_btn.cget("text") == "关闭" and "离线" not in dt.ENGINES)
# 4. 取消
def slow(*a, **k):
    while not app.rt_cancel: time.sleep(0.02)
    raise pd.Cancelled()
ri.install = slow; app._rt_start(); pump(0.2); app._rt_cancel_or_close()
ok("cancel shows resumable message", pump(3, lambda: "已取消" in app.rt_msg.cget("text")) and str(app.rt_retry.cget("state")) == "normal")
# 5. 重试成功：真实走安装流程
ri.install = real_inst; app.rt_mirror.set("zzz.invalid=yyy.invalid"); app._rt_start()
ok("retry succeeds: components installed", pump(10, lambda: ri.installed(dt._runtime_dir()) is not None and not app.rt_busy))
pump(0.5)
ok("no restart needed: 离线 engine now offered", "离线" in dt.ENGINES and "离线" in app.engine.cget("values"))
ok("progress window closed, pack dialog + download dialog opened", not app._rt_alive() and app.pack_win.winfo_exists() and app._dl_alive())
ok("mirror setting remembered", json.load(open(dt.CONFIG_PATH)).get("pack_mirror") == "zzz.invalid=yyy.invalid")
ok("site on sys.path for next launch", os.path.join(dt._runtime_dir(), "site") in sys.path)
app._dl_close(); app.pack_win.destroy()
# 6. 已有运行库时直接进入语言包对话框，不再询问
n_asked = len(asked); app._show_offline_packs(); pump(0.2)
ok("with runtime present goes straight to pack dialog", len(asked) == n_asked and app.pack_win.winfo_exists())
app.quit(); httpd.shutdown()
print("ALL OK" if all(res) else "FAILED"); sys.exit(0 if all(res) else 1)
