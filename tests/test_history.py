"""翻译历史：存储模块 + 主程序接入（自动保存 / 翻译记忆 / 收藏 / 历史窗口 / 导出）。需 xvfb。"""
import csv
import json
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import history_store as hs
import desktop_translator as dt

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


tmpd = tempfile.mkdtemp()

# ---------- 1. 存储模块 ----------
h = hs.HistoryStore(os.path.join(tmpd, "a.db"), max_items=3)
a = h.add("hello", "你好", "en", "zh-CN", "Google", "main", "auto", "zh-CN")
ok("add returns id", isinstance(a, int))
b = h.add("hello", "您好", "en", "zh-CN", "微软", "hover", "auto", "zh-CN")
ok("same key dedups (one row, count 2, newest dst)", b == a and h.count() == 1 and h.get(a)["count"] == 2
   and h.get(a)["dst"] == "您好" and h.get(a)["kind"] == "hover")
ok("add empty -> None", h.add("", "x") is None and h.add("x", "  ") is None)
h.set_fav(a, True)
for i in range(6):
    h.add("t%d" % i, "译%d" % i, "en", "zh-CN", "G", "main", "auto", "zh-CN")
    time.sleep(0.002)
rows = h.search()
ok("prune keeps newest 3 non-favs + the favourite", h.count() == 4 and any(r["id"] == a for r in rows)
   and [r["src"] for r in rows if not r["fav"]] == ["t5", "t4", "t3"])
ok("search by term in src or dst", [r["src"] for r in h.search("译4")] == ["t4"] and [r["src"] for r in h.search("T4")] == ["t4"])
ok("search AND of terms", h.search("t5 译5") != [] and h.search("t5 译4") == [])
ok("search escapes % and _", h.search("100%") == [] and h.search("a_b") == [])
ok("fav_only", [r["src"] for r in h.search(fav_only=True)] == ["hello"])
ok("find with auto source ignores source lang", h.find("hello", "auto", "zh-CN")["id"] == a)
ok("find respects target language", h.find("hello", "auto", "en") is None)
ok("lookup returns dst", h.lookup("hello", "auto", "zh-CN") == "您好")
ok("delete", h.delete([a]) == 1 and h.get(a) is None)
h.add("keep", "留", "en", "zh-CN", "G", "main", "auto", "zh-CN", fav=True)
n = h.clear(keep_fav=True)
ok("clear keeps favourites", h.count() == 1 and h.search()[0]["src"] == "keep" and n >= 1)
ok("clear(keep_fav=False) wipes all", h.clear(keep_fav=False) == 1 and h.count() == 0)

# 导出
h.add("你好 世界", "Hello, \"world\"\n第二行", "zh-CN", "en", "Google", "screenshot", "auto", "en", fav=True)
for ext in (".csv", ".txt", ".json"):
    p = os.path.join(tmpd, "x" + ext)
    ok("export %s" % ext, h.export(p) == 1 and os.path.getsize(p) > 0)
with open(os.path.join(tmpd, "x.csv"), encoding="utf-8-sig", newline="") as f:
    rws = list(csv.reader(f))
ok("csv utf-8-sig, header + quoted multiline round trip", rws[0][0] == "时间" and rws[1][2] == 'Hello, "world"\n第二行'
   and rws[1][6] == "截图翻译" and rws[1][7] == "★")
ok("json fields", json.load(open(os.path.join(tmpd, "x.json"), encoding="utf-8"))[0]["favorite"] is True)
try:
    h.export(os.path.join(tmpd, "nope", "dir", "x.csv"))
    ok("export to bad path raises OSError", False)
except OSError:
    ok("export to bad path raises OSError", True)

# 坏路径 / 坏库：绝不抛异常
bad = hs.HistoryStore(os.path.join(tmpd, "a.db", "sub", "x.db"))     # a.db 是文件，不能当目录
ok("unwritable store never raises", bad.add("a", "b") is None and bad.search() == [] and bad.count() == 0
   and bad.lookup("a") is None and bad.clear() == 0)
corrupt = os.path.join(tmpd, "corrupt.db")
open(corrupt, "wb").write(b"this is not sqlite" * 50)
cs = hs.HistoryStore(corrupt)
ok("corrupt db never raises", cs.add("a", "b") is None and cs.search() == [])

# 并发写
cc = hs.HistoryStore(os.path.join(tmpd, "c.db"), max_items=0)
ths = [threading.Thread(target=lambda k=k: [cc.add("s%d-%d" % (k, i), "d") for i in range(25)]) for k in range(6)]
[t.start() for t in ths]
[t.join() for t in ths]
ok("concurrent adds from 6 threads all stored", cc.count() == 150)

# ---------- 2. 主程序接入 ----------
app = dt.App()
app.root.update()
app.history = hs.HistoryStore(os.path.join(tmpd, "app.db"), max_items=2000)
app.cfg["history_on"] = True

# 主窗口翻译结果 -> 自动保存
app.seq += 1
my = app.seq
app._req = (my, "hello world", "auto", "zh-CN", "main")
app.pairs = [("hello world", "你好，世界")]
app._hist_save_main(my, "en", "zh-CN", "Google")
r = app.history.find("hello world", "auto", "zh-CN")
ok("main result auto-saved", r and r["dst"] == "你好，世界" and r["sl"] == "en" and r["engine"] == "Google" and r["kind"] == "main")
app.cfg["history_on"] = False
app._req = (my, "off", "auto", "zh-CN", "main"); app.pairs = [("off", "关")]
app._hist_save_main(my, "en", "zh-CN", "Google")
ok("history_on off -> nothing saved", app.history.find("off", "auto", "zh-CN") is None)
app.cfg["history_on"] = True

# 气泡 worker（悬停 / 指针）保存，来源区分
dt.translate = lambda text, sl, tl, smart, engine, cancelled=None: ("译:" + text, "en", "zh-CN")
app.bseq += 1
app._bubble_worker(app.bseq, "pointer text", "auto", "zh-CN", True, "Google", "hover")
r = app.history.find("pointer text", "auto", "zh-CN")
ok("bubble worker saves with kind=hover", r and r["kind"] == "hover" and r["dst"] == "译:pointer text")
while not app.q.empty():
    app.q.get_nowait()

# 翻译记忆
app.cfg["history_reuse"] = False
ok("reuse off -> no hit", app._hist_reuse_main(app.seq, "hello world", "auto", "zh-CN") is False)
app.cfg["history_reuse"] = True
app.seq += 1
ok("reuse on -> hit", app._hist_reuse_main(app.seq, "hello world", "auto", "zh-CN") is True)
msg = app.q.get_nowait()
ok("reuse queues a result with stored text", msg[0] == "result" and msg[2] is True and msg[3][0] == [("hello world", "你好，世界")])
ok("reuse marks result as from-history", app._from_hist == app.seq)
ok("reuse miss for other target language", app._hist_reuse_main(app.seq, "hello world", "auto", "ja") is False)
app.cfg["history_reuse"] = False

# 收藏
app.pairs = [("hello world", "你好，世界")]
app._req = (app.seq, "hello world", "auto", "zh-CN", "main")
app.favorite_current()
ok("favorite_current stars the row", app.history.find("hello world", "auto", "zh-CN")["fav"] == 1)
app.favorite_current()
ok("favorite_current again un-stars", app.history.find("hello world", "auto", "zh-CN")["fav"] == 0)
app.pairs = []
app.favorite_current()
ok("favorite with nothing to save says so", "没有可收藏" in app.status.cget("text"))

# 历史窗口
app.history.clear(keep_fav=False)
for i, (s_, d_) in enumerate((("apple", "苹果"), ("banana", "香蕉"), ("cherry", "樱桃"))):
    app.history.add(s_, d_, "en", "zh-CN", "Google", "main", "auto", "zh-CN", fav=(i == 1))
    time.sleep(0.002)
app.open_history()
app.root.update()
ok("history window lists all rows newest first", list(app.hist_tv.get_children()) ==
   [str(r["id"]) for r in app.history.search()] and len(app.hist_tv.get_children()) == 3)
app.hist_q.set("香蕉")
app._hist_refresh()
ok("search filters", [app.hist_rows[i]["src"] for i in app.hist_tv.get_children()] == ["banana"])
app.hist_q.set("")
app.hist_fav.set(True)
app._hist_refresh()
ok("only-favourites filter", [app.hist_rows[i]["src"] for i in app.hist_tv.get_children()] == ["banana"])
app.hist_fav.set(False)
app._hist_refresh()
iid = [i for i in app.hist_tv.get_children() if app.hist_rows[i]["src"] == "cherry"][0]
app.hist_tv.selection_set(iid)
app._hist_on_select()
ok("detail shows source + translation", "cherry" in app.hist_detail.get("1.0", "end") and "樱桃" in app.hist_detail.get("1.0", "end"))
app._hist_load()
ok("load puts text into main window without retranslating",
   app.src.get("1.0", "end").strip() == "cherry" and app.plain_result() == "樱桃" and "来自历史记录" in app.status.cget("text"))
app._hist_toggle_fav()
ok("toggle fav from window", app.history.find("cherry", "auto", "zh-CN")["fav"] == 1)
app._set_clip = lambda t: setattr(app, "_clip", t)
app._hist_copy()
ok("copy translation from window", app._clip == "樱桃")

dt.messagebox.askyesno = lambda *a, **k: True
dt.messagebox.showinfo = lambda *a, **k: None
dt.messagebox.showerror = lambda *a, **k: None
app.hist_tv.selection_set(iid)
app._hist_delete()
ok("delete selected", app.history.find("cherry", "auto", "zh-CN") is None and app.history.count() == 2)

out = os.path.join(tmpd, "out.csv")
dt.filedialog.asksaveasfilename = lambda **k: out
app._hist_export(None)
ok("export all via dialog", os.path.exists(out) and len(open(out, encoding="utf-8-sig").read().splitlines()) == 3)
dt.filedialog.asksaveasfilename = lambda **k: ""
os.remove(out)
app._hist_export(None)
ok("export cancelled writes nothing", not os.path.exists(out))

app._hist_clear()
ok("clear keeps favourites", app.history.count() == 1 and app.history.search()[0]["src"] == "banana")

# 设置：保存上限 / 开关
app.history_max_var.set(50)
app._on_history_opt()
ok("history_max applied to store + config", app.history.max_items == 100 and json.load(open(dt.CONFIG_PATH))["history_max"] == 100)
app.history_on_var.set(False)
app._on_history_opt()
ok("history_on saved", json.load(open(dt.CONFIG_PATH))["history_on"] is False)
app.history_on_var.set(True)
app._on_history_opt()

app.root.destroy()
print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
