; Inno Setup 脚本 — 生成带卸载功能的安装向导（需 Inno Setup 6.x）
;   标准版：需先有 RealtimeTranslate.exe（build_exe.bat 生成）          →  iscc installer.iss
;   离线版：需先有 dist\RealtimeTranslateOffline\（build_offline.bat 生成） →  iscc /DOFFLINE=1 installer.iss
;   两个版本使用同一个 AppId：互相覆盖升级，开始菜单/自启项/设置通用。
;
; 中文安装界面：官方安装包不带简体中文语言包。如需中文向导，请从
;   https://jrsoftware.org/files/istrans/  下载 ChineseSimplified.isl
; 放到本文件同目录（或 Inno Setup 的 Languages 目录）。找不到时自动回退为英文向导，不会编译失败。

#ifndef MyAppVersion
  #define MyAppVersion "2.14.0"
#endif
#define MyAppName "实时翻译"
#ifdef OFFLINE
  #define MyEdition "_Offline"
  #define MyEditionLabel "（离线版）"
#else
  #define MyEdition ""
  #define MyEditionLabel ""
#endif
#define MyAppNameEn "RealtimeTranslate"
#define MyAppPublisher "Realtime Translate"
#define MyAppExeName "RealtimeTranslate.exe"

[Setup]
AppId={{A8F3C2E1-9B4D-4E7A-8C1F-2D6E5B9A0F3C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}{#MyEditionLabel}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppNameEn}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=RealtimeTranslate{#MyEdition}_Setup_v{#MyAppVersion}
#ifdef OFFLINE
; 离线版体积大：用 64 位模式 + 更强压缩，并允许在较慢机器上多线程压缩
Compression=lzma2/max
LZMANumBlockThreads=4
#else
Compression=lzma2
#endif
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}
; 与 desktop_translator.py 中的 MUTEX_NAME 一致：程序运行时安装/卸载会提示先关闭，
; 升级时自动关闭旧版本，避免 exe 被占用写入失败
AppMutex=RealtimeTranslate_SingleInstance
CloseApplications=yes
RestartApplications=no
#ifexist "app.ico"
SetupIconFile=app.ico
#endif

[Languages]
#ifexist "ChineseSimplified.isl"
Name: "chinesesimplified"; MessagesFile: "ChineseSimplified.isl"
#elif FileExists(CompilerPath + "Languages\ChineseSimplified.isl")
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#endif
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"; Flags: unchecked
Name: "autostart"; Description: "开机自动启动（最小化到托盘，随时用 Ctrl+Alt+T 唤出）"; GroupDescription: "附加选项:"; Flags: unchecked

[Files]
#ifdef OFFLINE
; onedir：exe + _internal（运行库）+ 内置语言包，整个文件夹递归安装
Source: "dist\RealtimeTranslateOffline\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#else
Source: "RealtimeTranslate.exe"; DestDir: "{app}"; Flags: ignoreversion
#endif

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; 与程序内「开机自启」复选框使用同一个注册表值，二者互通；卸载时自动清除
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "RealtimeTranslate"; ValueData: """{app}\{#MyAppExeName}"" --minimized"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 {#MyAppName}"; Flags: nowait postinstall skipifsilent

; v2.10：不再无条件删除 %APPDATA%\RealtimeTranslate。
; 那个目录里有翻译历史数据库（history.db）、设置（config.json）、
; 用户导入 / 下载的离线语言包（models）等，用户重装 / 升级时往往还想留着，
; 所以卸载最后一步（见下面 [Code]）弹窗问一句：删不删。

[Code]
// 卸载收尾：询问是否同时删除用户数据（翻译历史数据库、设置、离线语言包）。
//   选「是」：整个数据目录删除，无法恢复；
//   选「否」（默认按钮）：保留，以后重装能接着用；
//   静默卸载（/SILENT /VERYSILENT）或 /SUPPRESSMSGBOXES：一律保留，绝不静默删用户数据。
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir, Msg: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;
  DataDir := ExpandConstant('{userappdata}\RealtimeTranslate');
  if not DirExists(DataDir) then
    Exit;
  if UninstallSilent then
    Exit;
  Msg := '是否同时删除「实时翻译」的用户数据？' + #13#10 + #13#10 +
         '包括：翻译历史记录数据库、程序设置、术语表、已导入 / 下载的离线语言包。' + #13#10 +
         '位置：' + DataDir + #13#10 + #13#10 +
         '选「是」：全部删除，无法恢复。' + #13#10 +
         '选「否」：保留这些数据，以后重新安装可以继续使用。';
  if MsgBox(Msg, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    DelTree(DataDir, True, True, True);
end;
