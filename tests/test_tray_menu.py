"""托盘菜单：菜单项生成 / 构建 / 命令分发（用假的 user32，Linux 上就能测）+ 主程序命令处理。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import tray_win32
import desktop_translator as dt

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def flat(items):
    for it in items:
        if it.get("sub"):
            yield from flat(it["sub"])
        else:
            yield it


# ---- 1. 菜单项 ----
snap = {"top": True, "watch": False, "pointer": True, "hover": False,
        "scope": "line", "auto_off": True, "autostart": False}
items = dt.tray_menu_items(snap, True)
ids = [i.get("id") for i in flat(items) if i.get("id")]
for need in ("show", "shot", "clip", "pointer", "hover", "scope:word", "scope:line", "scope:paragraph",
             "watch", "top", "auto_off", "autostart", "settings", "netcheck", "packs", "quit"):
    ok("menu has " + need, need in ids)
by = {i["id"]: i for i in flat(items) if i.get("id")}
ok("checked reflects snapshot", by["top"]["checked"] and not by["watch"]["checked"] and not by["hover"]["checked"])
ok("scope radio: only current checked", [k for k in ("word", "line", "paragraph") if by["scope:" + k]["checked"]] == ["line"])
ok("show is default item", by["show"].get("default") is True)
ok("no autostart item off Windows", "autostart" not in [i.get("id") for i in dt.tray_menu_items(snap, False)])
ok("tooltip short & has state", len(dt.tray_tooltip(snap)) < 127 and "整行" in dt.tray_tooltip(snap))

# ---- 2. 构建 + 分发（假 user32） ----
class FakeUser32:
    def __init__(self, pick):
        self.pick, self.log, self.n = pick, [], 100

    def CreatePopupMenu(self):
        self.n += 1
        return self.n

    def AppendMenuW(self, h, flags, ident, label):
        self.log.append((h, flags, ident, label))
        return 1

    def SetMenuDefaultItem(self, *a):
        self.log.append(("default",) + a)

    def GetCursorPos(self, ref):
        return True

    def SetForegroundWindow(self, h):
        return 1

    def TrackPopupMenu(self, h, flags, x, y, r, hwnd, rc):
        # 选第 pick 个「命令项」（不是子菜单 / 分隔线）
        cmds = [e[2] for e in self.log if len(e) == 4 and not (e[1] & (tray_win32._MF_POPUP | tray_win32._MF_SEPARATOR))]
        return cmds[self.pick]

    def PostMessageW(self, *a):
        return 1

    def DestroyMenu(self, h):
        self.log.append(("destroy", h))


got, shown = [], []
tray = tray_win32.TrayIcon(
    "x", "t", on_show=lambda: shown.append("show"), on_screenshot=lambda: shown.append("shot"),
    on_quit=lambda: shown.append("quit"),
    menu_provider=lambda: dt.tray_menu_items(snap, True), on_command=got.append)
tray._hwnd = 1
u = FakeUser32(pick=0)
tray._show_menu(u)
ok("menu built with a popup submenu", any(e[1] & tray_win32._MF_POPUP for e in u.log if len(e) == 4))
ok("checked flag set on checked items", any((e[1] & tray_win32._MF_CHECKED) and e[3] == "窗口置顶" for e in u.log if len(e) == 4))
ok("default item set", any(e[0] == "default" for e in u.log))
ok("menu destroyed", any(e[0] == "destroy" for e in u.log))
ok("pick 'show' -> on_show", shown == ["show"])

labels = [e[3] for e in u.log if len(e) == 4 and not (e[1] & (tray_win32._MF_POPUP | tray_win32._MF_SEPARATOR))]
for label, expect in (("监听剪贴板", "watch"), ("整段", "scope:paragraph"), ("翻译剪贴板内容(&V)", "clip")):
    got.clear()
    idx = labels.index(label)
    tray._show_menu(FakeUser32(pick=idx))
    ok("pick %s -> on_command(%s)" % (label, expect), got == [expect])
shown.clear()
tray._show_menu(FakeUser32(pick=len(labels) - 1))
ok("pick quit -> on_quit", shown == ["quit"])

# provider 抛异常 -> 退回默认菜单，不崩
bad = tray_win32.TrayIcon("x", "t", menu_provider=lambda: 1 / 0)
bad._hwnd = 1
u2 = FakeUser32(pick=0)
bad._show_menu(u2)
ok("provider error falls back to default menu", any(e[3] == "显示主窗口(&S)" for e in u2.log if len(e) == 4))

# ---- 3. 主程序命令（真 App） ----
app = dt.App()
app.root.update()
app._refresh_tray_state()
ok("snapshot filled", set(app._tray_snap) >= {"top", "watch", "pointer", "hover", "scope", "auto_off"})
before = app.hover_var.get()
app._on_tray_cmd("hover")
ok("tray hover toggles var", app.hover_var.get() == (not before))
import json
ok("tray hover persisted", json.load(open(dt.CONFIG_PATH))["hover"] == (not before))
app._on_tray_cmd("scope:paragraph")
ok("tray scope sets combobox + cfg", app.scope_cb.get() == "整段" and json.load(open(dt.CONFIG_PATH))["pointer_scope"] == "paragraph")
ok("snapshot follows", app._tray_snap["scope"] == "paragraph" and app._tray_snap["hover"] == (not before))
b = app.pointer_var.get()
app._on_tray_cmd("pointer")
ok("tray pointer toggles", app.pointer_var.get() == (not b))
t = app.top_var.get()
app._on_tray_cmd("top")
ok("tray top toggles", app.top_var.get() == (not t))
app._get_clip = lambda: "hello clip"
app.translate_now = lambda: shown.append("translate")
shown.clear()
app._on_tray_cmd("clip")
ok("tray clip -> source box + translate", app.src.get("1.0", "end").strip() == "hello clip" and shown == ["translate"])
app._on_tray_cmd("unknown-cmd")
ok("unknown command ignored", True)

# 第一次隐藏弹气泡，只弹一次
class FakeTray:
    def __init__(self): self.n = []
    def is_running(self): return True
    def notify(self, *a, **k): self.n.append(a); return True
    def set_tooltip(self, t): return True
    def stop(self): pass
app.tray = FakeTray()
app.cfg.pop("tray_tip_shown", None)
app.hide_window()
app.root.deiconify()
app.hide_window()
ok("hide-to-tray balloon shown exactly once", len(app.tray.n) == 1 and app.cfg["tray_tip_shown"] is True)
app.tray = None
app.root.destroy()
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
