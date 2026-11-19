"""宠物动画包（pets/<id>.pet）的读取，以及显示用的像素格式转换。只用标准库（zlib/struct/json/base64）。

文件格式 RTPET1：
    b"RTPET1\\n" + uint32 头长度 + 头(JSON utf-8) + 各帧数据
    头 = {"w":112,"h":112,"anims":{"idle":[0,1,2,3],...},"frames":[[偏移,长度],...]}
    每帧 = zlib 压缩的 w*h*4 字节 RGBA（直通 alpha，不预乘）
"""
import base64
import json
import os
import struct
import zlib

MAGIC = b"RTPET1\n"
ANIMS = ("idle", "blink", "sleep", "think", "happy", "sad", "alert")


class PetPackError(Exception):
    pass


class PetPack:
    def __init__(self, path):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            raise PetPackError("读不到动画包：%s" % e)
        if not data.startswith(MAGIC) or len(data) < len(MAGIC) + 4:
            raise PetPackError("不是有效的动画包")
        (hl,) = struct.unpack_from("<I", data, len(MAGIC))
        start = len(MAGIC) + 4
        try:
            head = json.loads(data[start:start + hl].decode("utf-8"))
            self.w, self.h = int(head["w"]), int(head["h"])
            self.anims = {k: list(v) for k, v in head["anims"].items()}
            self._frames = [tuple(x) for x in head["frames"]]
        except (ValueError, KeyError, TypeError) as e:
            raise PetPackError("动画包头损坏：%s" % e)
        self._body = data[start + hl:]
        self._cache = {}
        for a in ANIMS:
            if not self.anims.get(a):
                raise PetPackError("动画包缺少动画：%s" % a)
        for off, ln in self._frames:
            if off < 0 or off + ln > len(self._body):
                raise PetPackError("动画包数据被截断")

    def frames(self, anim):
        return self.anims.get(anim) or self.anims["idle"]

    def rgba(self, idx):
        """第 idx 帧的 RGBA 字节（w*h*4）。"""
        b = self._cache.get(idx)
        if b is None:
            off, ln = self._frames[idx]
            try:
                b = zlib.decompress(self._body[off:off + ln])
            except zlib.error as e:
                raise PetPackError("动画帧损坏：%s" % e)
            if len(b) != self.w * self.h * 4:
                raise PetPackError("动画帧大小不对")
            self._cache[idx] = b
        return b


def rgba_to_png(w, h, rgba):
    """RGBA 字节 → PNG 字节（标准库实现，给 tkinter.PhotoImage 用）。"""
    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag, body):
        c = struct.pack(">I", len(body)) + tag + body
        return c + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b""))


def rgba_to_b64png(w, h, rgba):
    return base64.b64encode(rgba_to_png(w, h, rgba)).decode("ascii")


def rgba_to_bgra_premul(rgba):
    """Windows 分层窗口（UpdateLayeredWindow）要的格式：BGRA + 预乘 alpha。"""
    out = bytearray(len(rgba))
    for i in range(0, len(rgba), 4):
        a = rgba[i + 3]
        if a == 255:
            out[i], out[i + 1], out[i + 2], out[i + 3] = rgba[i + 2], rgba[i + 1], rgba[i], 255
        elif a:
            out[i] = rgba[i + 2] * a // 255
            out[i + 1] = rgba[i + 1] * a // 255
            out[i + 2] = rgba[i] * a // 255
            out[i + 3] = a
    return bytes(out)


def pack_path(pets_dir, pid):
    return os.path.join(pets_dir, pid + ".pet")
