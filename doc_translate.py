"""文档翻译 — 纯函数，不碰界面、不碰网络、不碰 Windows。

支持 .txt / .md / .srt / .docx：
- .txt / .md：按段落（连续的非空行）分块翻译，空行与段落结构原样保留
  （.md 的标题、列表行按段落走，不解析 Markdown 语法，只保证翻完
  结构不变、标记符号不丢）。
- .srt：只翻字幕正文行，序号与时间轴原样保留。

做法思路参考了 QTranslate（github.com/ahatem/QTranslate，文档翻译
支持 TXT / SRT 等）与 Pot（github.com/pot-app/pot-desktop）的功能清单，
代码是本项目自己写的，没有复制任何一方（QTranslate 新版是 Kotlin，
Pot 是 GPL-3.0，本项目只借鉴功能清单）。
"""

import io
import os
import re
import zipfile
from xml.sax.saxutils import escape as _xml_escape
from xml.sax.saxutils import unescape as _xml_unescape

SUPPORTED_DOC_EXTS = {".txt", ".md", ".srt", ".docx"}
SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}

_TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}( .*)?$")


# v2.10：大文件保护。超过上限直接拒绝（给出明确提示），不再把整个文件读进内存后卡死。
MAX_TEXT_BYTES = 50 * 1024 * 1024        # .txt / .md / .srt
MAX_DOCX_BYTES = 100 * 1024 * 1024       # .docx 压缩包本身
MAX_DOCX_XML_BYTES = 200 * 1024 * 1024   # word/document.xml 解压后（防压缩炸弹）
MAX_PDF_BYTES = 200 * 1024 * 1024        # .pdf（与 pdf_translate.MAX_PDF_BYTES 一致）
LARGE_DOC_BYTES = 5 * 1024 * 1024        # 超过这个大小先问一句再翻


def size_limit_for(ext):
    """按扩展名返回文件大小上限（字节）。"""
    ext = (ext or "").lower()
    if ext == ".pdf":
        return MAX_PDF_BYTES
    if ext == ".docx":
        return MAX_DOCX_BYTES
    return MAX_TEXT_BYTES


def decode_text(raw):
    """字节 → 文本：UTF-8(带/不带 BOM) → UTF-16(带 BOM) → GB18030 → 宽松 UTF-8。
    旧版只认 UTF-8，GBK 编码的中文 txt / srt 会直接「打不开文档」。"""
    raw = raw or b""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("gb18030")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def read_text_file(path, max_bytes=MAX_TEXT_BYTES):
    """读文本文档；超过 max_bytes 抛 ValueError（消息可直接给用户看）。"""
    size = os.path.getsize(path)
    if size > max_bytes:
        raise ValueError("文件太大（%.1f MB），上限 %d MB，请拆成几份再翻译"
                         % (size / 1048576.0, max_bytes // 1048576))
    with open(path, "rb") as f:
        return decode_text(f.read())


def _check_docx_zip(zin):
    """docx 压缩包里 document.xml 解压后太大就拒绝（压缩炸弹）。"""
    try:
        info = zin.getinfo("word/document.xml")
    except KeyError:
        return
    if info.file_size > MAX_DOCX_XML_BYTES:
        raise ValueError("文档正文太大（解压后 %.0f MB），已拒绝处理" % (info.file_size / 1048576.0))


def supported_doc_ext(path):
    """是不是支持的文档扩展名（.txt / .md / .srt / .docx，不区分大小写）。"""
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


# ---------------------------------------------------------------- DOCX
# 只用标准库 zipfile：.docx 就是个 zip，word/document.xml 里是正文。
# 不用 ElementTree 重写整份 XML（它会改命名空间前缀、丢掉一些细节）：
# 直接在原始 XML 文本上按段落替换 <w:t> 的内容，其余字节原样保留，
# 所以样式、图片、页眉页脚、其他部件都不会动。
_P_RE = re.compile(r"<w:p\b.*?</w:p>", re.DOTALL)
_T_RE = re.compile(r"(<w:t[^>]*>)(.*?)(</w:t>)", re.DOTALL)


def docx_paragraph_texts(xml_bytes):
    """从 word/document.xml 的原始字节里读出每段的文字（按段落顺序）。

    一段 = 一个 <w:p>…</w:p>；段内所有 <w:t> 的文字拼起来就是段落文字。
    空段落也保留（返回空串），段数与原文一致。
    """
    xml = (xml_bytes or b"").decode("utf-8", errors="replace")
    texts = []
    for m in _P_RE.finditer(xml):
        parts = [_xml_unescape(t) for _, t, _ in _T_RE.findall(m.group(0))]
        texts.append("".join(parts))
    return texts


def docx_replace_texts(xml_bytes, new_texts):
    """把每段的译文写回 word/document.xml：译文放进该段第一个 <w:t>，
    其余 <w:t> 清空；段落之外的所有字节原样保留。

    new_texts 与 docx_paragraph_texts 的段数必须一致，否则抛 ValueError。
    """
    xml = (xml_bytes or b"").decode("utf-8", errors="replace")
    paras = list(_P_RE.finditer(xml))
    if len(new_texts) != len(paras):
        raise ValueError("段落数对不上：原文 %d 段，译文 %d 段"
                         % (len(paras), len(new_texts)))
    out, pos = [], 0
    for m, new in zip(paras, new_texts):
        out.append(xml[pos:m.start()])
        block = m.group(0)
        # 第一个 <w:t> 放译文，其余清空
        state = {"first": True}
        def _repl(mm):
            if state["first"]:
                state["first"] = False
                return mm.group(1) + _xml_escape(new) + mm.group(3)
            return mm.group(1) + mm.group(3)
        out.append(_T_RE.sub(_repl, block))
        pos = m.end()
    out.append(xml[pos:])
    return "".join(out).encode("utf-8")


def docx_translate_bytes(data, fn, progress=None):
    """翻译整个 .docx 文件（字节进、字节出）：fn(段落文字) -> 译文。

    空段落不翻译、原样保留；其他 zip 条目（样式、图片、页眉页脚等）
    按原压缩方式原样复制。不是合法的 .docx（解不开 zip / 没有
    word/document.xml）时抛 ValueError / zipfile.BadZipFile。
    """
    try:
        zin = zipfile.ZipFile(io.BytesIO(data or b""))
    except zipfile.BadZipFile:
        raise ValueError("不是合法的 .docx 文件（解不开 zip）")
    try:
        names = zin.namelist()
        if "word/document.xml" not in names:
            raise ValueError("不是合法的 .docx 文件（缺少 word/document.xml）")
        _check_docx_zip(zin)
        xml = zin.read("word/document.xml")
        texts = docx_paragraph_texts(xml)
        done = []
        for i, t in enumerate(texts):
            done.append(t if not t.strip() else fn(t))
            if progress:
                progress(i + 1, len(texts))
        return docx_rebuild(data, done)
    finally:
        zin.close()


def docx_document_xml(data):
    """从 .docx 字节里取出 word/document.xml 的原始字节。"""
    try:
        zin = zipfile.ZipFile(io.BytesIO(data or b""))
    except zipfile.BadZipFile:
        raise ValueError("不是合法的 .docx 文件（解不开 zip）")
    try:
        if "word/document.xml" not in zin.namelist():
            raise ValueError("不是合法的 .docx 文件（缺少 word/document.xml）")
        _check_docx_zip(zin)
        return zin.read("word/document.xml")
    finally:
        zin.close()


def docx_rebuild(data, translated):
    """按 translated（与 docx_paragraph_texts 一一对应）重建整个 .docx。

    其他 zip 条目按原压缩方式原样复制。
    """
    zin = zipfile.ZipFile(io.BytesIO(data or b""))
    try:
        _check_docx_zip(zin)
        xml = zin.read("word/document.xml")
        new_xml = docx_replace_texts(xml, translated)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                payload = new_xml if item.filename == "word/document.xml" \
                    else zin.read(item.filename)
                zout.writestr(item, payload)
        return buf.getvalue()
    finally:
        zin.close()
