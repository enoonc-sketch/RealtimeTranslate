"""术语表 JSON 导入 / 导出（纯函数，v2.8.0 新增）。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import glossary as g

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


# 往返：dump -> load 保持词对不变
pairs = [["Maxum II", "Maxum II"], ["cat", "猫"], ["hello", "你好"]]
text = g.dump_glossary_json(pairs)
loaded, skipped, err = g.load_glossary_json(text)
ok("round-trip preserves pairs", loaded == pairs and skipped == 0 and err is None)
ok("dump output is a JSON list of src/dst objects",
   isinstance(json.loads(text), list)
   and json.loads(text) == [{"src": "Maxum II", "dst": "Maxum II"},
                            {"src": "cat", "dst": "猫"},
                            {"src": "hello", "dst": "你好"}])
ok("dump keeps CJK unescaped (ensure_ascii=False)",
   "猫" in text and "你好" in text)

# 中文术语往返
cjk = [["色谱仪", "色谱仪"], ["分析仪表", "分析仪表"]]
loaded, skipped, err = g.load_glossary_json(g.dump_glossary_json(cjk))
ok("CJK terms round-trip", loaded == cjk and skipped == 0 and err is None)

# 格式错误的 JSON：不崩溃，返回 error 且 pairs 为空
loaded, skipped, err = g.load_glossary_json("{not json")
ok("malformed JSON returns error, not crash",
   loaded == [] and skipped == 0 and err is not None)
ok("malformed JSON error is a short string",
   isinstance(err, str) and 0 < len(err) < 100)
loaded, skipped, err = g.load_glossary_json("")
ok("empty string is malformed JSON",
   loaded == [] and skipped == 0 and err is not None)
loaded, skipped, err = g.load_glossary_json(None)
ok("None input returns error, not crash",
   loaded == [] and skipped == 0 and err is not None)

# 顶层不是列表
loaded, skipped, err = g.load_glossary_json('{"a": 1}')
ok("top-level dict returns error",
   loaded == [] and skipped == 0 and err is not None)
loaded, skipped, err = g.load_glossary_json('"just a string"')
ok("top-level string returns error",
   loaded == [] and skipped == 0 and err is not None)

# 重复 src 只留第一条，重复的计入 skipped
loaded, skipped, err = g.load_glossary_json(
    '[{"src": "a", "dst": "A"}, {"src": "a", "dst": "A2"}, {"src": "b", "dst": "B"}]')
ok("duplicate src kept once", loaded == [["a", "A"], ["b", "B"]])
ok("duplicate counted in skipped", skipped == 1 and err is None)

# 空 src / 空 dst 计入 skipped
loaded, skipped, err = g.load_glossary_json(
    '[{"src": "", "dst": "X"}, {"src": "y", "dst": ""}, {"src": "ok", "dst": "OK"}]')
ok("empty src/dst dropped", loaded == [["ok", "OK"]])
ok("empty src/dst counted in skipped", skipped == 2 and err is None)

# 超长词计入 skipped（MAX_TERM_LEN = 40）
loaded, skipped, err = g.load_glossary_json(
    json.dumps([{"src": "z" * 41, "dst": "Z"}, {"src": "ok", "dst": "OK"}],
               ensure_ascii=False))
ok("over-long term dropped", loaded == [["ok", "OK"]])
ok("over-long term counted in skipped", skipped == 1 and err is None)

# 非对象条目与缺 src/dst 的对象计入 skipped
loaded, skipped, err = g.load_glossary_json(
    '[{"src": "a", "dst": "A"}, "plain", 123, {"src": "b"}, {"dst": "D"}, null]')
ok("non-dict and missing-key entries dropped",
   loaded == [["a", "A"]])
ok("non-dict and missing-key entries counted in skipped",
   skipped == 5 and err is None)

# 空列表
loaded, skipped, err = g.load_glossary_json("[]")
ok("load of [] gives ([], 0, None)", loaded == [] and skipped == 0 and err is None)
ok("dump of empty gives []", g.dump_glossary_json([]) == "[]")
ok("dump of None gives []", g.dump_glossary_json(None) == "[]")
ok("dump of bad input gives []", g.dump_glossary_json(123) == "[]")

# dump 先清洗：重复 / 空 / 超长不进导出结果
out = g.dump_glossary_json([["a", "A"], ["a", "A2"], ["", "x"], ["z" * 41, "Z"]])
ok("dump sanitizes before exporting",
   json.loads(out) == [{"src": "a", "dst": "A"}])

# 上限 200：超出部分计入 skipped
big = json.dumps([{"src": "t%d" % i, "dst": "x"} for i in range(250)],
                 ensure_ascii=False)
loaded, skipped, err = g.load_glossary_json(big)
ok("load caps at 200 pairs", len(loaded) == 200 and err is None)
ok("over-cap entries counted in skipped", skipped == 50)

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
