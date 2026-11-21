"""v2.15.3 取词加载提示：位置计算（纯逻辑）。"""
import os, random
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(os.path.join(BASE, "desktop_translator.py"), encoding="utf-8").read()
ns = {}; exec(s[s.index("def spinner_frames"):s.index("class GrabSpinner")], ns)
P = ns["spinner_position"]; B = (0, 0, 1920, 1080)
assert P((100, 100), (90, 24), B) == (116, 118)
assert P((100, 100), (90, 24), B, (210, 55)) == (116, 161)
assert P((1900, 100), (90, 24), B)[0] < 1900 and P((100, 1070), (90, 24), B)[1] < 1070
random.seed(3)
for _ in range(5000):
    x, y = P((random.randint(-100, 4000), random.randint(-100, 2200)), (random.randint(1, 300), random.randint(1, 60)), B,
             (random.randint(0, 500), random.randint(0, 300)))
    assert 0 <= x <= 1920 and 0 <= y <= 1080
assert len(ns["spinner_frames"]()) == 4
print("PASS test_spinner_v2153")
