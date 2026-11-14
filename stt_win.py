"""语音输入（STT）— 只用 Windows 自带的 System.Speech，不装任何库。

做法：Python 只负责起一个 PowerShell 5.1 进程，识别交给
System.Speech 的 SpeechRecognitionEngine + DictationGrammar
（系统自带语音识别）；认到的文字由 PowerShell 写进一个 UTF-8
临时文件，Python 再读回来。语音内容绝不拼进命令行。

15 秒超时：15 秒内没听到说话就停（Recognize 带超时参数）。
没麦克风 / 识别失败 / 超时都只返回状态，不抛异常。

非 Windows 上 import 安全：is_available() 为 False，
recognize() 直接返回 ("unavailable", "")。
"""

import os
import subprocess
import sys
import tempfile

IS_WIN = sys.platform.startswith("win")

try:
    from tts_win import culture_for
except Exception:      # noqa: BLE001  tts_win 缺失时用自己的映射
    _CULTURES = {"zh-CN": "zh-CN", "zh-TW": "zh-TW", "en": "en-US",
                 "ja": "ja-JP", "ko": "ko-KR", "fr": "fr-FR", "de": "de-DE",
                 "es": "es-ES", "ru": "ru-RU"}

    def culture_for(lang_code):
        code = str(lang_code or "").strip().replace("_", "-")
        if code in _CULTURES:
            return _CULTURES[code]
        return _CULTURES.get(code.split("-")[0].lower(), "en-US")

TIMEOUT_MIN, TIMEOUT_MAX = 5, 60
DEFAULT_TIMEOUT = 15


def clamp_timeout(seconds):
    """识别超时钳制到 5~60 秒；坏值回 15 秒。"""
    try:
        return max(TIMEOUT_MIN, min(int(seconds), TIMEOUT_MAX))
    except Exception:
        return DEFAULT_TIMEOUT


def is_available():
    """本机能不能语音输入：只有 Windows 才行（需要 powershell.exe）。"""
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


# 固定识别脚本：只把结果写进 -OutFile，命令行里没有任何语音内容。
# 退出码：0 认到了、2 超时（15 秒内没听到说话）、1 其他失败（没麦克风等）。
_PS_SCRIPT = r"""param([string]$OutFile, [string]$Culture, [int]$TimeoutSec)
Add-Type -AssemblyName System.Speech
try {
  $rec = New-Object System.Speech.Recognition.SpeechRecognitionEngine($Culture)
  $rec.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
  $rec.SetInputToDefaultAudioDevice()
  $r = $rec.Recognize([TimeSpan]::FromSeconds($TimeoutSec))
  if ($null -eq $r -or -not $r.Text.Trim()) { exit 2 }
  [System.IO.File]::WriteAllText($OutFile, $r.Text, [System.Text.Encoding]::UTF8)
  exit 0
} catch {
  [Console]::Error.WriteLine($_.Exception.Message)
  exit 1
}
"""


def build_command(out_file, script_file, lang_code, timeout=DEFAULT_TIMEOUT):
    """拼出识别命令（纯函数，便于测试）：命令里只有两个临时文件路径、
    culture、超时秒数。非 Windows 返回 None。"""
    ps = _find_powershell()
    if not IS_WIN or not ps:
        return None
    return [ps, "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", os.path.abspath(script_file),
            "-OutFile", os.path.abspath(out_file),
            "-Culture", culture_for(lang_code),
            "-TimeoutSec", str(clamp_timeout(timeout))]


def recognize(lang_code, timeout=DEFAULT_TIMEOUT):
    """听一次（阻塞，最多等 timeout 秒），返回 (status, text)。

    status："ok"（text 是认到的文字）、"timeout"（超时没听到）、
    "unavailable"（非 Windows / 没 powershell）、"error"（没麦克风等，
    text 里是原因）。绝不抛异常。
    """
    timeout = clamp_timeout(timeout)
    if not IS_WIN:
        return "unavailable", ""
    ps = _find_powershell()
    if not ps:
        return "unavailable", ""
    out_fd, out_path = tempfile.mkstemp(suffix=".txt", prefix="rt-stt-")
    os.close(out_fd)
    ps_fd, ps_path = tempfile.mkstemp(suffix=".ps1", prefix="rt-stt-")
    try:
        with os.fdopen(ps_fd, "w", encoding="utf-8") as f:
            f.write(_PS_SCRIPT)
        cmd = build_command(out_path, ps_path, lang_code, timeout)
        if cmd is None:
            return "unavailable", ""
        kwargs = {"capture_output": True, "timeout": timeout + 10}
        if IS_WIN:
            kwargs["creationflags"] = 0x08000000       # CREATE_NO_WINDOW：不弹黑窗
        try:
            proc = subprocess.run(cmd, **kwargs)
        except subprocess.TimeoutExpired:
            return "timeout", ""
        except Exception as e:      # noqa: BLE001
            return "error", str(e)[:200]
        if proc.returncode == 0:
            try:
                with open(out_path, "r", encoding="utf-8") as f:
                    text = f.read().strip()
            except Exception:
                text = ""
            return ("ok", text) if text else ("timeout", "")
        if proc.returncode == 2:
            return "timeout", ""
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        return "error", err[-200:] or "语音识别失败"
    finally:
        for p in (out_path, ps_path):
            try:
                os.remove(p)
            except Exception:
                pass
