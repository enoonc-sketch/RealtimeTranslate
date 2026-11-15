"""文档翻译 / 图片翻译 / 生词本 / 界面字号：xvfb 下跑 App。"""
import json
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import desktop_translator as dt

tmp = tempfile.mkdtemp()
dt.DATA_DIR = os.path.join(tmp, "data")
dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.HISTORY_PATH = os.path.join(dt.DATA_DIR, "history.db")
dt.CACHE.clear()
dt.g_translate = lambda t, sl, tl: ("译:" + t[:20], "en")

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def pump(sec, until=None):
    end = time.time() + sec
    while time.time() < end:
        app.root.update()
        time.sleep(0.02)
        if until and until():
            return True
    return bool(until and until())


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


app = dt.App()
r = app.root
app.root.update()

# ---- 1. 文档翻译 .txt：段落结构保留，默认保存路径，载入主窗口 + 存历史 ----
doc_path = os.path.join(tmp, "notes.txt")
open(doc_path, "w", encoding="utf-8").write("Hello world\n\nGood morning\n")
out_path = os.path.join(tmp, "notes-译文.txt")
real_fd = dt.filedialog
dt.filedialog.askopenfilename = lambda *a, **k: doc_path
dt.filedialog.asksaveasfilename = lambda *a, **k: out_path
try:
    app._translate_doc_file()
    ok("doc txt finishes", pump(5, lambda: os.path.exists(out_path)))
    got = open(out_path, encoding="utf-8").read()
    ok("doc txt keeps blank line + translates paras",
       got == "译:Hello world\n\n译:Good morning")
    ok("doc txt loaded into main window",
       "Hello world" in app.src.get("1.0", "end") and "译:Hello world" in app.plain_result())
    ok("doc txt saved to history as doc",
       any(row["kind"] == "doc" for row in app.history.search("", False, limit=10)))
    ok("doc status mentions done", "文档翻译完成" in app.status.cget("text"))
finally:
    dt.filedialog = real_fd

# ---- 2. 文档翻译 .srt：序号与时间轴原样保留 ----
srt_path = os.path.join(tmp, "sub.srt")
open(srt_path, "w", encoding="utf-8").write(
    "1\n00:00:01,000 --> 00:00:04,000\nHello world\n\n"
    "2\n00:00:05,000 --> 00:00:08,500\nGood morning\n")
srt_out = os.path.join(tmp, "sub-译文.srt")
dt.filedialog.askopenfilename = lambda *a, **k: srt_path
dt.filedialog.asksaveasfilename = lambda *a, **k: srt_out
try:
    app._translate_doc_file()
    ok("doc srt finishes", pump(5, lambda: os.path.exists(srt_out)))
    got = open(srt_out, encoding="utf-8").read()
    ok("doc srt keeps index+times, translates text only",
       got == "1\n00:00:01,000 --> 00:00:04,000\n译:Hello world\n\n"
              "2\n00:00:05,000 --> 00:00:08,500\n译:Good morning\n")
finally:
    dt.filedialog = real_fd

# ---- 3. v2.7：.docx 现在支持（走通一次）；v2.8：.pdf 也支持（输出 -译文.txt） ----
import zipfile
docx_path = os.path.join(tmp, "x.docx")
with zipfile.ZipFile(docx_path, "w") as z:
    z.writestr("word/document.xml", b'<w:document xmlns:w="urn:docx"><w:body><w:p><w:r><w:t>Hello world</w:t></w:r></w:p><w:p><w:r><w:t>Good morning</w:t></w:r></w:p></w:body></w:document>')
    z.writestr("[Content_Types].xml", b"<Types/>")
docx_out = os.path.join(tmp, "x-\u8bd1\u6587.docx")
dt.filedialog.askopenfilename = lambda *a, **k: docx_path
dt.filedialog.asksaveasfilename = lambda *a, **k: docx_out
try:
    app._translate_doc_file()
    ok("doc docx finishes", pump(5, lambda: os.path.exists(docx_out)))
    import doc_translate as _d
    with zipfile.ZipFile(docx_out) as z:
        _texts = _d.docx_paragraph_texts(z.read("word/document.xml"))
    ok("doc docx translates paragraphs", _texts == ["\u8bd1:Hello world", "\u8bd1:Good morning"])
finally:
    dt.filedialog = real_fd

# v2.8 PDF：一页带 Tj 文字 → 翻成 -译文.txt；一页没文字 → 提示改用截图翻译
def _mini_pdf(body):
    stream = b"BT /F1 12 Tf 72 720 Td " + body + b" Tj ET\n"
    head = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R"
            b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n")
    tail = (b"endstream\nendobj\n"
            b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
            b"trailer<</Root 1 0 R>>\n%%EOF\n")
    return head + b"4 0 obj<</Length %d>>stream\n" % len(stream) + stream + tail


pdf_path = os.path.join(tmp, "x.pdf")
open(pdf_path, "wb").write(_mini_pdf(b"(Hello PDF world)"))
pdf_out = os.path.join(tmp, "x-\u8bd1\u6587.txt")
dt.filedialog.askopenfilename = lambda *a, **k: pdf_path
dt.filedialog.asksaveasfilename = lambda *a, **k: pdf_out
try:
    app._translate_doc_file()
    ok("doc pdf finishes as txt", pump(5, lambda: os.path.exists(pdf_out)))
    ok("doc pdf translates text",
       open(pdf_out, encoding="utf-8").read() == "\u8bd1:Hello PDF world")
finally:
    dt.filedialog = real_fd
empty_pdf = os.path.join(tmp, "empty.pdf")
open(empty_pdf, "wb").write(_mini_pdf(b""))
dt.filedialog.askopenfilename = lambda *a, **k: empty_pdf
try:
    app._translate_doc_file()      # v2.10：读 / 解析在后台线程，提示通过队列回来，要等一下
    ok("pdf with no text points at screenshot translation",
       pump(5, lambda: "\u622a\u56fe\u7ffb\u8bd1" in app.status.cget("text")))
finally:
    dt.filedialog = real_fd

# ---- 4. 图片翻译：mock OCR 走通一次；非 Windows 报不可用 ----
img_path = os.path.join(tmp, "shot.png")
open(img_path, "wb").write(b"\x89PNG\r\n\x1a\n")
real_is_win = dt.IS_WIN
real_ocr = dt.ocr_win.ocr_image
dt.filedialog.askopenfilename = lambda *a, **k: img_path
try:
    dt.IS_WIN = True
    dt.ocr_win.ocr_image = lambda path, lang=None: "hello image"
    dt.ocr_win.ocr_available = lambda: True
    app._translate_image_file()
    ok("image ocr flows into main window",
       pump(5, lambda: "hello image" in app.src.get("1.0", "end")
            and app.plain_result().startswith("译:")))
    ok("image result saved as image kind",
       any(row["kind"] == "image" for row in app.history.search("hello image", False, limit=10)))
    # 非 Windows：不调 OCR，只报状态
    dt.IS_WIN = False
    called = []
    dt.ocr_win.ocr_image = lambda *a, **k: called.append(1) or "x"
    app._translate_image_file()
    ok("image on linux: windows-only status, ocr not called",
       "只在 Windows 上可用" in app.status.cget("text") and called == [])
finally:
    dt.IS_WIN = real_is_win
    dt.ocr_win.ocr_image = real_ocr
    dt.filedialog = real_fd

# ---- 5. 生词本：只看单词过滤 ----
app.history.add("hello", "你好", "en", "zh-CN", "Google", "main", "en", "zh-CN")
app.history.add("hello world", "你好世界", "en", "zh-CN", "Google", "main", "en", "zh-CN")
app.history.add("你好", "Hello", "zh-CN", "en", "Google", "main", "zh-CN", "en")
app.history.add("a b c d", "甲乙丙丁", "en", "zh-CN", "Google", "main", "en", "zh-CN")
app.open_vocab()
app.root.update()
shown = [app.hist_tv.item(i)["values"][1] for i in app.hist_tv.get_children()]
ok("vocab shows only word entries", set(shown) == {"hello", "你好"})
ok("vocab checkbox is on", app.hist_word_only.get() is True)
app.hist_word_only.set(False)
app._hist_refresh()
shown = [app.hist_tv.item(i)["values"][1] for i in app.hist_tv.get_children()]
ok("unchecking shows all again", "hello world" in shown)
app.hist_win.withdraw()

# ---- 6. 词典区：Google 响应 fixture + 单词候选 ----
app.engine.set("Google")
app._set_src("hello")
app.seq += 1
my = app.seq
dt._LAST_GOOGLE.update(text="hello", sl="auto", tl="zh-CN", data=[
    [["你好", "hello", None, None]],
    [["interjection", ["你好", "喂"]], ["noun", ["招呼"]]],
    "en"])
app._req = (my, "hello", "auto", "zh-CN", "main")
app.pairs = [("hello", "你好")]
app._update_dict_area()
app.root.update()
ok("dict area shows entries",
   app.dict_frame.winfo_ismapped() and "你好" in app.dict_label.cget("text")
   and "感叹词" not in app.dict_label.cget("text") and "interjection" in app.dict_label.cget("text"))
# 解析不到 → 隐藏
dt._LAST_GOOGLE.update(text="hello", sl="auto", tl="zh-CN", data=[
    [["你好", "hello", None, None]], None, "en"])
app._update_dict_area()
ok("dict area hides when nothing parsed", not app.dict_frame.winfo_ismapped())
# 长句不是候选 → 隐藏
app._req = (my, "this is a very long sentence for translation", "auto", "zh-CN", "main")
app._update_dict_area()
ok("dict area hides for long text", not app.dict_frame.winfo_ismapped())
# 非 Google 引擎 → 隐藏
app.engine.set("微软")
app._req = (my, "hello", "auto", "zh-CN", "main")
app._update_dict_area()
ok("dict area hides for non-Google engine", not app.dict_frame.winfo_ismapped())
app.engine.set("Google")

# ---- 7. 语音输入：非 Windows 报不可用；按钮存在 ----
ok("voice button exists", any(w.winfo_class() == "TButton" and w.cget("text") == "🎤 语音输入"
                              for w in walk(app.root) if w.winfo_toplevel() is app.root))
app.start_voice_input()
ok("voice on linux: windows-only status", "只在 Windows 上可用" in app.status.cget("text")
   and not app._stt_busy)
# mock 走通：Windows + 识别到文字 → 填进原文框并翻译
real_stt = dt.stt_win
dt.IS_WIN = True
dt.stt_win.is_available = lambda: True
dt.stt_win.recognize = lambda lang: ("ok", "voice hello")
try:
    app.start_voice_input()
    ok("voice recognized text flows into main window",
       pump(5, lambda: "voice hello" in app.src.get("1.0", "end")
            and app.plain_result().startswith("译:")))
finally:
    dt.IS_WIN = real_is_win
    dt.stt_win = real_stt

# ---- 8. 界面字号 ----
def font_size(w):
    return int(str(w.cget("font")).split()[-1]) if isinstance(w.cget("font"), str) else w.cget("font")[1]
app.font_size_var.set(16)
app._on_font_size()
ok("font size applies to src/dst", font_size(app.src) == 16 and font_size(app.dst) == 16)
ok("font size saved", json.load(open(dt.CONFIG_PATH))["font_size"] == 16)
app.font_size_var.set(99)
app._on_font_size()
ok("font size clamped to 18", app.cfg["font_size"] == 18 and font_size(app.src) == 18)
dt.messagebox.askyesno = lambda *a, **k: True
app._reset_settings()
ok("reset restores font size 11", app.cfg["font_size"] == 11 and font_size(app.src) == 11
   and json.load(open(dt.CONFIG_PATH))["font_size"] == 11)

app.root.destroy()
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
