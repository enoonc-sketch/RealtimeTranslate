"""朗读语音选择（v2.9.0 新增）。

tts_win.list_voices() 用 PowerShell 枚举 System.Speech 已安装的语音；
speak() / build_command() 多一个 voice 参数（语音名），PS 脚本里
优先 SelectVoice(名字)，失败回落到 SelectVoiceByCulture。
语音名只来自本机枚举出的列表或配置里的下拉选择；PS 脚本里
SelectVoice 失败也不抛错，只用默认语音读。

测试用 mock 的 subprocess.run / Popen，不真起 PowerShell。
Linux 上没有 subprocess.STARTUPINFO 等 Windows 专属名字，测试
先把假的注进去，跑完再还原。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import tts_win

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


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


class FakeProc:
    returncode = 0
    stdout = b""
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
real_is_win = tts_win.IS_WIN
try:
    subprocess.run = fake_run
    subprocess.Popen = FakePopen
    tts_win.IS_WIN = True
    tts_win._find_powershell = lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

    # ---- 1. list_voices：解析 PS 输出 ----
    FakeProc.returncode = 0
    FakeProc.stdout = ("Microsoft Huihui Desktop\tzh-CN\tFemale\n"
                       "Microsoft Zira Desktop\ten-US\tFemale\n").encode("utf-8")
    voices = tts_win.list_voices()
    ok("list_voices returns 2 voices", len(voices) == 2)
    ok("list_voices first voice",
       voices[0] == {"name": "Microsoft Huihui Desktop", "culture": "zh-CN", "gender": "Female"})
    ok("list_voices second voice culture",
       voices[1]["name"] == "Microsoft Zira Desktop" and voices[1]["culture"] == "en-US")
    ok("list_voices run hides window",
       seen_run.get("creationflags") == 0x08000000
       and seen_run.get("startupinfo") is not None)

    # 空输出 / 失败都返回 []，不抛错
    FakeProc.stdout = b""
    ok("list_voices empty output -> []", tts_win.list_voices() == [])
    FakeProc.stdout = b"not-a-voice-line\n"
    ok("list_voices garbage line skipped", tts_win.list_voices() == [])
    FakeProc.returncode = 1
    FakeProc.stdout = b"Microsoft Huihui Desktop\tzh-CN\tFemale\n"
    ok("list_voices nonzero exit -> []", tts_win.list_voices() == [])

    # ---- 2. build_command 带 voice ----
    FakeProc.returncode = 0
    cmd = tts_win.build_command("t.txt", "s.ps1", "zh-CN", rate=2,
                                voice="Microsoft Huihui Desktop")
    ok("build_command has -Voice + name",
       cmd is not None and "-Voice" in cmd
       and cmd[cmd.index("-Voice") + 1] == "Microsoft Huihui Desktop")
    cmd2 = tts_win.build_command("t.txt", "s.ps1", "zh-CN", rate=0, voice=None)
    ok("build_command voice=None passes empty -Voice",
       cmd2 is not None and "-Voice" in cmd2 and cmd2[cmd2.index("-Voice") + 1] == "")
    ok("build_command keeps -Culture", "-Culture" in cmd and "zh-CN" in cmd)

    # ---- 3. speak 把 voice 传进 Popen 命令 ----
    ok("speak with voice starts",
       tts_win.speak("hello", "en-US", voice="Microsoft Zira Desktop") is True)
    cmd3 = seen_popen.get("cmd") or []
    ok("speak Popen cmd carries -Voice + name",
       "-Voice" in cmd3 and cmd3[cmd3.index("-Voice") + 1] == "Microsoft Zira Desktop")
    ok("speak Popen hides window",
       seen_popen.get("creationflags") == 0x08000000
       and seen_popen.get("startupinfo") is not None)
    tts_win.stop()

    # ---- 4. PS 脚本：优先 SelectVoice，失败回落 culture ----
    ok("PS script tries SelectVoice first", "SelectVoice($Voice)" in tts_win._PS_SCRIPT)
    ok("PS script falls back to SelectVoiceByCulture",
       "SelectVoiceByCulture($Culture)" in tts_win._PS_SCRIPT)
    ok("PS script accepts -Voice param", "[string]$Voice" in tts_win._PS_SCRIPT)

    # ---- 5. 非 Windows：list_voices 为 []，speak 为 False ----
    tts_win.IS_WIN = False
    ok("non-Windows list_voices -> []", tts_win.list_voices() == [])
    ok("non-Windows speak -> False", tts_win.speak("hello", "en-US") is False)
    ok("non-Windows build_command -> None",
       tts_win.build_command("t.txt", "s.ps1", "en-US") is None)
finally:
    subprocess.run = real_run
    subprocess.Popen = real_popen
    tts_win.IS_WIN = real_is_win
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
