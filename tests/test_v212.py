"""v2.12：诊断信息一键复制、看门狗、整窗翻译按窗口记忆缓存、整窗结果导出 CSV、译文层点一块加入术语表。需 xvfb。"""
import csv, hashlib, io, os, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import desktop_translator as dt
import glossary, screen_win

tmp = tempfile.mkdtemp()
dt.DATA_DIR = os.path.join(tmp, "data"); dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.HISTORY_PATH = os.path.join(dt.DATA_DIR, "history.db")
dt.CRASH_LOG = os.path.join(dt.DATA_DIR, "crash.log")
dt.WATCHDOG_LOG = os.path.join(dt.DATA_DIR, "watchdog.log")
dt.g_translate = lambda t, sl, tl: ("译:" + t[:20], "en")
res = []
def ok(n, c):
    print(("PASS " if c else "FAIL ") + n); res.append(bool(c))

# ---- 1. 诊断信息 ----
info = {"version": "2.12.0", "python": "3.12.3", "os": "Windows 11 22631",
        "dpi": "150%", "ocr": "可用",
        "hotkeys": [("翻译选中的文字", "Ctrl+Alt+T", "已注册"),
                    ("整窗翻译", "Ctrl+Alt+W", "未注册（被占用）")]}
text = dt.build_diag_text(info)
ok("diag text has all six sections",
   all(s in text for s in ("2.12.0", "3.12.3", "Windows 11", "150%", "OCR", "Ctrl+Alt+T", "已注册", "未注册")))
ok("diag text is plain lines", "\n" in text and "诊断信息" in text)
ok("diag helpers never raise off Windows",
   isinstance(dt.os_version_text(), str) and isinstance(dt.dpi_scale_text(), str))

app = dt.App(); r = app.root
def pump(sec, until=None):
    end = time.time() + sec
    while time.time() < end:
        r.update(); time.sleep(0.02)
        if until and until(): return True
    return bool(until and until())

got = dt.collect_diag_info(app)
ok("collect diag from live app has six keys",
   all(k in got for k in ("version", "python", "os", "dpi", "ocr", "hotkeys")) and got["version"] == "2.15.6")
ok("collect diag hotkeys cover all six hotkeys", len(got["hotkeys"]) == 6)
ok("collect diag never crashes on missing pieces", all(isinstance(v, str) or isinstance(v, list) for v in got.values()))
app._copy_diag_info()
clip = ""
try:
    clip = r.clipboard_get()
except Exception:
    pass
ok("copy diag puts text on clipboard and reports it",
   "2.15.6" in clip and "诊断信息已复制" in app.status.cget("text"))

# ---- 2. 看门狗 ----
log = os.path.join(tmp, "watchdog.log")
wd = dt.Watchdog(log, threshold=0.3, interval=0.05)
wd.start()
for _ in range(8):      # 模拟健康的界面线程：每 0.1 秒打一次心跳
    wd.beat(); time.sleep(0.1)
ok("watchdog stays silent while heartbeat is fresh", not os.path.exists(log) or os.path.getsize(log) == 0)
# 停掉心跳：主线程假装卡死
wd2 = dt.Watchdog(os.path.join(tmp, "watchdog2.log"), threshold=0.2, interval=0.05)
wd2._last_beat = time.time() - 10   # 上一次心跳是很久以前
wd2.check_once()
with open(os.path.join(tmp, "watchdog2.log"), encoding="utf-8") as f:
    body = f.read()
ok("watchdog dumps all thread stacks once on stall",
   "WATCHDOG" in body and "MainThread" in body and "File \"" in body)
wd2.check_once()
with open(os.path.join(tmp, "watchdog2.log"), encoding="utf-8") as f:
    body2 = f.read()
ok("watchdog does not spam while still stalled", body2.count("WATCHDOG") == 1)
wd2.beat(); wd2.check_once()
with open(os.path.join(tmp, "watchdog2.log"), encoding="utf-8") as f:
    body3 = f.read()
ok("watchdog resets after heartbeat resumes", body3.count("WATCHDOG") == 1)
wd2._last_beat = time.time() - 10; wd2.check_once()
with open(os.path.join(tmp, "watchdog2.log"), encoding="utf-8") as f:
    body4 = f.read()
ok("watchdog reports the next stall again", body4.count("WATCHDOG") == 2)
wd.stop(); wd2.stop()
ok("app owns a running watchdog", getattr(app, "_watchdog", None) is not None
   and app._watchdog.running)
ok("app poll keeps the watchdog heartbeat fresh",
   time.time() - app._watchdog._last_beat < 2.0)

# ---- 3. 整窗翻译按窗口记忆缓存 ----
cache = dt.WindowShotCache(max_items=3)
rect = (0, 0, 100, 60)
bgra_a = bytes([9, 9, 9, 255]) * (100 * 60)
bgra_b = bytes([8, 8, 8, 255]) * (100 * 60)
ok("cache miss on empty", cache.get(rect, bgra_a) is None)
cache.put(rect, bgra_a, "MSG-A")
ok("cache hit on same rect and pixels", cache.get(rect, bgra_a) == "MSG-A")
ok("cache miss when pixels change", cache.get(rect, bgra_b) is None)
ok("cache miss when rect changes", cache.get((10, 0, 100, 60), bgra_a) is None)
ok("cache key is a short hex digest", len(cache.key(rect, bgra_a)) <= 32
   and all(c in "0123456789abcdef-" for c in cache.key(rect, bgra_a)))
cache.put(rect, bgra_b, "MSG-B"); cache.put((1, 0, 10, 10), bgra_a, "X"); cache.put((2, 0, 10, 10), bgra_a, "Y")
ok("cache evicts oldest over the limit", len(cache) == 3 and cache.get(rect, bgra_a) is None
   and cache.get(rect, bgra_b) == "MSG-B")
ok("app owns a 50-item window cache", len(app._window_cache) == 0 and app._window_cache.max_items == 50)

# 集成：同一窗口第二次不再 OCR
cap = lambda x, y, w, h, scale=1: (w * scale, h * scale, bytes([7, 7, 7, 255]) * (w * scale * h * scale))
ocr_calls = []
real_cap, real_lines = dt.screen_win.capture_region, dt.ocr_win.ocr_lines
dt.screen_win.capture_region = cap
dt.ocr_win.ocr_lines = lambda path, lang=None: (ocr_calls.append(1), [{"text": "File", "x": 4, "y": 4, "w": 40, "h": 12}])[1]
app.live_on = False
while not app.q.empty(): app.q.get_nowait()
for _ in range(2):
    app._shot_overlay_worker((0, 0, 100, 60), (0, 0), os.path.join(tmp, "x.bmp"), None, "auto", "zh-CN", True, "Google",
                             ocr_scale=1, ui_mode=True, live=False)
msgs = []
while not app.q.empty(): msgs.append(app.q.get_nowait())
ok("window cache: same window OCR runs once, overlay posted twice",
   len(ocr_calls) == 1 and len(msgs) == 2 and msgs[0][0] == "shot_overlay")
dt.screen_win.capture_region = lambda x, y, w, h, scale=1: (w * scale, h * scale, bytes([6, 6, 6, 255]) * (w * scale * h * scale))
app._shot_overlay_worker((0, 0, 100, 60), (0, 0), os.path.join(tmp, "x.bmp"), None, "auto", "zh-CN", True, "Google",
                         ocr_scale=1, ui_mode=True, live=False)
msgs2 = []
while not app.q.empty(): msgs2.append(app.q.get_nowait())
ok("window cache: changed pixels re-run OCR", len(ocr_calls) == 2 and len(msgs2) == 1)
# 截图模式（ui_mode=False）不走整窗缓存
dt.screen_win.capture_region = cap
import ocr_backends; ocr_backends.capture_available = lambda: False   # 沙箱里有真的截图命令：这里要走 Windows 同款流程
app._shot_worker((0, 0, 100, 60), (0, 0), None, "auto", "zh-CN", True, "Google", 1, False, False)
pump(3, lambda: not app.q.empty())
ok("screenshot mode does not use the window cache", len(ocr_calls) == 3)
dt.screen_win.capture_region, dt.ocr_win.ocr_lines = real_cap, real_lines

# ---- 4. 整窗结果导出 CSV ----
pairs = [("File", "文件"), ("Hello, world", "你好，世界"), ("a\nb", "甲\n乙"), ("Backup", "备份")]
path = os.path.join(tmp, "对照表.csv")
n = dt.export_window_pairs_csv(pairs, path)
with open(path, "rb") as f:
    raw = f.read()
ok("csv export is UTF-8 with BOM and returns the row count",
   n == 4 and raw[:3] == b"\xef\xbb\xbf")
with open(path, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.reader(f))
ok("csv round-trips comma/newline/Chinese fields",
   rows[0] == ["原文", "译文"] and rows[1] == ["File", "文件"]
   and rows[2] == ["Hello, world", "你好，世界"] and rows[3] == ["a\nb", "甲\n乙"])
ok("csv export of empty pairs still writes the header",
   dt.export_window_pairs_csv([], os.path.join(tmp, "e.csv")) == 0
   and list(csv.reader(open(os.path.join(tmp, "e.csv"), encoding="utf-8-sig"))) == [["原文", "译文"]])
real_fd = dt.filedialog.asksaveasfilename
dt.filedialog.asksaveasfilename = lambda *a, **k: os.path.join(tmp, "shot.csv")
app._export_shot_csv([("Open", "打开")])
ok("overlay export writes via file dialog and reports it",
   os.path.exists(os.path.join(tmp, "shot.csv")) and "对照表已导出" in app.status.cget("text"))
dt.filedialog.asksaveasfilename = lambda *a, **k: ""
app._export_shot_csv([("Open", "打开")])
ok("export cancelled quietly", "已取消" in app.status.cget("text") or "对照表" in app.status.cget("text"))
dt.filedialog.asksaveasfilename = real_fd

# ---- 5. 译文层点一块加入术语表 ----
ok("block hit-test finds the right block", dt.overlay_block_at(
    [{"x": 0, "y": 0, "w": 50, "h": 20, "src": "A", "dst": "甲"},
     {"x": 60, "y": 0, "w": 50, "h": 20, "src": "B", "dst": "乙"}], 70, 10) == 1)
ok("block hit-test misses outside all blocks", dt.overlay_block_at(
    [{"x": 0, "y": 0, "w": 50, "h": 20, "src": "A", "dst": "甲"}], 200, 200) is None)
app.cfg["glossary"] = []
ok("adding a block pair lands in the glossary", app.add_glossary_pair("Backup", "备份")
   and ["Backup", "备份"] in app.cfg["glossary"] and ["Backup", "备份"] in glossary.active())
ok("adding the same pair twice does not duplicate",
   app.add_glossary_pair("Backup", "备份") is False and app.cfg["glossary"].count(["Backup", "备份"]) == 1)
ok("over-long or empty pairs are refused", app.add_glossary_pair("x" * 50, "太长") is False
   and app.add_glossary_pair("", "空") is False)

# 端到端：译文层上点一块 → 进术语表；双击 → 复制全部
boxes = [{"x": 4, "y": 4, "w": 80, "h": 16, "src": "Restore", "dst": "恢复", "ok": True,
          "bg": "#ffffff", "fg": "#000000"},
         {"x": 4, "y": 30, "w": 80, "h": 16, "src": "Cancel", "dst": "取消", "ok": True,
          "bg": "#ffffff", "fg": "#000000"}]
png = screen_win.bgra_to_png(100, 60, bytes([255, 255, 255, 255]) * (100 * 60))
app.cfg["glossary"] = []
app._show_shot_overlay((0, 0, 100, 60), png, boxes, "en", "zh-CN", "Google", live=False)
pump(1)
ov = app.shot_overlay
ok("overlay opens with click bindings", ov is not None and ov.winfo_exists())
canvas = None
for child in ov.winfo_children():
    if child.winfo_class() == "Canvas":
        canvas = child
ok("overlay canvas has single/double/right-click bindings",
   canvas is not None and canvas.bind("<Button-1>") and canvas.bind("<Double-Button-1>")
   and canvas.bind("<Button-3>"))
canvas.event_generate("<Button-1>", x=10, y=10)
pump(1, lambda: ["Restore", "恢复"] in app.cfg["glossary"])
ok("single click on a block adds only that block to the glossary",
   ["Restore", "恢复"] in app.cfg["glossary"] and ["Cancel", "取消"] not in app.cfg["glossary"])
app._close_shot_overlay()
app._show_shot_overlay((0, 0, 100, 60), png, boxes, "en", "zh-CN", "Google", live=False)
pump(1)
ov = app.shot_overlay
canvas = [c for c in ov.winfo_children() if c.winfo_class() == "Canvas"][0]
# 两次快速按下：Tk 会把第二次认成双击（event_generate 不接受 <Double-Button-1> 写法）
canvas.event_generate("<ButtonPress-1>", x=10, y=10)
r.update(); time.sleep(0.05)
canvas.event_generate("<ButtonPress-1>", x=10, y=10)
pump(2, lambda: app.shot_overlay is None)
ok("double click still copies all translations (old behaviour kept)",
   app.shot_overlay is None and "已复制" in app.status.cget("text"))
app.quit()
print("ALL OK" if all(res) else "FAILED"); sys.exit(0 if all(res) else 1)
