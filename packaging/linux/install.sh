#!/usr/bin/env bash
# 免 root 安装 / 卸载（tar.gz 版用）
#   ./install.sh             安装到 ~/.local/opt/realtime-translate，加菜单项和命令 realtime-translate
#   ./install.sh --uninstall 卸载（询问是否删除 ~/.config/RealtimeTranslate 里的历史和设置）
#   ./install.sh --uninstall --purge   卸载并删除用户数据
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
DEST="$PREFIX/opt/realtime-translate"
BIN="$PREFIX/bin/realtime-translate"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/realtime-translate.desktop"
DATA="${XDG_CONFIG_HOME:-$HOME/.config}/RealtimeTranslate"

if [ "${1:-}" = "--uninstall" ]; then
  pkill -f "$DEST/realtime-translate" 2>/dev/null || true
  rm -rf "$DEST" "$BIN" "$APPS/realtime-translate.desktop" "$ICONS/realtime-translate.png" "$AUTOSTART"
  command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
  if [ -d "$DATA" ]; then
    if [ "${2:-}" = "--purge" ]; then rm -rf "$DATA"; echo "已删除用户数据"
    elif [ -t 0 ]; then
      read -r -p "同时删除翻译历史、设置和语言包（$DATA）？[y/N] " a
      case "$a" in y|Y) rm -rf "$DATA"; echo "已删除用户数据";; *) echo "已保留用户数据";; esac
    else echo "已保留用户数据：$DATA"; fi
  fi
  echo "卸载完成"; exit 0
fi

pkill -f "$DEST/realtime-translate" 2>/dev/null || true
mkdir -p "$DEST" "$(dirname "$BIN")" "$APPS" "$ICONS"
rm -rf "$DEST"/*                                  # 升级：先清旧程序文件（用户数据在 ~/.config，不受影响）
cp -a "$HERE"/. "$DEST"/
ln -sf "$DEST/realtime-translate" "$BIN"
[ -f "$HERE/realtime-translate.png" ] && cp "$HERE/realtime-translate.png" "$ICONS/"
sed "s#^Exec=.*#Exec=$DEST/realtime-translate %U#" "$HERE/realtime-translate.desktop" > "$APPS/realtime-translate.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
echo "已安装到 $DEST"
echo "从应用菜单打开「实时翻译」，或在终端运行 realtime-translate（确认 $PREFIX/bin 在 PATH 里）"
echo "可选依赖：sudo apt install tesseract-ocr tesseract-ocr-chi-sim xclip   （截图 OCR、剪贴板）"
[ "${XDG_SESSION_TYPE:-}" = "wayland" ] && echo "注意：当前是 Wayland 会话，全局快捷键不可用（需 X11 / Xorg 会话）。" || true
