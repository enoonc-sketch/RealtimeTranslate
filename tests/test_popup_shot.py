"""取词弹窗方式 / 跟随指针小窗口 / 应用按钮取词 / 截图译文盖在截图上 / × 不退出。需 xvfb。"""
import json
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import history_store as hs
import ocr_win
import screen_win
import desktop_translator as dt

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


# ---------- 纯逻辑：PNG / 背景色 / 分段 ----------
w_, h_ = 60, 40
bgra = bytearray()
for y in range(h_ - 1, -1, -1):                       # bottom-up
    for x in range(w_):
        bgra += bytes([240, 240, 240, 255]) if x < 30 else bytes([30, 30, 30, 255])
png = screen_win.bgra_to_png(w_, h_, bytes(bgra))
ok("png signature + IEND", png[:8] == b"\x89PNG\r\n\x1a\n" and png.endswith(b"IEND\xaeB`\x82"))
ok("sample_bg picks light bg on the left half", screen_win.sample_bg(w_, h_, bytes(bgra), 4, 10, 20, 12) == "#f4f4f4"
   or screen_win.sample_bg(w_, h_, bytes(bgra), 4, 10, 20, 12).startswith("#f"))
ok("sample_bg picks dark bg on the right half", screen_win.sample_bg(w_, h_, bytes(bgra), 36, 10, 20, 12) < "#303030")
ok("text colour contrast", screen_win.text_color_for("#f4f4f4") == "#000000" and screen_win.text_color_for("#1e1e1e") == "#ffffff")

L = lambda t, x, y, w=200, h=16: {"text": t, "x": x, "y": y, "w": w, "h": h}
lines = [L("Title line", 10, 5, 120, 30), L("para one a", 10, 50), L("para one b", 10, 70),
         L("para two", 10, 110), L("right col", 400, 50)]
groups = ocr_win.group_paragraphs(lines)
ok("group_paragraphs: title / para1 / right col / para2 separated, reading order",
   groups == [[0], [1, 2], [4], [3]])
ok("paragraph_box is union", ocr_win.paragraph_box(lines, [1, 2]) == (10, 50, 200, 36))

# ---------- 界面 ----------
app = dt.App()
app.root.update()
tmpd = tempfile.mkdtemp()
app.history = hs.HistoryStore(os.path.join(tmpd, "h.db"))
dt.translate = lambda text, sl, tl, smart, engine, cancelled=None: ("译:" + text, "en", "zh-CN")


def drain():
    out = []
    while not app.q.empty():
        out.append(app.q.get_nowait())
    return out


def set_popup(mode):
    app.popup_cb.set(dt.POPUP_NAMES[mode])
    app._on_popup_opt()


# --- 5. 点 × 不退出 ---
quits = []
app.quit = lambda: quits.append(1)
app.tray = None
app.cfg["close_action"] = "tray"
iconified = []
app.root.iconify = lambda: iconified.append(1)          # xvfb 没有窗口管理器，iconify 不会真的生效，只验证走了这条路
app._on_close()
ok("× without tray: minimizes instead of quitting", quits == [] and iconified == [1])
del app.root.iconify
app.root.deiconify()
class T:
    def is_running(self): return True
    def notify(self, *a, **k): return True
    def set_tooltip(self, t): return True
    def stop(self): pass
app.tray = T()
app._on_close()
ok("× with tray: hides to tray, still not quitting", quits == [] and app.root.state() == "withdrawn")
app.root.deiconify()
app.tray = None
app.cfg["close_action"] = "quit"
app._on_close()
ok("only close_action=quit really quits", quits == [1])
app.cfg["close_action"] = "tray"

# --- 6. 小窗口：大小 / 跟随 / 设置 ---
set_popup("mini")
app.mini_w_var.set(300); app.mini_h_var.set(100)
app._on_mini_size()
app.mini.show((200, 150), "head", "body text")
app.root.update()
ok("mini window uses configured size", app.mini.win.winfo_width() == 300 and app.mini.win.winfo_height() == 100)
ok("mini placed right-below pointer", (app.mini.win.winfo_x(), app.mini.win.winfo_y()) == (216, 172))
app.mini.win.winfo_pointerxy = lambda: (500, 400)
app.root.update()
time.sleep(0.12)
app.root.update()
ok("mini follows the pointer", (app.mini.win.winfo_x(), app.mini.win.winfo_y()) == (516, 422))
app.mini.hide_for_capture()
app.root.update()
ok("mini hides during capture", app.mini.alive() and not app.mini.win.winfo_viewable())
app.mini.update("h2", "译文来了")
app.root.update()
ok("mini reappears when result arrives", app.mini.win.winfo_viewable() and app.mini.body.cget("text") == "译文来了")
app.mini.hide_for_capture()
app.mini.hidden_at = time.time() - 3
time.sleep(0.1)
app.root.update()
ok("hidden mini with no result closes itself", not app.mini.alive())

app.mini_w_var.set(5); app.mini_h_var.set(99999)
app._on_mini_size()
ok("mini size clamped (160..800 x 60..500) + saved", (app.cfg["mini_w"], app.cfg["mini_h"]) == (160, 500)
   and json.load(open(dt.CONFIG_PATH))["mini_w"] == 160)
app.mini_w_var.set(420); app.mini_h_var.set(140)
app._on_mini_size()
app._preview_mini()
app.root.update()
ok("preview shows mini at new size", app.mini.win.winfo_width() == 420 and app.mini.win.winfo_height() == 140)
app.mini.close()

# 取词结果走小窗口
app.cfg["history_reuse"] = False
app.grab_mode = "hover"
app._pointer_translate("hello", (300, 300))
ok("mini mode: 'translating…' shown in mini, bubble not used", app.mini.alive() and not app.bubble.alive())
time.sleep(0.3)
for m in drain():
    if m[0] == "bubble":
        app._on_bubble(*m[1:])
app.root.update()
ok("mini mode: translation lands in mini window", "译:hello" in app.mini.body.cget("text"))
r = app.history.find("hello", "auto", app._codes()[1])
ok("hover result stored with kind=hover", r and r["kind"] == "hover")
app.mini.close()

# 弹窗方式：气泡 / 不弹窗
set_popup("bubble")
app.grab_mode = "pointer"
app._pointer_translate("world", (300, 300))
ok("bubble mode uses bubble", app.bubble.alive() and not app.mini.alive())
app.bubble.close()
time.sleep(0.3); drain()
set_popup("main")
called = []
app.translate_now = lambda: called.append(app._kind_hint)
app._pointer_translate("quiet", (300, 300))
ok("popup 'main' mode: no popup at all, text goes to main window",
   not app.bubble.alive() and not app.mini.alive() and app.src.get("1.0", "end").strip() == "quiet" and called == ["pointer"])
app.popup_cb.set(dt.POPUP_NAMES["mini"])
app._on_popup_opt()
ok("popup mode saved from settings", json.load(open(dt.CONFIG_PATH))["popup_mode"] == "mini")
app.popup_cb.set(dt.POPUP_NAMES["bubble"]); app._on_popup_opt()
del app.translate_now

# --- 4. 悬停：本程序的按钮能取，文本框 / 弹窗不取 ---
app.root.update()
btn = [w for w in walk(app.root) if w.winfo_class() == "TButton" and w.winfo_ismapped()][0]
bx, by = btn.winfo_rootx() + 5, btn.winfo_rooty() + 5
ok("hover over an app button is NOT blocked", app._hover_blocked((bx, by)) is False)
sx, sy = app.src.winfo_rootx() + 20, app.src.winfo_rooty() + 20
ok("hover over own source box is blocked", app._hover_blocked((sx, sy)) is True)
dx, dy = app.dst.winfo_rootx() + 20, app.dst.winfo_rooty() + 20
ok("hover over own translation box is blocked", app._hover_blocked((dx, dy)) is True)
app.bubble.show((50, 50), "h", "b")
app.root.update()
ok("hover over the bubble is blocked", app._hover_blocked((app.bubble.win.winfo_rootx() + 5, app.bubble.win.winfo_rooty() + 5)) is True)
app.bubble.close()
app.open_settings("grab")
app.root.update()
lbl = [w for w in walk(app.settings_win) if w.winfo_class() in ("TLabel", "TCheckbutton") and w.winfo_ismapped()][0]
ok("hover over the settings window's labels/checks is not blocked",
   app._hover_blocked((lbl.winfo_rootx() + 3, lbl.winfo_rooty() + 3)) is False)
app.close_settings()

# OCR 放大：单词 / 整行放 2 倍，整段不放大；坐标按倍数换算
caps = []
dt.IS_WIN = True
dt.screen_bounds = lambda: (0, 0, 1920, 1080)
screen_win.capture_file = lambda path, x, y, w, h, scale=1: (caps.append((x, y, w, h, scale)), open(path, "wb").write(b"x"))
dt.ocr_win.ocr_available = lambda: True
seen = {}
dt.ocr_win.ocr_words = lambda p, lang=None: (seen.update(words=True) or [{"text": "Save", "x": 420, "y": 100, "w": 80, "h": 30}])
dt.ocr_win.ocr_lines = lambda p, lang=None: [{"text": "Save as...", "x": 10, "y": 10, "w": 300, "h": 20}]
t = app._ocr_pick((1000, 500), "word")
# 区域左上角 = (1000-210, 500-55) = (790, 445)；放大 2 倍后指针在 ((210)*2, (55)*2) = (420, 110)
ok("word OCR captured at 2x and found the button word", caps[-1][4] == 2 and t == "Save")
app._ocr_pick((1000, 500), "paragraph")
ok("paragraph OCR not upscaled", caps[-1][4] == 1)

# --- 3. 截图翻译：译文盖在截图上 ---
rect = (100, 80, 300, 160)
cw, ch = 300, 160
bg = bytearray()
for y in range(ch):
    for x in range(cw):
        bg += bytes([250, 250, 250, 255])             # 白底
raw = bytes(bg)
screen_win.capture_region = lambda x, y, w, h, scale=1: (cw, ch, raw)
screen_win.save_bmp = lambda path, w, h, b: open(path, "wb").write(b"x") and path
ocr_lines_out = [L("Hello world", 20, 20, 150, 18), L("second line here", 20, 40, 170, 18), L("Footer text", 20, 120, 120, 18)]
dt.ocr_win.ocr_lines = lambda p, lang=None: ocr_lines_out
app.cfg["shot_mode"] = "overlay"
app._shot_overlay_worker(rect, (100, 80), os.path.join(tmpd, "shot.bmp"))
msgs = drain()
ov = [m for m in msgs if m[0] == "shot_overlay"]
ok("worker sends one shot_overlay message", len(ov) == 1)
_, rc, png2, boxes, det, target, engine, _live = ov[0]
ok("paragraphs translated: 2 boxes, first merges 2 lines",
   len(boxes) == 2 and boxes[0]["src"] == "Hello world second line here" and boxes[0]["dst"] == "译:Hello world second line here"
   and boxes[1]["dst"] == "译:Footer text")
ok("box background sampled from the screenshot (white) with black text", boxes[0]["bg"].startswith("#f") and boxes[0]["fg"] == "#000000")
ok("box geometry is the paragraph union", (boxes[0]["x"], boxes[0]["y"], boxes[0]["w"], boxes[0]["h"]) == (20, 20, 170, 38))

dt.ocr_win.ocr_lines = lambda p, lang=None: []
app._shot_overlay_worker(rect, (100, 80), os.path.join(tmpd, "shot.bmp"))
m = drain()
ok("no text found -> falls back to the old message", m and m[0][0] == "shot_ocr" and m[0][3] == (100, 80))

app._show_shot_overlay(rc, png2, boxes, det, target, engine)
app.root.update()
ovw = app.shot_overlay
ok("overlay window exists at the selected rectangle", ovw is not None and ovw.winfo_width() == 300 and ovw.winfo_height() == 160
   and (ovw.winfo_x(), ovw.winfo_y()) == (100, 80))
cv = [w for w in walk(ovw) if w.winfo_class() == "Canvas"][0]
types = [cv.type(i) for i in cv.find_all()]
texts = [cv.itemcget(i, "text") for i in cv.find_all() if cv.type(i) == "text"]
ok("canvas has the screenshot image + cover rectangles + translated text",
   "image" in types and types.count("rectangle") >= 2 and "译:Hello world second line here" in texts and "译:Footer text" in texts)
ok("translated text drawn inside the original paragraph area",
   all(cv.bbox(i)[0] >= 15 and cv.bbox(i)[2] <= cw for i in cv.find_all()
       if cv.type(i) == "text" and cv.itemcget(i, "text").startswith("译:")))
ok("main window synced + history saved as screenshot",
   "Hello world" in app.src.get("1.0", "end") and app.history.find(
       "Hello world second line here\nFooter text", *app._codes()) is not None
   and app.history.search("Footer")[0]["kind"] == "screenshot")
ok("hover is blocked while overlay is shown", app._hover_blocked((0, 0)) is True)
copied = []
app._set_clip = lambda t: copied.append(t)
# v2.12：单击一块是加入术语表，双击才是复制全部（两次快速按下，Tk 会把第二次认成双击）
cv.event_generate("<ButtonPress-1>", x=50, y=50)
app.root.update(); time.sleep(0.05)
cv.event_generate("<ButtonPress-1>", x=50, y=50)
app.root.update()
ok("double click copies all translated text and closes", copied == ["译:Hello world second line here\n译:Footer text"]
   and app.shot_overlay is None)
app._show_shot_overlay(rc, png2, boxes, det, target, engine)
app.root.update()
cv = [w for w in walk(app.shot_overlay) if w.winfo_class() == "Canvas"][0]
cv.event_generate("<Button-3>", x=5, y=5)
app.root.update()
ok("right click opens a menu instead of closing", app.shot_overlay is not None
   and getattr(app, "_overlay_menu", None) is not None)
app._overlay_menu.invoke("关闭")
app.root.update()
ok("menu Close closes the overlay", app.shot_overlay is None)
# 一段翻译失败不拖垮整张图
def flaky(text, sl, tl, smart, engine, cancelled=None):
    if "Footer" in text:
        raise RuntimeError("boom")
    return "译:" + text, "en", "zh-CN"
dt.translate = flaky
dt.ocr_win.ocr_lines = lambda p, lang=None: ocr_lines_out
app._shot_overlay_worker(rect, (100, 80), os.path.join(tmpd, "shot.bmp"))
fb = [m for m in drain() if m[0] == "shot_overlay"][0][3]
ok("one failing paragraph is marked, others fine", [b["ok"] for b in fb] == [True, False] and "翻译失败" in fb[1]["dst"])
app._show_shot_overlay(rc, png2, fb, "en", "zh-CN", "Google")
app.root.update()
app._close_shot_overlay()

# 设置：截图翻译结果方式
app.shot_cb.set(dt.SHOT_NAMES["main"]); app._save()
ok("shot_mode saved", json.load(open(dt.CONFIG_PATH))["shot_mode"] == "main")
app.shot_cb.set(dt.SHOT_NAMES["overlay"]); app._save()

# 恢复默认包含新选项
dt.messagebox.askyesno = lambda *a, **k: True
app.popup_cb.set(dt.POPUP_NAMES["mini"]); app.mini_w_var.set(700)
app._reset_settings()
c = json.load(open(dt.CONFIG_PATH))
ok("reset restores popup/mini/shot defaults", c["popup_mode"] == "bubble" and c["mini_w"] == 320 and c["mini_h"] == 110
   and c["shot_mode"] == "overlay")

app.root.destroy()
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
