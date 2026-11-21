#!/usr/bin/env bash
# AppImage：bash packaging/linux/build_appimage.sh   （先自动跑 build_linux.sh；会下载 appimagetool）
set -euo pipefail
cd "$(dirname "$0")/../.."
[ -x dist/RealtimeTranslate/realtime-translate ] || bash packaging/linux/build_linux.sh
VER=$(python3 -c 'import re;print(re.search(r"__version__ = \"([^\"]+)\"",open("desktop_translator.py",encoding="utf-8").read()).group(1))')
ARCH=$(uname -m)
APPDIR=$(mktemp -d)/RealtimeTranslate.AppDir
install -d "$APPDIR/usr/opt/realtime-translate" "$APPDIR/usr/share/metainfo"
cp -a dist/RealtimeTranslate/. "$APPDIR/usr/opt/realtime-translate/"
rm -f "$APPDIR/usr/opt/realtime-translate/install.sh"
install -m 0755 packaging/linux/AppRun "$APPDIR/AppRun"
cp packaging/linux/realtime-translate.desktop "$APPDIR/"
cp packaging/linux/realtime-translate.metainfo.xml "$APPDIR/usr/share/metainfo/com.realtimetranslate.app.appdata.xml"
if [ -f dist/RealtimeTranslate/realtime-translate.png ]; then cp dist/RealtimeTranslate/realtime-translate.png "$APPDIR/"; fi
TOOL=.buildenv-linux/appimagetool-$ARCH.AppImage
if [ ! -x "$TOOL" ]; then
  mkdir -p .buildenv-linux
  curl -fsSL -o "$TOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"
  chmod +x "$TOOL"
fi
mkdir -p Output
OUT="Output/RealtimeTranslate_v${VER}_${ARCH}.AppImage"
ARCH=$ARCH APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$OUT"
sha256sum "$OUT"
echo "完成：$OUT   chmod +x 后双击运行"
