"""窗口最小宽度必须装得下选项区 / 按钮行（回归：右侧复选框、「范围」、「退出」被裁掉）。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import desktop_translator as dt

ok_all = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    ok_all.append(bool(cond))


app = dt.App()
app.root.update()
need = max(w.winfo_reqwidth() for w in app._fit_rows) + 28
minw = app.root.minsize()[0]
ok("minsize covers widest row (%d >= %d)" % (minw, need), minw >= need)
ok("window not narrower than minsize", app.root.winfo_width() >= minw)

# 已存的过窄宽度要被撑开
app.root.geometry("400x600+50+50")
app._fit_min_width()
app.root.update()
ok("narrow saved width widened", app.root.winfo_width() >= minw)

# 每个选项行的右边缘都在窗口内
app.root.update()
right = app.root.winfo_width()
rows_in = True
for row in app._fit_rows[3].winfo_children():
    for w in row.winfo_children():
        if w.winfo_rootx() + w.winfo_width() > app.root.winfo_rootx() + right:
            rows_in = False
ok("all option widgets inside window", rows_in)
app.root.destroy()
print("ALL OK" if all(ok_all) else "FAILED")
sys.exit(0 if all(ok_all) else 1)
