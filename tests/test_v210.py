"""v2.10：整窗翻译、关闭 / 最小化到任务栏、卸载询问删库、大文件卡死修复。需 xvfb。"""
import io
import os
import random
import re
import sys
import tempfile
import threading
import time
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import desktop_translator as dt
import doc_translate
import ocr_win
import pdf_translate
import screen_win
import settings_io

tmp = tempfile.mkdtemp()
dt.DATA_DIR = os.path.join(tmp, "data")
dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.HISTORY_PATH = os.path.join(dt.DATA_DIR, "history.db")
dt.CACHE.clear()
dt.g_translate = lambda t, sl, tl: ("译:" + t[:20], "en")

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def timed(fn):
    t = time.time()
    r = fn()
    return r, time.time() - t


# ======================================================================
# 1. 纯逻辑：整窗翻译的分组 / 取窗口
# ======================================================================
ok("window_rect_at returns None off Windows", screen_win.window_rect_at(10, 10) is None)

menu = [{"text": t, "x": 10, "y": 10 + i * 22, "w": 60, "h": 16}
        for i, t in enumerate(["New File", "Open...", "Save", "Save As", "Exit"])]
g = ocr_win.group_ui_lines(menu)
ok("menu items are translated one by one", len(g) == 5 and all(len(x) == 1 for x in g))
para = [{"text": "This is a long sentence that wraps over several lines in a body text %d" % i,
         "x": 10, "y": 10 + i * 20, "w": 520, "h": 16} for i in range(4)]
g = ocr_win.group_ui_lines(para)
ok("body paragraph stays one group", len(g) == 1 and len(g[0]) == 4)
ok("empty input ok", ocr_win.group_ui_lines([]) == [])

# ======================================================================
# 2. 大文件：to_units / split_long / translate_many
# ======================================================================
def old_to_units(text, reflow):
    """v2.9 的实现（参照物）：小输入上新旧结果必须完全一致。"""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            if out and out[-1] != "":
                out.append("")
            continue
        if (reflow and out and out[-1] and len(out[-1]) >= 45
                and not out[-1].endswith(dt._END) and not dt._BULLET.match(s)):
            glue = "" if (dt._cjk(out[-1][-1]) and dt._cjk(s[0])) else " "
            out[-1] = out[-1] + glue + s
        else:
            out.append(s)
    while out and out[-1] == "":
        out.pop()
    return out


rnd = random.Random(7)
words = ["alpha", "beta", "gamma.", "delta", "你好", "世界。", "- item", "1) x", "end!", "",
         "a longer line of text that goes past the reflow threshold easily", "  ", "标题"]
same = True
for _ in range(300):
    txt = "\n".join(rnd.choice(words) for _ in range(rnd.randint(1, 12)))
    for rf in (True, False):
        if old_to_units(txt, rf) != dt.to_units(txt, rf):
            same = False
ok("to_units matches v2.9 on small inputs (reflow on/off)", same)

big = "\n".join("word%d and some more text without any ending" % i for i in range(300000))
units, dur = timed(lambda: dt.to_units(big, True))
ok("300k lines w/o punctuation reflow finishes fast (<8s): %.2fs" % dur, dur < 8)
ok("merged unit length is capped", max(len(u) for u in units) <= dt.REFLOW_MAX + 100)
ok("no text lost by reflow", sum(len(u.split()) for u in units) == 300000 * 8)

one_line = "x" * (8 * 1024 * 1024)
parts, dur = timed(lambda: dt.split_long(one_line))
ok("8MB single line split fast (<3s): %.2fs" % dur, dur < 3)
ok("split_long loses nothing, chunks <= CHUNK",
   "".join(parts) == one_line and max(map(len, parts)) <= dt.CHUNK)
ok("split_long exact multiple has no empty chunk",
   dt.split_long("a" * (dt.CHUNK * 2)) == ["a" * dt.CHUNK, "a" * dt.CHUNK])

dt.CACHE.clear()
outs = dt.translate_many(["t%d" % i for i in range(500)], "en", "zh-CN", "Google")
ok("translate_many keeps order", outs == ["译:t%d" % i for i in range(500)])
ok("translate_many empty", dt.translate_many([], "en", "zh-CN", "Google") == [])

# 一段失败：其余排队任务快速退出，抛的是真错误而不是 cancelled
# 注意：先关掉自动离线回退，否则在线抛错后会走离线回退（那是预期行为），
# 失败就不会向上传播；这里测的是"无回退可用时失败要传播、其余任务要停下"。
_prev_auto_offline = dt.AUTO_OFFLINE
dt.AUTO_OFFLINE = False
calls = []


def flaky(t, sl, tl):
    calls.append(t)
    if t == "t10":
        raise ValueError("boom")
    time.sleep(0.01)
    return ("译:" + t, "en")


dt.g_translate = flaky
dt.CACHE.clear()
try:
    dt.translate_many(["t%d" % i for i in range(3000)], "en", "zh-CN", "Google")
    ok("failure propagates", False)
except Exception as e:      # noqa: BLE001
    ok("failure propagates as the real error", "boom" in str(e) or "ValueError" in repr(e))
ok("after a failure the rest of 3000 are not all attempted (%d)" % len(calls), len(calls) < 600)
dt.AUTO_OFFLINE = _prev_auto_offline
dt.g_translate = lambda t, sl, tl: ("译:" + t[:20], "en")

# 取消
dt.g_translate = lambda t, sl, tl: (time.sleep(0.01), ("译:" + t, "en"))[1]
dt.CACHE.clear()
flag = threading.Event()
threading.Timer(0.2, flag.set).start()
t0 = time.time()
try:
    dt.translate_many(["c%d" % i for i in range(5000)], "en", "zh-CN", "Google", cancelled=flag.is_set)
    ok("cancel raises", False)
except RuntimeError as e:
    ok("cancel raises cancelled", "cancelled" in str(e))
ok("cancel returns quickly (%.2fs)" % (time.time() - t0), time.time() - t0 < 4)
dt.g_translate = lambda t, sl, tl: ("译:" + t[:20], "en")

# ======================================================================
# 3. PDF / docx / 文本文件：大小与炸弹保护
# ======================================================================
bomb = zlib.compress(b"\0" * (80 * 1024 * 1024), 9)       # 压缩后很小，解压 80MB
try:
    pdf_translate._inflate(bomb)
    ok("inflate refuses oversize stream", False)
except ValueError:
    ok("inflate refuses oversize stream", True)
ok("inflate normal stream still works", pdf_translate._inflate(zlib.compress(b"BT (hi) Tj ET")) == b"BT (hi) Tj ET")

img_pdf = (b"%PDF-1.4\n1 0 obj\n<</Type/XObject/Subtype/Image/Filter/FlateDecode/Length 9>>\nstream\n"
           + zlib.compress(b"\0" * 1000000) + b"\nendstream\nendobj\n"
           b"2 0 obj\n<</Length 25>>\nstream\nBT (Visible text) Tj ET\nendstream\nendobj\n")
payloads = list(pdf_translate._iter_stream_payloads(img_pdf))
ok("image streams are skipped, text stream kept",
   len(payloads) == 1 and b"Visible text" in payloads[0])
ok("pdf with image + text extracts text", "Visible text" in pdf_translate.extract_pdf_text(img_pdf))

ok("size limits per type", doc_translate.size_limit_for(".txt") == doc_translate.MAX_TEXT_BYTES
   and doc_translate.size_limit_for(".docx") == doc_translate.MAX_DOCX_BYTES
   and doc_translate.size_limit_for(".pdf") == doc_translate.MAX_PDF_BYTES)
ok("decode utf-8 bom", doc_translate.decode_text("\ufeffhello 你好".encode("utf-8")) == "hello 你好")
ok("decode gbk (v2.9 could not open it)", doc_translate.decode_text("你好，世界".encode("gb18030")) == "你好，世界")
ok("decode utf-16", doc_translate.decode_text("hi 你好".encode("utf-16")) == "hi 你好")
p_txt = os.path.join(tmp, "a.txt")
open(p_txt, "wb").write(b"x" * 2048)
try:
    doc_translate.read_text_file(p_txt, max_bytes=1024)
    ok("read_text_file rejects oversize", False)
except ValueError as e:
    ok("read_text_file rejects oversize with readable message", "文件太大" in str(e))

zbuf = io.BytesIO()
with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("word/document.xml", b"<w:p><w:t>a</w:t></w:p>" + b" " * 1024)
old_max = doc_translate.MAX_DOCX_XML_BYTES
doc_translate.MAX_DOCX_XML_BYTES = 100
try:
    doc_translate.docx_document_xml(zbuf.getvalue())
    ok("docx oversized document.xml rejected", False)
except ValueError:
    ok("docx oversized document.xml rejected", True)
doc_translate.MAX_DOCX_XML_BYTES = old_max
ok("docx normal still reads", b"<w:p>" in doc_translate.docx_document_xml(zbuf.getvalue()))

# ======================================================================
# 4. 设置导入导出 / 托盘菜单 / 安装脚本
# ======================================================================
cfg, _ignored, err = settings_io.import_settings(
    settings_io.export_settings(dict(dt.DEFAULTS, hotkey_window="ctrl+alt+m", minimize_action="tray")),
    dt.DEFAULTS)
ok("hotkey_window + minimize_action survive export/import",
   err is None and cfg["hotkey_window"] == "ctrl+alt+m" and cfg["minimize_action"] == "tray")
ok("defaults have the new keys", dt.DEFAULTS["hotkey_window"] == "ctrl+alt+w"
   and dt.DEFAULTS["minimize_action"] == "taskbar" and "taskbar" in dt.CLOSE_NAMES)
items = dt.tray_menu_items({"hotkey_window": "Ctrl+Alt+M"}, True)
by = {i.get("id"): i for i in items if i.get("id")}
ok("tray menu has window translate with its hotkey", "window" in by and "Ctrl+Alt+M" in by["window"]["label"])
ok("validate_hotkey_cfg covers the 6th hotkey",
   dt.validate_hotkey_cfg({"hotkey_window": "bogus"})["hotkey_window"] == "ctrl+alt+w"
   and dt.validate_hotkey_cfg({"hotkey_window": "ctrl+alt+t"})["hotkey_window"] == "ctrl+alt+w")

iss = open(os.path.join(ROOT, "installer.iss"), "rb").read()
ok("installer.iss has UTF-8 BOM (Chinese text in [Code])", iss.startswith(b"\xef\xbb\xbf"))
iss = iss.decode("utf-8-sig")
ok("installer no longer unconditionally deletes user data", "[UninstallDelete]" not in iss)
ok("installer asks before deleting data",
   "CurUninstallStepChanged" in iss and "usPostUninstall" in iss and "MsgBox(" in iss
   and "DelTree(DataDir" in iss)
ok("default button is No, silent uninstall keeps data",
   "MB_DEFBUTTON2" in iss and "UninstallSilent" in iss)
ok("installer version bumped", '#define MyAppVersion "2.15.4"' in iss and dt.__version__ == "2.15.4")

# ======================================================================
# 5. 界面：关闭 / 最小化 / 整窗翻译 / 大文档 / 取消
# ======================================================================
app = dt.App()
r = app.root


def pump(sec, until=None):
    end = time.time() + sec
    while time.time() < end:
        r.update()
        time.sleep(0.02)
        if until and until():
            return True
    return bool(until and until())


class FakeTray:
    def __init__(self):
        self.notes = []

    def is_running(self):
        return True

    def notify(self, *a):
        self.notes.append(a)

    def set_tooltip(self, *a):
        pass

    def stop(self):
        pass


calls = []
r_iconify, r_withdraw = r.iconify, r.withdraw
r.iconify = lambda: calls.append("iconify")
r.withdraw = lambda: calls.append("withdraw")
app.tray = FakeTray()

app.cfg["close_action"] = "taskbar"
app._on_close()
ok("close_action=taskbar -> minimize, not hidden", calls == ["iconify"])
calls.clear()
app.cfg["close_action"] = "tray"
app._on_close()
ok("close_action=tray -> withdraw to tray", calls == ["withdraw"])
calls.clear()
app.tray = None
app._on_close()
ok("no tray -> falls back to taskbar minimize", calls == ["iconify"])
calls.clear()
app.tray = FakeTray()
app.cfg["close_action"] = "taskbar"
app.hide_window()
ok("Esc follows close_action=taskbar", calls == ["iconify"])
calls.clear()

# 点「–」：默认留在任务栏；选「收进托盘」才藏
class Ev:
    widget = r


app.cfg["minimize_action"] = "taskbar"
after_calls = []
real_after = r.after
r.after = lambda ms, fn=None, *a: after_calls.append(fn)
app._on_unmap(Ev())
ok("minimize_action=taskbar leaves window alone", after_calls == [])
app.cfg["minimize_action"] = "tray"
app._on_unmap(Ev())
ok("minimize_action=tray schedules hide-to-tray", len(after_calls) == 1)
r.state = lambda *a: "iconic"
app._minimize_to_tray()
ok("iconic + tray -> withdraw", calls == ["withdraw"])
del r.state
r.after = real_after
calls.clear()
r.iconify, r.withdraw = r_iconify, r_withdraw
app.cfg["minimize_action"] = "taskbar"
app.cfg["close_action"] = "tray"
app.tray = None

# 设置页下拉与保存
app.close_cb.set(dt.CLOSE_NAMES["taskbar"])
app.min_cb.set(dt.MINIMIZE_NAMES["tray"])
app._save()
import json
saved = json.load(open(dt.CONFIG_PATH))
ok("settings page saves close_action / minimize_action",
   saved["close_action"] == "taskbar" and saved["minimize_action"] == "tray" and "hotkey_window" in saved)
app.close_cb.set(dt.CLOSE_NAMES["tray"])
app.min_cb.set(dt.MINIMIZE_NAMES["taskbar"])
app._save()
ok("hotkey_window var exists in settings page", app.hotkey_window_var.get() == "Ctrl+Alt+W")

# ---- 整窗翻译：调度 ----
rec = []
app._shot_worker = lambda *a, **k: rec.append((a, k))
real_win, real_ocr_av = dt.IS_WIN, dt.ocr_win.ocr_available
real_rect, real_bounds = dt.screen_win.window_rect_at, dt.screen_bounds
dt.IS_WIN = True
dt.ocr_win.ocr_available = lambda: True
dt.screen_bounds = lambda: (0, 0, 1920, 1080)

dt.screen_win.window_rect_at = lambda x, y, skip_pid=None: (100, 100, 300, 200)
app.window_translate()
pump(0.3, lambda: rec)
ok("window_translate hands the window rect to the shot worker", len(rec) == 1 and rec[0][0][0] == (100, 100, 300, 200))
ok("small window (menu) is OCR'd at 2x, ui_mode on", rec[0][0][-3:-1] == (2, True))
rec.clear()
dt.screen_win.window_rect_at = lambda x, y, skip_pid=None: (0, 0, 1900, 1000)
app.window_translate()
pump(0.3, lambda: rec)
ok("big window is OCR'd at 1x", rec and rec[0][0][-3:-1] == (1, True))
rec.clear()
dt.screen_win.window_rect_at = lambda x, y, skip_pid=None: (-50, -50, 5000, 4000)
app.window_translate()
pump(0.3, lambda: rec)
ok("rect is clamped to the screen", rec and rec[0][0][0][0] >= 0 and rec[0][0][0][2] <= 1920 and rec[0][0][0][3] <= 1080)
rec.clear()
dt.screen_win.window_rect_at = lambda x, y, skip_pid=None: None
app.window_translate()
pump(0.2)
ok("no window under pointer -> friendly status, no worker", not rec and "没找到" in app.status.cget("text"))
dt.screen_win.window_rect_at = lambda x, y, skip_pid=None: (10, 10, 5, 5)
app.window_translate()
pump(0.2)
ok("tiny window rejected", not rec and "太小" in app.status.cget("text"))

# 延迟触发（主窗口按钮 / 托盘菜单）
after_calls.clear()
r.after = lambda ms, fn=None, *a: after_calls.append((ms, fn))
r.iconify = lambda: calls.append("iconify")
app.window_translate(delay_ms=3000)
ok("delayed mode minimizes main window and waits 3s",
   calls == ["iconify"] and after_calls and after_calls[0][0] == 3000
   and after_calls[0][1] == app._window_translate_now)
r.after = real_after
r.iconify = r_iconify
calls.clear()

# 热键 6 / 托盘命令
hits = []
app.window_translate = lambda delay_ms=0: hits.append(delay_ms)
app._on_hotkey(6)
app._on_tray_cmd("window")
ok("hotkey 6 -> immediate; tray menu -> 3s delay", hits == [0, 3000])
del app.window_translate

dt.IS_WIN = False
app.window_translate()
ok("non-Windows: clear message", "只支持 Windows" in app.status.cget("text"))
dt.IS_WIN = real_win
dt.ocr_win.ocr_available = real_ocr_av
dt.screen_win.window_rect_at, dt.screen_bounds = real_rect, real_bounds

# ---- OCR 放大 2 倍后坐标缩回 1:1、菜单项逐行翻 ----
real_cap, real_ocr_lines = dt.screen_win.capture_region, dt.ocr_win.ocr_lines


def fake_cap(x, y, w, h, scale=1):
    return w * scale, h * scale, bytes([200, 200, 200, 255]) * (w * scale * h * scale)


def fake_lines(path, lang=None):
    # 2 倍图上的坐标：三个竖排的短菜单项
    return [{"text": t, "x": 20, "y": 20 + i * 44, "w": 120, "h": 30} for i, t in enumerate(["File", "Edit", "Help"])]


dt.screen_win.capture_region, dt.ocr_win.ocr_lines = fake_cap, fake_lines
dt.CACHE.clear()
app._shot_overlay_worker((0, 0, 200, 150), (5, 5), os.path.join(tmp, "s.bmp"), None, "auto", "zh-CN",
                         True, "Google", ocr_scale=2, ui_mode=True)
msg = None
while not app.q.empty():
    m = app.q.get_nowait()
    if m[0] == "shot_overlay":
        msg = m
ok("overlay worker posts a result", msg is not None)
boxes = msg[3]
ok("menu items translated separately (3 boxes)", len(boxes) == 3 and [b["src"] for b in boxes] == ["File", "Edit", "Help"])
ok("coordinates scaled back to 1x", boxes[0]["x"] == 10 and boxes[0]["y"] == 10 and boxes[0]["w"] == 60 and boxes[0]["h"] == 15)
dt.screen_win.capture_region, dt.ocr_win.ocr_lines = real_cap, real_ocr_lines

# ---- 大文档：不卡界面、不炸、译文框只显示前一部分、复制 / 保存是全文 ----
N = 30000
doc_path = os.path.join(tmp, "big.txt")
with open(doc_path, "w", encoding="utf-8") as f:
    f.write("\n\n".join("Paragraph number %d of the big file." % i for i in range(N)))
out_path = os.path.join(tmp, "big-译文.txt")
real_fd = dt.filedialog
dt.filedialog.askopenfilename = lambda *a, **k: doc_path
dt.filedialog.asksaveasfilename = lambda *a, **k: out_path
real_ask = dt.messagebox.askyesno
dt.messagebox.askyesno = lambda *a, **k: True
dt.CACHE.clear()
dt.CACHE_MAX = 800
ticks = []
t0 = time.time()
app._translate_doc_file()
ok("doc job marked busy right away + cancel button shown", app._doc_busy and app.doc_cancel_btn.winfo_manager() == "pack")
# 界面线程在翻译期间一直能处理事件（旧版读文件 / 渲染会整个卡住）
last = time.time()
worst = 0.0
end = time.time() + 120
while time.time() < end and not os.path.exists(out_path):
    r.update()
    now = time.time()
    worst = max(worst, now - last)
    last = now
    time.sleep(0.005)
ok("30k-paragraph doc finishes", os.path.exists(out_path))
pump(1.0)
ok("UI never froze more than 1.5s while translating (worst %.2fs)" % worst, worst < 1.5)
got = open(out_path, encoding="utf-8").read().split("\n")
ok("saved file has every paragraph", sum(1 for ln in got if ln.startswith("译:")) == N)
shown = app.dst.get("1.0", "end")
ok("result box shows only the first part", len(shown) <= dt.App.RENDER_MAX_CHARS + 400 and "后面还有" in shown)
ok("copy/plain_result is the full text", app.plain_result().count("译:") == N)
ok("busy flag and cancel button reset after done", not app._doc_busy and app.doc_cancel_btn.winfo_manager() == "")
ok("status says done", "文档翻译完成" in app.status.cget("text"))
dt.CACHE_MAX = 800

# ---- 取消 ----
dt.g_translate = lambda t, sl, tl: (time.sleep(0.01), ("译:" + t[:20], "en"))[1]
dt.CACHE.clear()
slow_path = os.path.join(tmp, "slow.txt")
with open(slow_path, "w", encoding="utf-8") as f:
    f.write("\n\n".join("Slow paragraph %d" % i for i in range(5000)))
dt.filedialog.askopenfilename = lambda *a, **k: slow_path
save_called = []
dt.filedialog.asksaveasfilename = lambda *a, **k: (save_called.append(1), "")[1]
app._translate_doc_file()
pump(0.5)
ok("slow doc is running", app._doc_busy)
app._translate_doc_file()                    # 再点一次：不会开第二个任务
ok("second doc job refused while busy", "已经有一份文档" in app.status.cget("text"))
app._cancel_doc()
t0 = time.time()
finished = pump(8, lambda: not app._doc_busy)
ok("cancel stops the job quickly (%.1fs)" % (time.time() - t0), finished and time.time() - t0 < 6)
ok("cancel status shown, no save dialog", "已取消" in app.status.cget("text") and not save_called)
ok("cancel button hidden again", app.doc_cancel_btn.winfo_manager() == "")

# ---- 太大的文件：直接拒绝；较大的文件：先问 ----
dt.g_translate = lambda t, sl, tl: ("译:" + t[:20], "en")
huge = os.path.join(tmp, "huge.txt")
open(huge, "wb").write(b"a")
real_getsize = os.path.getsize
os.path.getsize = lambda p: 80 * 1024 * 1024 if p == huge else real_getsize(p)
dt.filedialog.askopenfilename = lambda *a, **k: huge
app._translate_doc_file()
ok("oversize file is refused with a clear message, no job started",
   "文件太大" in app.status.cget("text") and not app._doc_busy)
os.path.getsize = real_getsize
dt.messagebox.askyesno = real_ask
dt.filedialog = real_fd

# ---- GBK 编码的 txt 现在能翻 ----
gbk = os.path.join(tmp, "gbk.txt")
open(gbk, "wb").write("第一段\n\n第二段".encode("gb18030"))
gbk_out = os.path.join(tmp, "gbk-译文.txt")
dt.filedialog.askopenfilename = lambda *a, **k: gbk
dt.filedialog.asksaveasfilename = lambda *a, **k: gbk_out
dt.CACHE.clear()
app._translate_doc_file()
ok("GBK txt translates", pump(8, lambda: os.path.exists(gbk_out)) and "第一段" in open(gbk_out, encoding="utf-8").read())
dt.filedialog = real_fd

# ---- 消息队列洪水：每轮 _poll 最多处理 300 条 ----
app._doc_busy = True
for i in range(1000):
    app.q.put(("doc_prog", i, 1000))
app._poll()
ok("_poll drains at most 300 messages per tick", 600 <= app.q.qsize() <= 750)
while not app.q.empty():
    app.q.get_nowait()
app._doc_busy = False

# ---- render 小结果不受影响 ----
app.pairs = [("a", "甲"), ("", ""), ("b", "乙")]
app.bi_var.set(False)
app.render()
ok("small result renders in full without the truncation note", app.dst.get("1.0", "end").strip() == "甲\n\n乙")
app.bi_var.set(True)
app.render()
ok("bilingual render still works", "a" in app.dst.get("1.0", "end") and "乙" in app.dst.get("1.0", "end"))
app.bi_var.set(False)

app.quit()
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
