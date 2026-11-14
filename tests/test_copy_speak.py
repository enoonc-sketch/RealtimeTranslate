"""复制闭环 + 朗读按钮 + 快捷键保存：xvfb 下跑 App。"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import desktop_translator as dt

tmp = tempfile.mkdtemp()
dt.DATA_DIR = os.path.join(tmp, "data")
dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.HISTORY_PATH = os.path.join(dt.DATA_DIR, "history.db")
dt.g_translate = lambda t, sl, tl: ("译:" + t[:20], "en")

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def pump(sec, until=None):
    end = time.time() + sec
    while time.time() < end:
        app.root.update()
        time.sleep(0.02)
        if until and until():
            return True
    return bool(until and until())


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def buttons_with(text):
    return [w for w in walk(app.root) if w.winfo_class() == "TButton"
            and w.cget("text") == text and w.winfo_toplevel() is app.root]


app = dt.App()
r = app.root
app.root.update()

# ---- 1. 复制原文 / 复制译文 / 双语复制 ----
app._set_src("Hello world")
app.pairs = [("Hello world", "你好，世界")]
app.detected = "en"
app.render()
app.copy_source()
ok("copy_source copies src", r.clipboard_get() == "Hello world")
ok("copy_source sets last_clip", app.last_clip == "Hello world")
ok("copy_source status", app.status.cget("text") == "已复制原文")
app.copy_result()
ok("copy_result unchanged", r.clipboard_get() == "你好，世界"
   and app.status.cget("text") == "已复制译文")
app.bi_var.set(False)
ok("copy_bilingual off: src + blank + dst",
   app.copy_bilingual() == "Hello world\n\n你好，世界")
app.bi_var.set(True)
app.pairs = [("Hello", "你好"), ("World", "世界")]
ok("copy_bilingual on: per-pair lines",
   app.copy_bilingual() == "Hello\n你好\n\nWorld\n世界")
app.bi_var.set(False)
app.pairs = [("Hello world", "你好，世界")]

# ---- 2. 自动复制：开 → 译完剪贴板就是译文，且不触发监听循环 ----
app.auto_copy_var.set(True)
app._save()
ok("auto_copy saved", json.load(open(dt.CONFIG_PATH))["auto_copy"] is True)
app._set_src("auto copy me")
app.translate_now()
pump(2.0, lambda: app.plain_result().startswith("译:"))
ok("auto_copy on: clipboard holds translation",
   r.clipboard_get() == app.plain_result() and app.last_clip == app.plain_result())
ok("auto_copy on: status appends 已复制", "已复制" in app.status.cget("text"))
seq0 = app.seq
pump(1.5)                      # 剪贴板监听跑几轮：不能把刚复制的译文又翻一遍
ok("auto_copy: no re-translate storm (seq stable)", app.seq == seq0)

# ---- 3. 自动复制：关 → 剪贴板不动 ----
app.auto_copy_var.set(False)
app._save()
r.clipboard_clear()
r.clipboard_append("SENTINEL")
app.last_clip = "SENTINEL"
app._set_src("do not copy me")
app.translate_now()
pump(2.0, lambda: app.plain_result().startswith("译:"))
ok("auto_copy off: clipboard untouched", r.clipboard_get() == "SENTINEL")

# ---- 4. 朗读按钮：存在；Linux 上点只报状态，不崩 ----
ok("speak buttons exist", len(buttons_with("🔊 原文")) == 1 and len(buttons_with("🔊 译文")) == 1)
ok("copy source button exists", len(buttons_with("复制原文")) == 1)
app._set_src("hello speak")
app.pairs = [("hello speak", "你好朗读")]
app.render()
buttons_with("🔊 原文")[0].invoke()
ok("speak src on linux: windows-only status, no crash",
   app.status.cget("text") == "朗读只在 Windows 上可用")
buttons_with("🔊 译文")[0].invoke()
ok("speak dst on linux: windows-only status, no crash",
   app.status.cget("text") == "朗读只在 Windows 上可用")

# ---- 5. 气泡：点一下复制（250ms 后关），双击朗读且不关 ----
app2_ok = True
app.bubble.show((200, 200), "hello", "译:hello", lang="zh-CN")
app.root.update()
ok("bubble foot mentions double-click speak", "双击朗读" in app.bubble.foot.cget("text"))
app.bubble._dblclick()
app.root.update()
ok("bubble double-click speaks (linux: status) and stays open",
   app.status.cget("text") == "朗读只在 Windows 上可用" and app.bubble.alive())
app.bubble._click()
pump(0.5)
ok("bubble single click copies & closes", r.clipboard_get() == "译:hello"
   and not app.bubble.alive())

# ---- 6. 小窗口：点一下复制，双击朗读，右键关闭 ----
app.mini.show((200, 200), "hello", "译:hello", lang="zh-CN")
app.root.update()
ok("mini foot mentions double-click speak", "双击朗读" in app.mini.foot.cget("text"))
app.mini._click()
ok("mini single click copies, window stays", r.clipboard_get() == "译:hello" and app.mini.alive())
app.mini._dblclick()
ok("mini double-click speaks (linux: status)", app.status.cget("text") == "朗读只在 Windows 上可用")
app.mini.close()
ok("mini close works", not app.mini.alive())

# ---- 7. 历史窗口有「朗读译文」按钮 ----
app.open_history()
app.root.update()
hist_texts = [w.cget("text") for w in walk(app.hist_win) if w.winfo_class() == "TButton"]
ok("history has 朗读译文 button", "朗读译文" in hist_texts)
app.hist_win.withdraw()

# ---- 8. 快捷键保存：非法 / 重复不保存并恢复，合法保存并刷新显示 ----
errs = []
dt.messagebox.showerror = lambda *a, **k: errs.append(a)
app.hotkey_main_var.set("bogus")
ok("save bad hotkey rejected", app._save_hotkeys() is False and errs
   and app.hotkey_main_var.get() == "Ctrl+Alt+T")
errs.clear()
app.hotkey_main_var.set("Ctrl+Alt+D")     # 和指针取词重复
ok("save duplicate hotkey rejected", app._save_hotkeys() is False and errs
   and app.hotkey_main_var.get() == "Ctrl+Alt+T")
app.hotkey_main_var.set("Ctrl+Shift+T")
app.hotkey_pointer_var.set("Ctrl+Shift+D")
app.hotkey_shot_var.set("Ctrl+Shift+S")
ok("save valid hotkeys", app._save_hotkeys() is True)
cfg = json.load(open(dt.CONFIG_PATH))
ok("hotkeys saved to config", cfg["hotkey_main"] == "ctrl+shift+t"
   and cfg["hotkey_pointer"] == "ctrl+shift+d" and cfg["hotkey_shot"] == "ctrl+shift+s")
ok("about label follows new hotkeys", "Ctrl+Shift+T" in app.about_hotkey_label.cget("text"))
ok("tray snap follows new hotkeys", app._tray_snap.get("hotkey_main") == "Ctrl+Shift+T")

# ---- 9. 语速钳制 + 恢复默认 ----
app.tts_rate_var.set(99)
app._on_tts_rate()
ok("tts_rate clamped to 10", app.cfg["tts_rate"] == 10 and app.tts_rate_var.get() == 10)
app.tts_rate_var.set(-99)
app._on_tts_rate()
ok("tts_rate clamped to -10", app.cfg["tts_rate"] == -10)
dt.messagebox.askyesno = lambda *a, **k: True
app.auto_copy_var.set(True)
app.tts_rate_var.set(5)
app._on_tts_rate()
app.hotkey_main_var.set("Ctrl+Shift+Q")
app._save_hotkeys()
app._reset_settings()
cfg = json.load(open(dt.CONFIG_PATH))
ok("reset: auto_copy False", cfg["auto_copy"] is False and app.auto_copy_var.get() is False)
ok("reset: tts_rate 0", cfg["tts_rate"] == 0 and app.tts_rate_var.get() == 0)
ok("reset: hotkeys to defaults", cfg["hotkey_main"] == "ctrl+alt+t"
   and cfg["hotkey_pointer"] == "ctrl+alt+d" and cfg["hotkey_shot"] == "ctrl+alt+s"
   and app.hotkey_main_var.get() == "Ctrl+Alt+T")
ok("reset: hint shows defaults", "Ctrl+Alt+T" in app.hint.cget("text")
   or "Ctrl+Alt+T" in app.about_hotkey_label.cget("text"))

app.root.destroy()
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
