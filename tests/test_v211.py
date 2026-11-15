"""v2.11：悬停整窗翻译、文档预估耗时、实时刷新。需 xvfb。"""
import json, os, sys, tempfile, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import desktop_translator as dt
import screen_win, settings_io

tmp = tempfile.mkdtemp()
dt.DATA_DIR = os.path.join(tmp, "data"); dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.HISTORY_PATH = os.path.join(dt.DATA_DIR, "history.db")
dt.g_translate = lambda t, sl, tl: ("译:" + t[:20], "en")
res = []
def ok(n, c):
    print(("PASS " if c else "FAIL ") + n); res.append(bool(c))

# ---- 预估耗时（纯函数） ----
ok("online estimate scales with segments", dt.estimate_doc_seconds(4000, 0, "Google") == 4000 * 0.5 / dt.WORKERS)
ok("chars add requests", dt.estimate_doc_seconds(0, dt.CHUNK * 10, "Google") == 10 * 0.5 / dt.WORKERS)
ok("offline is slower", dt.estimate_doc_seconds(100, 0, "离线") > dt.estimate_doc_seconds(100, 0, "Google"))
ok("duration formats", dt.fmt_duration(5) == "约 5 秒" and dt.fmt_duration(61) == "约 2 分钟" and "小时" in dt.fmt_duration(7200)
   and dt.fmt_duration(0) == "约 1 秒")
cfg, _i, err = settings_io.import_settings(settings_io.export_settings(dict(dt.DEFAULTS, hover_window=True, live_interval=5)), dt.DEFAULTS)
ok("new settings survive export/import", err is None and cfg["hover_window"] is True and cfg["live_interval"] == 5)
ok("live_interval clamped on import", settings_io.import_settings(json.dumps(
    {"app": "RealtimeTranslate", "version": 1, "config": {"live_interval": 999}, "glossary": []}), dt.DEFAULTS)[0]["live_interval"] == 30)

app = dt.App(); r = app.root
def pump(sec, until=None):
    end = time.time() + sec
    while time.time() < end:
        r.update(); time.sleep(0.02)
        if until and until(): return True
    return bool(until and until())

# ---- 文档预估：大文档先问；不想翻就取消 ----
real_fd, real_ask = dt.filedialog, dt.messagebox.askyesno
big = os.path.join(tmp, "big.txt")
open(big, "w", encoding="utf-8").write("\n\n".join("Paragraph %d" % i for i in range(2500)))
dt.filedialog.askopenfilename = lambda *a, **k: big
saved = []
dt.filedialog.asksaveasfilename = lambda *a, **k: (saved.append(1), "")[1]
asked = []
dt.messagebox.askyesno = lambda title, msg, **k: (asked.append(msg), False)[1]
dt.CACHE.clear()
app._translate_doc_file()
ok("big doc asks with segments and estimate", pump(8, lambda: asked) and "2500" in asked[0] and "预计" in asked[0])
ok("answering No cancels cleanly", pump(5, lambda: not app._doc_busy) and "已取消" in app.status.cget("text") and not saved)
small = os.path.join(tmp, "small.txt")
open(small, "w", encoding="utf-8").write("Hello\n\nWorld")
dt.filedialog.askopenfilename = lambda *a, **k: small
asked.clear(); out = os.path.join(tmp, "small-译文.txt")
dt.filedialog.asksaveasfilename = lambda *a, **k: out
app._translate_doc_file()
ok("small doc is not asked", pump(8, lambda: os.path.exists(out)) and not asked)
dt.messagebox.askyesno = lambda *a, **k: True
dt.g_translate = lambda t, sl, tl: (time.sleep(0.002), ("译:" + t[:20], "en"))[1]
dt.CACHE.clear(); dt.filedialog.askopenfilename = lambda *a, **k: big
out2 = os.path.join(tmp, "big-译文.txt"); dt.filedialog.asksaveasfilename = lambda *a, **k: out2
app._translate_doc_file()
seen = []
end = time.time() + 60
while time.time() < end and not os.path.exists(out2):
    r.update(); time.sleep(0.02)
    t = app.status.cget("text")
    if "剩余" in t: seen.append(t)
ok("Yes translates, status showed remaining time", os.path.exists(out2) and seen)
dt.filedialog, dt.messagebox.askyesno = real_fd, real_ask
dt.g_translate = lambda t, sl, tl: ("译:" + t[:20], "en")

# ---- 悬停整窗：同一窗口只翻一次 ----
calls = []
app._start_window_worker = lambda rect, pos, live=False: calls.append((rect, live))
real = (dt.IS_WIN, dt.screen_win.window_rect_at, dt.screen_bounds)
dt.IS_WIN = True; dt.screen_bounds = lambda: (0, 0, 1920, 1080)
cur = [(100, 100, 300, 200)]
dt.screen_win.window_rect_at = lambda x, y, skip_pid=None: cur[0]
r.winfo_containing = lambda x, y: None
app._on_hover_window((150, 150))
app._on_hover_window((160, 150))
ok("same window translated once", len(calls) == 1 and calls[0] == ((100, 100, 300, 200), False))
cur[0] = (500, 100, 300, 200)
app._on_hover_window((520, 150))
ok("different window translated again", len(calls) == 2)
r.winfo_containing = lambda x, y: app.src
app._on_hover_window((0, 0)); cur[0] = (1, 1, 400, 300); app._on_hover_window((5, 5))
ok("pointer over our own window is ignored", len(calls) == 2)
del r.winfo_containing

# _hover_check 在整窗模式下走整窗、且至少等 1.2 秒
app.hover_var.set(True); app.hover_win_var.set(True); app.cfg["hover_ms"] = 300
fired = []
app._on_hover_window = lambda pos: fired.append(pos)
app._on_hover = lambda pos: fired.append("word")
app.bubble.alive = lambda: False
app._hover_blocked = lambda pos: False
app.grabbing = False; app.shot_win = None
r.winfo_pointerxy = lambda: (50, 50)
app.hover_last = None
app._hover_check()
app.hover_since -= 0.5; app._hover_check()
ok("window hover waits at least 1.2s", not fired)
app.hover_since -= 1.0; app._hover_check()
ok("window hover fires and replaces word hover", fired == [(50, 50)])
app.hover_win_var.set(False)

# ---- 实时刷新 ----
dt.ocr_win.ocr_available = lambda: True
dt.screen_win.window_rect_at = lambda x, y, skip_pid=None: (100, 100, 300, 200)
calls.clear(); app.live_var.set(True)
app.live_start()
ok("live start launches a live worker on the window", app.live_on and calls == [((100, 100, 300, 200), True)])
app._live_done()
ok("after a round it schedules the next tick", app._live_job is not None and not app._live_busy)
app.live_var.set(True)
app.hotkey_window_label  # property exists
app._on_hotkey(6)
ok("pressing the window hotkey stops live mode", not app.live_on and not app.live_var.get() and app._live_job is None)
app.live_var.set(True); app.live_start(); app._on_shot_ocr(True, "", (0, 0))
ok("empty OCR in live mode just waits for the next round", app.live_on and app._live_job is not None)
app.live_stop()

# 画面不变就复用上次结果，不再 OCR
import zlib
cap = lambda x, y, w, h, scale=1: (w * scale, h * scale, bytes([9, 9, 9, 255]) * (w * scale * h * scale))
ocr_calls = []
dt.screen_win.capture_region = cap
dt.ocr_win.ocr_lines = lambda path, lang=None: (ocr_calls.append(1), [{"text": "File", "x": 4, "y": 4, "w": 40, "h": 12}])[1]
app.live_on = True; app._live_crc = app._live_msg = None
while not app.q.empty(): app.q.get_nowait()
for _ in range(2):
    app._shot_overlay_worker((0, 0, 100, 60), (0, 0), os.path.join(tmp, "x.bmp"), None, "auto", "zh-CN", True, "Google",
                             ocr_scale=1, ui_mode=True, live=True)
msgs = []
while not app.q.empty(): msgs.append(app.q.get_nowait())
ok("unchanged screen: OCR runs once, overlay re-posted twice", len(ocr_calls) == 1 and len(msgs) == 2 and msgs[0][-1] is True)
app.live_on = False

# 译文层：live 时点击穿透调用、不写主窗口
ct = []
real_ct = dt.screen_win.make_click_through
dt.screen_win.make_click_through = lambda wid: (ct.append(wid), True)[1]
app.pairs = []; app.live_on = True; app._live_busy = True
app._show_shot_overlay(*msgs[0][1:])
ok("live overlay is click-through, main window untouched, next tick scheduled",
   ct and app.pairs == [] and not app._live_busy and app._live_job is not None)
app.live_stop()
ok("non-Windows toggle is refused politely", True)
dt.IS_WIN = False; app.live_var.set(True); app._on_live_toggle()
ok("toggle off-Windows unchecks and explains", not app.live_var.get() and "只支持 Windows" in app.status.cget("text"))
dt.IS_WIN = real[0]
ok("click-through no-op off Windows", real_ct(1) is False)

# 设置保存
app.hover_win_var.set(True); app.live_int_var.set("5"); app._on_live_interval(); app._on_pointer_opt()
saved = json.load(open(dt.CONFIG_PATH))
ok("settings saved", saved["hover_window"] is True and saved["live_interval"] == 5)
app.quit()
print("ALL OK" if all(res) else "FAILED"); sys.exit(0 if all(res) else 1)
