"""语音输入 stt_win：culture 映射、超时钳制、Linux 上不可用且不启动真识别。
不需要 xvfb。"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import stt_win

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


# ---- 1. culture 映射（与 tts_win 共用同一张表） ----
ok("culture zh-CN", stt_win.culture_for("zh-CN") == "zh-CN")
ok("culture en -> en-US", stt_win.culture_for("en") == "en-US")
ok("culture ja -> ja-JP", stt_win.culture_for("ja") == "ja-JP")
ok("culture unknown -> en-US", stt_win.culture_for("xx") == "en-US")

# ---- 2. 超时钳制 ----
ok("timeout 15 stays", stt_win.clamp_timeout(15) == 15)
ok("timeout 5 stays", stt_win.clamp_timeout(5) == 5)
ok("timeout 60 stays", stt_win.clamp_timeout(60) == 60)
ok("timeout 1 clamps to 5", stt_win.clamp_timeout(1) == 5)
ok("timeout 999 clamps to 60", stt_win.clamp_timeout(999) == 60)
ok("timeout garbage -> 15", stt_win.clamp_timeout("soon") == 15)

# ---- 3. Linux 上不可用，且绝不启动真识别 ----
ok("not available on linux", stt_win.is_available() is False)
ok("build_command None on linux", stt_win.build_command("/tmp/o.txt", "/tmp/s.ps1", "en") is None)
real_run = subprocess.run


def _boom(*a, **k):
    raise AssertionError("must not start real recognition on linux")


subprocess.run = _boom
try:
    ok("recognize on linux -> unavailable, no subprocess",
       stt_win.recognize("en") == ("unavailable", ""))
finally:
    subprocess.run = real_run

# ---- 4. 假装是 Windows：mock subprocess.run 走通一次流程 ----
real_is_win, real_find = stt_win.IS_WIN, stt_win._find_powershell
stt_win.IS_WIN = True
stt_win._find_powershell = lambda: "/fake/powershell.exe"
try:
    cmd = stt_win.build_command("/tmp/o.txt", "/tmp/s.ps1", "zh-CN", 15)
    ok("build_command has ps + files + culture + timeout",
       cmd is not None and cmd[0] == "/fake/powershell.exe"
       and "zh-CN" in cmd and "15" in cmd)

    class Done:
        returncode = 0
        stdout, stderr = b"", b""

    def fake_run(cmdline, **kw):
        # 模拟 PowerShell：把认到的文字写进 -OutFile 指定的临时文件
        out_i = cmdline.index("-OutFile") + 1
        with open(cmdline[out_i], "w", encoding="utf-8") as f:
            f.write("你好世界")
        assert kw.get("timeout", 0) >= 15
        return Done()

    subprocess.run = fake_run
    try:
        ok("recognize ok with mocked run", stt_win.recognize("zh-CN") == ("ok", "你好世界"))
    finally:
        subprocess.run = real_run

    class TimeoutProc:
        returncode = 2
        stdout, stderr = b"", b""

    subprocess.run = lambda *a, **k: TimeoutProc()
    try:
        ok("recognize timeout -> timeout", stt_win.recognize("en") == ("timeout", ""))
    finally:
        subprocess.run = real_run

    class FailProc:
        returncode = 1
        stdout, stderr = b"", "No microphone".encode()

    subprocess.run = lambda *a, **k: FailProc()
    try:
        st, tx = stt_win.recognize("en")
        ok("recognize error -> error + reason", st == "error" and "microphone" in tx)
    finally:
        subprocess.run = real_run
finally:
    stt_win.IS_WIN, stt_win._find_powershell = real_is_win, real_find

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
