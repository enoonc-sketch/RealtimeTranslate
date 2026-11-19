"""把 tools/pet_render 渲染出的 PNG 帧打成 pets/<id>.pet（开发用，需要 Pillow；用户机器不需要）。
用法：python tools/pack_pets.py _frames pets
"""
import json
import os
import struct
import sys
import zlib

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from pet_catalog import pet_ids  # noqa: E402

ORDER = [("idle", 4), ("blink", 1), ("sleep", 4), ("think", 4), ("happy", 6), ("sad", 3), ("alert", 3)]
SIZE = 112


def load(path):
    im = Image.open(path).convert("RGBA")
    # 用预乘 alpha 缩小，边缘不会出现白边/黑边
    return im.convert("RGBa").resize((SIZE, SIZE), Image.LANCZOS).convert("RGBA")


def main(src, dst):
    os.makedirs(dst, exist_ok=True)
    total = 0
    for pid in pet_ids():
        anims, frames, blobs, off = {}, [], [], 0
        for name, n in ORDER:
            idx = []
            for i in range(n):
                blob = zlib.compress(load(os.path.join(src, pid, "%s_%d.png" % (name, i))).tobytes(), 9)
                frames.append([off, len(blob)]); blobs.append(blob); off += len(blob); idx.append(len(frames) - 1)
            anims[name] = idx
        head = json.dumps({"w": SIZE, "h": SIZE, "anims": anims, "frames": frames}, separators=(",", ":")).encode("utf-8")
        out = os.path.join(dst, pid + ".pet")
        with open(out, "wb") as f:
            f.write(b"RTPET1\n" + struct.pack("<I", len(head)) + head + b"".join(blobs))
        total += os.path.getsize(out)
        print("%-8s %6.1f KB" % (pid, os.path.getsize(out) / 1024))
    print("合计 %.2f MB" % (total / 1048576))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
