"""非 Windows 的 OCR / 截图后端（v2.13）。

Windows 用系统自带 OCR（ocr_win.py + winocr.ps1）。macOS / Linux 上没有同样的系统接口，
这里用 tesseract 命令行（brew install tesseract tesseract-lang / apt install tesseract-ocr
tesseract-ocr-chi-sim ...）识别，截图用系统自带的命令：
    macOS : screencapture -x -R x,y,w,h
    Linux : grim（Wayland）/ gnome-screenshot / scrot / ImageMagick import（X11）
只用标准库；没装 tesseract / 没有截图命令时 available() 为 False，调用方给出明确提示，不崩。
"""
import csv
import io
import os
import shutil
import subprocess
import sys
import tempfile

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

# 程序里的语言代码 → tesseract 语言包名
TESS_LANG = {
    "zh-CN": "chi_sim", "zh-TW": "chi_tra", "en": "eng", "ja": "jpn", "ko": "kor",
    "fr": "fra", "de": "deu", "es": "spa", "ru": "rus", "pt": "por", "it": "ita",
    "ar": "ara", "th": "tha", "vi": "vie", "id": "ind", "hi": "hin", "tr": "tur",
    "pl": "pol", "nl": "nld", "uk": "ukr", "sv": "swe", "he": "heb",
}


class BackendError(Exception):
    pass


def _no_window():
    return {}


# L-10：tesseract 的 TSV 输出限流（10 MB）—— 超过直接拒绝，不全读进内存。
MAX_TSV_BYTES = 10 << 20


def tesseract_path():
    """tesseract 可执行文件路径；没有返回 None。

    L-07：先试固定安装路径（不受 PATH 注入影响），再试 which（macOS 的 GUI
    程序 PATH 里常常没有 Homebrew 目录，所以 which 仍保留作兜底）。
    """
    for cand in ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract", "/usr/bin/tesseract",
                 "/snap/bin/tesseract"):
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return shutil.which("tesseract")


def installed_langs():
    exe = tesseract_path()
    if not exe:
        return []
    try:
        r = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=10)
        return [x.strip() for x in (r.stdout or "").splitlines()[1:] if x.strip()]
    except Exception:      # noqa: BLE001
        return []


def tess_lang_arg(code):
    """把程序语言代码换成 tesseract 的 -l 参数。auto / 没装对应语言包时：用已装的「中文 + 英文」组合。"""
    have = installed_langs()
    want = []
    if code and code != "auto":
        t = TESS_LANG.get(code)
        if t and (not have or t in have):
            want.append(t)
    if not want:
        for t in ("chi_sim", "eng"):
            if not have or t in have:
                want.append(t)
    if "eng" not in want and (not have or "eng" in have):
        want.append("eng")
    return "+".join(want) or "eng"


def available():
    return tesseract_path() is not None


def recognize(image_path, lang=None, timeout=60, psm=6):
    """识别一张图，返回和 winocr.ps1 -Json 同样结构的 dict：{"lines":[{"text","words":[{text,x,y,w,h}]}]}。"""
    exe = tesseract_path()
    if not exe:
        raise BackendError("没有找到 tesseract。请先安装：macOS 用 brew install tesseract tesseract-lang，"
                           "Linux 用 sudo apt install tesseract-ocr tesseract-ocr-chi-sim")
    cmd = [exe, os.path.abspath(image_path), "stdout", "-l", tess_lang_arg(lang),
           "--psm", str(psm), "tsv"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise BackendError("OCR 超时（%d 秒）" % timeout)
    except Exception as e:      # noqa: BLE001
        raise BackendError("启动 tesseract 失败：%s" % e)
    if r.returncode != 0:
        raise BackendError((r.stderr or b"").decode("utf-8", "replace")[-400:] or "tesseract 失败")
    # L-10：TSV 输出限流 —— 超过 10 MB 直接拒绝，不全读进内存。
    if len(r.stdout or b"") > MAX_TSV_BYTES:
        raise BackendError("OCR 输出过大（超过 %d MB），已拒绝" % (MAX_TSV_BYTES >> 20))
    return parse_tsv((r.stdout or b"").decode("utf-8", "replace"))


def parse_tsv(tsv):
    """tesseract 的 TSV 输出 → {"lines": [...]}。纯函数，可在任何系统上测试。"""
    lines, order = {}, []
    reader = csv.reader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
    header = None
    for row in reader:
        if not row:
            continue
        if header is None:
            header = row
            continue
        if len(row) < 12:
            continue
        try:
            level = int(row[0])
            key = (int(row[2]), int(row[3]), int(row[4]))
            left, top, w, h = int(row[6]), int(row[7]), int(row[8]), int(row[9])
            conf = float(row[10])
        except ValueError:
            continue
        text = row[11].strip() if len(row) > 11 else ""
        if level != 5 or not text or conf < 0:
            continue
        if key not in lines:
            lines[key] = []
            order.append(key)
        lines[key].append({"text": text, "x": left, "y": top, "w": w, "h": h})
    out = []
    for key in order:
        words = lines[key]
        out.append({"text": _join_words([w["text"] for w in words]), "words": words})
    return {"lines": out}


def _join_words(words):
    out = ""
    for w in words:
        if not out:
            out = w
            continue
        a, b = out[-1], w[0]
        cjk = lambda c: "\u3000" <= c <= "\u9fff" or "\uac00" <= c <= "\ud7af" or "\uff00" <= c <= "\uffef"  # noqa: E731
        out += w if (cjk(a) or cjk(b)) else " " + w
    return out


# ---------------------------------------------------------------- 截图
def _capture_cmds(x, y, w, h, path):
    if IS_MAC:
        return [["screencapture", "-x", "-R", "%d,%d,%d,%d" % (x, y, w, h), path]]
    geo = "%dx%d+%d+%d" % (w, h, x, y)
    return [
        ["grim", "-g", "%d,%d %dx%d" % (x, y, w, h), path],
        ["import", "-window", "root", "-crop", geo, "+repage", path],
        ["scrot", "-a", "%d,%d,%d,%d" % (x, y, w, h), "-o", path],
    ]


def capture_available():
    if IS_MAC:
        return shutil.which("screencapture") is not None
    return any(shutil.which(c[0]) for c in _capture_cmds(0, 0, 1, 1, "x.png"))


def capture_file(path, x, y, w, h):
    """截屏区域存成 PNG，返回 path。没有可用命令抛 BackendError。"""
    last = ""
    for cmd in _capture_cmds(int(x), int(y), int(w), int(h), path):
        if not shutil.which(cmd[0]):
            continue
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=15)
            if r.returncode == 0 and os.path.isfile(path) and os.path.getsize(path) > 0:
                return path
            last = (r.stderr or b"").decode("utf-8", "replace")[-200:]
        except Exception as e:      # noqa: BLE001
            last = str(e)
    raise BackendError("没有可用的截图命令（macOS 需要「屏幕录制」权限；Linux 请安装 grim / scrot / imagemagick）。%s" % last)
