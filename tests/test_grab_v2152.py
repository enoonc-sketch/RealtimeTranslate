"""v2.15.2 取词优化：去标点、最贴合的词、中文连词、手抖容差；附随机压测（稳定性）。"""
import os, sys, random
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
import ocr_win
W = lambda t, x, y, w=40, h=20: {"text": t, "x": x, "y": y, "w": w, "h": h}
res = []
def ok(n, c): print(("PASS " if c else "FAIL ") + n); res.append(bool(c))
ok("strip punct", ocr_win.pick_word_at([W("Hello,", 0, 0), W("world.", 50, 0)], 60, 10) == "world")
ok("smallest box wins", ocr_win.pick_word_at([W("big", 0, 0, 200, 60), W("in", 10, 10, 20, 20)], 15, 15) == "in")
ok("cjk run", ocr_win.pick_word_at([W("翻", 0, 0, 20, 20), W("译", 22, 0, 20, 20), W("器", 44, 0, 20, 20),
                                    W("远", 200, 0, 20, 20)], 30, 10) == "翻译器")
ok("blank None", ocr_win.pick_word_at([W("  ", 0, 0)], 5, 5) is None)
ok("brackets", ocr_win.pick_word_at([W("(test)", 0, 0)], 10, 10) == "test")
ok("only punct kept", ocr_win.clean_word("...") == "...")
random.seed(1); bad = 0
for _ in range(20000):
    ws = [W(random.choice(["a", "中", "，", "x.y", "", "日本"]), random.randint(-50, 500), random.randint(-50, 300),
            random.randint(0, 80), random.randint(0, 40)) for _ in range(random.randint(0, 30))]
    try:
        ocr_win.pick_word_at(ws, random.randint(-100, 600), random.randint(-100, 400))
    except Exception:
        bad += 1
ok("fuzz 20000 rounds no exception", bad == 0)
src = open(os.path.join(os.path.dirname(HERE), "desktop_translator.py"), encoding="utf-8").read()
ok("hover jitter tolerance", "> 3 or abs(pos[1] - last[1]) > 3" in src)
assert all(res), "some tests failed"
