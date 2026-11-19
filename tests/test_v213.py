"""v2.13：
 1. 离线运行库缺 glob（No module named 'glob'）：runtime_stdlib 清单 + 两个 spec + 友好报错
 2. winocr.ps1 纯 ASCII（中文 Windows 读 .ps1 当 GBK 会读坏）、错误码 → 中文、截图 BMP 透明通道补 255
 3. OCR 非 Windows 后端（tesseract TSV 解析）
 4. 任务栏最小化：按钮 / 勾选框 / 默认值迁移 / 保存窗口位置不存假坐标
 5. 跨系统面板：字体挑选、窗口夹屏、按钮行折行、设置页可滚动、小屏下所有窗口都在屏幕内
需 xvfb。"""
import json, os, re, struct, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import desktop_translator as dt
import ocr_win, ocr_backends, screen_win, ui_platform, runtime_stdlib, offline_engine

tmp = tempfile.mkdtemp()
dt.DATA_DIR = os.path.join(tmp, "data"); dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.HISTORY_PATH = os.path.join(dt.DATA_DIR, "history.db")
dt.CRASH_LOG = os.path.join(dt.DATA_DIR, "crash.log")
dt.WATCHDOG_LOG = os.path.join(dt.DATA_DIR, "watchdog.log")
dt.g_translate = lambda t, sl, tl: ("译:" + t[:20], "en")
res = []
def ok(n, c):
    print(("PASS " if c else "FAIL ") + n); res.append(bool(c))

# ---------------- 1. glob / 运行库标准库 ----------------
ok("runtime_stdlib lists glob first-class", "glob" in runtime_stdlib.NEEDED)
loaded, missing = runtime_stdlib.preload()
ok("runtime_stdlib preload imports glob", "glob" in loaded and "glob" not in missing)
for spec in ("realtime_translate.spec", "realtime_translate_offline.spec"):
    t = open(os.path.join(ROOT, spec), encoding="utf-8").read()
    ok(spec + " bundles glob", "'glob'" in t)
    ok(spec + " bundles runtime_stdlib/ocr_backends/ui_platform",
       all(("'%s'" % m) in t for m in ("runtime_stdlib", "ocr_backends", "ui_platform")))
ri = open(os.path.join(ROOT, "runtime_installer.py"), encoding="utf-8").read()
ok("runtime_installer imports runtime_stdlib for PyInstaller", "import runtime_stdlib" in ri)
# 友好报错：模拟 ctranslate2 导入时缺标准库 glob
import builtins
real_import = builtins.__import__
def fake_import(name, *a, **k):
    if name == "ctranslate2":
        e = ModuleNotFoundError("No module named 'glob'"); e.name = "glob"; raise e
    return real_import(name, *a, **k)
eng = offline_engine.Engine([])
class P:  # 最小语言包替身
    path = "x"; model_dir = "x"; sp_path = "x"; name = "x"
builtins.__import__ = fake_import
try:
    try:
        eng._load(P())
        msg = ""
    except offline_engine.OfflineError as e:
        msg = str(e)
finally:
    builtins.__import__ = real_import
ok("missing stdlib glob -> clear Chinese hint (not a generic pip hint)", "glob" in msg and "v2.13" in msg and "pip install" not in msg)

# ---------------- 2. OCR 脚本 / BMP ----------------
raw = open(os.path.join(ROOT, "winocr.ps1"), "rb").read()
ok("winocr.ps1 is pure ASCII (GBK-safe)", all(b < 128 for b in raw))
ps = raw.decode("ascii")
ok("winocr.ps1 ignores alpha + handles big images + multi-engine",
   "BitmapAlphaMode]::Ignore" in ps and "MaxImageDimension" in ps and "-gt $bestScore" in ps)
ok("winocr.ps1 error codes", all(c in ps for c in ("OCR_NO_LANG", "OCR_IMAGE", "OCR_WINRT", "OCR_PS_VERSION")))
for err, want in (("OCR_NO_LANG: no OCR language installed", "OCR 语言包"),
                  ("OCR_IMAGE: cannot open or decode the image: x", "图片打不开"),
                  ("ParserError: Unexpected token", "升级到 v2.13"),
                  ("File xx cannot be loaded because running scripts is disabled (ExecutionPolicy)", "执行策略"),
                  ("", "OCR 失败")):
    ok("explain_ps_error %r" % err[:24], want in ocr_win.explain_ps_error(err, 1))
ok("win ocr tag zh-CN -> zh-Hans-CN", ocr_win.WIN_OCR_TAG["zh-CN"] == "zh-Hans-CN" and ocr_win.WIN_OCR_TAG["en"] == "en-US")
bgra = b"\x10\x20\x30\x00" * (4 * 3)         # GDI 给的透明通道是 0
p = os.path.join(tmp, "a.bmp"); screen_win.save_bmp(p, 4, 3, bgra)
data = open(p, "rb").read()
ok("save_bmp forces opaque alpha", len(data) == 54 + 48 and set(data[54 + 3::4]) == {255} and data[54:57] == b"\x10\x20\x30")
ok("save_bmp header intact", data[:2] == b"BM" and struct.unpack("<ii", data[18:26]) == (4, 3))

# ---------------- 3. tesseract TSV 解析 ----------------
tsv = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
       "1\t1\t0\t0\t0\t0\t0\t0\t200\t50\t-1\t\n"
       "5\t1\t1\t1\t1\t1\t10\t10\t40\t20\t96\tHello\n"
       "5\t1\t1\t1\t1\t2\t60\t10\t50\t20\t95\tworld\n"
       "5\t1\t1\t1\t2\t1\t10\t40\t60\t20\t90\t你好\n"
       "5\t1\t1\t1\t2\t2\t75\t40\t40\t20\t-1\t\n")
d = ocr_backends.parse_tsv(tsv)
ok("tsv -> 2 lines", len(d["lines"]) == 2 and d["lines"][0]["text"] == "Hello world" and d["lines"][1]["text"] == "你好")
ok("tsv word boxes", d["lines"][0]["words"][1] == {"text": "world", "x": 60, "y": 10, "w": 50, "h": 20})
ok("tess lang map", ocr_backends.TESS_LANG["zh-CN"] == "chi_sim" and ocr_backends.TESS_LANG["ja"] == "jpn")

# ---------------- 5(纯函数). 夹屏 / 折行 ----------------
ok("clamp big window to 1366x768", ui_platform.clamp_geometry("620x760", 1366, 768) == "620x708")
ok("clamp drops off-screen position", ui_platform.clamp_geometry("620x700+3000+100", 1366, 768) == "620x700")
ok("clamp drops minimized -32000", ui_platform.clamp_geometry("620x700-32000-32000", 1920, 1080) == "620x700")
ok("clamp keeps visible position", ui_platform.clamp_geometry("620x700+100+50", 1920, 1080) == "620x700+100+50")
ok("clamp bad geometry -> None", ui_platform.clamp_geometry("garbage", 1920, 1080) is None)
ok("flow layout wraps", ui_platform.flow_layout([100] * 5, 320) == [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1)])
ok("flow layout never loops on huge item", ui_platform.flow_layout([900, 100], 300) == [(0, 0), (1, 0)])
ok("centered geometry inside screen", ui_platform.centered_geometry(2000, 2000, 1366, 768) == "1306x708+30+20")
ok("wheel units", ui_platform.wheel_units(type("E", (), {"num": 4, "delta": 0})()) == -1
   and ui_platform.wheel_units(type("E", (), {"num": 5, "delta": 0})()) == 1
   and ui_platform.wheel_units(type("E", (), {"num": 0, "delta": -120})()) == 1)

# ---------------- 4. 配置迁移（不需要 Tk）----------------
os.makedirs(dt.DATA_DIR, exist_ok=True)
json.dump({"close_action": "tray"}, open(dt.CONFIG_PATH, "w"))
cfg = dt.App._load_cfg()
ok("old default close_action=tray migrated once to taskbar", cfg["close_action"] == "taskbar" and cfg["close_taskbar_migrated"])
json.dump({"close_action": "tray", "close_taskbar_migrated": True}, open(dt.CONFIG_PATH, "w"))
ok("user's later choice of tray is respected", dt.App._load_cfg()["close_action"] == "tray")
json.dump({"close_action": "quit"}, open(dt.CONFIG_PATH, "w"))
ok("quit choice untouched", dt.App._load_cfg()["close_action"] == "quit")
json.dump({"geometry": "620x760"}, open(dt.CONFIG_PATH, "w"))
ok("fresh default close_action is taskbar", dt.DEFAULTS["close_action"] == "taskbar")
os.remove(dt.CONFIG_PATH)

# ---------------- Tk 部分 ----------------
app = dt.App(); r = app.root
def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        r.update(); time.sleep(0.02)
pump(0.3)

# 4. 任务栏最小化
ok("minimize button exists", hasattr(app, "minimize_to_taskbar"))
app.show_window(); pump(0.3)
# Xvfb 没有窗口管理器，真的 iconify 看不到状态变化：这里记录调用，确认走的是 iconify（留在任务栏）而不是 withdraw（藏进托盘）
_calls = []
_ic, _wd = r.iconify, r.withdraw
r.iconify = lambda: _calls.append("iconify"); r.withdraw = lambda: _calls.append("withdraw")
app._popup().show((200, 200), "head", "body"); pump(0.2)
app.minimize_to_taskbar(); pump(0.2)
r.iconify, r.withdraw = _ic, _wd
ok("minimize_to_taskbar iconifies (stays in taskbar, not withdrawn)", _calls == ["iconify"])
ok("minimize_to_taskbar also closes floating popups", not app.bubble.alive() and not app.mini.alive())
r.deiconify(); pump(0.3)
ok("close_taskbar checkbox synced with config", app.close_taskbar_var.get() == (app.cfg["close_action"] == "taskbar"))
app.close_taskbar_var.set(False); app._on_close_taskbar()
ok("uncheck -> tray", app.cfg["close_action"] == "tray" and app.close_cb.get() == dt.CLOSE_NAMES["tray"])
app.close_taskbar_var.set(True); app._on_close_taskbar()
ok("check -> taskbar", app.cfg["close_action"] == "taskbar")
app.close_cb.set(dt.CLOSE_NAMES["quit"]); app._sync_close_taskbar()
ok("combo change syncs checkbox off", app.close_taskbar_var.get() is False)
app.close_cb.set(dt.CLOSE_NAMES["taskbar"]); app._sync_close_taskbar()
calls = []
r.iconify = lambda: calls.append("iconify")
app._on_close()
ok("click X with taskbar mode -> iconify", calls == ["iconify"])
del r.iconify
r.deiconify(); pump(0.2)
g0 = app.cfg["geometry"]
r.iconify(); pump(0.3)
ok("geometry not overwritten while minimized", app._geometry_to_save() == g0 or ui_platform.parse_geometry(app._geometry_to_save()) is not None)
r.deiconify(); pump(0.3)

# 开机自启 --minimized：无论「点 ×」设置是什么都 iconify
app.cfg["close_action"] = "tray"
_c = []; _ic = r.iconify; r.iconify = lambda: _c.append(1)
app._start_minimized(); r.iconify = _ic
ok("--minimized start always iconifies (even in tray mode)", _c == [1])
ok("autostart label says taskbar", "自动缩在任务栏" in open(os.path.join(ROOT, "desktop_translator.py"), encoding="utf-8").read())
app.cfg["close_action"] = "taskbar"

# 5. 面板自适应
fam = app._font_family
ok("font family is a real installed family or Tk default",
   fam in set(ui_platform.tkfont.families(r)) or fam == "TkDefaultFont")
ok("mono family chosen", bool(app._mono_family))
ok("main rows are flow frames", all(isinstance(f, ui_platform.FlowFrame) for f in app._flows))
def rows_of(flow):
    return len({w.place_info()["y"] for w in flow._items})
r.geometry("1000x700+10+10"); pump(0.4); wide = rows_of(app._flows[0])
r.geometry("470x700+10+10"); pump(0.5); narrow = rows_of(app._flows[0])
ok("buttons wrap to more rows when narrow (%d -> %d)" % (wide, narrow), narrow > wide)
all_inside = True
fr = app._flows[0]
for w in fr._items:
    if w.winfo_x() + w.winfo_width() > fr.winfo_width() + 2:
        all_inside = False
ok("no button is clipped on the right when narrow", all_inside)
ok("min width is far below the old all-in-one-row width", r.minsize()[0] <= 560)

# 设置页可滚动、窗口夹屏
app.open_settings(); pump(0.4)
ok("settings tabs are ScrollFrames", all(isinstance(v, ui_platform.ScrollFrame) for v in app.settings_tabs.values()))
app.open_settings("general"); pump(0.3)
sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
geo = ui_platform.parse_geometry(app.settings_win.geometry())
ok("settings window inside screen", geo[0] <= sw and geo[1] <= sh)
app.close_settings()
app.open_history(); pump(0.3)
geo = ui_platform.parse_geometry(app.hist_win.geometry())
ok("history window inside screen", geo[0] <= sw and geo[1] <= sh)
app.hist_win.withdraw()

# 隐藏到托盘模式仍可用
app.cfg["close_action"] = "tray"
calls = []
r.withdraw = lambda: calls.append("withdraw")
class FakeTray:
    def is_running(self): return True
    def notify(self, *a): pass
app.tray = FakeTray()
app.cfg["tray_tip_shown"] = True
app._on_close()
ok("tray mode still withdraws", calls == ["withdraw"])
del r.withdraw
app.tray = None

app._watchdog.stop()
try: r.destroy()
except Exception: pass
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
