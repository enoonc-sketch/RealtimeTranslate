"""词典解析 parse_dict / 词典候选 / 生词判定 / 图片扩展名。
用写死的 Google 响应 fixture，不联网。不需要 xvfb。"""
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


# Google translate_a/single 返回结构（写死 fixture）：
# data[0] = 句子 [[译文, 原文, None, transliteration], ...]
# data[1] = 词典 [[词性, [释义...], ...], ...]
# data[2] = 检测到的源语言
NO_DICT = [[["Hello", "你好", None, None]], None, "zh-CN"]
DICT_ONLY = [[["run", "跑", None, None]],
             [["verb", ["跑", "运行", "经营"], [["sprint", "dash"]]],
              ["noun", ["跑步", "行程"]]],
             "zh-CN"]
DICT_TRANSlit = [[["Hello", "你好", None, "Nǐ hǎo"]],
                 [["interjection", ["你好", "喂"]]],
                 "zh-CN"]

p = dt.parse_dict(NO_DICT)
ok("no dict -> empty entries", p["entries"] == [])
ok("no translit -> empty", p["translit"] == "")
p = dt.parse_dict(DICT_ONLY)
ok("dict entries parsed", p["entries"] == [
    {"pos": "verb", "meanings": ["跑", "运行", "经营"]},
    {"pos": "noun", "meanings": ["跑步", "行程"]}])
ok("dict no translit", p["translit"] == "")
p = dt.parse_dict(DICT_TRANSlit)
ok("translit from segment[3]", p["translit"] == "Nǐ hǎo")
ok("dict with translit", p["entries"] == [{"pos": "interjection", "meanings": ["你好", "喂"]}])
ok("parse_dict bad input safe", dt.parse_dict(None) == {"entries": [], "translit": ""}
   and dt.parse_dict({}) == {"entries": [], "translit": ""}
   and dt.parse_dict([[], [], "en"]) == {"entries": [], "translit": ""})
ok("parse_dict caps meanings", len(dt.parse_dict(
    [[["x", "y", None, None]], [["noun", ["m%d" % i for i in range(20)]]], "en"])
    ["entries"][0]["meanings"]) == 8)

# ---- 词典候选 ----
for t, want in (("hello", True), ("hello world", True), ("one two three", True),
                ("one two three four", False), ("a" * 21, False),
                ("hello\nworld", False), ("", False), ("   ", False),
                ("你好", True), ("你好世界", True)):
    ok("dict candidate %r -> %s" % (t, want), dt.is_dict_candidate(t) is want)

# ---- 生词判定 ----
for t, want in (("hello", True), ("你好", True), ("hello world", False),
                ("hello-world", True), ("", False), ("a" * 31, False),
                ("a" * 30, True), ("  hello  ", True), ("hel\nlo", False)):
    ok("word entry %r -> %s" % (t, want), dt.is_word_entry(t) is want)

# ---- 图片扩展名 ----
for p, want in (("a.png", True), ("a.JPG", True), ("a.jpeg", True),
                ("a.bmp", True), ("a.tif", True), ("a.txt", False),
                ("a.gif", False)):
    ok("image file %s -> %s" % (p, want), dt.is_supported_image_file(p) is want)

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
