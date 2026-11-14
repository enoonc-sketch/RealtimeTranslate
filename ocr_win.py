"""Windows 自带 OCR — 调系统内置的 Windows.Media.Ocr，不用装任何库。

做法：Python 只负责截图存 BMP，识别交给 Windows PowerShell 5.1
（powershell.exe）里的 winocr.ps1（同目录）。WinRT 是异步接口，
PowerShell 里用 AsTask/Await 等它完成——这是从 Python 调系统 OCR
的常规做法，PowerShell 7（pwsh）不支持 WinRT，所以必须用 5.1。

要求：Windows 10+，且装了对应语言的 OCR 语言包
（设置 → 语言 → OCR，或 Get-WindowsCapability -Online 查
Language.OCR*）。没装会报 OcrError，里面写明原因。

非 Windows 上 import 安全，ocr_image 会直接抛 OcrError。
"""

import json
import os
import shutil
import subprocess
import sys

IS_WIN = sys.platform.startswith("win")


class OcrError(Exception):
    pass


def _script_path():
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "winocr.ps1")


def find_powershell():
    """Windows PowerShell 5.1 的完整路径；找不到返回 None。"""
    if not IS_WIN:
        return None
    system_root = os.environ.get("SystemRoot") or r"C:\Windows"
    cand = os.path.join(system_root, "System32", "WindowsPowerShell",
                        "v1.0", "powershell.exe")
    if os.path.isfile(cand):
        return cand
    return shutil.which("powershell")


def ocr_available():
    return IS_WIN and find_powershell() is not None \
        and os.path.isfile(_script_path())


def _run_ps(image_path, lang=None, want_json=False, timeout=60):
    ps = find_powershell()
    if not IS_WIN or not ps:
        raise OcrError("截图 OCR 只支持 Windows，且需要 Windows PowerShell 5.1")
    script = _script_path()
    if not os.path.isfile(script):
        raise OcrError("找不到 winocr.ps1（打包时漏了该文件）")
    cmd = [ps, "-NoProfile", "-ExecutionPolicy", "Bypass",
           "-File", script, "-Path", os.path.abspath(image_path)]
    if lang:
        cmd += ["-Language", lang]
    if want_json:
        cmd += ["-Json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise OcrError("OCR 超时（%d 秒），图片可能太大或 OCR 卡住了" % timeout)
    except Exception as e:
        raise OcrError("启动 PowerShell OCR 失败：%s" % e)
    out = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        raise OcrError(err[-500:] or "OCR 失败（退出码 %d）" % proc.returncode)
    return out, err


def ocr_image(image_path, lang=None, timeout=60):
    """识别一张图片，返回按行拼好的文字（没认出返回空串）。"""
    out, _ = _run_ps(image_path, lang=lang, timeout=timeout)
    return out


def ocr_words(image_path, lang=None, timeout=60):
    """识别一张图片，返回单词列表 [{text, x, y, w, h}]（坐标是图片内像素）。

    悬停取词用：按光标位置挑离得最近的单词。
    """
    out, _ = _run_ps(image_path, lang=lang, want_json=True, timeout=timeout)
    if not out:
        return []
    try:
        data = json.loads(out)
    except Exception:
        return []
    words = []
    for line in data.get("lines", []):
        for w in line.get("words", []):
            words.append({"text": w.get("text", ""),
                          "x": int(w.get("x", 0)), "y": int(w.get("y", 0)),
                          "w": int(w.get("w", 0)), "h": int(w.get("h", 0))})
    return [w for w in words if w["text"]]


def pick_word_at(words, px, py):
    """在单词列表里挑离 (px, py) 最近的单词；没有返回 None。

    优先选包住光标的单词，其次选中心点最近的（放宽到 1.5 倍字高，
    否则光标刚好落在词间空隙时会取不到）。
    """
    if not words:
        return None
    inside = [w for w in words
              if w["x"] <= px <= w["x"] + w["w"] and w["y"] <= py <= w["y"] + w["h"]]
    if inside:
        return inside[0]["text"]
    best, best_d = None, None
    for w in words:
        cx, cy = w["x"] + w["w"] / 2.0, w["y"] + w["h"] / 2.0
        d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
        if d <= max(w["h"], 12) * 1.5 and (best_d is None or d < best_d):
            best, best_d = w, d
    return best["text"] if best else None


# ---------------------------------------------------------------------------
# 取行 / 取段落（悬停取词、指针取词的「整行」「整段」范围用）
# 下面都是纯逻辑，不碰 Windows，Linux 上也能测。
# ---------------------------------------------------------------------------

def ocr_lines(image_path, lang=None, timeout=60):
    """识别一张图片，返回行列表 [{text, x, y, w, h}]（坐标是图片内像素）。

    行框由该行所有单词的框合并而成；text 用系统 OCR 给的整行文字。
    """
    out, _ = _run_ps(image_path, lang=lang, want_json=True, timeout=timeout)
    if not out:
        return []
    try:
        data = json.loads(out)
    except Exception:
        return []
    raw = data.get("lines", []) if isinstance(data, dict) else []
    if isinstance(raw, dict):               # PowerShell 单元素有时不带数组括号
        raw = [raw]
    lines = []
    for ln in raw:
        words = ln.get("words", []) or []
        if isinstance(words, dict):
            words = [words]
        boxes = [(int(w.get("x", 0)), int(w.get("y", 0)),
                  int(w.get("w", 0)), int(w.get("h", 0))) for w in words]
        if not boxes:
            continue
        x0 = min(b[0] for b in boxes)
        y0 = min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes)
        y1 = max(b[1] + b[3] for b in boxes)
        text = (ln.get("text") or "").strip()
        if not text:
            text = join_lines([w.get("text", "") for w in words])
        if text:
            lines.append({"text": text, "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0})
    return lines


def _is_cjk(ch):
    return ("\u3000" <= ch <= "\u9fff" or "\uac00" <= ch <= "\ud7af"
            or "\uff00" <= ch <= "\uffef")


def join_lines(texts):
    """把多行文字拼成一段：中日韩直接相连，英文用空格；行尾连字符不加空格。"""
    out = ""
    for t in texts:
        t = (t or "").strip()
        if not t:
            continue
        if not out:
            out = t
            continue
        a, b = out[-1], t[0]
        if _is_cjk(a) or _is_cjk(b) or a == "-":
            out += t
        else:
            out += " " + t
    return out


def _rect_dist(ln, px, py):
    dx = max(ln["x"] - px, 0, px - (ln["x"] + ln["w"]))
    dy = max(ln["y"] - py, 0, py - (ln["y"] + ln["h"]))
    return (dx * dx + dy * dy) ** 0.5


def pick_line_index(lines, px, py):
    """离 (px, py) 最近的行的下标；离得太远（超过 1.5 倍字高）返回 None。"""
    best, best_d = None, None
    for i, ln in enumerate(lines):
        d = _rect_dist(ln, px, py)
        if d <= max(ln["h"], 12) * 1.5 and (best_d is None or d < best_d):
            best, best_d = i, d
    return best


def _same_paragraph(a, b):
    """两行是不是上下相邻、属于同一段（字高相近、行距不大、左右有重叠）。"""
    ha, hb = a["h"], b["h"]
    if min(ha, hb) <= 0:
        return False
    ratio = float(ha) / hb
    if ratio > 1.6 or ratio < 0.625:             # 标题和正文字号差得多：分开
        return False
    top, bot = (a, b) if a["y"] <= b["y"] else (b, a)
    if bot["y"] < top["y"] + 0.5 * top["h"]:     # 几乎同一行（分栏并排）：不是上下相邻
        return False
    gap = bot["y"] - (top["y"] + top["h"])
    if gap > 0.75 * (ha + hb) / 2.0:             # 行距明显大于正常行距：段间空行
        return False
    ov = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    if ov >= 0.25 * min(a["w"], b["w"]):
        return True
    return abs(a["x"] - b["x"]) <= 2 * max(ha, hb)


def paragraph_indices(lines, idx):
    """从第 idx 行出发，向上下扩展出同一段的所有行（按从上到下排序）。"""
    seen = {idx}
    todo = [idx]
    while todo:
        cur = todo.pop()
        for j, other in enumerate(lines):
            if j not in seen and _same_paragraph(lines[cur], other):
                seen.add(j)
                todo.append(j)
    return sorted(seen, key=lambda k: (lines[k]["y"], lines[k]["x"]))


def pick_text_at(lines, px, py, scope):
    """按范围取光标处的文字：scope = "line"（一行）或 "paragraph"（一段）。没有返回 None。"""
    i = pick_line_index(lines, px, py)
    if i is None:
        return None
    if scope == "line":
        return lines[i]["text"] or None
    return join_lines([lines[k]["text"] for k in paragraph_indices(lines, i)]) or None
