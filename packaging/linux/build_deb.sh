#!/usr/bin/env bash
# .deb：bash packaging/linux/build_deb.sh   （先自动跑 build_linux.sh）
set -euo pipefail
cd "$(dirname "$0")/../.."
[ -x dist/RealtimeTranslate/realtime-translate ] || bash packaging/linux/build_linux.sh
VER=$(python3 -c 'import re;print(re.search(r"__version__ = \"([^\"]+)\"",open("desktop_translator.py",encoding="utf-8").read()).group(1))')
case "$(uname -m)" in x86_64) DARCH=amd64;; aarch64) DARCH=arm64;; *) DARCH=$(dpkg --print-architecture);; esac
ROOTFS=$(mktemp -d)
install -d "$ROOTFS/DEBIAN" "$ROOTFS/opt/realtime-translate" "$ROOTFS/usr/bin" \
  "$ROOTFS/usr/share/applications" "$ROOTFS/usr/share/icons/hicolor/256x256/apps" "$ROOTFS/usr/share/metainfo"
cp -a dist/RealtimeTranslate/. "$ROOTFS/opt/realtime-translate/"
rm -f "$ROOTFS/opt/realtime-translate/install.sh"
ln -s /opt/realtime-translate/realtime-translate "$ROOTFS/usr/bin/realtime-translate"
cp packaging/linux/realtime-translate.desktop "$ROOTFS/usr/share/applications/"
cp packaging/linux/realtime-translate.metainfo.xml "$ROOTFS/usr/share/metainfo/com.realtimetranslate.app.metainfo.xml"
[ -f dist/RealtimeTranslate/realtime-translate.png ] && cp dist/RealtimeTranslate/realtime-translate.png "$ROOTFS/usr/share/icons/hicolor/256x256/apps/"
SIZE=$(du -sk "$ROOTFS" | cut -f1)
sed -e "s/^Architecture: .*/Architecture: $DARCH/" -e "s/^Installed-Size: .*/Installed-Size: $SIZE/" \
    -e "s/^Version: .*/Version: $VER/" packaging/linux/debian/control > "$ROOTFS/DEBIAN/control"
for s in postinst prerm postrm; do install -m 0755 "packaging/linux/debian/$s" "$ROOTFS/DEBIAN/$s"; done
mkdir -p Output
DEB="Output/realtime-translate_${VER}_${DARCH}.deb"
fakeroot dpkg-deb --build --root-owner-group "$ROOTFS" "$DEB" 2>/dev/null || dpkg-deb --build --root-owner-group "$ROOTFS" "$DEB"
rm -rf "$ROOTFS"
dpkg-deb --info "$DEB" | sed -n '1,12p'
sha256sum "$DEB"
echo "完成：$DEB   安装：sudo apt install ./$(basename "$DEB")   卸载：sudo apt remove realtime-translate"
