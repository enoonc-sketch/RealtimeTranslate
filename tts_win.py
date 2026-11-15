"""朗读发音（TTS）— 只用 Windows 自带的 System.Speech，不装任何库。

做法：Python 只负责把要读的文字写进一个 UTF-8 临时文件，
朗读交给 Windows PowerShell 5.1（powershell.exe）里的固定脚本
（见 _PS_SCRIPT）：脚本从临时文件读文字，用 System.Speech
的 SpeechSynthesizer 按指定 culture 朗读。用户文字永远不拼进
命令行（防注入：文字里哪怕有引号、分号、$() 也只当成文件内容）。

非 Windows 上 import 安全：is_available() 为 False，speak() 直接
返回 False，绝不抛异常、不启动任何进程。

注意：如果系统里没有该语言的语音（设置 → 语言 → 添加语言），
System.Speech 会用默认语音朗读（可能读不准），或 SelectVoiceByCulture
抛错时 speak() 返回 False；程序只在状态栏明说失败，不崩。
"""

import os
import subprocess
import sys
import tempfile
import threading

IS_WIN = sys.platform.startswith("win")

# 语言代码 → Windows 语音 culture（System.Speech 用 culture 挑语音）
CULTURES = {
    "zh-CN": "zh-CN", "zh-TW": "zh-TW", "en": "en-US", "ja": "ja-JP",
    "ko": "ko-KR", "fr": "fr-FR", "de": "de-DE", "es": "es-ES",
    "ru": "ru-RU", "pt": "pt-PT", "it": "it-IT", "ar": "ar-SA",
    "th": "th-TH", "vi": "vi-VN", "id": "id-ID", "hi": "hi-IN",
    "tr": "tr-TR", "pl": "pl-PL", "nl": "nl-NL", "uk": "uk-UA",
    "sv": "sv-SE", "he": "he-IL",
}

RATE_MIN, RATE_MAX = -10, 10


def clamp_rate(rate):
    """语速钳制到 -10..10（System.Speech 的 Rate 取值范围）；坏值回 0。"""
    try:
        return max(RATE_MIN, min(int(rate), RATE_MAX))
    except Exception:
        return 0


def culture_for(lang_code):
    """语言代码 → culture：先精确匹配，再按主语言匹配，都没有回 en-US。"""
    code = str(lang_code or "").strip().replace("_", "-")
    if code in CULTURES:
        return CULTURES[code]
    base = code.split("-")[0].lower()
    if base == "zh":
        return "zh-CN"          # 裸 "zh" 默认简体中文
    if base in CULTURES:
        return CULTURES[base]
    return "en-US"


def is_available():
    """本机能不能朗读：只有 Windows 才行（需要 powershell.exe）。"""
    if not IS_WIN:
        return False
    return _find_powershell() is not None


def _find_powershell():
    if not IS_WIN:
        return None
    system_root = os.environ.get("SystemRoot") or r"C:\Windows"
    cand = os.path.join(system_root, "System32", "WindowsPowerShell",
                        "v1.0", "powershell.exe")
    if os.path.isfile(cand):
        return cand
    import shutil
    return shutil.which("powershell")


# 固定朗读脚本：只从 -TextFile 读文字，命令行里没有任何用户文字。
# 参数：-TextFile 文字文件（UTF-8）、-Culture 语音 culture、-Rate 语速、
#   -Voice 语音名（v2.9：指定了就优先按名字选语音，选不到回落到 culture）。
# 枚举已安装语音的脚本：每行「名字<TAB>culture<TAB>性别」。
_LIST_VOICES_SCRIPT = r"""Add-Type -AssemblyName System.Speech
$sp = New-Object System.Speech.Synthesis.SpeechSynthesizer
foreach ($v in $sp.GetInstalledVoices()) {
  $i = $v.VoiceInfo
  "$($i.Name)`t$($i.Culture)`t$($i.Gender)"
}
"""


def list_voices(timeout=15):
    """列出 Windows 已安装的朗读语音（System.Speech）。

    返回 [{"name": 语音名, "culture": "zh-CN", "gender": "Female"}, ...]。
    非 Windows / 没有语音 / 枚举失败都返回 []，绝不抛异常。
    """
    if not IS_WIN:
        return []
    ps = _find_powershell()
    if not ps:
        return []
    try:
        script_path = _write_temp(_LIST_VOICES_SCRIPT, ".ps1")
    except Exception:
        return []
    try:
        cmd = [ps, "-NoProfile", "-ExecutionPolicy", "Bypass",
               "-File", os.path.abspath(script_path)]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                                  **_no_window_kwargs())
        except Exception:
            return []
        if proc.returncode != 0:
            return []
        out = (proc.stdout or b"").decode("utf-8", errors="replace")
        voices = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0].strip():
                voices.append({"name": parts[0].strip(),
                               "culture": parts[1].strip(),
                               "gender": parts[2].strip() if len(parts) > 2 else ""})
        return voices
    finally:
        _cleanup_files([script_path])


_PS_SCRIPT = r"""param([string]$TextFile, [string]$Culture, [int]$Rate, [string]$Voice)
$text = [System.IO.File]::ReadAllText($TextFile, [System.Text.Encoding]::UTF8)
if (-not $text.Trim()) { exit 0 }
Add-Type -AssemblyName System.Speech
$sp = New-Object System.Speech.Synthesis.SpeechSynthesizer
if ($Voice) { try { $sp.SelectVoice($Voice) } catch { try { $sp.SelectVoiceByCulture($Culture) } catch { } } }
else { try { $sp.SelectVoiceByCulture($Culture) } catch { } }
$sp.Rate = $Rate
$sp.Speak($text)
"""


def _no_window_kwargs():
    """起子进程时不弹黑窗：CREATE_NO_WINDOW + STARTUPINFO 藏窗口，双保险。

    只有 CREATE_NO_WINDOW 时个别机器仍会闪黑窗（2.6.0 修完用户真机仍报），
    再补 STARTUPINFO（STARTF_USESHOWWINDOW + SW_HIDE）压住。
    非 Windows 返回 {}；Linux 上没有 subprocess.STARTUPINFO 时只给
    creationflags（POSIX 下这两个参数都被忽略，不影响运行）。
    """
    if not IS_WIN:
        return {}
    kw = {"creationflags": 0x08000000}  # CREATE_NO_WINDOW
    try:
        si_cls = getattr(subprocess, "STARTUPINFO", None)
        if si_cls is not None:
            si = si_cls()
            si.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
            si.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
            kw["startupinfo"] = si
    except Exception:
        pass
    return kw


def build_command(text_file, script_file, lang_code, rate=0, voice=None):
    """拼出朗读命令（纯函数，便于测试）：命令里只有两个临时文件路径、
    culture、语速、语音名，绝不含用户文字。非 Windows 返回 None。"""
    ps = _find_powershell()
    if not IS_WIN or not ps:
        return None
    return [ps, "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", os.path.abspath(script_file),
            "-TextFile", os.path.abspath(text_file),
            "-Culture", culture_for(lang_code), "-Rate", str(clamp_rate(rate)),
            "-Voice", voice or ""]


def _write_temp(text, suffix):
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="rt-tts-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


_lock = threading.Lock()
_proc = None            # 正在朗读的 powershell 进程（同一时间只读一个）
_files = []             # 本次朗读的临时文件（读完即删）


def _cleanup_files(paths):
    for p in paths:
        try:
            os.remove(p)
        except Exception:
            pass


def is_speaking():
    """当前是否正在朗读。"""
    with _lock:
        return _proc is not None and _proc.poll() is None


def stop():
    """停掉正在进行的朗读（没在读时什么也不做，不抛异常）。"""
    global _proc, _files
    with _lock:
        proc, files = _proc, _files
        _proc, _files = None, []
    if proc is not None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        except Exception:
            pass
    _cleanup_files(files)


def speak(text, lang_code, rate=0, voice=None):
    """朗读 text（非阻塞：另起 powershell 进程，立刻返回 True）。

    voice 是 Windows 已安装语音的名字（v2.9；None/空串 = 系统默认语音）。
    再调一次 speak() 会先停掉上一次。失败（非 Windows / 没文字 /
    起不来进程）返回 False，绝不向界面抛异常。
    """
    global _proc, _files
    if not IS_WIN or not (text or "").strip():
        return False
    ps = _find_powershell()
    if not ps:
        return False
    stop()                       # 同一时间只读一个：新朗读先停旧的
    try:
        txt_path = _write_temp(text, ".txt")
    except Exception:
        return False
    # 脚本也写进临时文件：命令行里只有两个文件路径 + culture + 语速。
    try:
        ps_path = _write_temp(_PS_SCRIPT, ".ps1")
    except Exception:
        _cleanup_files([txt_path])
        return False
    cmd = build_command(txt_path, ps_path, lang_code, rate, voice=voice)
    if cmd is None:
        _cleanup_files([txt_path, ps_path])
        return False
    try:
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        kwargs.update(_no_window_kwargs())       # 不弹黑窗（双保险，见 _no_window_kwargs）
        proc = subprocess.Popen(cmd, **kwargs)
    except Exception:
        _cleanup_files([txt_path, ps_path])
        return False
    with _lock:
        _proc, _files = proc, [txt_path, ps_path]
    # 读完（或被 stop）后由 _reap 线程删临时文件：进程退出前文件不能删。
    threading.Thread(target=_reap, args=(proc, [txt_path, ps_path]), daemon=True).start()
    return True


def _reap(proc, paths):
    try:
        proc.wait()
    except Exception:
        pass
    with _lock:
        global _proc, _files
        if _proc is proc:
            _proc, _files = None, []
    _cleanup_files(paths)
