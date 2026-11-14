"""朗读发音 tts_win：culture 映射、语速钳制、Linux 上不可用且不抛异常、
命令里绝不含用户文字。不需要 xvfb。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import tts_win

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


# ---- 1. culture 映射 ----
for code, want in (("zh-CN", "zh-CN"), ("zh-TW", "zh-TW"), ("en", "en-US"),
                   ("ja", "ja-JP"), ("ko", "ko-KR"), ("fr", "fr-FR"),
                   ("de", "de-DE"), ("es", "es-ES"), ("ru", "ru-RU"),
                   ("pt", "pt-PT"), ("it", "it-IT"), ("ar", "ar-SA"),
                   ("th", "th-TH"), ("vi", "vi-VN"), ("id", "id-ID"),
                   ("hi", "hi-IN"), ("tr", "tr-TR"), ("pl", "pl-PL"),
                   ("nl", "nl-NL"), ("uk", "uk-UA"), ("sv", "sv-SE"),
                   ("he", "he-IL")):
    ok("culture %s -> %s" % (code, want), tts_win.culture_for(code) == want)
ok("culture zh -> zh-CN", tts_win.culture_for("zh") == "zh-CN")
ok("culture zh_CN underscore -> zh-CN", tts_win.culture_for("zh_CN") == "zh-CN")
ok("culture unknown -> en-US", tts_win.culture_for("xx") == "en-US")
ok("culture empty -> en-US", tts_win.culture_for("") == "en-US")
ok("culture None -> en-US", tts_win.culture_for(None) == "en-US")

# ---- 2. 语速钳制 ----
ok("rate 0 stays", tts_win.clamp_rate(0) == 0)
ok("rate 10 stays", tts_win.clamp_rate(10) == 10)
ok("rate -10 stays", tts_win.clamp_rate(-10) == -10)
ok("rate 99 clamps to 10", tts_win.clamp_rate(99) == 10)
ok("rate -99 clamps to -10", tts_win.clamp_rate(-99) == -10)
ok("rate garbage -> 0", tts_win.clamp_rate("fast") == 0)
ok("rate None -> 0", tts_win.clamp_rate(None) == 0)

# ---- 3. Linux 上不可用，不抛异常 ----
ok("not available on linux", tts_win.is_available() is False)
ok("speak False on linux", tts_win.speak("hello", "en") is False)
ok("speak empty False", tts_win.speak("   ", "en") is False)
ok("stop safe when nothing speaking", (tts_win.stop() or True) and not tts_win.is_speaking())
ok("build_command None on linux", tts_win.build_command("/tmp/x.txt", "/tmp/x.ps1", "en") is None)

# ---- 4. 命令里绝不含用户文字（假装是 Windows，mock 掉 Popen） ----
real_is_win, real_find = tts_win.IS_WIN, tts_win._find_powershell
tts_win.IS_WIN = True
tts_win._find_powershell = lambda: "/fake/powershell.exe"
try:
    cmd = tts_win.build_command("/tmp/rt-tts-abc.txt", "/tmp/rt-tts-abc.ps1", "zh-CN", 3)
    ok("build_command has ps + files + culture + rate",
       cmd is not None and cmd[0] == "/fake/powershell.exe"
       and "/tmp/rt-tts-abc.txt" in cmd and "/tmp/rt-tts-abc.ps1" in cmd
       and "zh-CN" in cmd and "3" in cmd)
    evil = "hello\"; Remove-Item C:\\ -Recurse; $(whoami)"
    ok("user text not in command line", evil not in " ".join(cmd))

    import subprocess
    import threading
    seen = {}

    class FakeProc:
        """像真进程一样活着，直到 terminate/kill 才退出（wait 会阻塞等它）。"""

        def __init__(self, *a, **k):
            seen["args"] = a[0] if a else k.get("args")
            seen["kwargs"] = k
            self._done = threading.Event()

        def poll(self):
            return None if not self._done.is_set() else 0

        def wait(self, timeout=None):
            self._done.wait(timeout)
            return 0

        def terminate(self):
            self._done.set()

        def kill(self):
            self._done.set()

    real_popen = subprocess.Popen
    subprocess.Popen = FakeProc
    try:
        ok("speak returns True with mocked Popen", tts_win.speak(evil, "en", rate=99) is True)
        ok("Popen args contain no user text", evil not in " ".join(seen["args"]))
        ok("rate clamped in Popen args", "10" in seen["args"])
        ok("is_speaking while mocked proc alive", tts_win.is_speaking())
        # 第二次 speak 先停掉第一次
        first = tts_win._proc
        ok("second speak stops first", tts_win.speak("second", "en") is True
           and first.poll() == 0)
        tts_win.stop()
        ok("stop ends speaking", not tts_win.is_speaking())
    finally:
        subprocess.Popen = real_popen
finally:
    tts_win.IS_WIN, tts_win._find_powershell = real_is_win, real_find

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
