"""Windows 截图 — 只用 Python 标准库 ctypes（GDI BitBlt），不用 Pillow。

capture_region(x, y, w, h) -> (宽, 高, BGRA 字节串)，左上角原点。
save_bmp(path, w, h, bgra) -> 写 32 位 BMP（纯 Python，不用 Pillow）。

非 Windows 上 import 安全，capture_region 会抛 RuntimeError。
"""

import os
import struct
import sys
import zlib

IS_WIN = sys.platform.startswith("win")


def clamp_region(x, y, w, h, bounds):
    """把区域夹到虚拟桌面内。bounds=(左, 上, 右, 下)，返回 (x, y, w, h)。"""
    left, top, right, bottom = bounds
    x = max(left, min(x, right - 1))
    y = max(top, min(y, bottom - 1))
    w = max(1, min(w, right - x))
    h = max(1, min(h, bottom - y))
    return x, y, w, h


def save_bmp(path, width, height, bgra):
    """bgra 是 GetDIBits 返回的 bottom-up 行序（文件正好也要这个顺序）。"""
    if width <= 0 or height <= 0:
        raise ValueError("bad size")
    if len(bgra) < width * height * 4:
        raise ValueError("bgra too short")
    row = width * 4
    data = bgra[:row * height]
    file_size = 54 + len(data)
    header = struct.pack("<2sIHHI", b"BM", file_size, 0, 0, 54)
    dib = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 32, 0,
                      len(data), 2835, 2835, 0, 0)
    with open(path, "wb") as f:
        f.write(header)
        f.write(dib)
        f.write(data)
    return path


def get_cursor_pos():
    """返回 (x, y)，失败 / 非 Windows 返回 None。"""
    if not IS_WIN:
        return None
    try:
        import ctypes
        import ctypes.wintypes as wt

        class POINT(ctypes.Structure):
            _fields_ = [("x", wt.LONG), ("y", wt.LONG)]

        p = POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(p)):
            return p.x, p.y
    except Exception:
        pass
    return None


def capture_region(x, y, width, height, scale=1):
    """截取屏幕区域。返回 (宽, 高, BGRA bytes)。

    scale > 1 时用 GDI 的 HALFTONE 平滑放大后再返回（宽高也是放大后的）：
    按钮、菜单这类小号界面文字，放大 2 倍后系统 OCR 才认得出来。
    """
    if not IS_WIN:
        raise RuntimeError("截图只支持 Windows")
    if width <= 0 or height <= 0:
        raise ValueError("bad size")
    import ctypes
    import ctypes.wintypes as wt

    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    SRCCOPY = 0x00CC0020
    DIB_RGB_COLORS = 0

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
            ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
            ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
            ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
            ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]

    scale = max(1, int(scale or 1))
    out_w, out_h = width * scale, height * scale
    hdc_screen = user32.GetDC(None)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, out_w, out_h)
    try:
        old = gdi32.SelectObject(hdc_mem, hbitmap)
        if scale == 1:
            ok = gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, x, y, SRCCOPY)
        else:
            gdi32.SetStretchBltMode(hdc_mem, 4)          # HALFTONE：放大后字边更平滑
            gdi32.SetBrushOrgEx(hdc_mem, 0, 0, None)
            ok = gdi32.StretchBlt(hdc_mem, 0, 0, out_w, out_h,
                                  hdc_screen, x, y, width, height, SRCCOPY)
        if not ok:
            raise RuntimeError("BitBlt 失败（可能被 DRM / 全屏独占挡住）")
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = out_w
        bmi.bmiHeader.biHeight = out_h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buf = ctypes.create_string_buffer(out_w * out_h * 4)
        lines = gdi32.GetDIBits(hdc_mem, hbitmap, 0, out_h, buf, ctypes.byref(bmi),
                                DIB_RGB_COLORS)
        if not lines:
            raise RuntimeError("GetDIBits 失败")
        gdi32.SelectObject(hdc_mem, old)
        return out_w, out_h, buf.raw
    finally:
        if hbitmap:
            gdi32.DeleteObject(hbitmap)
        if hdc_mem:
            gdi32.DeleteDC(hdc_mem)
        if hdc_screen:
            user32.ReleaseDC(None, hdc_screen)


def capture_file(path, x, y, width, height, scale=1):
    """截取区域并存为 BMP，返回 path（scale > 1 时存放大后的图）。"""
    w, h, bgra = capture_region(x, y, width, height, scale)
    return save_bmp(path, w, h, bgra)


def bgra_to_png(width, height, bgra, bottom_up=True):
    """BGRA 像素 -> PNG 字节（纯标准库 zlib + struct，不用 Pillow）。

    Tk 8.6 的 PhotoImage 原生能读 PNG，截图翻译把截图显示在 Canvas 上就靠它。
    bottom_up=True 对应 GetDIBits 返回的「从下往上」行序。
    """
    if width <= 0 or height <= 0 or len(bgra) < width * height * 4:
        raise ValueError("bad image")
    row = width * 4
    raw = bytearray()
    order = range(height - 1, -1, -1) if bottom_up else range(height)
    for r in order:
        line = bgra[r * row:(r + 1) * row]
        rgb = bytearray(width * 3)
        rgb[0::3] = line[2::4]
        rgb[1::3] = line[1::4]
        rgb[2::3] = line[0::4]
        raw.append(0)                      # 过滤类型 0（不过滤）
        raw.extend(rgb)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 1))
            + chunk(b"IEND", b""))


def sample_bg(width, height, bgra, x, y, w, h, bottom_up=True):
    """估计 (x, y, w, h) 这块文字区域的背景色：取它四周一圈像素里最常见的颜色。返回 '#rrggbb'。"""
    def px(ix, iy):
        ix = max(0, min(width - 1, ix))
        iy = max(0, min(height - 1, iy))
        ry = (height - 1 - iy) if bottom_up else iy
        o = (ry * width + ix) * 4
        return bgra[o + 2], bgra[o + 1], bgra[o]

    pts = []
    step_x = max(1, w // 24)
    step_y = max(1, h // 8)
    for ix in range(x, x + w + 1, step_x):
        pts.append(px(ix, y - 2))
        pts.append(px(ix, y + h + 2))
    for iy in range(y, y + h + 1, step_y):
        pts.append(px(x - 2, iy))
        pts.append(px(x + w + 2, iy))
    counts = {}
    for r, g, b in pts:
        key = (r >> 3, g >> 3, b >> 3)
        counts[key] = counts.get(key, 0) + 1
    r, g, b = max(counts, key=counts.get)
    return "#%02x%02x%02x" % (min(255, r * 8 + 4), min(255, g * 8 + 4), min(255, b * 8 + 4))


def text_color_for(bg_hex):
    """按背景亮度挑黑 / 白字。"""
    r, g, b = int(bg_hex[1:3], 16), int(bg_hex[3:5], 16), int(bg_hex[5:7], 16)
    return "#000000" if 0.299 * r + 0.587 * g + 0.114 * b > 140 else "#ffffff"
