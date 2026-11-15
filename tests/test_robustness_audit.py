"""健壮性审计回归测试（v2.7 审计发现的问题）。

1. 所有调 PowerShell 的地方都必须带 CREATE_NO_WINDOW（OCR 漏过一次，不能再漏）。
2. worker 线程里不能碰 Tk 控件：悬停/截图 worker 用的语言与屏幕范围必须由
   Tk 线程读好传进去；_ocr_pick / _shot_worker / _shot_overlay_worker 在
   worker 线程里调 _codes() 就会立刻失败。
3. 后台线程静默死掉：网络检查 worker 崩了要让界面显示结论、写崩溃日志；
   离线预热 worker 崩了要写崩溃日志。
需 xvfb（第 2、3 部分要跑界面）。
"""
import os
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import desktop_translator as dt
import ocr_win
import stt_win
import tts_win

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


# ---- 1. CREATE_NO_WINDOW：三个 PowerShell 调用者 ----
class FakeProc:
    returncode = 0
    stdout = b"hi"
    stderr = b""


seen = {}


def fake_run(cmd, **kwargs):
    seen.clear()
    seen.update(kwargs)
    return FakeProc()


real_run = subprocess.run
subprocess.run = fake_run
try:
    ocr_win.IS_WIN = True
    ocr_win.find_powershell = lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    ocr_win._script_path = lambda: os.path.join(os.path.dirname(HERE), "winocr.ps1")
    ocr_win._run_ps("x.bmp")
    ok("ocr _run_ps passes CREATE_NO_WINDOW", seen.get("creationflags") == 0x08000000)

    stt_win.IS_WIN = True
    stt_win._find_powershell = lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    st, _ = stt_win.recognize("zh-CN")
    ok("stt recognize passes CREATE_NO_WINDOW", seen.get("creationflags") == 0x08000000)
finally:
    subprocess.run = real_run
    ocr_win.IS_WIN = False
    stt_win.IS_WIN = False


class FakePopen:
    def wait(self):
        return 0


seen_popen = {}


def fake_popen(cmd, **kwargs):
    seen_popen.clear()
    seen_popen.update(kwargs)
    return FakePopen()


real_popen = subprocess.Popen
subprocess.Popen = fake_popen
try:
    tts_win.IS_WIN = True
    tts_win._find_powershell = lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    tts_win.speak("hello", "en")
    ok("tts speak passes CREATE_NO_WINDOW", seen_popen.get("creationflags") == 0x08000000)
    tts_win.stop()
finally:
    subprocess.Popen = real_popen
    tts_win.IS_WIN = False

# ---- 2/3. 界面部分 ----
dt.DATA_DIR = tempfile.mkdtemp()
dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.HISTORY_PATH = os.path.join(dt.DATA_DIR, "history.db")
dt.CRASH_LOG = os.path.join(dt.DATA_DIR, "crash.log")
app = dt.App()
r = app.root


def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        r.update()
        time.sleep(0.02)


# 2a. _ocr_pick 在 worker 线程里绝不能调 _codes()
calls = []


def raising_codes():
    calls.append(1)
    raise AssertionError("_codes() called from worker thread")


orig_codes = app._codes
app._codes = raising_codes
ocr_win.ocr_available = lambda: True
import screen_win
orig_capture = screen_win.capture_file
screen_win.capture_file = lambda *a, **k: None
orig_words = ocr_win.ocr_words
ocr_win.ocr_words = lambda *a, **k: [{"text": "hi", "x": 190, "y": 90, "w": 20, "h": 12}]  # 2 倍放大后光标在 (200, 100) 附近
try:
    word = app._ocr_pick((100, 50), "word", "en", (0, 0, 1920, 1080))
    ok("_ocr_pick works without _codes()", word == "hi" and not calls)
finally:
    app._codes = orig_codes
    screen_win.capture_file = orig_capture
    ocr_win.ocr_words = orig_words

# 2b. _hover_worker 把 lang/bounds 传给 _ocr_pick，不在 worker 里读 Tk
seen_hover = {}


def fake_pick(pos, scope, lang=None, bounds=None):
    seen_hover.update(lang=lang, bounds=bounds)
    return "hello"


orig_pick = app._ocr_pick
app._ocr_pick = fake_pick
app._codes = raising_codes
calls.clear()
t = threading.Thread(target=app._hover_worker,
                     args=((100, 50), "word", "en", (0, 0, 1920, 1080)), daemon=True)
t.start()
t.join(5)
hover_msgs = []
while not app.q.empty():
    try:
        hover_msgs.append(app.q.get_nowait())
    except Exception:
        break
ok("_hover_worker passes lang/bounds through",
   seen_hover.get("lang") == "en" and seen_hover.get("bounds") == (0, 0, 1920, 1080))
ok("_hover_worker never calls _codes()", not calls)
ok("_hover_worker delivers hover_ocr",
   any(m[0] == "hover_ocr" and m[1] == "hello" for m in hover_msgs))
app._ocr_pick = orig_pick
app._codes = orig_codes

# 2c. _shot_worker / _shot_overlay_worker 在 worker 线程里不调 _codes()
app._codes = raising_codes
calls.clear()
screen_win.capture_file = lambda *a, **k: None
orig_ocr_image = ocr_win.ocr_image
ocr_win.ocr_image = lambda *a, **k: "shot text"
app.cfg["shot_mode"] = "main"
t = threading.Thread(target=app._shot_worker,
                     args=((0, 0, 100, 100), (0, 0), "en", "auto", "zh-CN", True, "Google"),
                     daemon=True)
t.start()
t.join(5)
msgs = []
while not app.q.empty():
    try:
        msgs.append(app.q.get_nowait())
    except Exception:
        break
ok("_shot_worker never calls _codes()", not calls)
ok("_shot_worker delivers shot_ocr", any(m[0] == "shot_ocr" for m in msgs))
screen_win.capture_file = orig_capture
ocr_win.ocr_image = orig_ocr_image
app._codes = orig_codes

# 3a. 网络检查 worker 崩了：界面要显示结论，不是一直「检测中」
import netcheck
orig_run_all = netcheck.run_all


def boom(*a, **k):
    raise RuntimeError("boom")


netcheck.run_all = boom
app.open_netcheck()          # 建网络检查窗口（里面调 _start_netcheck）
pump(1.5)
try:
    txt = app.net_txt.get("1.0", "end")
except Exception:
    txt = ""
ok("netcheck worker crash surfaces in UI", "检测本身出错" in txt)
ok("netcheck worker crash logged", os.path.exists(dt.CRASH_LOG) and "netcheck failed" in open(dt.CRASH_LOG, encoding="utf-8").read())
netcheck.run_all = orig_run_all

# 3b. 离线预热 worker 崩了：写崩溃日志
import offline_engine
orig_present = offline_engine.runtime_present
offline_engine.runtime_present = lambda: True
orig_route = dt.OFFLINE.route
orig_warmup = dt.OFFLINE.warmup
dt.OFFLINE.route = lambda *a, **k: ["p1"]
dt.OFFLINE.warmup = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("warmup boom"))
try:
    app.engine.set("离线")
    app.sl.set("英语")        # 显示名：_codes() 靠显示名反查代码；否则 sl 是 auto，会走 OFFLINE.packs（沙箱里为空）直接返回
    app.tl.set("中文")
except Exception:
    pass
app._warming = False
if os.path.exists(dt.CRASH_LOG):
    os.remove(dt.CRASH_LOG)
app._warmup()
time.sleep(1.0)
ok("warmup worker crash logged",
   os.path.exists(dt.CRASH_LOG) and "warmup failed" in open(dt.CRASH_LOG, encoding="utf-8").read())
dt.OFFLINE.route = orig_route
dt.OFFLINE.warmup = orig_warmup
offline_engine.runtime_present = orig_present

app.quit()
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
