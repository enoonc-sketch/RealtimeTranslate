"""OCR 调 PowerShell 时绝不能弹黑窗口（回归：悬停取词每次 OCR 都闪一个黑框）。

根因：ocr_win._run_ps 用 subprocess.run 直接起 powershell.exe，没传
CREATE_NO_WINDOW；TTS（tts_win）与语音输入（stt_win）早就有这个标志，
只有 OCR 漏了。悬停取词每停 0.8 秒就调一次 OCR，所以黑窗不停地闪。

测试用 mock 的 subprocess.run 断言 creationflags，不真起 PowerShell。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import ocr_win

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


class FakeProc:
    returncode = 0
    stdout = b"hello"
    stderr = b""


seen = {}


def fake_run(cmd, **kwargs):
    seen.clear()
    seen.update(kwargs)
    seen["cmd"] = cmd
    return FakeProc()


real_run = subprocess.run
subprocess.run = fake_run
try:
    # Windows 路径：必须带 CREATE_NO_WINDOW
    ocr_win.IS_WIN = True
    ocr_win.find_powershell = lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    ocr_win._script_path = lambda: os.path.join(os.path.dirname(HERE), "winocr.ps1")
    out, _ = ocr_win._run_ps("x.bmp")
    ok("ocr returns stdout", out == "hello")
    ok("creationflags is CREATE_NO_WINDOW (0x08000000)",
       seen.get("creationflags") == 0x08000000)
    ok("still captures output", seen.get("capture_output") is True)
    ok("powershell 5.1 via -File", "-File" in seen["cmd"])

    # 非 Windows：根本不启动进程，直接报 OcrError
    ocr_win.IS_WIN = False
    seen.clear()
    try:
        ocr_win._run_ps("x.bmp")
        ok("non-Windows raises OcrError", False)
    except ocr_win.OcrError:
        ok("non-Windows raises OcrError", True)
    ok("non-Windows never spawns powershell", "cmd" not in seen)
finally:
    subprocess.run = real_run

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
