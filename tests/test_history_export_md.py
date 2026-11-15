"""翻译历史导出 .md（v2.9.0 新增）。

格式：标题 + 导出时间/条数，按日期分组（新日期在前），每条原文 +
译文 + 语言/引擎/来源（收藏带 ★）。复用已有的 export(path, rows)
入口：界面上的“导出”对话框里选 .md 就走这条；.csv/.txt/.json/
.tsv 原样不动。
"""
import os
import sqlite3
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from history_store import HistoryStore

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


tmp = tempfile.mkdtemp(prefix="rt29-md-")
store = HistoryStore(os.path.join(tmp, "history.db"))
store.add("hello", "你好", sl="en", tl="zh-CN", engine="Google", kind="main")
store.add("good morning", "早上好", sl="en", tl="zh-CN", engine="Google", kind="main")
rid = store.add("thank you", "谢谢", sl="en", tl="zh-CN", engine="微软", kind="hover")
store.set_fav(rid, True)
# 把第三条的 ts 改到昨天，验证按日期分组
yesterday = time.time() - 86400
with sqlite3.connect(os.path.join(tmp, "history.db")) as c:
    c.execute("UPDATE history SET ts=? WHERE id=?", (yesterday, rid))
    c.commit()

today = time.strftime("%Y-%m-%d", time.localtime())
yday = time.strftime("%Y-%m-%d", time.localtime(yesterday))

md_path = os.path.join(tmp, "history.md")
n = store.export(md_path)
text = open(md_path, encoding="utf-8").read()
ok("export .md returns 3", n == 3)
ok("md has title", text.startswith("# 翻译记录"))
ok("md has count", "共 3 条" in text)
ok("md has today heading", ("## " + today) in text)
ok("md has yesterday heading", ("## " + yday) in text)
ok("md newest date first",
   ("## " + today) in text and ("## " + yday) in text
   and text.index("## " + today) < text.index("## " + yday))
ok("md has all sources", "hello" in text and "good morning" in text and "thank you" in text)
ok("md has all translations", "你好" in text and "早上好" in text and "谢谢" in text)
ok("md marks favorite", "★" in text)
ok("md has engine/source meta", "Google" in text and "微软" in text and "悬停取词" in text)
ok("md has language meta", "en → zh-CN" in text)

# 只导指定 rows
rows = store.search("hello")
md2 = os.path.join(tmp, "one.md")
n2 = store.export(md2, rows)
text2 = open(md2, encoding="utf-8").read()
ok("export subset returns 1", n2 == 1)
ok("subset md only has hello", "hello" in text2 and "good morning" not in text2)

# 空库
store2 = HistoryStore(os.path.join(tmp, "empty.db"))
md3 = os.path.join(tmp, "empty.md")
n3 = store2.export(md3)
text3 = open(md3, encoding="utf-8").read()
ok("export empty returns 0", n3 == 0)
ok("empty md still has title", text3.startswith("# 翻译记录"))
ok("empty md has no date heading", "\n## " not in text3)

# 旧格式不受影响：.txt 还是老样子
txt_path = os.path.join(tmp, "history.txt")
n4 = store.export(txt_path)
text4 = open(txt_path, encoding="utf-8").read()
ok("export .txt still works", n4 == 3 and "hello" in text4 and "你好" in text4)

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
