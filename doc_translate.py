"""文档翻译 — 纯函数，不碰界面、不碰网络、不碰 Windows。

支持 .txt / .md / .srt：
- .txt / .md：按段落（连续的非空行）分块翻译，空行与段落结构原样保留
  （.md 的标题、列表行按段落走，不解析 Markdown 语法，只保证翻完
  结构不变、标记符号不丢）。
- .srt：只翻字幕正文行，序号与时间轴原样保留。

做法思路参考了 QTranslate（github.com/ahatem/QTranslate，文档翻译
支持 TXT / SRT 等）与 Pot（github.com/pot-app/pot-desktop）的功能清单，
代码是本项目自己写的，没有复制任何一方（QTranslate 新版是 Kotlin，
Pot 是 GPL-3.0，本项目只借鉴功能清单）。
"""

import os
import re

SUPPORTED_DOC_EXTS = {".txt", ".md", ".srt"}
SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}( .*)?$")


def supported_doc_ext(path):
    """是不是支持的文档扩展名（.txt / .md / .srt，不区分大小写）。"""
    return os.path.splitext(str(path or ""))[1].lower() in SUPPORTED_DOC_EXTS


def supported_image_ext(path):
    """是不是支持的图片扩展名（.png / .jpg / .jpeg / .bmp / .tif / .tiff）。"""
    return os.path.splitext(str(path or ""))[1].lower() in SUPPORTED_IMAGE_EXTS


def _para_spans(text):
    """找出所有段落的 (start, end) 位置：一段 = 连续的非空行。

    段落不含结尾换行；空行、行首行尾的空白、文件头尾的换行都不属于
    任何段落，重建时原样保留，所以 identity 重建与原文逐字相同。
    """
    text = text or ""
    n = len(text)
    lines, pos = [], 0          # 每行 (行首, 行尾不含换行)
    while pos < n:
        j = text.find("\n", pos)
        if j < 0:
            lines.append((pos, n))
            break
        lines.append((pos, j))
        pos = j + 1
    spans, cur = [], None
    for s, e in lines:
        if text[s:e].strip():
            if cur is None:
                cur = [s, e]
            else:
                cur[1] = e
        elif cur is not None:
            spans.append(tuple(cur))
            cur = None
    if cur is not None:
        spans.append(tuple(cur))
    return spans


def split_paragraphs(text):
    """把文本按段落拆成列表（空行分隔；空段落不保留，见 rebuild）。"""
    return [text[s:e] for s, e in _para_spans(text or "")]


def rebuild_paragraphs(translated, original):
    """把翻好的段落按原文的段落位置拼回去。

    translated 与 split_paragraphs(original) 一一对应；
    空行、缩进、文件头尾换行全部按原文原样保留。
    """
    spans = _para_spans(original or "")
    if len(translated) != len(spans):
        raise ValueError("段落数对不上：原文 %d 段，译文 %d 段" % (len(spans), len(translated)))
    out, pos = [], 0
    for (s, e), t in zip(spans, translated):
        out.append(original[pos:s])
        out.append(t)
        pos = e
    out.append(original[pos:])
    return "".join(out)


def translate_paragraphs(text, fn, progress=None):
    """按段落翻译全文：fn(段落) -> 译文；progress(已翻段数, 总段数) 可选。

    返回翻好的全文（结构与原文一致）。fn 抛异常就直接向上传，
    由调用方决定是整篇失败还是逐段标红——这里不吞异常。
    """
    paras = split_paragraphs(text or "")
    done = []
    for i, p in enumerate(paras):
        done.append(fn(p))
        if progress:
            progress(i + 1, len(paras))
    return rebuild_paragraphs(done, text or "")


# ---------------------------------------------------------------- SRT
def srt_parse(text):
    """解析 SRT 字幕：返回 [{"index": 序号, "times": "时间轴行",
    "text": "正文（多行用 \\n 连着）"}]。

    序号不是数字、时间轴格式不对、块里没有正文的块会被跳过
    （解析不到就整块丢掉，不报错——调用方按解析出的块数判断）。
    """
    blocks, cur = [], []
    for ln in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if ln.strip():
            cur.append(ln)
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    out = []
    for b in blocks:
        if len(b) < 3:
            continue
        try:
            idx = int(b[0].strip())
        except ValueError:
            continue
        if not _TIME_RE.match(b[1].strip()):
            continue
        body = "\n".join(b[2:])
        if not body.strip():
            continue
        out.append({"index": idx, "times": b[1].strip(), "text": body})
    return out


def srt_rebuild(blocks):
    """把 srt_parse 的结果拼回 SRT 文本：序号与时间轴逐字保留，
    块之间一个空行，文件末尾一个换行（标准 SRT 写法）。"""
    parts = []
    for b in blocks:
        parts.append("%d\n%s\n%s" % (b["index"], b["times"], b["text"]))
    return "\n\n".join(parts) + ("\n" if parts else "")


def srt_translate(text, fn, progress=None):
    """翻译 SRT 全文：只翻每块的正文，序号与时间轴原样保留。"""
    blocks = srt_parse(text or "")
    for i, b in enumerate(blocks):
        b["text"] = fn(b["text"])
        if progress:
            progress(i + 1, len(blocks))
    return srt_rebuild(blocks)
