#!/usr/bin/env bash
# macOS 一键构建：.app → (可选)签名+公证 → .dmg
#   bash packaging/macos/build_macos.sh
# 环境变量（都可选）：
#   MAC_ARCH=universal2|arm64|x86_64     目标架构（默认本机；universal2 需要 universal2 版 Python）
#   MAC_SIGN_ID="Developer ID Application: 名字 (TEAMID)"   有就签名
#   MAC_NOTARY_PROFILE=名字               有就公证（先 xcrun notarytool store-credentials 名字）
set -euo pipefail
cd "$(dirname "$0")/../.."
ROOT="$PWD"; HERE="$ROOT/packaging/macos"
VER=$(python3 -c 'import re;print(re.search(r"__version__ = \"([^\"]+)\"",open("desktop_translator.py",encoding="utf-8").read()).group(1))')
APP="dist/实时翻译.app"; DMG="Output/RealtimeTranslate_v${VER}_macOS.dmg"
echo "== 实时翻译 ${VER} macOS 构建 =="

echo "[1/6] 检查 Python / tkinter"
python3 -c 'import sys,tkinter;assert sys.version_info>=(3,9);print("  Python",sys.version.split()[0],"Tk",tkinter.TkVersion)'

echo "[2/6] 独立构建环境"
[ -x .buildenv-mac/bin/python ] || python3 -m venv .buildenv-mac
BPY=.buildenv-mac/bin/python
$BPY -m pip install -q --disable-pip-version-check -r requirements-lock.txt "pynput>=1.7"

echo "[3/6] 生成 app.icns（从 app.ico）"
if [ ! -f "$HERE/app.icns" ]; then
  TMP=$(mktemp -d); SET="$TMP/app.iconset"; mkdir "$SET"
  sips -s format png app.ico --out "$TMP/base.png" >/dev/null
  for s in 16 32 128 256 512; do
    sips -z $s $s "$TMP/base.png" --out "$SET/icon_${s}x${s}.png" >/dev/null
    d=$((s*2)); sips -z $d $d "$TMP/base.png" --out "$SET/icon_${s}x${s}@2x.png" >/dev/null
  done
  iconutil -c icns "$SET" -o "$HERE/app.icns"; rm -rf "$TMP"
fi

echo "[4/6] 打包 .app"
rm -rf build dist
$BPY -m PyInstaller --noconfirm --clean packaging/macos/realtime_translate_mac.spec
[ -d "$APP" ] || { echo "打包失败：没有 $APP"; exit 1; }
"$APP/Contents/MacOS/RealtimeTranslate" --selftest || { echo "自检失败"; exit 1; }

echo "[5/6] 签名 / 公证"
if [ -n "${MAC_SIGN_ID:-}" ]; then
  codesign --force --deep --options runtime --timestamp \
    --entitlements "$HERE/entitlements.plist" --sign "$MAC_SIGN_ID" "$APP"
  codesign --verify --deep --strict "$APP"
else
  echo "  未设置 MAC_SIGN_ID：跳过签名（用户首次打开需右键「打开」）"
fi

echo "[6/6] 制作 DMG"
mkdir -p Output; rm -f "$DMG"
STAGE=$(mktemp -d); cp -R "$APP" "$STAGE/"; ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "实时翻译 ${VER}" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"
if [ -n "${MAC_SIGN_ID:-}" ]; then codesign --sign "$MAC_SIGN_ID" --timestamp "$DMG"; fi
if [ -n "${MAC_SIGN_ID:-}" ] && [ -n "${MAC_NOTARY_PROFILE:-}" ]; then
  xcrun notarytool submit "$DMG" --keychain-profile "$MAC_NOTARY_PROFILE" --wait
  xcrun stapler staple "$DMG"
fi
shasum -a 256 "$DMG"
echo "完成：$DMG"
echo "提示：首次使用全局快捷键需在「系统设置 → 隐私与安全性 → 辅助功能」里勾选实时翻译；"
echo "      截图 / 悬停 OCR 需要 brew install tesseract tesseract-lang，并授予「屏幕录制」权限。"
