"""悬停缓存：同一位置 2 秒内复用 OCR 结果，移开/换范围/过期就重认。"""
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


c = dt.HoverCache(ttl=2.0, bucket=8)
hit, val = c.get((100, 50), "word", now=1000.0)
ok("empty cache is a miss", hit is c._MISS)

c.put((100, 50), "word", "hello", now=1000.0)
hit, val = c.get((100, 50), "word", now=1001.0)
ok("same position within TTL hits", hit is True and val == "hello")
hit, val = c.get((103, 53), "word", now=1001.0)
ok("same 8px bucket hits", hit is True and val == "hello")
hit, val = c.get((108, 50), "word", now=1001.0)
ok("moved out of bucket misses", hit is c._MISS)
hit, val = c.get((100, 50), "line", now=1001.0)
ok("different scope misses", hit is c._MISS)
hit, val = c.get((100, 50), "word", now=1002.0)
ok("at TTL boundary still hits", hit is True)
hit, val = c.get((100, 50), "word", now=1002.5)
ok("past TTL misses", hit is c._MISS)

# None 也能缓存：该位置没认出字，2 秒内不再重跑 OCR
c.put((200, 200), "word", None, now=1000.0)
hit, val = c.get((200, 200), "word", now=1001.0)
ok("cached None is a hit (not a miss)", hit is True and val is None)

# 覆盖旧值
c.put((100, 50), "word", "bye", now=1003.0)
hit, val = c.get((100, 50), "word", now=1003.5)
ok("put overwrites", hit is True and val == "bye")
c.clear()
hit, val = c.get((100, 50), "word", now=1003.5)
ok("clear empties cache", hit is c._MISS)

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
