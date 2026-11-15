"""术语表：清洗 / 占位符保护 / 还原（纯函数）。"""
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


ok("empty glossary is identity",
   g.apply_glossary("hello world", []) == ("hello world", {}))
ok("restore with empty mapping is identity",
   g.restore_glossary("hello", {}) == "hello")

out, m = g.apply_glossary("Use Maxum II for analysis.", [["Maxum II", "Maxum II"]])
ok("term protected", "\ue000" in out and "Maxum II" not in out)
ok("restore puts fixed translation back",
   g.restore_glossary(out, m) == "Use Maxum II for analysis.")

# 长词先换：先换 Maxum II，再换 Maxum，否则长词会被切碎
out, m = g.apply_glossary("Maxum II and Maxum",
                          [["Maxum", "M"], ["Maxum II", "M2"]])
ok("longest term first", g.restore_glossary(out, m) == "M2 and M")

# 中文术语
out, m = g.apply_glossary("打开色谱仪设置", [["色谱仪", "色谱仪"]])
ok("CJK term protected", "色谱仪" not in out)
ok("CJK restore", g.restore_glossary(out, m) == "打开色谱仪设置")

# 同一词出现多次只用一个占位符
out, m = g.apply_glossary("cat cat cat", [["cat", "猫"]])
ok("repeated term, one placeholder", len(m) == 1 and out.count("cat") == 0)
ok("repeated restore", g.restore_glossary(out, m) == "猫 猫 猫")

# 清洗：去空、去重、超长丢掉、上限 200
clean = g.sanitize_pairs([["a", "A"], ["a", "A2"], ["", "x"], ["y", ""], ["z" * 41, "Z"]])
ok("sanitize dedups and drops bad", clean == [["a", "A"]])
ok("sanitize caps at 200",
   len(g.sanitize_pairs([["t%d" % i, "x"] for i in range(300)])) == 200)

# 占位符与原文撞上：换一对备用私有区字符，照样能保护和还原
text = "has \ue000 marker and Maxum"
out, m = g.apply_glossary(text, [["Maxum", "M"]])
ok("marker collision falls back to second pair",
   "\ue002" in out and "Maxum" not in out)
ok("collision restore exact", g.restore_glossary(out, m) == "has \ue000 marker and M")

# 没出现的词不产生占位符
out, m = g.apply_glossary("nothing here", [["Maxum", "M"]])
ok("absent term produces no mapping", out == "nothing here" and m == {})

# set_active / active
g.set_active([["Maxum", "M"], ["", "x"]])
ok("set_active sanitizes", g.active() == [["Maxum", "M"]])
out, m = g.protect("Maxum works")
ok("protect uses active glossary", g.restore(out, m) == "M works")
g.set_active([])

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
