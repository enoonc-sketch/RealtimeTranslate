"""翻译并替换原文：replace_decision 纯逻辑 + _do_replace 流程（mock 掉
Windows 句柄/粘贴）+ 热键 4 路由 + 托盘菜单项。需 xvfb。"""
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import desktop_translator as dt

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


# ---- 1. 纯逻辑 ----
ok("paste when same window", dt.replace_decision(True, True, False) == "paste")
ok("clipboard-only when window changed", dt.replace_decision(True, False, False) == "clipboard-only")
ok("terminal never pastes", dt.replace_decision(True, True, True) == "skip-terminal")
ok("non-windows unavailable", dt.replace_decision(False, True, False) == "unavailable")

# ---- 2. _do_replace：mock 句柄与粘贴 ----
tmp = tempfile.mkdtemp()
dt.DATA_DIR = os.path.join(tmp, "data")
dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.HISTORY_PATH = os.path.join(dt.DATA_DIR, "history.db")
dt.g_translate = lambda t, sl, tl: ("译:" + t[:20], "en")
app = dt.App()
r = app.root
app.root.update()
app.pairs = [("hello", "你好")]
app.render()

pastes, focuses = [], []
real_fg, real_term, real_focus, real_paste = (dt.foreground_window_win,
                                             dt.foreground_is_terminal_win,
                                             dt.focus_window_win, dt.send_paste_win)
real_is_win = dt.IS_WIN
dt.IS_WIN = True            # 模拟 Windows：句柄/粘贴本身已 mock，只测决策与流程
dt.focus_window_win = lambda h: focuses.append(h) or True
dt.send_paste_win = lambda: pastes.append(1)
try:
    # 前台窗口没变：粘贴
    dt.foreground_window_win = lambda: 111
    dt.foreground_is_terminal_win = lambda: False
    app._replace_hwnd = 111
    pastes.clear(); focuses.clear()
    app._do_replace()
    ok("same window -> paste sent", pastes == [1] and focuses == [111])
    ok("same window -> clipboard holds dst", r.clipboard_get() == "你好")
    ok("same window -> status 已替换", "已把选中文字替换为译文" in app.status.cget("text"))
    ok("same window -> last_clip guards watch", app.last_clip == "你好")
    # 前台窗口变了：不粘贴，只留剪贴板
    dt.foreground_window_win = lambda: 999
    pastes.clear(); focuses.clear()
    app._do_replace()
    ok("window changed -> no paste", pastes == [] and focuses == [])
    ok("window changed -> clipboard still holds dst", r.clipboard_get() == "你好")
    ok("window changed -> status explains", "前台窗口已变" in app.status.cget("text"))
    # 终端：不粘贴
    dt.foreground_window_win = lambda: 111
    dt.foreground_is_terminal_win = lambda: True
    pastes.clear()
    app._do_replace()
    ok("terminal -> no paste", pastes == [])
    ok("terminal -> status explains", "终端窗口" in app.status.cget("text"))
    # 句柄拿不到（0）：按窗口变了处理
    dt.foreground_is_terminal_win = lambda: False
    dt.foreground_window_win = lambda: 0
    app._replace_hwnd = 0
    pastes.clear()
    app._do_replace()
    ok("hwnd 0 -> no paste", pastes == [])
finally:
    dt.IS_WIN = real_is_win
    (dt.foreground_window_win, dt.foreground_is_terminal_win,
     dt.focus_window_win, dt.send_paste_win) = (real_fg, real_term, real_focus, real_paste)

# ---- 3. 非 Windows 上热键只报状态 ----
calls = []
app._on_replace_hotkey()
ok("non-windows replace -> status only, not grabbing",
   "只在 Windows 上可用" in app.status.cget("text") and not app.grabbing)

# ---- 4. 热键 4 路由到替换 ----
seen = []
app._on_replace_hotkey = lambda: seen.append("replace")
app._on_hotkey(4)
ok("hotkey 4 routes to replace", seen == ["replace"])
app._on_hotkey(3)  # 截图：非 Windows 只报状态，不崩
_st = app.status.cget("text")
ok("hotkey 3 still screenshot path (non-Windows: status only, no crash)",
   "只支持 Windows" in _st or "tesseract" in _st or "截图命令" in _st or app.shot_win is not None)

# ---- 5. 托盘菜单有替换项，快捷键文字跟随配置 ----
items = dt.tray_menu_items({"pointer": True, "hotkey_replace": "Ctrl+Shift+R"}, True)
by = {i.get("id"): i for i in items if i.get("id")}
ok("tray has replace item", "replace" in by)
ok("tray replace label follows config", "Ctrl+Shift+R" in by["replace"]["label"])
items = dt.tray_menu_items({"pointer": True}, True)
by = {i.get("id"): i for i in items if i.get("id")}
ok("tray replace label falls back to default", "Ctrl+Alt+R" in by["replace"]["label"])

# ---- 6. 替换快捷键可保存 ----
errs = []
dt.messagebox.showerror = lambda *a, **k: errs.append(a)
app.hotkey_replace_var.set("Ctrl+Shift+R")
ok("save replace hotkey", app._save_hotkeys() is True)
import json
ok("replace hotkey saved", json.load(open(dt.CONFIG_PATH))["hotkey_replace"] == "ctrl+shift+r")
ok("tray snap has replace label", app._tray_snap.get("hotkey_replace") == "Ctrl+Shift+R")
app.hotkey_replace_var.set("Ctrl+Alt+T")   # 和主窗口重复
ok("duplicate replace hotkey rejected", app._save_hotkeys() is False and errs)

app.root.destroy()
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
