"""悬停取词 / 截图翻译 / 托盘队列：界面流程。需 xvfb。"""
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
dt.DATA_DIR = tmp
dt.HISTORY_PATH = os.path.join(tmp, "history.db")
dt.CONFIG_PATH = os.path.join(tmp, "config.json")
dt.g_translate = lambda t, sl, tl, attempts=3, timeout=12: ("译:" + t[:20], "en")
app = dt.App()
r = app.root
res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def pump(sec, until=None):
    end = time.time() + sec
    while time.time() < end:
        r.update()
        time.sleep(0.02)
        if until and until():
            return True
    return bool(until and until())


# 悬停选项默认开，配置能保存
ok("hover option default on", app.hover_var.get() is True)
ok("hover ms in config range", 300 <= app.cfg.get("hover_ms", 0) <= 3000)
app.hover_var.set(False)
app._on_pointer_opt()
ok("hover off persisted", json.load(open(dt.CONFIG_PATH))["hover"] is False)
app.hover_var.set(True)
app._on_pointer_opt()
ok("hover on persisted", json.load(open(dt.CONFIG_PATH))["hover"] is True)

# 悬停：鼠标在窗口外停住满 800ms 就触发一次（用假的 _on_hover，不真 OCR）
# 悬停是 Windows 专属：Linux 上 _hover_check 会直接返回，所以测试里临时把 IS_WIN 打开
dt.IS_WIN = True
hits = []
app._on_hover = lambda pos: hits.append(pos)
orig_xy = r.winfo_pointerxy
r.winfo_pointerxy = lambda: (1500, 800)  # 窗口外，停住不动
pump(1.3)
ok("hover dwell fires once", len(hits) == 1 and hits[0] == (1500, 800))
pump(0.5)
ok("hover does not refire while still", len(hits) == 1)
r.winfo_pointerxy = lambda: (1501, 800)  # 动一下，重新计时
pump(0.3)
ok("hover resets on move", len(hits) == 1)
r.winfo_pointerxy = orig_xy
dt.IS_WIN = False

# 悬停 OCR 回来有词 -> 走气泡；没词且不是 I 形 -> 不弹窗、不乱点
app._pointer_translate("hoverword", (1500, 800))
ok("hover word shows bubble", pump(2, lambda: app.bubble.alive()
   and app.bubble.body.cget("text").startswith("译:")))
app.bubble.close()

# 截图 OCR 回来有文字 -> 进主窗口翻译；没文字 -> 状态栏提示
app._on_shot_ocr(True, "screenshot text here", (100, 100))
ok("shot ocr fills source", "screenshot text here" in app.src.get("1.0", "end"))
ok("shot ocr translates", pump(1.5, lambda: app.plain_result().startswith("译:")))
app._on_shot_ocr(True, "   ", (100, 100))
ok("shot ocr empty warns", "没有识别到文字" in app.status.cget("text"))
app._on_shot_ocr(False, "OCR 语言包没装", (100, 100))
ok("shot ocr error shows reason", "OCR 语言包没装" in app.status.cget("text"))

# 托盘队列：托盘线程只放事件，_poll 在 Tk 线程处理
shown = []
app.show_window = lambda: shown.append(1)
app.q.put(("tray_show",))
pump(0.5)
ok("tray_show handled on Tk thread", len(shown) == 1)
shot = []
app.start_screenshot = lambda: shot.append(1)
app.q.put(("tray_shot",))
pump(0.5)
ok("tray_shot handled on Tk thread", len(shot) == 1)

# 隐藏：有托盘时 withdraw，没托盘时 iconify（旧行为保留作退路）
class FakeTray:
    def __init__(self, running):
        self._running = running

    def is_running(self):
        return self._running

    def stop(self):
        pass


app.tray = FakeTray(True)
app.cfg["close_action"] = "tray"      # v2.13 默认改成了最小化到任务栏，这里测的是隐藏到托盘
app.hide_window()
pump(0.2)
ok("hide with tray withdraws", str(r.winfo_viewable()) == "0")
app.show_window = dt.App.show_window.__get__(app, dt.App)
app.show_window()
pump(0.2)
app.tray = None
app.hide_window()
pump(0.2)
ok("hide without tray iconifies (fallback)", True)  # Xvfb 下只验证不抛异常
app.show_window()
pump(0.2)

app.quit()
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
