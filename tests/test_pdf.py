"""pdf_translate 测试：PDF 夹具全部在测试里手写（最小合法结构，不依赖 xref）。"""
import os
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import pdf_translate as p

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def make_pdf(content_stream, extra_objs="", flate=False, resources_extra=""):
    """造一个单页 PDF：content_stream 是页面内容流的原始字节。

    flate=True 时内容流用 FlateDecode 压缩。extra_objs 可追加额外对象
    （如 ToUnicode CMap 流、图片 XObject），resources_extra 可追加资源字典内容。
    """
    if flate:
        stream_data = zlib.compress(content_stream)
        filt = " /Filter /FlateDecode"
    else:
        stream_data = content_stream
        filt = ""
    parts = []
    parts.append(b"%PDF-1.4\n")
    parts.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    parts.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    parts.append(b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                 b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >>"
                 + resources_extra.encode("latin-1") + b" >> >> endobj\n")
    parts.append(b"4 0 obj << /Length %d%s >> stream\n" % (len(stream_data), filt.encode("latin-1")))
    parts.append(stream_data)
    parts.append(b"\nendstream endobj\n")
    parts.append(b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
    if extra_objs:
        parts.append(extra_objs.encode("latin-1") if isinstance(extra_objs, str)
                     else extra_objs)
    parts.append(b"%%EOF\n")
    return b"".join(parts)


# (1) 未压缩流 + Tj
pdf1 = make_pdf(b"BT /F1 24 Tf 100 700 Td (Hello PDF world) Tj ET")
t1 = p.extract_pdf_text(pdf1)
ok("uncompressed Tj extracts text", "Hello PDF world" in t1)

# 同一份 PDF 走文件路径也能提
with tempfile.TemporaryDirectory() as d:
    fp = os.path.join(d, "a.pdf")
    with open(fp, "wb") as f:
        f.write(pdf1)
    ok("extract by file path", "Hello PDF world" in p.extract_pdf_text(fp))

# (2) FlateDecode 流 + Tj
pdf2 = make_pdf(b"BT /F1 24 Tf 100 700 Td (Flate hello world) Tj ET", flate=True)
ok("flate stream extracts text",
   "Flate hello world" in p.extract_pdf_text(pdf2))

# (3) 图片页：只有 XObject 图片、没有文字操作
img_obj = (b"6 0 obj << /Type /XObject /Subtype /Image /Width 2 /Height 2 "
           b"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Length 12 >> stream\n"
           b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\nendstream endobj\n")
pdf3 = make_pdf(b"q 100 0 0 100 0 0 cm /Im1 Do Q",
                extra_objs=img_obj,
                resources_extra=" /XObject << /Im1 6 0 R >>")
t3 = p.extract_pdf_text(pdf3)
ok("image-only page yields no text", len(t3.strip()) < p.PDF_TRANSLATE_MIN_CHARS)
with tempfile.TemporaryDirectory() as d:
    fp = os.path.join(d, "scan.pdf")
    with open(fp, "wb") as f:
        f.write(pdf3)
    try:
        p.translate_pdf(fp, lambda t: t.upper())
        ok("image-only translate_pdf raises ValueError", False)
    except ValueError as e:
        msg = str(e)
        ok("image-only translate_pdf raises ValueError", True)
        ok("error mentions scanned/image",
           "扫描" in msg or "图片" in msg or "scanned" in msg or "image" in msg)
        ok("error points to screenshot translation",
           "截图" in msg or "screenshot" in msg)

# (4) TJ 数组：多个字面串用空格连起来
pdf4 = make_pdf(b"BT /F1 12 Tf 100 700 Td [(Hello) (World)] TJ ET")
t4 = p.extract_pdf_text(pdf4)
ok("TJ array joins words with space", "Hello World" in t4)

# (4b) 两个 Tj 不粘连
pdf4b = make_pdf(b"BT /F1 12 Tf 100 700 Td (Hello) Tj (World) Tj ET")
ok("separate Tj calls do not run together",
   "Hello World" in p.extract_pdf_text(pdf4b))

# (5) 十六进制串 <48656C6C6F> -> Hello
pdf5 = make_pdf(b"BT /F1 12 Tf 100 700 Td <48656C6C6F> Tj ET")
ok("hex string decodes", "Hello" in p.extract_pdf_text(pdf5))

# (6) 字面串转义：\( \) \\ 与八进制 \101 (=A)
pdf6 = make_pdf(b"BT /F1 12 Tf 100 700 Td (a\\(b\\)c \\101) Tj ET")
ok("literal escapes decoded", "a(b)c A" in p.extract_pdf_text(pdf6))

# (7) ToUnicode CMap：字形码 0001->H 0002->i
cmap_stream = (b"/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
               b"/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
               b"/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
               b"1 beginbfchar\n<0001> <0048>\n<0002> <0069>\nendbfchar\n"
               b"endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend")
cmap_obj = (b"6 0 obj << /Length %d >> stream\n" % len(cmap_stream)
            + cmap_stream + b"\nendstream endobj\n")
pdf7 = make_pdf(b"BT /F1 12 Tf 100 700 Td (\x00\x01\x00\x02\x00\x01) Tj ET",
                extra_objs=cmap_obj)
ok("ToUnicode CMap maps glyph codes", "HiH" in p.extract_pdf_text(pdf7))

# (8) ToUnicode bfrange：0003-0005 -> A-C
cmap2 = (b"begincmap\n1 beginbfrange\n<0003> <0005> <0041>\nendbfrange\nendcmap\n")
cmap2_obj = (b"6 0 obj << /Length %d >> stream\n" % len(cmap2)
             + cmap2 + b"\nendstream endobj\n")
pdf8 = make_pdf(b"BT /F1 12 Tf 100 700 Td (\x00\x03\x00\x04\x00\x05) Tj ET",
                extra_objs=cmap2_obj)
ok("ToUnicode bfrange maps range", "ABC" in p.extract_pdf_text(pdf8))

# (9) 畸形文件不抛异常
ok("empty bytes return empty", p.extract_pdf_text(b"") == "")
ok("garbage returns empty without raising", p.extract_pdf_text(b"not a pdf at all") == "")
ok("truncated stream returns what it can",
   "Hello" in p.extract_pdf_text(
       b"4 0 obj << /Length 10 >> stream\nBT (Hello) Tj ET"))
ok("bad flate falls back instead of raising",
   isinstance(p.extract_pdf_text(
       b"4 0 obj << /Filter /FlateDecode /Length 4 >> stream\nXXXX\nendstream endobj\n"), str))

# (10) translate_pdf：文件名规则 + 写译文 + 返回值
with tempfile.TemporaryDirectory() as d:
    fp = os.path.join(d, "foo.pdf")
    with open(fp, "wb") as f:
        f.write(pdf1)
    out_path, text = p.translate_pdf(fp, lambda t: "TRANSLATED:" + t)
    ok("output filename rule foo.pdf -> foo-译文.txt",
       out_path == os.path.join(d, "foo-译文.txt"))
    ok("output file exists", os.path.isfile(out_path))
    with open(out_path, "r", encoding="utf-8") as f:
        written = f.read()
    ok("translated stub output written",
       written == "TRANSLATED:" + text)
    ok("returned text is the extracted text", "Hello PDF world" in text)

# (11) 常量与空文本边界：9 个字符不够 10 个
ok("PDF_TRANSLATE_MIN_CHARS is 10", p.PDF_TRANSLATE_MIN_CHARS == 10)
with tempfile.TemporaryDirectory() as d:
    fp = os.path.join(d, "short.pdf")
    with open(fp, "wb") as f:
        f.write(make_pdf(b"BT /F1 12 Tf 100 700 Td (123456789) Tj ET"))
    try:
        p.translate_pdf(fp, lambda t: t)
        ok("9-char text raises ValueError", False)
    except ValueError:
        ok("9-char text raises ValueError", True)

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
