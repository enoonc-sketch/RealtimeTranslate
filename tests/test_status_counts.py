"""v2.8 状态栏字数：format_status_counts 纯函数。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import desktop_translator as dt

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


ok("basic", dt.format_status_counts(128, 96) == "原文 128 字 · 译文 96 字")
ok("zero", dt.format_status_counts(0, 0) == "原文 0 字 · 译文 0 字")
ok("single char", dt.format_status_counts(1, 1) == "原文 1 字 · 译文 1 字")
ok("CJK length is len()", dt.format_status_counts(len("你好世界"), len("Hello")) ==
   "原文 4 字 · 译文 5 字")

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
