"""文档翻译 doc_translate：段落拆分/重建、SRT 解析/重建、扩展名校验。
不需要 xvfb。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import doc_translate as d

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


# ---- 1. 段落拆分 ----
ok("split basic", d.split_paragraphs("第一段\n\n第二段\n\n第三段") == ["第一段", "第二段", "第三段"])
ok("split multi-line para", d.split_paragraphs("第一行\n第二行\n\n下一段") == ["第一行\n第二行", "下一段"])
ok("split ignores blank-only", d.split_paragraphs("\n\n\n  \n\n") == [])
ok("split no trailing newline", d.split_paragraphs("A\n\nB") == ["A", "B"])
ok("split single para", d.split_paragraphs("只有一段") == ["只有一段"])
ok("split empty", d.split_paragraphs("") == [])

# ---- 2. 重建：identity 逐字还原 ----
for text in ("第一段\n\n第二段\n\n第三段",
             "第一段\n\n第二段\n\n第三段\n",
             "\n\n第一段\n\n\n第二段\n",
             "第一行\n第二行\n\n下一段",
             "A\n\nB",
             "只有一段",
             "",
             "  前有空格\n\n后有空格  \n"):
    paras = d.split_paragraphs(text)
    ok("rebuild identity %r" % text[:20], d.rebuild_paragraphs(paras, text) == text)
ok("rebuild translated keeps blanks",
   d.rebuild_paragraphs(["一", "二"], "第一段\n\n\n第二段\n") == "一\n\n\n二\n")
try:
    d.rebuild_paragraphs(["only one"], "A\n\nB")
    ok("rebuild mismatched count raises", False)
except ValueError:
    ok("rebuild mismatched count raises", True)

# ---- 3. 按段落翻译 ----
prog = []
out = d.translate_paragraphs("你好\n\n世界", lambda p: "译:" + p,
                             progress=lambda a, b: prog.append((a, b)))
ok("translate_paragraphs", out == "译:你好\n\n译:世界" and prog == [(1, 2), (2, 2)])

# ---- 4. SRT 解析 / 重建往返 ----
SRT = ("1\n00:00:01,000 --> 00:00:04,000\nHello world\n\n"
       "2\n00:00:05,000 --> 00:00:08,500\nHow are you?\nNice to meet you.\n")
blocks = d.srt_parse(SRT)
ok("srt_parse count", len(blocks) == 2)
ok("srt_parse first", blocks[0] == {"index": 1, "times": "00:00:01,000 --> 00:00:04,000",
                                    "text": "Hello world"})
ok("srt_parse multi-line cue", blocks[1]["text"] == "How are you?\nNice to meet you.")
ok("srt_rebuild round-trips exactly", d.srt_rebuild(blocks) == SRT)
ok("srt_parse skips bad blocks",
   d.srt_parse("xx\n00:00:01,000 --> 00:00:04,000\nbad\n\n"
               "3\nnot-a-time\nbad\n\n"
               "4\n00:00:09,000 --> 00:00:10,000\nGood\n") == [
       {"index": 4, "times": "00:00:09,000 --> 00:00:10,000", "text": "Good"}])
ok("srt_parse CRLF", len(d.srt_parse(SRT.replace("\n", "\r\n"))) == 2)
out = d.srt_translate(SRT, lambda t: "译:" + t.replace("\n", "/"))
ok("srt_translate keeps index+times",
   out.startswith("1\n00:00:01,000 --> 00:00:04,000\n译:Hello world\n\n2\n")
   and "译:How are you?/Nice to meet you." in out)

# ---- 5. 扩展名校验 ----
for p, want in (("a.txt", True), ("a.MD", True), ("a.srt", True),
                ("a.docx", False), ("a.pdf", False), ("a.png", False),
                ("a.png", False), ("noext", False), ("", False)):
    ok("doc ext %s -> %s" % (p, want), d.supported_doc_ext(p) is want)
for p, want in (("a.png", True), ("a.JPG", True), ("a.jpeg", True),
                ("a.bmp", True), ("a.tif", True), ("a.tiff", True),
                ("a.gif", False), ("a.webp", False), ("a.txt", False)):
    ok("image ext %s -> %s" % (p, want), d.supported_image_ext(p) is want)

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
