"""界面流程：网络检查对话框、离线语言包对话框（含导入）、离线引擎翻译、Esc。需 xvfb。"""
import os, sys, tempfile, time, zipfile, socket, urllib.error
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import desktop_translator as dt, offline_engine as oe, netcheck as nc
from make_fake_model import make_pkg
from tkinter import filedialog

tmp = tempfile.mkdtemp()
dt.DATA_DIR = os.path.join(tmp, "data"); dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.USER_MODELS_DIR = os.path.join(dt.DATA_DIR, "models")
en = ["hello world this is a test", "good morning everyone"] * 8; zh = ["你好世界这是一个测试", "大家早上好"] * 8
bundled = os.path.join(tmp, "bundled"); make_pkg(bundled, "en", "zh", en + zh)
dt.OFFLINE = oe.Engine([(dt.USER_MODELS_DIR, "用户导入"), (bundled, "内置")])
dt.ENGINES[:] = ["Google", "微软", "离线"]
U = urllib.error.URLError
dt.g_translate = lambda t, sl, tl, attempts=3, timeout=12: (_ for _ in ()).throw(U(socket.timeout("timed out")))
dt.ms_translate = lambda t, sl, tl, attempts=3, timeout=15: ("你好", "en")
nc.check_connectivity = lambda: nc.Check("net", "基础联网（外网 TCP 直连）", True, 15)
nc.check_dns = lambda: nc.Check("dns", "DNS 解析", True)

app = dt.App(); r = app.root
def pump(sec, until=None):
    # 2026-11-20：离线首次翻译（载模型 + 推理）在慢机器上要 2.5~3.7 秒，
    # 固定等 2.5 秒就断言是时间竞态 —— 允许按条件等（最多 sec 秒）。
    end = time.time() + sec
    while time.time() < end:
        r.update(); time.sleep(0.02)
        if until and until(): return True
    return bool(until and until())
res = []
def ok(name, cond): print(("PASS " if cond else "FAIL ") + name); res.append(cond)

# 1. network check dialog
app.open_netcheck(); pump(1.5)
txt = app.net_txt.get("1.0", "end")
ok("netcheck shows google failure + hint", "✘ Google 翻译" in txt and "超时" in txt)
ok("netcheck shows ms ok + conclusion", "✔ 微软翻译" in txt and "结论：" in txt)
ok("switch button offered for 微软", str(app.net_btn_sw.cget("state")) == "normal" and "微软" in app.net_btn_sw.cget("text"))
app._apply_reco(); pump(0.8)
ok("apply recommendation switches engine", app.engine.get() == "微软")
app._copy_net_report(); ok("report copied to clipboard", "网络检查" in r.clipboard_get())
app.net_win.destroy()

# 2. auto fallback status in main window (google dead, offline has en->zh)
app.engine.set("Google"); app._set_src("hello world this is a test"); app.translate_now()
ok("auto fallback to offline shown in status",
   pump(8, lambda: "已自动改用离线" in app.status.cget("text")) and app.plain_result() != "")

# 3. offline engine + pack dialog + import
app.engine.set("离线"); app._update_engine_hint()
ok("engine hint shows 1 pack", "1 个语言包" in app.engine_hint.cget("text"))
app._show_offline_packs(); pump(0.3)
rows = [app.pack_tv.item(i)["values"] for i in app.pack_tv.get_children()]
ok("pack dialog lists en→zh", len(rows) == 1 and rows[0][3] == "可用")
src = make_pkg(os.path.join(tmp, "src"), "zh", "en", zh + en, seed=1)
arc = os.path.join(tmp, "translate-zh_en-1_0.argosmodel")
with zipfile.ZipFile(arc, "w") as z:
    for rt, _, fs in os.walk(src):
        for f in fs: z.write(os.path.join(rt, f), os.path.relpath(os.path.join(rt, f), os.path.dirname(src)))
filedialog.askopenfilenames = lambda **k: (arc,)
app._import_packs(); pump(2.5)
ok("import adds zh→en", len(app.pack_tv.get_children()) == 2 and "已导入" in app.pack_msg.cget("text"))
ok("engine hint updated to 2 packs", "2 个语言包" in app.engine_hint.cget("text"))
app._set_src("你好世界"); app.translate_now(); pump(2.0)
ok("offline zh→en result", app.plain_result() != "" and "翻译失败" not in app.dst.get("1.0", "end"))

# 4. missing pair error is clear
app.tl.set("日语"); app._set_src("hello"); app.translate_now(); pump(2.0)
shown = app.dst.get("1.0", "end")
ok("missing pair message", "没有 en → ja 的离线语言包" in shown)
app.pack_win.destroy(); app.quit()
print("ALL OK" if all(res) else "FAILED"); sys.exit(0 if all(res) else 1)
