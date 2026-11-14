"""高级设置：分类页、和主窗口共用变量、取词延迟、× 行为、恢复默认、托盘入口。需 xvfb。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import desktop_translator as dt

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def texts(w):
    out = []
    for x in walk(w):
        try:
            if "text" in x.keys():
                out.append(str(x.cget("text")))
        except Exception:
            pass
    return out


app = dt.App()
app.root.update()
sw = app.settings_win
ok("settings window exists, hidden at start", not sw.winfo_viewable())

# 分类页
tabs = [app.settings_nb.tab(i, "text") for i in range(app.settings_nb.index("end"))]
ok("tabs: 常规/翻译/取词/历史/托盘/离线与网络/快捷键与关于",
   tabs == ["常规", "翻译", "取词", "历史", "托盘", "离线与网络", "快捷键与关于"])
ok("取词 tab holds scope + hover wait", any(w is app.scope_cb for w in walk(app.settings_tabs["grab"])))
ok("翻译 tab has 合并断行", any("合并断行" in t for t in texts(app.settings_tabs["translate"])))
ok("离线与网络 tab has 网络检查 / 离线语言包…",
   {"网络检查", "离线语言包…"} <= set(texts(app.settings_tabs["offline"])))
ok("main window keeps a 高级设置… button", any(t == "高级设置…" for t in texts(app.root)))
ok("main window no longer has 范围 combobox", app.scope_cb.winfo_toplevel() is sw)
ok("main 离线语言包… button still on main window",
   any(t == "离线语言包…" for f in app.root.winfo_children() for t in texts(f)
       if f.winfo_toplevel() is app.root))

# 打开 / 关闭 / 选页
app.open_settings("grab")
app.root.update()
ok("open_settings shows window on requested tab", sw.winfo_viewable() and
   app.settings_nb.select() == str(app.settings_tabs["grab"]))
app.close_settings()
app.root.update()
ok("close_settings hides window", not sw.winfo_viewable())

# 悬停等待
app.hover_ms_var.set(1200); app._on_hover_ms()
ok("hover_ms saved", json.load(open(dt.CONFIG_PATH))["hover_ms"] == 1200 and app.cfg["hover_ms"] == 1200)
app.hover_ms_var.set(50); app._on_hover_ms()
ok("hover_ms clamped to 300", app.hover_ms_var.get() == 300 and app.cfg["hover_ms"] == 300)
app.hover_ms_var.set(99999); app._on_hover_ms()
ok("hover_ms clamped to 3000", app.cfg["hover_ms"] == 3000)

# 点 ×
quits = []
app.quit = lambda: quits.append(1)
class T:
    def is_running(self): return True
    def notify(self, *a, **k): return True
    def set_tooltip(self, t): return True
    def stop(self): pass
app.tray = T()
app.close_cb.set("隐藏到托盘"); app._save()
app._on_close()
ok("× with tray + 隐藏到托盘 -> hides, no quit", not quits and not app.root.winfo_viewable())
app.root.deiconify()
app.close_cb.set("直接退出"); app._save()
ok("close_action saved", json.load(open(dt.CONFIG_PATH))["close_action"] == "quit")
app._on_close()
ok("× with 直接退出 -> quits", quits == [1])
app.tray = None

# 托盘提示开关
app.tray = T()
n = []
app.tray.notify = lambda *a, **k: n.append(1)
app.root.deiconify(); app.cfg.pop("tray_tip_shown", None)
app.tray_tip_var.set(False); app._save()
app.hide_window()
ok("tray tip off -> no balloon", n == [])
app.root.deiconify(); app.tray_tip_var.set(True); app._save()
app.hide_window()
ok("tray tip on -> one balloon", n == [1])
app.tray = None
app.root.deiconify()

# 托盘菜单入口
app._on_tray_cmd("settings")
app.root.update()
ok("tray 'settings' opens window", sw.winfo_viewable())
app.close_settings()

# 恢复默认
dt.messagebox.askyesno = lambda *a, **k: True
app.top_var.set(False); app.smart_var.set(False); app.hover_var.set(False)
app.scope_cb.set("整段"); app.hover_ms_var.set(2000); app._on_hover_ms()
app.close_cb.set("直接退出"); app.tray_tip_var.set(False)
app._reset_settings()
d = dt.DEFAULTS
cfg = json.load(open(dt.CONFIG_PATH))
ok("reset: vars back to defaults", app.top_var.get() == d["top"] and app.smart_var.get() == d["smart"]
   and app.hover_var.get() == d["hover"] and app.scope_cb.get() == "单词")
ok("reset: saved to config", cfg["top"] == d["top"] and cfg["pointer_scope"] == "word"
   and cfg["hover_ms"] == 800 and cfg["close_action"] == "tray" and cfg["tray_tip"] is True)
dt.messagebox.askyesno = lambda *a, **k: False
app.top_var.set(False); app._on_top()
app._reset_settings()
ok("reset cancelled -> unchanged", app.top_var.get() is False)

# 主窗口和设置窗口共用变量：同一个变量绑了两处控件
ok("shared var: 窗口置顶 in main and in settings",
   sum(1 for w in walk(app.root) if "variable" in w.keys() and str(w.cget("variable")) == str(app.top_var)) >= 2)

# 配置校验：坏值回落
cfg = dt.App._load_cfg()
ok("cfg has close_action/tray_tip defaults", cfg["close_action"] in dt.CLOSE_NAMES and cfg["tray_tip"] in (True, False))

app.root.destroy()
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
