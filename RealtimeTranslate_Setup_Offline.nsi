; RealtimeTranslate - 离线版 NSIS 安装脚本
; 打包 PyInstaller onedir 输出 dist\RealtimeTranslateOffline\（exe + _internal + 内置语言包）。
; 安装 / 卸载逻辑与标准版完全一致，统一维护在 RealtimeTranslate_Setup.nsi 里。
!define OFFLINE
!include "RealtimeTranslate_Setup.nsi"
