; RealtimeTranslate - NSIS 安装脚本（标准版 / 离线版共用）
;   标准版：makensis RealtimeTranslate_Setup.nsi
;   离线版：makensis RealtimeTranslate_Setup_Offline.nsi   （它只是 !define OFFLINE 后 include 本文件）
;
; v2.15.4 安装 / 卸载基本功能：
;   - 组件页：可勾选「开始菜单 / 桌面快捷方式 / 开机自启」（旧版没有组件页，后两项永远装不上）
;   - 安装前检测程序是否在运行（单实例互斥体），提示后自动关闭，避免 exe 被占用写入失败
;   - 检测到旧版本：显示旧版本号，装回原目录并清理旧版残留（不调用旧卸载程序，用户数据完全不碰）
;   - 离线版 64 位程序装到 Program Files（64 位），标准版装到 Program Files (x86)
;   - 快捷方式装给所有用户（SetShellVarContext all），卸载时同样清理
;   - 「应用和功能」里显示版本、发布者、大小、安装位置，支持静默卸载
;   - 卸载：先关闭正在运行的程序 → 删程序文件、快捷方式、自启项 → 询问是否删除用户数据
;     （默认「否」；静默卸载 /S 一律保留数据，加 /DELDATA 才删）
;   - 安装 / 卸载均支持静默参数：Setup.exe /S [/D=安装目录]，Uninstall.exe /S [/DELDATA]

Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "x64.nsh"

!define APP_VERSION "2.15.4"
!define APP_NAME "实时翻译"
!define APP_ID "RealtimeTranslate"
!define APP_EXE "RealtimeTranslate.exe"
!define APP_PUBLISHER "Realtime Translate"
!define APP_MUTEX "RealtimeTranslate_SingleInstance"   ; 与 single_instance.DEFAULT_MUTEX_NAME 一致，勿改
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_ID}"
!define RUN_KEY "Software\Microsoft\Windows\CurrentVersion\Run"

!ifdef OFFLINE
  !define EDITION_LABEL " 离线版"
  !define OUT_SUFFIX "_Offline"
!else
  !define EDITION_LABEL ""
  !define OUT_SUFFIX ""
!endif

Name "${APP_NAME} ${APP_VERSION}${EDITION_LABEL}"
OutFile "Output\RealtimeTranslate_Setup_v${APP_VERSION}${OUT_SUFFIX}.exe"
!ifdef OFFLINE
InstallDir "$PROGRAMFILES64\${APP_ID}"
!else
InstallDir "$PROGRAMFILES32\${APP_ID}"
!endif
InstallDirRegKey HKLM "Software\${APP_ID}" "InstallDir"
RequestExecutionLevel admin
ShowInstDetails show
ShowUnInstDetails show
SetCompressor /SOLID lzma
Icon "app.ico"
UninstallIcon "app.ico"
BrandingText "${APP_NAME} ${APP_VERSION}${EDITION_LABEL}"

VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "CompanyName" "${APP_PUBLISHER}"
VIAddVersionKey "FileVersion" "${APP_VERSION}.0"
VIAddVersionKey "ProductVersion" "${APP_VERSION}.0"
VIAddVersionKey "FileDescription" "${APP_NAME}${EDITION_LABEL}安装程序"
VIAddVersionKey "LegalCopyright" "${APP_PUBLISHER}"

Var OldVersion
Var OldDir

; ---------------------------------------------------------------- 界面
!define MUI_ABORTWARNING
!define MUI_ICON "app.ico"
!define MUI_UNICON "app.ico"
!define MUI_WELCOMEPAGE_TEXT "将在电脑上安装 ${APP_NAME} ${APP_VERSION}${EDITION_LABEL}。$\r$\n$\r$\n如果程序正在运行，安装程序会先自动关闭它。你的翻译历史、设置和语言包不会受影响。$\r$\n$\r$\n点「下一步」继续。"
!insertmacro MUI_PAGE_WELCOME
!define MUI_COMPONENTSPAGE_SMALLDESC
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "立即运行${APP_NAME}"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

; ---------------------------------------------------------------- 公共：关闭正在运行的程序
; 用单实例互斥体判断是否在运行；在运行就问一句（静默模式直接关），先正常结束，3 秒后强制结束。
!macro CLOSE_APP UN
Function ${UN}CloseRunningApp
  StrCpy $R9 0
  loop:
    System::Call 'kernel32::OpenMutexW(i 0x00100000, i 0, w "${APP_MUTEX}") p .r0'
    ${If} $0 == 0
      Return
    ${EndIf}
    System::Call 'kernel32::CloseHandle(p r0)'
    ${If} $R9 == 0
      MessageBox MB_OKCANCEL|MB_ICONINFORMATION "${APP_NAME}正在运行，需要先关闭它。$\r$\n$\r$\n点「确定」自动关闭并继续。" /SD IDOK IDOK +2
      Abort
      nsExec::Exec 'taskkill /IM "${APP_EXE}"'
    ${ElseIf} $R9 == 6
      nsExec::Exec 'taskkill /F /T /IM "${APP_EXE}"'
    ${ElseIf} $R9 > 20
      MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "无法关闭${APP_NAME}。请在托盘图标上右键「退出」后点「重试」。" /SD IDCANCEL IDRETRY +2
      Abort
      StrCpy $R9 0
      Goto loop
    ${EndIf}
    Sleep 500
    IntOp $R9 $R9 + 1
    Goto loop
FunctionEnd
!macroend
!insertmacro CLOSE_APP ""
!insertmacro CLOSE_APP "un."

; ---------------------------------------------------------------- 安装
Function .onInit
  !ifdef OFFLINE
    ${IfNot} ${RunningX64}
      MessageBox MB_ICONSTOP "离线版需要 64 位 Windows。请改用标准版安装包。" /SD IDOK
      Abort
    ${EndIf}
    SetRegView 64
  !endif
  ; 检测旧版本
  ReadRegStr $OldVersion HKLM "${UNINST_KEY}" "DisplayVersion"
  ReadRegStr $OldDir HKLM "Software\${APP_ID}" "InstallDir"
  ${If} $OldDir != ""
    StrCpy $INSTDIR $OldDir          ; 升级时装回原来的目录
  ${EndIf}
  ${If} $OldVersion != ""
    ${If} $OldVersion == "${APP_VERSION}"
      MessageBox MB_YESNO|MB_ICONQUESTION "已安装同一版本（${APP_VERSION}）。要重新安装（修复）吗？" /SD IDYES IDYES +2
      Abort
    ${Else}
      MessageBox MB_OKCANCEL|MB_ICONINFORMATION "检测到已安装 ${APP_NAME} $OldVersion，将升级到 ${APP_VERSION}。$\r$\n你的翻译历史、设置和语言包会保留。" /SD IDOK IDOK +2
      Abort
    ${EndIf}
  ${EndIf}
FunctionEnd

Section "-关闭正在运行的程序"
  Call CloseRunningApp
  ; 升级：不调用旧版卸载程序（2.15.0 及以前的卸载程序在静默模式下会误删用户数据），
  ; 改为直接清掉旧版留下的、新版不再使用的东西，再覆盖安装。用户数据（%APPDATA%）完全不碰。
  ${If} $OldDir != ""
    DetailPrint "正在升级旧版本 $OldVersion ..."
    Delete "$OldDir\Uninstall.exe"
    !ifdef OFFLINE
      RMDir /r "$OldDir\_internal"       ; 运行库整体替换，防止旧版残留的 DLL 和新版混用
    !endif
    SetShellVarContext current           ; 旧版快捷方式建在当前用户下，新版改为所有用户
    Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
    Delete "$SMPROGRAMS\${APP_NAME}\卸载${APP_NAME}.lnk"
    RMDir "$SMPROGRAMS\${APP_NAME}"
    Delete "$DESKTOP\${APP_NAME}.lnk"
  ${EndIf}
SectionEnd

Section "${APP_NAME}（必选）" SecMain
  SectionIn RO
  SetShellVarContext all
  SetOutPath "$INSTDIR"
  !ifdef OFFLINE
    File /r "dist\RealtimeTranslateOffline\*.*"
  !else
    File "${APP_EXE}"
  !endif
  File /nonfatal "CHANGELOG.md"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  WriteRegStr HKLM "Software\${APP_ID}" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "Software\${APP_ID}" "Version" "${APP_VERSION}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayName" "${APP_NAME}${EDITION_LABEL}"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "${UNINST_KEY}" "Publisher" "${APP_PUBLISHER}"
  WriteRegStr HKLM "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINST_KEY}" "DisplayIcon" "$INSTDIR\${APP_EXE}"
  WriteRegStr HKLM "${UNINST_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKLM "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINST_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "${UNINST_KEY}" "EstimatedSize" "$0"
SectionEnd

Section "开始菜单快捷方式" SecStartMenu
  SetShellVarContext all
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\卸载${APP_NAME}.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

Section /o "桌面快捷方式" SecDesktop
  SetShellVarContext all
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
SectionEnd

Section /o "开机自动启动（缩在托盘）" SecAutostart
  ; 写当前用户的 Run 键，和程序内「开机自启」开关是同一个值，两边互通
  WriteRegStr HKCU "${RUN_KEY}" "${APP_ID}" '"$INSTDIR\${APP_EXE}" --minimized'
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "程序本体（必选）。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecStartMenu} "在开始菜单里放程序和卸载的快捷方式。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "在桌面放一个快捷方式。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecAutostart} "登录 Windows 后自动运行并缩在托盘；以后可在程序「高级设置 → 常规」里关掉。"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ---------------------------------------------------------------- 卸载
Function un.onInit
  !ifdef OFFLINE
    SetRegView 64
  !endif
FunctionEnd

Section "Uninstall"
  Call un.CloseRunningApp
  SetShellVarContext all

  ; 程序文件
  !ifdef OFFLINE
    RMDir /r "$INSTDIR\_internal"
    RMDir /r "$INSTDIR\offline_models"
  !endif
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\CHANGELOG.md"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"                       ; 不用 /r：用户自己放进安装目录的文件不误删

  ; 快捷方式（新版装给所有用户；旧版 2.15.0 以前装在当前用户下，两处都清）
  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\卸载${APP_NAME}.lnk"
  RMDir "$SMPROGRAMS\${APP_NAME}"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  SetShellVarContext current
  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\卸载${APP_NAME}.lnk"
  RMDir "$SMPROGRAMS\${APP_NAME}"
  Delete "$DESKTOP\${APP_NAME}.lnk"

  ; 注册表：自启项、安装信息
  DeleteRegValue HKCU "${RUN_KEY}" "${APP_ID}"
  DeleteRegKey HKLM "${UNINST_KEY}"
  DeleteRegKey HKLM "Software\${APP_ID}"

  ; 临时文件（托盘日志）
  Delete "$TEMP\RealtimeTranslate_tray.log"

  ; 用户数据：升级时（/KEEPDATA）不问不删；/DELDATA 强制删；否则询问（静默默认保留）
  ${GetParameters} $R0
  ClearErrors
  ${GetOptions} $R0 "/KEEPDATA" $R1
  ${IfNot} ${Errors}
    Goto done
  ${EndIf}
  ${IfNot} ${FileExists} "$APPDATA\${APP_ID}\*.*"
    Goto done
  ${EndIf}
  ClearErrors
  ${GetOptions} $R0 "/DELDATA" $R1
  ${IfNot} ${Errors}
    RMDir /r "$APPDATA\${APP_ID}"
    Goto done
  ${EndIf}
  MessageBox MB_YESNO|MB_DEFBUTTON2|MB_ICONQUESTION "是否同时删除「${APP_NAME}」的用户数据？$\r$\n$\r$\n包括：翻译历史记录、程序设置、术语表、已导入 / 下载的离线语言包。$\r$\n位置：$APPDATA\${APP_ID}$\r$\n$\r$\n选「是」：全部删除，无法恢复。$\r$\n选「否」：保留，以后重新安装可以继续使用。" /SD IDNO IDNO done
  RMDir /r "$APPDATA\${APP_ID}"
  done:
SectionEnd
