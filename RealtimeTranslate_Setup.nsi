; RealtimeTranslate 2.14.0 - NSIS installer script
; Mirrors installer.iss (Inno Setup): machine-wide admin install to
; Program Files (x86), single EXE, Start Menu shortcuts, optional
; desktop icon + autostart, uninstaller that asks before deleting
; %APPDATA%\RealtimeTranslate user data.
; Built with NSIS 3.09 on Linux because Inno Setup 6 is 32-bit (blocked
; in this sandbox) and Inno Setup 7 refuses Wine's Windows version.

!include "MUI2.nsh"
!include "LogicLib.nsh"

Name "实时翻译 2.14.0"
OutFile "Output\RealtimeTranslate_Setup_v2.14.0.exe"
InstallDir "$PROGRAMFILES32\RealtimeTranslate"
InstallDirRegKey HKLM "Software\RealtimeTranslate" "InstallDir"
RequestExecutionLevel admin
ShowInstDetails show
ShowUnInstDetails show
Icon "app.ico"
UninstallIcon "app.ico"

VIProductVersion "2.14.0.0"
VIAddVersionKey "ProductName" "实时翻译"
VIAddVersionKey "CompanyName" "Realtime Translate"
VIAddVersionKey "FileVersion" "2.14.0.0"
VIAddVersionKey "ProductVersion" "2.14.0.0"
VIAddVersionKey "FileDescription" "实时翻译安装程序"

!define MUI_ABORTWARNING
!define MUI_ICON "app.ico"
!define MUI_UNICON "app.ico"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\RealtimeTranslate.exe"
!define MUI_FINISHPAGE_RUN_TEXT "立即运行实时翻译"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Section "实时翻译 (必选)" SecMain
  SectionIn RO
  SetOutPath "$INSTDIR"
  File "RealtimeTranslate.exe"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\实时翻译"
  CreateShortcut "$SMPROGRAMS\实时翻译\实时翻译.lnk" "$INSTDIR\RealtimeTranslate.exe"
  CreateShortcut "$SMPROGRAMS\实时翻译\卸载实时翻译.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\RealtimeTranslate" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RealtimeTranslate" "DisplayName" "实时翻译 2.14.0"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RealtimeTranslate" "DisplayVersion" "2.14.0"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RealtimeTranslate" "Publisher" "Realtime Translate"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RealtimeTranslate" "UninstallString" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RealtimeTranslate" "DisplayIcon" "$INSTDIR\RealtimeTranslate.exe"
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RealtimeTranslate" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RealtimeTranslate" "NoRepair" 1
SectionEnd

Section /o "桌面快捷方式" SecDesktop
  CreateShortcut "$DESKTOP\实时翻译.lnk" "$INSTDIR\RealtimeTranslate.exe"
SectionEnd

Section /o "开机自动启动（最小化到托盘）" SecAutostart
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "RealtimeTranslate" '"$INSTDIR\RealtimeTranslate.exe" --minimized'
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\RealtimeTranslate.exe"
  Delete "$INSTDIR\Uninstall.exe"
  Delete "$SMPROGRAMS\实时翻译\实时翻译.lnk"
  Delete "$SMPROGRAMS\实时翻译\卸载实时翻译.lnk"
  Delete "$DESKTOP\实时翻译.lnk"
  RMDir "$SMPROGRAMS\实时翻译"
  RMDir "$INSTDIR"
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "RealtimeTranslate"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\RealtimeTranslate"
  DeleteRegKey HKLM "Software\RealtimeTranslate"
  ; Ask before deleting user data (history DB, settings, downloaded models).
  ; Default button is No (keep data), same as installer.iss.
  ${If} ${FileExists} "$APPDATA\RealtimeTranslate\*.*"
    MessageBox MB_YESNO|MB_DEFBUTTON2|MB_ICONQUESTION "是否同时删除“实时翻译”的用户数据？$\n$\n包括：翻译历史记录数据库、程序设置、术语表、已导入 / 下载的离线语言包。$\n位置：$APPDATA\RealtimeTranslate$\n$\n选“是”：全部删除，无法恢复。$\n选“否”：保留这些数据，以后重新安装可以继续使用。" IDNO +3
    RMDir /r "$APPDATA\RealtimeTranslate"
  ${EndIf}
SectionEnd
