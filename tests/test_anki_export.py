"""生词本导出 Anki (.tsv)：只导单词条目，每行「原文<TAB>译文」。"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import history_store

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


tmp = tempfile.mkdtemp()
store = history_store.HistoryStore(os.path.join(tmp, "history.db"), max_items=100)
store.add("apple", "苹果", "en", "zh-CN", "Google", "main", "en", "zh-CN")
store.add("Hello world", "你好世界", "en", "zh-CN", "Google", "main", "en", "zh-CN")
store.add("chromatograph", "色谱仪", "en", "zh-CN", "Google", "hover", "en", "zh-CN")
store.add("a b c d", "一二三四", "en", "zh-CN", "Google", "main", "en", "zh-CN")

path = os.path.join(tmp, "anki.tsv")
n = store.export(path)
ok("exports only word entries (2)", n == 2)
raw = open(path, encoding="utf-8").read()
lines = raw.splitlines()
ok("one line per word", len(lines) == 2)
ok("tab separated, no header",
   all("\t" in ln for ln in lines) and "时间" not in raw)
ok("word pair present", "apple\t苹果" in lines)
ok("hover word included", "chromatograph\t色谱仪" in lines)
ok("sentence excluded", "Hello world" not in raw and "a b c d" not in raw)
ok("no html in tsv", "<" not in raw and ">" not in raw)
ok("every row has exactly 2 columns",
   all(len(ln.split("\t")) == 2 for ln in lines))

# 全部是句子时导 0 条，但文件要能正常生成
store2 = history_store.HistoryStore(os.path.join(tmp, "h2.db"), max_items=100)
store2.add("only a sentence here", "只是一句话", "en", "zh-CN", "Google", "main", "en", "zh-CN")
p2 = os.path.join(tmp, "empty.tsv")
ok("no words -> 0 rows", store2.export(p2) == 0)
ok("empty tsv is an empty file", open(p2, encoding="utf-8").read() == "")

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
