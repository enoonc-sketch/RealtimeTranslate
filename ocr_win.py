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
import re
import shutil
import subprocess
import sys

try:
    import ocr_backends
except Exception:      # noqa: BLE001
    ocr_backends = None

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
    """Windows：系统 OCR（PowerShell 5.1 + winocr.ps1）；macOS / Linux：tesseract 命令行（v2.13）。"""
    if IS_WIN:
        return find_powershell() is not None and os.path.isfile(_script_path())
    return bool(ocr_backends and ocr_backends.available())


# Windows OCR 要的是 BCP-47 标签：程序里的 zh-CN / en 等先换成系统语言包的写法。
WIN_OCR_TAG = {
    "zh-CN": "zh-Hans-CN", "zh-TW": "zh-Hant-TW", "en": "en-US", "ja": "ja-JP", "ko": "ko-KR",
    "fr": "fr-FR", "de": "de-DE", "es": "es-ES", "ru": "ru-RU", "pt": "pt-BR", "it": "it-IT",
    "ar": "ar-SA", "th": "th-TH", "vi": "vi-VN", "id": "id-ID", "hi": "hi-IN", "tr": "tr-TR",
    "pl": "pl-PL", "nl": "nl-NL", "uk": "uk-UA", "sv": "sv-SE", "he": "he-IL",
}

# winocr.ps1 只吐 ASCII 错误码（它是无 BOM 文件，中文会在中文 Windows 上被当 GBK 读坏），这里翻成中文
_OCR_MSG = {
    "OCR_NO_LANG": "本机没有可用的 OCR 语言包。请到「设置 → 时间和语言 → 语言和区域」添加语言，"
                   "并勾选「光学字符识别」。",
    "OCR_PS_VERSION": "截图 OCR 需要 Windows PowerShell 5.1（powershell.exe），PowerShell 7 不支持系统 OCR。",
    "OCR_WINRT": "无法加载 Windows 系统 OCR 组件（需要 Windows 10 及以上，且未被组策略 / 安全软件禁用）。",
    "OCR_IMAGE": "图片打不开或格式不支持（支持 png / jpg / bmp / tif）。",
    "OCR_RECOGNIZE": "系统 OCR 识别失败，请换一张图片或稍后重试。",
}


def explain_ps_error(err, code=None):
    """把 PowerShell 的错误输出变成一句中文原因。认不出就原样截取末尾。"""
    err = (err or "").strip()
    m = re.search(r"(OCR_[A-Z_]+):\s*([^\r\n]*)", err)
    if m:
        base = _OCR_MSG.get(m.group(1), "")
        detail = m.group(2).strip()
        if base:
            return base + ("（%s）" % detail[:160] if detail and m.group(1) in ("OCR_IMAGE", "OCR_WINRT") else "")
    low = err.lower()
    if "parsererror" in low or "unexpected token" in low or "missing the terminator" in low \
            or "字符串" in err or "语法" in err:
        return "winocr.ps1 解析失败（旧版脚本含中文，中文 Windows 会读坏）。请升级到 v2.13 及以上。"
    if "executionpolicy" in low or "execution of scripts is disabled" in low or "禁止运行脚本" in err:
        return "PowerShell 执行策略禁止运行脚本（程序已用 -ExecutionPolicy Bypass，可能被组策略强制覆盖）。"
    if "constrainedlanguage" in low or "constrained language" in low:
        return "PowerShell 处于「受限语言模式」（常见于 AppLocker / 企业安全策略），系统 OCR 无法运行。"
    tail = err[-300:]
    if code is not None:
        return "OCR 失败（退出码 %s）%s" % (code, ("：" + tail) if tail else "")
    return tail or "OCR 失败"


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


def _run_ps(image_path, lang=None, want_json=False, timeout=60):
    ps = find_powershell()
    if not IS_WIN or not ps:
        raise OcrError("截图 OCR 只支持 Windows，且需要 Windows PowerShell 5.1")
    script = _script_path()
    if not os.path.isfile(script):
        raise OcrError("找不到 winocr.ps1（打包时漏了该文件）")
    cmd = [ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
           "-File", script, "-Path", os.path.abspath(image_path)]
    if lang and lang != "auto":
        cmd += ["-Language", WIN_OCR_TAG.get(lang, lang)]
    if want_json:
        cmd += ["-Json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                              **_no_window_kwargs())
    except subprocess.TimeoutExpired:
        raise OcrError("OCR 超时（%d 秒），图片可能太大或 OCR 卡住了" % timeout)
    except Exception as e:
        raise OcrError("启动 PowerShell OCR 失败：%s" % e)
    out = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        raise OcrError(explain_ps_error(err, proc.returncode))
    return out, err


def ocr_image(image_path, lang=None, timeout=60):
    """识别一张图片，返回按行拼好的文字（没认出返回空串）。"""
    if not IS_WIN:
        data = _backend_data(image_path, lang, timeout)
        return "\n".join(ln.get("text", "") for ln in data.get("lines", []) if ln.get("text"))
    out, _ = _run_ps(image_path, lang=lang, timeout=timeout)
    return out


def _backend_data(image_path, lang, timeout):
    """macOS / Linux：走 tesseract，结构和 winocr.ps1 -Json 一致。"""
    if not (ocr_backends and ocr_backends.available()):
        raise OcrError("未安装 tesseract：macOS 用 brew install tesseract tesseract-lang，"
                       "Linux 用 sudo apt install tesseract-ocr tesseract-ocr-chi-sim")
    try:
        return ocr_backends.recognize(image_path, lang=lang, timeout=timeout)
    except ocr_backends.BackendError as e:
        raise OcrError(str(e))


def _ocr_json(image_path, lang, timeout):
    """统一取 {"lines": [...]}：Windows 走 PowerShell，其余走 tesseract。解析失败返回 {}。"""
    if not IS_WIN:
        return _backend_data(image_path, lang, timeout)
    out, _ = _run_ps(image_path, lang=lang, want_json=True, timeout=timeout)
    if not out:
        return {}
    try:
        data = json.loads(out)
    except Exception:      # noqa: BLE001
        return {}
    return data if isinstance(data, dict) else {}


def ocr_words(image_path, lang=None, timeout=60):
    """识别一张图片，返回单词列表 [{text, x, y, w, h}]（坐标是图片内像素）。

    悬停取词用：按光标位置挑离得最近的单词。
    """
    data = _ocr_json(image_path, lang, timeout)
    words = []
    raw_lines = data.get("lines", []) or []
    if isinstance(raw_lines, dict):                 # PowerShell 单元素有时不带数组括号
        raw_lines = [raw_lines]
    for line in raw_lines:
        raw_words = line.get("words", []) or []
        if isinstance(raw_words, dict):
            raw_words = [raw_words]
        for w in raw_words:
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
    data = _ocr_json(image_path, lang, timeout)
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


def group_paragraphs(lines):
    """把一页 OCR 行分成若干段（每段是行下标列表），按从上到下、从左到右排序。

    截图翻译「盖在截图上」时按段翻译：整段一起翻上下文更完整，译文也盖在整段的框里。
    """
    seen, groups = set(), []
    for i in sorted(range(len(lines)), key=lambda k: (lines[k]["y"], lines[k]["x"])):
        if i in seen:
            continue
        idxs = paragraph_indices(lines, i)
        seen.update(idxs)
        groups.append(idxs)
    return groups


def paragraph_box(lines, idxs):
    """一段所有行的外框 (x, y, w, h)。"""
    x0 = min(lines[k]["x"] for k in idxs)
    y0 = min(lines[k]["y"] for k in idxs)
    x1 = max(lines[k]["x"] + lines[k]["w"] for k in idxs)
    y1 = max(lines[k]["y"] + lines[k]["h"] for k in idxs)
    return x0, y0, x1 - x0, y1 - y0


UI_SHORT_LINE = 28        # 平均每行少于这么多字：当作菜单 / 按钮栏 / 列表，逐行翻


def group_ui_lines(lines):
    """整窗翻译用的分组：先按段落分；某段里每行都很短（菜单项、按钮、列表项、
    表头），就拆成一行一组各翻各的——否则相邻的菜单项会被当成一句话连起来翻。
    成段的正文（行平均较长）仍按整段翻译，上下文完整。返回行下标列表的列表。
    """
    out = []
    for idxs in group_paragraphs(lines):
        if len(idxs) > 1:
            avg = sum(len(lines[k]["text"]) for k in idxs) / float(len(idxs))
            if avg < UI_SHORT_LINE:
                out.extend([k] for k in idxs)
                continue
        out.append(idxs)
    return out
