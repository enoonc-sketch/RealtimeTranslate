"""悬停取词 + 「跟随指针的小窗口」回归（2.15.8）。需 xvfb：xvfb-run -a python3 tests/test_hover_mini_v2158.py

症状：弹窗方式选「跟随指针的小窗口」时，悬停取词时灵时不灵——鼠标稍微挪一下又停在同一个词上，
小窗口就凭空消失。根因：取词截屏前小窗口先被藏起来，识别出「同一个词」被 HoverDedupe 拦下后
没人再把它显示出来，2 秒后它自己关了。另外每次 show() 都多起一条跟随循环（越叠越多）。
"""
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import history_store as hs
import desktop_translator as dt

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


app = dt.App()
app.root.update()
app.history = hs.HistoryStore(os.path.join(tempfile.mkdtemp(), "h.db"))
dt.translate = lambda text, sl, tl, smart, engine, cancelled=None: ("译:" + text, "en", "zh-CN")
dt.IS_WIN = True
dt.screen_bounds = lambda: (0, 0, 1920, 1080)
dt.cursor_is_ibeam_win = lambda: False
word = {"v": "hello"}
app._ocr_pick = lambda pos, scope, lang=None, bounds=None: (time.sleep(0.1), word["v"])[1]
app.popup_cb.set(dt.POPUP_NAMES["mini"])
app._on_popup_opt()
cur = {"p": (500, 400)}
app.root.winfo_pointerxy = lambda: cur["p"]
app.hover_var.set(True)
app.cfg["hover"] = True


def pump(sec):
    t = time.time()
    while time.time() - t < sec:
        app.root.update()
        app._poll()
        time.sleep(0.02)


def hover_at(pos, hold=0.95):
    cur["p"] = pos
    app._hover_check()          # 记下新位置
    pump(hold)
    app._hover_check()          # 停满 hover_ms，触发取词
    pump(0.6)


hover_at((500, 400))
ok("首次悬停：小窗口弹出并显示译文", app.mini.alive() and app.mini.win.winfo_viewable()
   and app.mini.body.cget("text") == "译:hello")

hover_at((510, 405))            # 挪 10px 再停在同一个词上 → 被去重
pump(dt.MiniWin.HIDE_TIMEOUT - 6.0 + 0.1 if dt.MiniWin.HIDE_TIMEOUT < 6 else 2.5)
ok("同一个词再悬停：小窗口还在（不会凭空消失）", app.mini.alive() and app.mini.win.winfo_viewable()
   and app.mini.hidden_at is None)

word["v"] = "world"
hover_at((700, 400))
ok("换一个词：小窗口换成新译文", app.mini.alive() and app.mini.body.cget("text") == "译:world")

# 跟随循环只留一条
fids = []
orig_after = app.root.after
app.root.after = lambda ms, fn=None, *a: (fids.append(fn), orig_after(ms, fn, *a))[1] if fn else orig_after(ms)
for i in range(5):
    app.mini.show((300 + i, 300), "h", "b")
pump(0.3)
app.root.after = orig_after
follow_calls = sum(1 for f in fids if getattr(f, "__name__", "") == "_follow")
ok("多次 show 后跟随循环不叠加（0.3s 内约 8 次调度，不是 40 次）", follow_calls < 20)

# 藏起来后没结果：超过 HIDE_TIMEOUT 才自己关；识别慢（>2 秒）时不被提前关掉
app.mini.show((300, 300), "h", "b")
app.mini.hide_for_capture()
app.mini.hidden_at = time.time() - 3.0
pump(0.2)
ok("藏起来 3 秒仍保留（旧版 2 秒就关，比 OCR 冷启动还短）", app.mini.alive())
app.mini.hidden_at = time.time() - (dt.MiniWin.HIDE_TIMEOUT + 1)
pump(0.2)
ok("藏起来超过 HIDE_TIMEOUT 且没结果：自己关掉", not app.mini.alive())

print("%d/%d" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
