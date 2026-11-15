"""v2.8 界面接线：粘贴图片翻译按钮、术语表/设置导入导出按钮、
_apply_cfg_to_ui、历史搜索框。需 xvfb。"""
import copy
import json
import os
import sys
import tempfile

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


tmp = tempfile.mkdtemp()
dt.CONFIG_PATH = os.path.join(tmp, "c.json")
dt.OLD_CONFIG_PATH = dt.CONFIG_PATH + ".old"
dt.HISTORY_PATH = os.path.join(tmp, "h.db")

app = dt.App()
app.root.update()
sw = app.settings_win

ok("main window has 粘贴图片翻译 button",
   any(t == "粘贴图片翻译" for t in texts(app.root)))
ok("settings general tab has 导出设置… / 导入设置…",
   {"导出设置…", "导入设置…"} <= set(texts(app.settings_tabs["general"])))
ok("settings translate tab has glossary 导入… / 导出…",
   "导入…" in texts(app.settings_tabs["translate"]) and
   "导出…" in texts(app.settings_tabs["translate"]))
ok("hotkey_clip var exists with default label",
   app.hotkey_clip_var.get() == "Ctrl+Shift+V")
ok("about label lists clip hotkey",
   "Ctrl+Shift+V" in app.about_hotkey_label.cget("text"))

# ---- _apply_cfg_to_ui：改一批值，界面与配置都要跟上 ----
cfg = copy.deepcopy(dt.DEFAULTS)
cfg.update({"top": False, "tl": "en", "engine": "Google", "dark_mode": True,
            "font_size": 14, "hotkey_clip": "ctrl+alt+v",
            "glossary": [["Maxum", "Maxum"]], "history_max": 500,
            "update_auto": False})
app._apply_cfg_to_ui(cfg)
app.root.update()
ok("apply: dark var on", app.dark_var.get() is True)
ok("apply: font size 14", app.font_size_var.get() == 14 and app.cfg["font_size"] == 14)
ok("apply: clip hotkey var", app.hotkey_clip_var.get() == "Ctrl+Alt+V")
ok("apply: glossary text", "Maxum = Maxum" in app.glossary_text.get("1.0", "end"))
ok("apply: tl combobox", app.tl.get() == dt.lang_name("en"))
ok("apply: history max", app.history.max_items == 500)
ok("apply: saved to config file",
   json.load(open(dt.CONFIG_PATH))["font_size"] == 14 and
   json.load(open(dt.CONFIG_PATH))["hotkey_clip"] == "ctrl+alt+v")
ok("apply: glossary active", dt.glossary.active() == [["Maxum", "Maxum"]])

# ---- 设置导出/导入 round-trip（经纯函数 + _apply_cfg_to_ui）----
import settings_io
blob = settings_io.export_settings(app.cfg)
cfg2, ignored, err = settings_io.import_settings(blob, dt.DEFAULTS)
ok("settings round-trip no error", err is None and ignored == 0)
ok("settings round-trip keeps clip hotkey", cfg2["hotkey_clip"] == "ctrl+alt+v")
ok("settings round-trip keeps glossary", cfg2["glossary"] == [["Maxum", "Maxum"]])
_, _, err2 = settings_io.import_settings("{not json", dt.DEFAULTS)
ok("settings import malformed -> error, no apply", err2 is not None)

# ---- 历史搜索框：筛 + 清空 ----
app.history.add("apple pie", "苹果派", "en", "zh-CN", "Google", "main")
app.history.add("banana bread", "香蕉面包", "en", "zh-CN", "Google", "main")
app.open_history()
app.root.update()
ok("history shows 2 rows", len(app.hist_tv.get_children()) == 2)
app.hist_q.set("apple")
app._hist_refresh()
ok("history search filters to 1", len(app.hist_tv.get_children()) == 1)
ok("history search shows apple row",
   "apple" in str(app.hist_tv.item(app.hist_tv.get_children()[0])["values"]))
app.hist_q.set("")
app._hist_refresh()
ok("history clear shows all again", len(app.hist_tv.get_children()) == 2)
ok("history has ✕ clear button", "✕" in texts(app.hist_win))

# ---- 粘贴图片翻译在 Linux 上只给提示，不崩 ----
app._translate_clipboard_image()
ok("clipboard image on Linux -> status message only",
   "只在 Windows 上可用" in app.status.cget("text"))

app.root.destroy()
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
