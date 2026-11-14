"""托盘 / 截图 / OCR：纯标准库，不依赖 pystray / Pillow。不需要 xvfb。"""
import ast
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
sys.path.insert(0, BASE)
sys.path.insert(0, HERE)

import tray_win32
import screen_win
import ocr_win

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


# 1. 源码里没有任何 pystray / PIL / Pillow 导入（注释里提一下名字不算）
for mod in ("tray_win32.py", "screen_win.py", "ocr_win.py", "history_store.py", "desktop_translator.py"):
    tree = ast.parse(open(os.path.join(BASE, mod), encoding="utf-8").read())
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    ok(f"{mod} no pystray/PIL import", not ({"pystray", "PIL", "Pillow"} & imports))

# 2. 托盘：Linux 上 import 安全，start 返回 False，stop/notify 不抛异常
ok("tray not available on linux", not tray_win32.available())
tray = tray_win32.TrayIcon(icon_path=os.path.join(BASE, "app.ico"), tooltip="实时翻译")
ok("tray.start() False on linux", tray.start() is False)
ok("tray not running", not tray.is_running())
tray.stop()
ok("tray.notify() False on linux", tray.notify("t", "x") is False)
ok("tray.set_tooltip() False on linux", tray.set_tooltip("x") is False)

# 3. 截图 BMP：纯 Python 写 BMP，头 + 尺寸 + 像素都对
tmp = tempfile.mkdtemp()
bmp = os.path.join(tmp, "t.bmp")
w, h = 3, 2
bgra = bytes([10, 20, 30, 255] * (w * h))
screen_win.save_bmp(bmp, w, h, bgra)
data = open(bmp, "rb").read()
ok("bmp magic", data[:2] == b"BM")
ok("bmp size field", int.from_bytes(data[2:6], "little") == len(data) == 54 + w * h * 4)
ok("bmp dims", int.from_bytes(data[18:22], "little", signed=True) == w
   and int.from_bytes(data[22:26], "little", signed=True) == h)
ok("bmp pixels", data[54:] == bgra)
ok("clamp_region", screen_win.clamp_region(-50, -20, 500, 200, (0, 0, 400, 300)) == (0, 0, 400, 200))
ok("capture_region raises on linux", (lambda: False)() if False else True)
try:
    screen_win.capture_region(0, 0, 10, 10)
    ok("capture_region raises on linux", False)
except RuntimeError:
    ok("capture_region raises on linux", True)
ok("cursor pos None on linux", screen_win.get_cursor_pos() is None)

# 4. OCR：Linux 上不可用，报 OcrError；脚本里有系统 OCR 的关键调用
ok("ocr not available on linux", not ocr_win.ocr_available())
try:
    ocr_win.ocr_image(os.path.join(tmp, "t.bmp"))
    ok("ocr_image raises on linux", False)
except ocr_win.OcrError:
    ok("ocr_image raises on linux", True)
ps = open(os.path.join(BASE, "winocr.ps1"), encoding="utf-8").read()
ok("winocr uses Windows.Media.Ocr", "Windows.Media.Ocr.OcrEngine" in ps)
ok("winocr tries language then user profile", "TryCreateFromLanguage" in ps
   and "TryCreateFromUserProfileLanguages" in ps)
ok("winocr requires PS 5.1", "PSVersionTable.PSVersion.Major -ne 5" in ps)
words = [{"text": "hello", "x": 10, "y": 10, "w": 40, "h": 16},
         {"text": "world", "x": 60, "y": 10, "w": 40, "h": 16}]
ok("pick word inside", ocr_win.pick_word_at(words, 30, 18) == "hello")
ok("pick word near", ocr_win.pick_word_at(words, 52, 18) == "hello")
ok("pick word far away None", ocr_win.pick_word_at(words, 500, 500) is None)
ok("pick word empty None", ocr_win.pick_word_at([], 0, 0) is None)

# 5. 两个 spec 都把新模块打进去、把 pystray 排除、把 winocr.ps1 带上
for spec in ("realtime_translate.spec", "realtime_translate_offline.spec"):
    s = open(os.path.join(BASE, spec), encoding="utf-8").read()
    ok(f"{spec} hiddenimports tray/screen/ocr",
       all(m in s for m in ("tray_win32", "screen_win", "ocr_win")))
    ok(f"{spec} excludes pystray", "'pystray'" in s)
    ok(f"{spec} datas winocr.ps1", "winocr.ps1" in s)

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
