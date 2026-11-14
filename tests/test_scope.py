"""悬停 / 指针取词的「单词 / 整行 / 整段」范围：OCR 行分组是纯逻辑，Linux 上就能测。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import ocr_win
import desktop_translator as dt

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def L(text, x, y, w=300, h=16):
    return {"text": text, "x": x, "y": y, "w": w, "h": h}


# 一页：标题 + 两段英文（段间空行）+ 一段中文 + 右侧另一栏
lines = [
    L("Installation", 10, 10, 160, 32),                       # 0 标题（字号大）
    L("The quick brown fox jumps over", 10, 60),              # 1 ┐
    L("the lazy dog and keeps running", 10, 80),              # 2 │ 第一段
    L("far away from the trans-", 10, 100, 220),              # 3 │
    L("lation office.", 10, 120, 100),                        # 4 ┘
    L("Second paragraph starts here.", 10, 160),              # 5 第二段（段间距 20 > 0.75*16）
    L("这是一段中文，", 10, 220, 200),                         # 6 ┐ 中文段
    L("没有空格分词。", 10, 240, 160),                         # 7 ┘
    L("Right column text one", 420, 60),                      # 8 右栏，和 1 同一行
    L("Right column text two", 420, 80),                      # 9
]

# 取行
ok("line: pointer inside line 2", ocr_win.pick_text_at(lines, 50, 88, "line") == "the lazy dog and keeps running")
ok("line: pointer just below text still picks it", ocr_win.pick_text_at(lines, 50, 100 - 2, "line") in
   ("the lazy dog and keeps running", "far away from the trans-"))
ok("line: far from everything -> None", ocr_win.pick_text_at(lines, 700, 500, "line") is None)
ok("line: empty -> None", ocr_win.pick_text_at([], 5, 5, "line") is None)

# 取段落
para1 = ocr_win.pick_text_at(lines, 50, 88, "paragraph")
ok("paragraph: 4 lines merged, hyphen join no space",
   para1 == "The quick brown fox jumps over the lazy dog and keeps running far away from the trans-lation office.")
ok("paragraph: stops at blank gap (second para alone)",
   ocr_win.pick_text_at(lines, 50, 168, "paragraph") == "Second paragraph starts here.")
ok("paragraph: heading not merged with body (font size differs)",
   ocr_win.pick_text_at(lines, 50, 20, "paragraph") == "Installation")
ok("paragraph: CJK joined without space",
   ocr_win.pick_text_at(lines, 50, 248, "paragraph") == "这是一段中文，没有空格分词。")
ok("paragraph: right column not merged with left",
   ocr_win.pick_text_at(lines, 430, 68, "paragraph") == "Right column text one Right column text two")
ok("paragraph indices sorted top->bottom", ocr_win.paragraph_indices(lines, 3) == [1, 2, 3, 4])
ok("join_lines english uses space", ocr_win.join_lines(["a b", "c d"]) == "a b c d")
ok("join_lines skips empty", ocr_win.join_lines(["", " x ", None, "y"]) == "x y")

# 配置 / 动作
ok("scope names", list(dt.SCOPE_NAMES) == ["word", "line", "paragraph"])
ok("plan: I-beam line", dt.pointer_plan(True, False, "line") == ["click3", "copy"])
ok("plan: I-beam word unchanged", dt.pointer_plan(True, False, "word") == ["click2", "copy"])

# 界面：范围下拉有三项；悬停 / 指针按所选范围走 OCR
app = dt.App()
ok("combobox has 3 scopes", list(app.scope_cb["values"]) == ["单词", "整行", "整段"])
ok("minsize still fits options", app.root.minsize()[0] >= max(w.winfo_reqwidth() for w in app._fit_rows))

calls = []
app._ocr_pick = lambda pos, scope: (calls.append((pos, scope)), "HELLO %s" % scope)[1]
app._hover_worker((100, 200), "line")
kind = app.q.get_nowait()
ok("hover worker passes scope + queues text", calls[-1] == ((100, 200), "line") and kind == ("hover_ocr", "HELLO line", (100, 200), False))

# 指针取词：整段走 OCR，不点击、结果进气泡
shown = []
app._pointer_translate = lambda text, xy: shown.append((text, xy))
app._get_clip = lambda: ""
app._set_clip = lambda t: None
dt.wait_keys_up_win = lambda keys: True
dt.click_here_win = lambda n: shown.append(("CLICK", n))
dt.send_copy_win = lambda: shown.append(("COPY",))
app.grab_mode, app.grab_xy, app.grab_scope, app.grabbing = "pointer", (5, 6), "paragraph", True
app.old_clip = ""
app._pointer_grab_win()
ok("pointer paragraph: OCR used, no click/copy", calls[-1] == ((5, 6), "paragraph") and shown == [])
app._on_copied()
ok("pointer paragraph: OCR text goes to bubble", shown == [("HELLO paragraph", (5, 6))])

# OCR 没取到 -> 退回三击 + Ctrl+C（只有 I 形光标才点）
shown.clear()
app._ocr_pick = lambda pos, scope: None
dt.cursor_is_ibeam_win = lambda: True
dt.foreground_is_terminal_win = lambda: False
app._seq0 = dt.clip_seq_win() if dt.IS_WIN else 0
dt.clip_seq_win = lambda: 0
app.grabbing = True
app._pointer_grab_win()
ok("pointer line: OCR miss falls back to triple-click + copy", shown == [("CLICK", 3), ("COPY",)])

# 单词范围不走 OCR（仍是双击）
shown.clear()
calls.clear()
app._ocr_pick = lambda pos, scope: (calls.append(scope), "x")[1]
app.grab_scope = "word"
app._pointer_grab_win()
ok("pointer word: still double-click, no OCR", shown == [("CLICK", 2), ("COPY",)] and calls == [])

app.root.destroy()
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
