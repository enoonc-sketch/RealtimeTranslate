"""悬停取词黑窗加固（回归：2.9.0）。

背景：2.6.0 给 ocr_win._run_ps 补了 CREATE_NO_WINDOW（0x08000000），
但用户 T 在真机上仍报“悬停取词老是弹黑窗”。T 装的是正常安装版
（可能是 2.6.0 也可能是 2.4.0，无法确定），所以两种可能都存在：
  (a) 他跑的还是 2.4.0（_run_ps 当时根本没带 creationflags）；
  (b) CREATE_NO_WINDOW 一个标志在他那台机器上没压住。
本轮的加固是 (b) 的对策：三处起子进程的地方（OCR / TTS / STT）
在 CREATE_NO_WINDOW 之外再补 STARTUPINFO（STARTF_USESHOWWINDOW +
SW_HIDE），双保险；同时把“每次 spawn 都带无窗口标志”钉死成测试。

测试用 mock 的 subprocess.run / Popen 断言 kwargs，不真起进程。
Linux 上没有 subprocess.STARTUPINFO / STARTF_USESHOWWINDOW /
SW_HIDE（只有 Windows 才有），测试先把假的注进去，跑完再还原。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import ocr_win
import stt_win
import tts_win

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


# ---- 假的 Windows STARTUPINFO（Linux 上 subprocess 没有这些） ----
class FakeStartupInfo:
    def __init__(self):
        self.dwFlags = 0
        self.wShowWindow = None


_MISSING = object()
_saved = {}
for _name, _val in (("STARTUPINFO", FakeStartupInfo),
                    ("STARTF_USESHOWWINDOW", 0x00000001),
                    ("SW_HIDE", 0)):
    _saved[_name] = getattr(subprocess, _name, _MISSING)
    setattr(subprocess, _name, _val)


def check_nowindow(name, kwargs):
    """断言一次 spawn 调用同时带了两道无窗口保险。"""
    ok(name + "：creationflags 是 CREATE_NO_WINDOW (0x08000000)",
       kwargs.get("creationflags") == 0x08000000)
    si = kwargs.get("startupinfo")
    ok(name + "：传了 STARTUPINFO", si is not None)
    if si is None:
        return
    ok(name + "：STARTUPINFO.dwFlags 含 STARTF_USESHOWWINDOW",
       bool(getattr(si, "dwFlags", 0) & 0x00000001))
    ok(name + "：STARTUPINFO.wShowWindow 是 SW_HIDE (0)",
       getattr(si, "wShowWindow", None) == 0)


class FakeProc:
    returncode = 0
    stdout = b"hello"
    stderr = b""


seen_run = {}
seen_popen = {}


def fake_run(cmd, **kwargs):
    seen_run.clear()
    seen_run.update(kwargs)
    seen_run["cmd"] = cmd
    return FakeProc()


class FakePopen:
    def __init__(self, cmd, **kwargs):
        seen_popen.clear()
        seen_popen.update(kwargs)
        seen_popen["cmd"] = cmd

    def poll(self):
        return None

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        pass

    def kill(self):
        pass


real_run = subprocess.run
real_popen = subprocess.Popen
real_ocr_win = ocr_win.IS_WIN
real_stt_win = stt_win.IS_WIN
real_tts_win = tts_win.IS_WIN
try:
    subprocess.run = fake_run
    subprocess.Popen = FakePopen

    # ---- 1. OCR：悬停取词唯一的子进程入口 ----
    ocr_win.IS_WIN = True
    ocr_win.find_powershell = lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    ocr_win._script_path = lambda: os.path.join(os.path.dirname(HERE), "winocr.ps1")
    out, _ = ocr_win._run_ps("x.bmp")
    ok("ocr returns stdout", out == "hello")
    check_nowindow("ocr _run_ps", seen_run)

    # ---- 2. TTS：朗读起 powershell（气泡双击朗读也会走这里） ----
    tts_win.IS_WIN = True
    tts_win._find_powershell = lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    ok("tts speak starts", tts_win.speak("hello", "en-US") is True)
    check_nowindow("tts speak Popen", seen_popen)
    tts_win.stop()

    # ---- 3. STT：语音输入起 powershell ----
    stt_win.IS_WIN = True
    stt_win._find_powershell = lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    st, _tx = stt_win.recognize("en-US", timeout=5)
    ok("stt recognize runs (empty result -> timeout)", st == "timeout")
    check_nowindow("stt recognize run", seen_run)

    # ---- 4. 非 Windows：三处都不启动进程 ----
    ocr_win.IS_WIN = False
    stt_win.IS_WIN = False
    tts_win.IS_WIN = False
    seen_run.clear()
    seen_popen.clear()
    try:
        ocr_win._run_ps("x.bmp")
        ok("non-Windows ocr raises OcrError", False)
    except ocr_win.OcrError:
        ok("non-Windows ocr raises OcrError", True)
    ok("non-Windows ocr never spawns", "cmd" not in seen_run)
    ok("non-Windows tts speak returns False", tts_win.speak("hello", "en-US") is False)
    ok("non-Windows tts never spawns", "cmd" not in seen_popen)
    st, _tx = stt_win.recognize("en-US", timeout=5)
    ok("non-Windows stt unavailable", st == "unavailable")
    ok("non-Windows stt never spawns", "cmd" not in seen_run)
finally:
    subprocess.run = real_run
    subprocess.Popen = real_popen
    ocr_win.IS_WIN = real_ocr_win
    stt_win.IS_WIN = real_stt_win
    tts_win.IS_WIN = real_tts_win
    for _name, _val in _saved.items():
        if _val is _MISSING:
            try:
                delattr(subprocess, _name)
            except Exception:
                pass
        else:
            setattr(subprocess, _name, _val)

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
