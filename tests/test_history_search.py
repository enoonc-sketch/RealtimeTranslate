"""v2.8 历史搜索：filter_history 纯函数（不筛库、不碰界面）。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import history_store as hs

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


ROWS = [
    {"src": "Hello world", "dst": "你好，世界"},
    {"src": "apple pie", "dst": "苹果派"},
    {"src": "色谱仪", "dst": "chromatograph"},
    {"src": "Maxum II 分析", "dst": "Maxum II analysis"},
]

ok("empty query returns all", hs.filter_history(ROWS, "") == ROWS)
ok("None query returns all", hs.filter_history(ROWS, None) == ROWS)
ok("whitespace query returns all", hs.filter_history(ROWS, "   ") == ROWS)
ok("substring in src", hs.filter_history(ROWS, "hello") == [ROWS[0]])
ok("substring in dst", hs.filter_history(ROWS, "苹果") == [ROWS[1]])
ok("case-insensitive", hs.filter_history(ROWS, "HELLO") == [ROWS[0]])
ok("case-insensitive dst", hs.filter_history(ROWS, "CHROMATOGRAPH") == [ROWS[2]])
ok("CJK query", hs.filter_history(ROWS, "色谱") == [ROWS[2]])
ok("whole query is one substring, not split words",
   hs.filter_history(ROWS, "maxum ii") == [ROWS[3]])
ok("no match", hs.filter_history(ROWS, "不存在") == [])
ok("empty entries", hs.filter_history([], "x") == [])
ok("None entries", hs.filter_history(None, "x") == [])
ok("does not mutate input", hs.filter_history(ROWS, "apple") == [ROWS[1]]
   and len(ROWS) == 4)
ok("leading/trailing spaces stripped", hs.filter_history(ROWS, "  apple  ") == [ROWS[1]])
ok("matches src or dst either side",
   len(hs.filter_history(ROWS, "maxum")) == 1 and
   hs.filter_history(ROWS, "maxum")[0] is ROWS[3])

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
