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

# 安全修复（2026-11-20，按安全评估报告 L-01）：.pet 包是外部文件，头里的尺寸 /
# 帧表未经校验就直接用 —— 恶意包可让程序解压出超大内存、或用越界帧索引崩溃。
# 宠物图实际最大约 512×512，这里按此设上限；文件本身超过 16MB 也直接拒绝。
MAX_PET_FILE_BYTES = 16 << 20       # 16 MB：正常 .pet 包远小于此
MAX_PET_HEADER_BYTES = 1 << 20      # 1 MB：头只是 JSON，超过即异常
MAX_PET_DIM = 512                   # 单边像素上限


class PetPackError(Exception):
    pass


class PetPack:
    def __init__(self, path):
        try:
            size = os.path.getsize(path)
            if size > MAX_PET_FILE_BYTES:
                raise PetPackError("动画包太大（%.1f MB，上限 %d MB），已拒绝"
                                   % (size / 1048576.0, MAX_PET_FILE_BYTES // 1048576))
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            raise PetPackError("读不到动画包：%s" % e)
        if not data.startswith(MAGIC) or len(data) < len(MAGIC) + 4:
            raise PetPackError("不是有效的动画包")
        (hl,) = struct.unpack_from("<I", data, len(MAGIC))
        if hl > MAX_PET_HEADER_BYTES:
            raise PetPackError("动画包头太大（%d 字节），已拒绝" % hl)
        start = len(MAGIC) + 4
        try:
            head = json.loads(data[start:start + hl].decode("utf-8"))
            self.w, self.h = int(head["w"]), int(head["h"])
            self.anims = {k: list(v) for k, v in head["anims"].items()}
            self._frames = [tuple(x) for x in head["frames"]]
        except (ValueError, KeyError, TypeError) as e:
            raise PetPackError("动画包头损坏：%s" % e)
        if not (1 <= self.w <= MAX_PET_DIM and 1 <= self.h <= MAX_PET_DIM):
            raise PetPackError("动画包尺寸不合法（%dx%d），已拒绝" % (self.w, self.h))
        self._body = data[start + hl:]
        n_frames = len(self._frames)
        for a in ANIMS:
            if not self.anims.get(a):
                raise PetPackError("动画包缺少动画：%s" % a)
            for i in self.anims[a]:
                if not isinstance(i, int) or not (0 <= i < n_frames):
                    raise PetPackError("动画 %s 的帧索引越界：%r" % (a, i))
        for off, ln in self._frames:
            if off < 0 or off + ln > len(self._body):
                raise PetPackError("动画包数据被截断")
        self._cache = {}

    def frames(self, anim):
        return self.anims.get(anim) or self.anims["idle"]

    def rgba(self, idx):
        """第 idx 帧的 RGBA 字节（w*h*4）。"""
        b = self._cache.get(idx)
        if b is None:
            if not isinstance(idx, int) or not (0 <= idx < len(self._frames)):
                raise PetPackError("帧索引越界：%r" % (idx,))
            off, ln = self._frames[idx]
            try:
                # L-01：解压限流 —— 压缩数据再小，解出来也不能超过 w*h*4+1 字节，
                # 否则就是恶意包（zip 炸弹），直接拒绝，不让它把内存撑爆。
                de = zlib.decompressobj()
                b = de.decompress(self._body[off:off + ln], self.w * self.h * 4 + 1)
                if de.unconsumed_tail or not de.eof:
                    raise PetPackError("动画帧数据异常")
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
