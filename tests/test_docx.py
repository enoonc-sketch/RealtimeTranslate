""".docx 翻译：标准库 zipfile -only，段落译文写回第一个 <w:t>，其余字节原样保留。"""
import io
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import doc_translate as d

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def make_docx(paras, extra=None):
    """造一个最小 .docx：paras 是每段的 [run 文本...] 列表。"""
    body = []
    for runs in paras:
        rs = "".join('<w:r><w:t>%s</w:t></w:r>' % r for r in runs)
        body.append("<w:p>%s</w:p>" % rs)
    xml = ('<w:document xmlns:w="urn:docx"><w:body>%s</w:body></w:document>'
           % "".join(body))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml.encode("utf-8"))
        z.writestr("[Content_Types].xml", b"<Types/>")
        z.writestr("word/styles.xml", b"<styles/>")
        if extra:
            for k, v in extra.items():
                z.writestr(k, v)
    return buf.getvalue()


ok("docx ext supported", d.supported_doc_ext("a.DOCX") and d.supported_doc_ext("a.docx"))
ok("txt still supported", d.supported_doc_ext("a.txt"))

data = make_docx([["Hello ", "world"], ["Second para"], []])
texts = d.docx_paragraph_texts(d.docx_document_xml(data))
ok("paragraph texts in order", texts == ["Hello world", "Second para", ""])
ok("empty paragraph kept", len(texts) == 3)

out = d.docx_translate_bytes(data, lambda t: "译:" + t)
z = zipfile.ZipFile(io.BytesIO(out))
ok("other parts preserved byte-for-byte",
   z.read("[Content_Types].xml") == b"<Types/>" and z.read("word/styles.xml") == b"<styles/>")
ok("part list unchanged", sorted(z.namelist()) == sorted(
    ["word/document.xml", "[Content_Types].xml", "word/styles.xml"]))
texts2 = d.docx_paragraph_texts(z.read("word/document.xml"))
ok("translated paragraphs", texts2 == ["译:Hello world", "译:Second para", ""])
ok("translation went into first run only",
   z.read("word/document.xml").decode("utf-8").count("译:Hello world") == 1)

# 特殊字符要转义，不能把 XML 写坏
data2 = make_docx([["a < b & \"c\""]])
out2 = d.docx_translate_bytes(data2, lambda t: "x < y & z")
texts3 = d.docx_paragraph_texts(zipfile.ZipFile(io.BytesIO(out2)).read("word/document.xml"))
ok("xml escaping round-trips", texts3 == ["x < y & z"])

# 段落数对不上要报错，不能静默错位
try:
    d.docx_replace_texts(b"<w:p><w:r><w:t>a</w:t></w:r></w:p>", ["x", "y"])
    ok("paragraph count mismatch raises", False)
except ValueError:
    ok("paragraph count mismatch raises", True)

# 不是 docx 要报错
try:
    d.docx_translate_bytes(b"not a zip", lambda t: t)
    ok("bad zip raises", False)
except ValueError:
    ok("bad zip raises", True)
try:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("other.xml", b"x")
    d.docx_translate_bytes(buf.getvalue(), lambda t: t)
    ok("missing document.xml raises", False)
except ValueError:
    ok("missing document.xml raises", True)

# 段落里的多 run：译文只进第一个 run，其余清空
data3 = make_docx([["one", "two", "three"]])
out3 = d.docx_translate_bytes(data3, lambda t: "ONE TWO THREE")
xml3 = zipfile.ZipFile(io.BytesIO(out3)).read("word/document.xml").decode("utf-8")
ok("multi-run paragraph merged into first run",
   "ONE TWO THREE" in xml3 and "two" not in xml3 and "three" not in xml3)

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
