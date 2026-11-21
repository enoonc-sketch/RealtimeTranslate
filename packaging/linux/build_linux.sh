#!/usr/bin/env bash
# Linux 可执行文件夹 + tar.gz：bash packaging/linux/build_linux.sh
# 依赖：python3 (>=3.9) python3-tk python3-venv；运行时可选 tesseract-ocr xclip
set -euo pipefail
cd "$(dirname "$0")/../.."
VER=$(python3 -c 'import re;print(re.search(r"__version__ = \"([^\"]+)\"",open("desktop_translator.py",encoding="utf-8").read()).group(1))')
ARCH=$(uname -m)
echo "== 实时翻译 ${VER} Linux (${ARCH}) =="
python3 -c 'import tkinter' 2>/dev/null || { echo "缺 tkinter：sudo apt install python3-tk"; exit 1; }
[ -x .buildenv-linux/bin/python ] || python3 -m venv .buildenv-linux
BPY=.buildenv-linux/bin/python
$BPY -m pip install -q --disable-pip-version-check -r requirements-lock.txt "pynput>=1.7"
rm -rf build dist/RealtimeTranslate
$BPY -m PyInstaller --noconfirm --clean packaging/linux/realtime_translate_linux.spec
OUT=dist/RealtimeTranslate
[ -x "$OUT/realtime-translate" ] || { echo "打包失败"; exit 1; }
# 图标 PNG（从 ico 提取 256px；没 python PIL 就用 ImageMagick；都没有就跳过）
$BPY - <<'EOF' || convert 'app.ico[5]' "$OUT/realtime-translate.png" 2>/dev/null || true
import struct, sys
data = open("app.ico", "rb").read()
n = struct.unpack_from("<H", data, 4)[0]
best = max((struct.unpack_from("<BBBBHHII", data, 6 + 16 * i) for i in range(n)), key=lambda e: (e[0] or 256))
blob = data[best[7]:best[7] + best[6]]
if blob[:8] != b"\x89PNG\r\n\x1a\n":
    sys.exit(1)
open("dist/RealtimeTranslate/realtime-translate.png", "wb").write(blob)
EOF
cp packaging/linux/realtime-translate.desktop "$OUT/"
cp packaging/linux/install.sh "$OUT/" && chmod +x "$OUT/install.sh"
cp CHANGELOG.md "$OUT/" 2>/dev/null || true
"$OUT/realtime-translate" --selftest || { echo "自检失败"; exit 1; }
mkdir -p Output
TAR="Output/RealtimeTranslate_v${VER}_linux_${ARCH}.tar.gz"
tar -C dist -czf "$TAR" RealtimeTranslate
sha256sum "$TAR"
echo "完成：$TAR   解压后运行 ./install.sh 安装到 ~/.local（不需要 root）"
