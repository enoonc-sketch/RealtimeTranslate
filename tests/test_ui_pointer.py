"""界面流程：在线下载对话框（列表/搜索/下载所选/所需/取消）、指针气泡（翻译/定位/点击复制/移开关闭）、取词决策。需 xvfb。"""
import json, os, sys, tempfile, time, zipfile, threading, http.server, functools
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import desktop_translator as dt, offline_engine as oe, pack_downloader as pd
from make_fake_model import make_pkg

tmp = tempfile.mkdtemp(); srv = os.path.join(tmp, "srv"); os.makedirs(srv)
dt.DATA_DIR = os.path.join(tmp, "data"); dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.USER_MODELS_DIR = os.path.join(dt.DATA_DIR, "models")
en = ["hello world this is a test", "good morning everyone"] * 8; zh = ["你好世界这是一个测试", "大家早上好"] * 8
mk = os.path.join(tmp, "mk")
def arch(name, out):
    with zipfile.ZipFile(out, "w") as z:
        for rt, _, fs in os.walk(os.path.join(mk, name)):
            for f in fs: z.write(os.path.join(rt, f), os.path.relpath(os.path.join(rt, f), mk))
make_pkg(mk, "en", "zh", en + zh); arch("translate-en_zh-1_0", os.path.join(srv, "en_zh.argosmodel"))
make_pkg(mk, "zh", "en", zh + en, seed=1); arch("translate-zh_en-1_0", os.path.join(srv, "zh_en.argosmodel"))
open(os.path.join(srv, "big.argosmodel"), "wb").write(b"x" * 20_000_000)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=srv))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
B = "http://127.0.0.1:%d/" % httpd.server_port
ent = lambda f, t, v, l: {"type": "translate", "from_code": f, "to_code": t, "from_name": f, "to_name": t, "package_version": v, "links": [B + l]}
open(os.path.join(srv, "index.json"), "w").write(json.dumps([
    ent("en", "zh", "1.0", "en_zh.argosmodel"), ent("zh", "en", "1.0", "zh_en.argosmodel"),
    ent("ja", "en", "1.1", "big.argosmodel"), ent("en", "ga", "1.0", "big.argosmodel")]))
pd.INDEX_URLS[:] = [B + "index.json"]

dt.OFFLINE = oe.Engine([(dt.USER_MODELS_DIR, "用户导入")])
dt.ENGINES[:] = ["Google", "微软", "离线"]
dt.g_translate = lambda t, sl, tl, attempts=3, timeout=12: ("译:" + t[:30], "en")

app = dt.App(); r = app.root
# 安全修复（2026-11-20）：_dl_start 在下载未钉死哈希的语言对前会弹确认框；
# 本测试用的假索引是 1.0 版（未钉死），这里桩掉确认框模拟用户点「是」，
# 否则 xvfb 下没人点确认、测试会一直等下去。
dt.messagebox.askyesno = lambda *a, **k: True
def pump(sec, until=None):
    end = time.time() + sec
    while time.time() < end:
        r.update(); time.sleep(0.02)
        if until and until(): return True
    return bool(until and until())
res = []
def ok(n, c): print(("PASS " if c else "FAIL ") + n); res.append(bool(c))

# ---------- 取词决策（纯逻辑） ----------
ok("plan: I-beam word", dt.pointer_plan(True, False, "word") == ["click2", "copy"])
ok("plan: I-beam paragraph", dt.pointer_plan(True, False, "paragraph") == ["click3", "copy"])
ok("plan: arrow/hand never clicks", dt.pointer_plan(False, False, "word") == ["copy"])
ok("plan: terminal w/o I-beam sends nothing (no Ctrl+C interrupt)", dt.pointer_plan(False, True, "word") == [])

# ---------- 下载对话框 ----------
app._show_offline_packs(); pump(0.2)
app._show_pack_download()
ok("list loads", pump(5, lambda: len(app.dl_tv.get_children()) == 4))
rows = {app.dl_tv.item(i)["values"][1]: app.dl_tv.item(i)["values"] for i in app.dl_tv.get_children()}
ok("rows show not-installed", rows["en-zh"][3] == "未安装")
app.dl_filter.set("zh"); pump(0.2)
ok("search filters", len(app.dl_tv.get_children()) == 2)
app.dl_filter.set("")
# 默认 自动检测 → 简体中文：需要 en→zh 和 zh→en
ok("needed pairs for auto->zh", app._needed_pairs() == [("en", "zh"), ("zh", "en")])
app._dl_needed()
ok("download needed finishes", pump(8, lambda: not app.dl_busy and len(dt.OFFLINE.pairs()) == 2))
ok("engine reloaded with both packs", dt.OFFLINE.pairs() == [("en", "zh"), ("zh", "en")])
ok("done message", "已安装" in app.dl_prog.cget("text") and "en → zh" in app.dl_prog.cget("text"))
ok("done message tells how to enable offline", "切到「离线」" in app.dl_prog.cget("text"))
# 速度 / 剩余时间显示
app._on_dl_prog(0, 1, "en → zh", 0, 50_000_000); time.sleep(0.6); app._on_dl_prog(0, 1, "en → zh", 6_000_000, 50_000_000)
ok("speed and ETA shown", "MB/s" in app.dl_prog.cget("text") and "剩约" in app.dl_prog.cget("text"))
# 离线引擎预热：切到「离线」后后台载入模型
ok("nothing preloaded yet", len(dt.OFFLINE._loaded) == 0)
app.engine.set("离线"); app._warmup()
ok("warm-up preloads models in background", pump(5, lambda: len(dt.OFFLINE._loaded) >= 1))
app.engine.set("Google")
ok("pack dialog refreshed", len(app.pack_tv.get_children()) == 2)
st = {app.dl_tv.item(i)["values"][1]: app.dl_tv.item(i)["values"][3] for i in app.dl_tv.get_children()}
ok("states updated", st["en-zh"] == "已安装" and st["zh-en"] == "已安装")
app._dl_needed()
ok("nothing left to download", "都已安装" in app.dl_prog.cget("text"))
ok("downloaded temp cleaned", not [f for f in os.listdir(dt._dl_dir()) if f.endswith(".argosmodel")])
ok("index cached", os.path.isfile(dt._index_cache()))
ok("config remembers mirror field", "pack_mirror" in json.load(open(dt.CONFIG_PATH)))

# 取消
for i, p in app.dl_iid.items():
    if p == ("ja", "en"): app.dl_tv.selection_set(i)
app.dl_mirror.set("127.0.0.1=127.0.0.1")        # 镜像替换不破坏链接
app._dl_selected(); app._dl_do_cancel()
ok("cancel stops and re-enables button", pump(8, lambda: not app.dl_busy) and "已取消" in app.dl_prog.cget("text")
   and str(app.dl_btn.cget("state")) == "normal" and ("ja", "en") not in dt.OFFLINE.pairs())
app._dl_close(); app.pack_win.destroy()

# ---------- 指针气泡 ----------
app.engine.set("Google"); app.sl.set("自动检测"); app.tl.set("简体中文")
app.grab_plan = ["click2", "copy"]
def warp(x, y):
    r.event_generate("<Motion>", warp=True, x=x - r.winfo_rootx(), y=y - r.winfo_rooty()); pump(0.05)
warp(300, 300)
app._pointer_translate("hello", (300, 300))
ok("bubble appears loading", pump(0.1, lambda: app.bubble.alive()) )
ok("bubble shows translation", pump(3, lambda: app.bubble.body.cget("text").startswith("译:")))
ok("bubble head has route", "英语" in app.bubble.head.cget("text") and "→" in app.bubble.head.cget("text"))
ok("bubble below-right of pointer", app.bubble.win.winfo_x() == 314 and app.bubble.win.winfo_y() == 322)
# 点击复制（点一下先复制，250ms 后关：等双击，双击到就改朗读）
app.bubble._click(); pump(0.5)
ok("click copies & closes", r.clipboard_get() == "译:hello" and not app.bubble.alive())
# 屏幕边缘：不越界、放不下就翻到指针上方
sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
warp(sw - 5, sh - 5); app._pointer_translate("edge case text", (sw - 5, sh - 5)); pump(1.0, lambda: app.bubble.body.cget("text").startswith("译:"))
w = app.bubble.win
ok("bubble clamped on-screen", w.winfo_x() + w.winfo_reqwidth() <= sw and w.winfo_y() + w.winfo_reqheight() <= sh and w.winfo_y() < sh - 5)
# 指针移开自动关闭（Xvfb 里无法真移动鼠标：把出现位置挪到很远处等价）
warp(10, 10)
ok("auto-closes when pointer moves away", pump(2, lambda: not app.bubble.alive()))
# 空取词提示（非 Windows 文案 / Windows 文案分支）
warp(200, 200); app._pointer_translate("", (200, 200)); pump(0.2)
ok("empty pick shows hint", app.bubble.alive() and "选中文字" in app.bubble.body.cget("text"))
app.bubble.win.event_generate("<Escape>"); pump(0.2)
ok("Esc closes bubble", not app.bubble.alive())
# 翻译失败走错误提示，不卡在「翻译中…」
dt.CACHE.clear(); dt.g_translate = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
dt.OFFLINE = oe.Engine([]); app._pointer_translate("fail", (200, 200))
ok("error shown in bubble", pump(4, lambda: "翻译失败" in app.bubble.body.cget("text")))
# 新取词覆盖旧结果（序号防串）
dt.g_translate = lambda t, sl, tl, attempts=3, timeout=12: ("译:" + t, "en")
app._pointer_translate("first", (200, 200)); app._pointer_translate("second", (200, 200))
pump(2, lambda: app.bubble.body.cget("text").startswith("译:"))
ok("latest pick wins", app.bubble.body.cget("text") == "译:second")
# 关闭选项后热键无效
app.pointer_var.set(False); app.grabbing = False; app._on_hotkey(2)
ok("disabled option ignores hotkey", not app.grabbing)
app.pointer_var.set(True); app.scope_cb.set("整段"); app._on_pointer_opt()
ok("scope persisted", json.load(open(dt.CONFIG_PATH))["pointer_scope"] == "paragraph")
app.quit(); httpd.shutdown()
print("ALL OK" if all(res) else "FAILED"); sys.exit(0 if all(res) else 1)
