"""Windows 截图 — 只用 Python 标准库 ctypes（GDI BitBlt），不用 Pillow。

capture_region(x, y, w, h) -> (宽, 高, BGRA 字节串)，左上角原点。
save_bmp(path, w, h, bgra) -> 写 32 位 BMP（纯 Python，不用 Pillow）。

非 Windows 上 import 安全，capture_region 会抛 RuntimeError。
"""

import os
import struct
import sys

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


def capture_region(x, y, width, height):
    """截取屏幕区域。返回 (width, height, BGRA bytes)。"""
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

    hdc_screen = user32.GetDC(None)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    try:
        old = gdi32.SelectObject(hdc_mem, hbitmap)
        if not gdi32.BitBlt(hdc_mem, 0, 0, width, height,
                            hdc_screen, x, y, SRCCOPY):
            raise RuntimeError("BitBlt 失败（可能被 DRM / 全屏独占挡住）")
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buf = ctypes.create_string_buffer(width * height * 4)
        lines = gdi32.GetDIBits(hdc_mem, hbitmap, 0, height, buf, ctypes.byref(bmi),
                                DIB_RGB_COLORS)
        if not lines:
            raise RuntimeError("GetDIBits 失败")
        gdi32.SelectObject(hdc_mem, old)
        return width, height, buf.raw
    finally:
        if hbitmap:
            gdi32.DeleteObject(hbitmap)
        if hdc_mem:
            gdi32.DeleteDC(hdc_mem)
        if hdc_screen:
            user32.ReleaseDC(None, hdc_screen)


def capture_file(path, x, y, width, height):
    """截取区域并存为 BMP，返回 path。"""
    w, h, bgra = capture_region(x, y, width, height)
    return save_bmp(path, w, h, bgra)
