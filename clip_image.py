"""剪贴板图片：CF_DIB -> BMP 转换 + 取剪贴板 DIB（纯标准库）。

dib_to_bmp() 是纯函数，不调任何 Windows API，可在任何平台单测。
get_clipboard_dib() 只在 Windows 上访问剪贴板，其余平台直接返回 None。
"""
import struct
import sys

CF_DIB = 8
CF_DIBV5 = 17

_BI_RGB = 0
_BI_BITFIELDS = 3           # v2.15.8：Win 截图 / 浏览器 / 微信复制出的 32 位图基本都是这个
_BI_ALPHABITFIELDS = 6
_SUPPORTED_BIT_COUNTS = (8, 24, 32)

# BITMAPFILEHEADER：14 字节，"BM" + 文件大小 + 保留字 x2 + 像素数据偏移
_FILE_HEADER = struct.Struct("<2sIHHI")
_INFO_HEADER_MIN = 40  # BITMAPINFOHEADER 最小长度


def dib_to_bmp(dib: bytes) -> bytes:
    """把剪贴板 CF_DIB 字节（BITMAPINFOHEADER + 调色板 + 像素）转成完整 .bmp。

    输出 = BITMAPFILEHEADER + 原信息头 + 调色板（如有）+ 像素原样。
    保留原 DIB 的有符号高度（正数 = 自底向上，负数 = 自顶向下），
    不改像素顺序、不重排数据。

    只支持 BI_RGB（compression == 0）的 8/24/32 位 DIB。
    输入非法时抛 ValueError。
    """
    if not isinstance(dib, (bytes, bytearray, memoryview)):
        raise ValueError("dib must be bytes-like, got %s" % type(dib).__name__)
    dib = bytes(dib)
    if len(dib) < 4:
        raise ValueError("DIB too short: %d bytes, need at least 4 for biSize" % len(dib))

    (header_size,) = struct.unpack_from("<I", dib, 0)
    if header_size < _INFO_HEADER_MIN:
        raise ValueError("bad DIB header size: %d (need >= %d)"
                         % (header_size, _INFO_HEADER_MIN))
    if len(dib) < header_size:
        raise ValueError("DIB truncated: header claims %d bytes, got %d"
                         % (header_size, len(dib)))
    if len(dib) < _INFO_HEADER_MIN:
        raise ValueError("DIB too short: %d bytes, need at least %d for BITMAPINFOHEADER"
                         % (len(dib), _INFO_HEADER_MIN))

    (bi_size, width, height, planes, bit_count, compression,
     _size_image, _x_pels, _y_pels, clr_used,
     _clr_important) = struct.unpack_from("<IiiHHIIiiII", dib, 0)

    if planes != 1:
        raise ValueError("unsupported DIB planes: %d (need 1)" % planes)
    bitfields = compression in (_BI_BITFIELDS, _BI_ALPHABITFIELDS)
    if bit_count not in _SUPPORTED_BIT_COUNTS and not (bitfields and bit_count == 16):
        raise ValueError("unsupported DIB bit depth: %d (need 8, 24 or 32)"
                         % bit_count)
    if compression != _BI_RGB and not bitfields:
        raise ValueError("unsupported DIB compression: %d (need 0/BI_RGB or BI_BITFIELDS)"
                         % compression)
    if width <= 0:
        raise ValueError("bad DIB width: %d (need > 0)" % width)
    if height == 0:
        raise ValueError("bad DIB height: 0 (need non-zero)")

    # 8 位 DIB 带调色板：biClrUsed 非零即为颜色数，否则默认 256 色。
    if bit_count == 8:
        num_colors = clr_used if clr_used else 256
        palette_size = num_colors * 4
    else:
        palette_size = 0
    if bitfields and header_size == _INFO_HEADER_MIN:
        # BITMAPINFOHEADER 之后紧跟 3（或 4）个 DWORD 颜色掩码；V4/V5 头里自带掩码，不用另算
        palette_size += 16 if compression == _BI_ALPHABITFIELDS else 12

    # 行宽按 4 字节对齐。
    stride = ((width * bit_count + 31) // 32) * 4
    pixel_size = stride * abs(height)

    need = header_size + palette_size + pixel_size
    if len(dib) < need:
        raise ValueError(
            "DIB truncated: need %d bytes (header %d + palette %d + pixels %d), got %d"
            % (need, header_size, palette_size, pixel_size, len(dib)))

    pixel_data = dib[header_size + palette_size: header_size + palette_size + pixel_size]
    palette = dib[header_size: header_size + palette_size]
    info_header = dib[:header_size]

    off_bits = 14 + header_size + palette_size
    file_size = off_bits + pixel_size
    file_header = _FILE_HEADER.pack(b"BM", file_size, 0, 0, off_bits)
    return file_header + info_header + palette + pixel_data


def get_clipboard_dib():
    """取剪贴板上的 CF_DIB 数据；没有 DIB 或任何出错时返回 None，永不抛错。

    非 Windows 平台直接返回 None。导入本模块在 Linux 上永不失败：
    ctypes 的 Windows 调用都在函数内、只在 win32 分支里执行。
    """
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalSize.restype = ctypes.c_size_t

        if not user32.OpenClipboard(None):
            return None
        try:
            handle = user32.GetClipboardData(CF_DIB)
            if not handle:
                return None
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return None
            try:
                size = kernel32.GlobalSize(handle)
                if not size:
                    return None
                return ctypes.string_at(ptr, size)
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
    except Exception:
        return None


def get_clipboard_image():
    """v2.15.8：取剪贴板上的图片，返回 (扩展名, 字节)；没有图片返回 (None, None)，永不抛错。

    依次试：注册格式 "PNG"（浏览器 / 微信 / Snipaste 常只给这个，CF_DIB 取不到）→ CF_DIB →
    CF_DIBV5。DIB 返回的是 .bmp（已转好），PNG 原样返回。非 Windows 平台返回 (None, None)。
    """
    if sys.platform != "win32":
        return None, None
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
        user32.RegisterClipboardFormatW.restype = wintypes.UINT
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalSize.restype = ctypes.c_size_t

        def grab(fmt):
            handle = user32.GetClipboardData(fmt)
            if not handle:
                return None
            ptr = kernel32.GlobalLock(handle)
            if not ptr:
                return None
            try:
                size = kernel32.GlobalSize(handle)
                return ctypes.string_at(ptr, size) if size else None
            finally:
                kernel32.GlobalUnlock(handle)

        if not user32.OpenClipboard(None):
            return None, None
        try:
            png_fmt = user32.RegisterClipboardFormatW("PNG")
            data = grab(png_fmt) if png_fmt else None
            if data and data[:8] == b"\x89PNG\r\n\x1a\n":
                return ".png", data
            for fmt in (CF_DIB, CF_DIBV5):
                dib = grab(fmt)
                if dib:
                    try:
                        return ".bmp", dib_to_bmp(dib)
                    except ValueError:
                        continue
            return None, None
        finally:
            user32.CloseClipboard()
    except Exception:
        return None, None
