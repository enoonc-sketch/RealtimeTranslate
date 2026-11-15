"""深色外观：切换不崩、对比度达标、切回浅色恢复原样。需 xvfb。"""
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


ok("dark text contrast >= 4.5",
   dt.contrast_ratio(dt.THEME_DARK["text_fg"], dt.THEME_DARK["text_bg"]) >= 4.5)
ok("dark gray contrast >= 4.5",
   dt.contrast_ratio(dt.THEME_DARK["gray"], dt.THEME_DARK["text_bg"]) >= 4.5)
ok("dark bubble contrast >= 4.5",
   dt.contrast_ratio(dt.THEME_DARK["bubble_fg"], dt.THEME_DARK["bubble_bg"]) >= 4.5)
ok("light text contrast >= 4.5",
   dt.contrast_ratio(dt.THEME_LIGHT["text_fg"], dt.THEME_LIGHT["text_bg"]) >= 4.5)
ok("contrast of identical colours is 1",
   abs(dt.contrast_ratio("#ffffff", "#ffffff") - 1.0) < 0.01)
ok("theme_colors returns copies", dt.theme_colors(True) is not dt.THEME_DARK)

dt.DATA_DIR = tempfile.mkdtemp()
dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.HISTORY_PATH = os.path.join(dt.DATA_DIR, "history.db")
app = dt.App()
r = app.root


def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        r.update()
        time.sleep(0.02)


orig_src_bg = app.src.cget("background")
orig_src_fg = app.src.cget("foreground")
ok("light theme is the default", app.cfg.get("dark_mode", False) is False)

# 切到深色
app.dark_var.set(True)
app._on_dark_mode()
pump(0.2)
ok("dark: src bg is dark", app.src.cget("background") == dt.THEME_DARK["text_bg"])
ok("dark: src fg is light", app.src.cget("foreground") == dt.THEME_DARK["text_fg"])
ok("dark: src contrast >= 4.5",
   dt.contrast_ratio(app.src.cget("foreground"), app.src.cget("background")) >= 4.5)
ok("dark: dst contrast >= 4.5",
   dt.contrast_ratio(app.dst.cget("foreground"), app.dst.cget("background")) >= 4.5)
ok("dark: cfg saved", app.cfg.get("dark_mode") is True)

# 深色下气泡也能正常弹出（颜色跟主题走）
app.bubble.show((200, 200), "Hello", "你好")
r.update()  # 立即检查：_watch 250ms 后会因指针远离自动关掉气泡，是正常行为
ok("dark: bubble shows", app.bubble.alive())
ok("dark: bubble body readable",
   dt.contrast_ratio(app.bubble.body.cget("foreground"),
                     app.bubble.body.cget("background")) >= 4.5)
app.bubble.close()

# 切回浅色：颜色恢复成启动时的样子
app.dark_var.set(False)
app._on_dark_mode()
pump(0.2)
ok("light: src bg restored", app.src.cget("background") == orig_src_bg)
ok("light: src fg restored", app.src.cget("foreground") == orig_src_fg)
ok("light: cfg saved", app.cfg.get("dark_mode") is False)

# render() 在深色下不再把译文写成黑字
app.dark_var.set(True)
app._on_dark_mode()
app._set_src("Hello")
app.pairs = [("Hello", "你好")]
app.render()
ok("dark: render keeps light text", app.dst.cget("foreground") == dt.THEME_DARK["text_fg"])
app.dark_var.set(False)
app._on_dark_mode()

app.quit()
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
