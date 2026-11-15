"""PDF 翻译 — 尽力而为（best-effort）的纯文本提取，不碰界面、不碰网络、不碰 Windows。

只用标准库（zlib、re）。支持：

- 未压缩内容流里的 Tj / TJ / ' / " 文字显示操作，字面串 "(...)"
  （含 PDF 转义 \\( \\) \\\\ \\n \\r \\t \\b \\f 与八进制 \\ddd）与十六进制串 <...>；
- FlateDecode 压缩流（zlib 解压，失败就按原字节尽力扫）；
- 文件里的 ToUnicode CMap（beginbfchar / beginbfrange），解析干净才用，
  解析失败就退回 latin-1 解码原始字节。

限制（故意不做）：没有 ToUnicode 的内嵌字体只能按 latin-1 猜字形码，
出来的可能是乱码；不保证版式与阅读顺序；图片型页面提不出文字；
不支持加密 PDF、对象流（ObjStm）与非 Flate 的压缩过滤器。

任何畸形文件都不会抛异常：extract_pdf_text 能提多少提多少，
提不出来就返回 ""。
"""

import os
import re
import zlib

PDF_TRANSLATE_MIN_CHARS = 10

__all__ = ["PDF_TRANSLATE_MIN_CHARS", "extract_pdf_text", "translate_pdf"]


# ------------------------------------------------------------------ 工具
_DELIMS = b" \t\r\n\f\x00()<>[]{}/%"
_WS = b" \t\r\n\f\x00"


# v2.10：单个流解压后最多 32 MB、整份 PDF 累计最多 256 MB 的内容流；
# 超过就放弃该流（按原字节处理）。旧版 decompress() 不设上限，一个带大量
# 图片 / 压缩炸弹的 PDF 会把内存吃光，程序直接卡死或闪退。
MAX_STREAM_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_PDF_BYTES = 200 * 1024 * 1024


def _inflate(raw, limit=MAX_STREAM_BYTES):
    """解 Flate 流：先按 zlib 包一层试，再按裸 deflate 试，都不行就抛错。
    解压结果超过 limit 字节时抛 ValueError（不再继续吃内存）。"""
    def _run(obj):
        out = obj.decompress(raw, limit + 1)
        if len(out) > limit:
            raise ValueError("流解压后过大，已放弃")
        return out
    try:
        return _run(zlib.decompressobj())
    except zlib.error:
        pass
    return _run(zlib.decompressobj(-15))


# ------------------------------------------------------------------ CMap
_BFCHAR_RE = re.compile(r"beginbfchar(.*?)endbfchar", re.DOTALL)
_BFRANGE_RE = re.compile(r"beginbfrange(.*?)endbfrange", re.DOTALL)
_BFCHAR_ENTRY_RE = re.compile(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")
_BFRANGE_RE_RE = re.compile(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")
_BFRANGE_ARR_RE = re.compile(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[([^\]]*)\]")
_HEX_IN_BRACKETS_RE = re.compile(r"<([0-9A-Fa-f]+)>")

# 单个 bfrange 展开上限：防畸形文件把内存撑爆。
_MAX_BFRANGE_SPAN = 10000


def _hex_to_unicode(hex_str):
    """把 CMap 目标码的十六进制串解成 Unicode 文本（UTF-16BE）。"""
    try:
        raw = bytes.fromhex(hex_str)
    except ValueError:
        return None
    if len(raw) % 2 == 1:
        return None
    try:
        return raw.decode("utf-16-be", errors="replace")
    except Exception:
        return None


def _parse_cmap(text):
    """从全文（含已解压的流）里解析 ToUnicode CMap，返回 {字形码字节: 文本}。

    任何结构性解析异常都返回 {}（调用方退回 latin-1）；个别坏条目只跳过该条。
    """
    cmap = {}
    try:
        for block in _BFCHAR_RE.findall(text or ""):
            for src, dst in _BFCHAR_ENTRY_RE.findall(block):
                try:
                    key = bytes.fromhex(src)
                except ValueError:
                    continue
                val = _hex_to_unicode(dst)
                if key and val is not None:
                    cmap[key] = val
        for block in _BFRANGE_RE.findall(text or ""):
            for lo, hi, dst in _BFRANGE_RE_RE.findall(block):
                try:
                    lo_b, hi_b, dst_b = (bytes.fromhex(lo), bytes.fromhex(hi),
                                         bytes.fromhex(dst))
                except ValueError:
                    continue
                nbytes = len(lo_b)
                if nbytes == 0 or len(hi_b) != nbytes or len(dst_b) % 2 == 1:
                    continue
                lo_i, hi_i = int.from_bytes(lo_b, "big"), int.from_bytes(hi_b, "big")
                if hi_i < lo_i or hi_i - lo_i > _MAX_BFRANGE_SPAN:
                    continue
                base = dst_b.decode("utf-16-be", errors="replace")
                if len(base) != 1:
                    continue
                for code in range(lo_i, hi_i + 1):
                    cmap[code.to_bytes(nbytes, "big")] = chr(ord(base) + (code - lo_i))
            for lo, hi, arr in _BFRANGE_ARR_RE.findall(block):
                try:
                    lo_b, hi_b = bytes.fromhex(lo), bytes.fromhex(hi)
                except ValueError:
                    continue
                nbytes = len(lo_b)
                if nbytes == 0 or len(hi_b) != nbytes:
                    continue
                lo_i, hi_i = int.from_bytes(lo_b, "big"), int.from_bytes(hi_b, "big")
                if hi_i < lo_i or hi_i - lo_i > _MAX_BFRANGE_SPAN:
                    continue
                vals = [_hex_to_unicode(h) for h in _HEX_IN_BRACKETS_RE.findall(arr)]
                for i, code in enumerate(range(lo_i, hi_i + 1)):
                    if i < len(vals) and vals[i] is not None:
                        cmap[code.to_bytes(nbytes, "big")] = vals[i]
    except Exception:
        return {}
    return cmap


def _apply_cmap(raw, cmap):
    """按 CMap 把字形码字节串翻成文本：最长匹配优先，对不上的字节退回 latin-1。"""
    if not cmap:
        return raw.decode("latin-1")
    max_len = max(len(k) for k in cmap)
    out, i, n = [], 0, len(raw)
    while i < n:
        hit = None
        for ln in range(min(max_len, n - i), 0, -1):
            val = cmap.get(raw[i:i + ln])
            if val is not None:
                hit = (val, ln)
                break
        if hit is not None:
            out.append(hit[0])
            i += hit[1]
        else:
            out.append(chr(raw[i]))
            i += 1
    return "".join(out)


def _decode_string_bytes(raw, cmap):
    """把一个 PDF 字符串的原始字节解成文本。"""
    if raw.startswith(b"\xfe\xff"):
        try:
            return raw[2:].decode("utf-16-be", errors="replace")
        except Exception:
            pass
    if raw.startswith(b"\xff\xfe"):
        try:
            return raw[2:].decode("utf-16-le", errors="replace")
        except Exception:
            pass
    return _apply_cmap(raw, cmap)


# -------------------------------------------------------------- 字符串解析
_ESCAPES = {0x6E: 0x0A, 0x72: 0x0D, 0x74: 0x09, 0x62: 0x08, 0x66: 0x0C,
            0x28: 0x28, 0x29: 0x29, 0x5C: 0x5C}  # n r t b f ( ) \


def _parse_literal(data, i):
    """解析 data[i] == '(' 起的字面串，返回 (原始字节, 结束位置)。"""
    out = bytearray()
    depth = 1
    i += 1
    n = len(data)
    while i < n and depth > 0:
        c = data[i]
        if c == 0x5C:  # 反斜杠
            if i + 1 >= n:
                break
            e = data[i + 1]
            if e in _ESCAPES:
                out.append(_ESCAPES[e])
                i += 2
            elif e in (0x0D, 0x0A):
                # 续行：反斜杠 + 换行直接丢掉（CRLF 算一个换行）
                i += 2
                if e == 0x0D and i < n and data[i] == 0x0A:
                    i += 1
            elif 0x30 <= e <= 0x37:
                j = i + 1
                digits = bytearray()
                while j < n and len(digits) < 3 and 0x30 <= data[j] <= 0x37:
                    digits.append(data[j])
                    j += 1
                out.append(int(bytes(digits), 8) & 0xFF)
                i = j
            else:
                out.append(e)
                i += 2
        elif c == 0x28:  # (
            depth += 1
            out.append(c)
            i += 1
        elif c == 0x29:  # )
            depth -= 1
            if depth > 0:
                out.append(c)
            i += 1
        else:
            out.append(c)
            i += 1
    return bytes(out), i


def _parse_hex_string(data, i):
    """解析 data[i] == '<'（不是 '<<'）起的十六进制串，返回 (原始字节, 结束位置)。"""
    i += 1
    digits = bytearray()
    n = len(data)
    while i < n and data[i] != 0x3E:  # '>'
        c = data[i]
        if (0x30 <= c <= 0x39) or (0x61 <= c <= 0x66) or (0x41 <= c <= 0x46):
            digits.append(c)
        i += 1
    if i < n:
        i += 1  # 跳过 '>'
    if len(digits) % 2 == 1:
        digits.append(ord("0"))
    try:
        return bytes.fromhex(digits.decode("ascii")), i
    except ValueError:
        return b"", i


# -------------------------------------------------------------- 内容流扫描
def _tokenize(data):
    """把内容流切成 token：('str', bytes) / ('num', str) / ('name', str) /
    ('word', str) / ('[', None) / (']', None) / ('<<', None) / ('>>', None)。"""
    tokens = []
    i, n = 0, len(data)
    while i < n:
        c = data[i]
        if c in _WS:
            i += 1
            continue
        if c == 0x25:  # % 注释：跳到行尾
            while i < n and data[i] not in (0x0A, 0x0D):
                i += 1
            continue
        if c == 0x28:  # (
            raw, i = _parse_literal(data, i)
            tokens.append(("str", raw))
            continue
        if c == 0x3C:  # <
            if i + 1 < n and data[i + 1] == 0x3C:
                tokens.append(("<<", None))
                i += 2
            else:
                raw, i = _parse_hex_string(data, i)
                tokens.append(("str", raw))
            continue
        if c == 0x3E:  # >
            if i + 1 < n and data[i + 1] == 0x3E:
                tokens.append((">>", None))
                i += 2
            else:
                i += 1
            continue
        if c == 0x5B:  # [
            tokens.append(("[", None))
            i += 1
            continue
        if c == 0x5D:  # ]
            tokens.append(("]", None))
            i += 1
            continue
        if c in (0x7B, 0x7D):  # { }
            i += 1
            continue
        if c == 0x2F:  # / 名字
            j = i + 1
            while j < n and data[j] not in _DELIMS:
                j += 1
            tokens.append(("name", data[i + 1:j].decode("latin-1")))
            i = j
            continue
        # 普通词：数字、操作符、true/false/null
        j = i
        while j < n and data[j] not in _DELIMS:
            j += 1
        word = data[i:j].decode("latin-1")
        i = j
        if not word:
            i += 1
            continue
        try:
            float(word)
            tokens.append(("num", word))
        except ValueError:
            tokens.append(("word", word))
    return tokens


def _last_string(stack):
    for kind, val in reversed(stack):
        if kind == "str":
            return val
    return None


def _last_array(stack):
    for kind, val in reversed(stack):
        if kind == "array":
            return val
    return None


def _extract_from_content(data, cmap):
    """从一段内容流字节里提文字：Tj/TJ/'/" 各拼一个空格分隔，ET 处换行。"""
    parts = []
    stack = []
    for kind, val in _tokenize(data):
        if kind == "[":
            stack.append(("[", None))
        elif kind == "]":
            items = []
            while stack and stack[-1][0] != "[":
                items.append(stack.pop())
            if stack:
                stack.pop()  # 丢掉 '['
            items.reverse()
            stack.append(("array", items))
        elif kind == "word":
            if val == "Tj":
                raw = _last_string(stack)
                if raw is not None:
                    parts.append(_decode_string_bytes(raw, cmap))
                    parts.append(" ")
            elif val == "TJ":
                arr = _last_array(stack)
                if arr is not None:
                    strs = [_decode_string_bytes(v, cmap)
                            for k, v in arr if k == "str"]
                    if strs:
                        parts.append(" ".join(strs))
                        parts.append(" ")
            elif val in ("'", '"'):
                raw = _last_string(stack)
                if raw is not None:
                    parts.append(_decode_string_bytes(raw, cmap))
                    parts.append(" ")
            elif val == "ET":
                parts.append("\n")
            stack = []  # 操作符吃掉操作数
        else:
            stack.append((kind, val))
    return "".join(parts)


# ------------------------------------------------------------------ 流提取
# (?<!end)：别把 endstream 的后半截也当成 stream 的开头（旧版会把下一个对象——常常是整张图片——当正文流再处理一遍）
_STREAM_RE = re.compile(rb"(?<!end)stream(\r\n|\n|\r)")
_FLATE_RE = re.compile(rb"/Fl(ateDecode)?[\s\[/]")


_BINARY_HINT_RE = re.compile(rb"/Subtype\s*/(Image|Type1C|CIDFontType0C|OpenType)|/FontFile|/Type\s*/(XObject|ObjStm|XRef)")


def _iter_stream_payloads(data):
    """逐个找出 stream…endstream 段；FlateDecode 的先解压，解不开就用原字节。

    v2.10：图片 / 字体文件 / 对象流这类二进制流不含正文，直接跳过
    （以前也解压，一份带几百张图的 PDF 能解出几 GB）；累计解压量封顶。
    """
    total = 0
    for m in _STREAM_RE.finditer(data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end < 0:
            end = data.find(b"endobj", start)
            if end < 0:
                end = len(data)
        window = data[max(0, m.start() - 1024):m.start()]
        # 流的字典在 stream 关键字前面：取最后一个 obj 之后的那段，免得把上一个对象的标记算进来
        cut = window.rfind(b" obj")
        dict_part = window[cut:] if cut >= 0 else window
        if _BINARY_HINT_RE.search(dict_part):
            continue
        raw = data[start:end]
        payload = raw
        if b"FlateDecode" in dict_part or _FLATE_RE.search(dict_part):
            try:
                payload = _inflate(raw)
            except Exception:
                payload = raw
        total += len(payload)
        if total > MAX_TOTAL_BYTES:
            return
        yield payload


def _extract_pdf_text_bytes(data):
    payloads = list(_iter_stream_payloads(data or b""))
    # CMap 只可能在含 beginbfchar / beginbfrange 的流里（或文件明文里）；
    # 以前把所有流 + 整个文件拼成一份巨大字符串再 decode，内存是文件的好几倍。
    cmap_parts = [p for p in payloads if b"beginbf" in p]
    if b"beginbf" in (data or b""):
        cmap_parts.append(data)
    cmap_text = b"\n".join(cmap_parts)
    cmap = _parse_cmap(cmap_text.decode("latin-1", errors="replace")) if cmap_parts else {}
    del cmap_text, cmap_parts
    parts = []
    for payload in payloads:
        try:
            parts.append(_extract_from_content(payload, cmap))
        except Exception:
            continue  # 单个流坏了不影响其他流
    return "\n".join(p for p in parts if p)


# ------------------------------------------------------------------ 对外接口
def extract_pdf_text(path_or_bytes):
    """提取 PDF 的纯文本（尽力而为）。

    path_or_bytes 可以是文件路径（str / PathLike）或 PDF 字节。
    畸形文件、读不到的文件一律不抛异常，返回已提出的文本（可能为 ""）。
    """
    try:
        if isinstance(path_or_bytes, (bytes, bytearray)):
            data = bytes(path_or_bytes)
        elif isinstance(path_or_bytes, (str, os.PathLike)):
            if os.path.getsize(path_or_bytes) > MAX_PDF_BYTES:
                return ""
            with open(path_or_bytes, "rb") as f:
                data = f.read()
        else:
            return ""
    except Exception:
        return ""
    try:
        return _extract_pdf_text_bytes(data)
    except Exception:
        return ""


def translated_txt_path(path):
    """输出文件名规则：foo.pdf -> foo-译文.txt（扩展名换掉、前面加 -译文）。"""
    root, _ext = os.path.splitext(str(path))
    return root + "-译文.txt"


def translate_pdf(path, translate_fn):
    """翻译一个 PDF：提取文字 -> translate_fn(全文) -> 写成 -译文.txt。

    成功返回 (out_path, extracted_text)：out_path 是源路径按
    translated_txt_path 规则得到的文件名，文件里是译文（UTF-8），
    返回的 text 是提取出的原文（不是译文）。
    可提取文字少于 PDF_TRANSLATE_MIN_CHARS（10）个字符时抛 ValueError
    （多半是扫描件/图片型 PDF，提示改用截图翻译）。
    文件读不到时 open 的 OSError 直接向上传；translate_fn 的异常也向上传。
    """
    with open(path, "rb") as f:
        data = f.read()
    text = extract_pdf_text(data)
    if len(text.strip()) < PDF_TRANSLATE_MIN_CHARS:
        raise ValueError(
            "这个 PDF 几乎没有可提取的文字（仅 %d 个字符），可能是扫描件/图片型 "
            "PDF (scanned/image-based)，请改用截图翻译 "
            "(use screenshot translation instead)。" % len(text.strip()))
    out_path = translated_txt_path(path)
    translated = translate_fn(text)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(translated)
    return out_path, text
