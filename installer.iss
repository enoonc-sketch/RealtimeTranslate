; Inno Setup 脚本 — 生成带卸载功能的安装向导（需 Inno Setup 6.x）
;   标准版：需先有 RealtimeTranslate.exe（build_exe.bat 生成）          →  iscc installer.iss
;   离线版：需先有 dist\RealtimeTranslateOffline\（build_offline.bat 生成） →  iscc /DOFFLINE=1 installer.iss
;   两个版本使用同一个 AppId：互相覆盖升级，开始菜单/自启项/设置通用。
;
; 中文安装界面：官方安装包不带简体中文语言包。如需中文向导，请从
;   https://jrsoftware.org/files/istrans/  下载 ChineseSimplified.isl
; 放到本文件同目录（或 Inno Setup 的 Languages 目录）。找不到时自动回退为英文向导，不会编译失败。

#ifndef MyAppVersion
  #define MyAppVersion "2.6.0"
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

[UninstallDelete]
; 程序设置保存在 %APPDATA%\RealtimeTranslate（config.json / crash.log）
Type: filesandordirs; Name: "{userappdata}\RealtimeTranslate"
