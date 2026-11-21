"""从 app.ico 取最大的 PNG 帧，生成 MSIX 需要的 Logo（纯标准库：用 tkinter 缩放）。"""
import os
import struct
import sys
import tkinter as tk

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SIZES = {"StoreLogo.png": 50, "Square44x44Logo.png": 44, "Square150x150Logo.png": 150}


def biggest_png(ico):
    data = open(ico, "rb").read()
    n = struct.unpack_from("<H", data, 4)[0]
    ents = [struct.unpack_from("<BBBBHHII", data, 6 + 16 * i) for i in range(n)]
    e = max(ents, key=lambda x: x[0] or 256)
    blob = data[e[7]:e[7] + e[6]]
    if blob[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit("app.ico 最大帧不是 PNG，请手动放 Assets 图标")
    return blob


def main(out):
    os.makedirs(out, exist_ok=True)
    src = os.path.join(out, "_src.png")
    open(src, "wb").write(biggest_png(os.path.join(ROOT, "app.ico")))
    root = tk.Tk(); root.withdraw()
    img = tk.PhotoImage(file=src)
    for name, size in SIZES.items():
        f = max(1, img.width() // size)
        small = img.subsample(f, f)
        small.write(os.path.join(out, name), format="png")
    os.remove(src)
    root.destroy()


if __name__ == "__main__":
    main(sys.argv[1])
