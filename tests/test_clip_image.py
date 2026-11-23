"""剪贴板 DIB -> BMP 转换（纯函数）+ 取剪贴板 DIB。"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import clip_image as ci

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def raises_valueerror(name, data):
    try:
        ci.dib_to_bmp(data)
    except ValueError:
        ok(name, True)
    except Exception as e:
        print("  got %s: %s" % (type(e).__name__, e))
        ok(name, False)
    else:
        ok(name, False)


def dib_header(width, height, bit_count, compression=0, clr_used=0, size_image=0):
    return struct.pack("<IiiHHIIiiII", 40, width, height, 1, bit_count,
                       compression, size_image, 0, 0, clr_used, 0)


# --- 2x2 24 位，自底向上：DIB 里底行在前 ---
# 底行：红 (BGR 0,0,255)、绿 (0,255,0)；顶行：蓝 (255,0,0)、白 (255,255,255)
row_bottom = bytes([0, 0, 255, 0, 255, 0, 0, 0])
row_top = bytes([255, 0, 0, 255, 255, 255, 0, 0])
pixels_24 = row_bottom + row_top
dib24 = dib_header(2, 2, 24) + pixels_24

bmp = ci.dib_to_bmp(dib24)
ok("24-bit starts with BM", bmp[:2] == b"BM")
ok("24-bit file size field matches len",
   struct.unpack_from("<I", bmp, 2)[0] == len(bmp) == 14 + 40 + 16)
ok("24-bit width field is 2", struct.unpack_from("<i", bmp, 18)[0] == 2)
ok("24-bit height field is 2", struct.unpack_from("<i", bmp, 22)[0] == 2)
ok("24-bit bit count preserved", struct.unpack_from("<H", bmp, 28)[0] == 24)
ok("24-bit pixel offset is 54", struct.unpack_from("<I", bmp, 10)[0] == 54)
ok("24-bit pixels round-trip, bottom row first in BMP",
   bmp[54:] == pixels_24)
ok("24-bit first BMP pixel is red (BGR 0,0,255)",
   bmp[54:57] == bytes([0, 0, 255]))

# --- 2x2 24 位，自顶向下：负高度原样保留，像素顺序不动 ---
dib_td = dib_header(2, -2, 24) + row_top + row_bottom
bmp_td = ci.dib_to_bmp(dib_td)
ok("top-down keeps negative height",
   struct.unpack_from("<i", bmp_td, 22)[0] == -2)
ok("top-down pixels preserved in order",
   bmp_td[54:] == row_top + row_bottom)
ok("top-down file size matches len",
   struct.unpack_from("<I", bmp_td, 2)[0] == len(bmp_td))

# --- 2x2 32 位 ---
row32_a = bytes([0, 0, 255, 255, 0, 255, 0, 255])
row32_b = bytes([255, 0, 0, 255, 255, 255, 255, 255])
dib32 = dib_header(2, 2, 32) + row32_a + row32_b
bmp32 = ci.dib_to_bmp(dib32)
ok("32-bit converts, bit count 32 preserved",
   struct.unpack_from("<H", bmp32, 28)[0] == 32
   and bmp32[:2] == b"BM"
   and struct.unpack_from("<I", bmp32, 2)[0] == len(bmp32) == 14 + 40 + 16)
ok("32-bit pixels round-trip", bmp32[54:] == row32_a + row32_b)

# --- 2x2 8 位带调色板 ---
palette = bytes([0, 0, 0, 0, 255, 255, 255, 0])  # 索引 0 黑、索引 1 白
pix8 = bytes([0, 1, 0, 0, 1, 0, 0, 0])           # 底行 0,1；顶行 1,0
dib8 = dib_header(2, 2, 8, clr_used=2) + palette + pix8
bmp8 = ci.dib_to_bmp(dib8)
ok("8-bit palette copied, offset accounts for it",
   struct.unpack_from("<I", bmp8, 10)[0] == 14 + 40 + 8
   and bmp8[54:62] == palette)
ok("8-bit bit count preserved", struct.unpack_from("<H", bmp8, 28)[0] == 8)
ok("8-bit pixels round-trip", bmp8[62:] == pix8)

# --- v2.15.8：BI_BITFIELDS（截图 / 浏览器 / 微信复制的 32 位图）---
_hdr = dib_header(2, 2, 32, compression=3)
_masks = struct.pack("<III", 0x00FF0000, 0x0000FF00, 0x000000FF)
_pix32 = bytes(range(16))
_bf = ci.dib_to_bmp(_hdr + _masks + _pix32)
ok("BI_BITFIELDS 32 位：能转，像素偏移含 12 字节掩码", _bf[:2] == b"BM"
   and struct.unpack_from("<I", _bf, 10)[0] == 14 + 40 + 12 and _bf[-16:] == _pix32)

# --- 非法输入都抛 ValueError ---
raises_valueerror("empty bytes raise ValueError", b"")
raises_valueerror("truncated header raises ValueError",
                  b"\x28\x00\x00\x00" + b"\x00" * 16)
raises_valueerror("bad header size (20) raises ValueError",
                  struct.pack("<I", 20) + b"\x00" * 36)
raises_valueerror("bit depth 16 raises ValueError",
                  dib_header(2, 2, 16) + pixels_24)
raises_valueerror("BI_RLE8 compression=1 raises ValueError",
                  dib_header(2, 2, 24, compression=1) + pixels_24)
raises_valueerror("truncated pixel data raises ValueError",
                  dib_header(2, 2, 24))
raises_valueerror("zero height raises ValueError",
                  dib_header(2, 0, 24))

# --- 取剪贴板：Linux 上返回 None，不抛错 ---
try:
    got = ci.get_clipboard_dib()
    ok("get_clipboard_dib() on Linux returns None",
       got is None if sys.platform != "win32" else got is None or isinstance(got, bytes))
except Exception as e:
    print("  got %s: %s" % (type(e).__name__, e))
    ok("get_clipboard_dib() on Linux returns None", False)

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
