"""回归：托盘代码不能直接用 ctypes.wintypes 里不存在的类型（LRESULT/HCURSOR）。"""
import os, re
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(BASE, "tray_win32.py"), encoding="utf-8").read()
assert src.count("import ctypes.wintypes as wt") == 1, "只允许 _wt() 里导入 wintypes"
assert 'hasattr(wt, "LRESULT")' in src
assert "> 0:" in src
print("PASS tray wintypes shim")
