; Inno Setup 脚本 — 生成带卸载功能的安装向导（需 Inno Setup 6.x）
;   v2.15.4：与 RealtimeTranslate_Setup.nsi 对齐——升级提示 / 同版本修复、沿用上次目录和勾选、
;   开始菜单快捷方式可选、离线版限 64 位、升级只清旧程序文件不碰用户数据、
;   卸载支持 /DELDATA（删用户数据）和 /KEEPDATA（不问不删），并清理托盘日志。
;   静默安装：Setup.exe /VERYSILENT [/DIR=目录] [/TASKS=desktopicon,autostart]
;   标准版：需先有 RealtimeTranslate.exe（build_exe.bat 生成）          →  iscc installer.iss
;   离线版：需先有 dist\RealtimeTranslateOffline\（build_offline.bat 生成） →  iscc /DOFFLINE=1 installer.iss
;   两个版本使用同一个 AppId：互相覆盖升级，开始菜单/自启项/设置通用。
;
; 中文安装界面：官方安装包不带简体中文语言包。如需中文向导，请从
;   https://jrsoftware.org/files/istrans/  下载 ChineseSimplified.isl
; 放到本文件同目录（或 Inno Setup 的 Languages 目录）。找不到时自动回退为英文向导，不会编译失败。

#ifndef MyAppVersion
  #define MyAppVersion "2.15.4"
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
#ifdef OFFLINE
; v2.15.4：离线版只有 64 位运行库（ctranslate2 没有 32 位版），32 位系统直接拒绝安装
ArchitecturesAllowed=x64
#endif
; v2.15.4：升级时沿用上次的安装目录和开始菜单组，组件页显示上次的勾选
UsePreviousAppDir=yes
UsePreviousTasks=yes
; 「应用和功能」里显示的名称（版本、发布者、大小由 Inno 自动写入）
UninstallDisplayName={#MyAppName}{#MyEditionLabel}
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
Name: "startmenu"; Description: "创建开始菜单快捷方式"; GroupDescription: "附加选项:"
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"; Flags: unchecked
Name: "autostart"; Description: "开机自动启动（最小化到托盘，随时用 Ctrl+Alt+T 唤出）"; GroupDescription: "附加选项:"; Flags: unchecked

[Files]
#ifdef OFFLINE
; onedir：exe + _internal（运行库）+ 内置语言包，整个文件夹递归安装
Source: "dist\RealtimeTranslateOffline\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#else
Source: "RealtimeTranslate.exe"; DestDir: "{app}"; Flags: ignoreversion
#endif
Source: "CHANGELOG.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[InstallDelete]
; v2.15.4 升级清理：只清安装目录里旧版的程序文件，用户数据（%APPDATA%）完全不碰
#ifdef OFFLINE
; 运行库整体替换，防止旧版残留的 DLL 和新版混用
Type: filesandordirs; Name: "{app}\_internal"
#endif

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenu
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"; Tasks: startmenu
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; 与程序内「开机自启」复选框使用同一个注册表值，二者互通；卸载时自动清除
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "RealtimeTranslate"; ValueData: """{app}\{#MyAppExeName}"" --minimized"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 {#MyAppName}"; Flags: nowait postinstall skipifsilent

; v2.10：不再无条件删除 %APPDATA%\RealtimeTranslate。
; 那个目录里有翻译历史数据库（history.db）、设置（config.json）、
; 用户导入 / 下载的离线语言包（models）等，用户重装 / 升级时往往还想留着，
; 所以卸载最后一步（见下面 [Code]
const
  NSIS_UNINST_KEY = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\RealtimeTranslate';
  INNO_UNINST_KEY = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{A8F3C2E1-9B4D-4E7A-8C1F-2D6E5B9A0F3C}_is1';

// 命令行里有没有某个开关（不区分大小写），例如 /DELDATA、/KEEPDATA
function HasSwitch(const Name: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Name) = 0 then
    begin
      Result := True;
      Exit;
    end;
end;

function ReadUninstValue(const Key, Name: String; var Value: String): Boolean;
begin
  Result := RegQueryStringValue(HKLM, Key, Name, Value) or
            RegQueryStringValue(HKCU, Key, Name, Value);
end;

// v2.15.4 安装前：提示升级 / 重装；检测到 NSIS 版安装包装过时提醒（两者不共用卸载信息）
function InitializeSetup(): Boolean;
var
  OldVer, NsisVer: String;
begin
  Result := True;
  if ReadUninstValue(INNO_UNINST_KEY, 'DisplayVersion', OldVer) and not WizardSilent then
  begin
    if OldVer = '{#MyAppVersion}' then
      Result := MsgBox('已安装同一版本（{#MyAppVersion}）。要重新安装（修复）吗？',
                       mbConfirmation, MB_YESNO) = IDYES
    else
      Result := MsgBox('检测到已安装 {#MyAppName} ' + OldVer + '，将升级到 {#MyAppVersion}。' + #13#10 +
                       '你的翻译历史、设置和语言包会保留。',
                       mbInformation, MB_OKCANCEL) = IDOK;
    if not Result then
      Exit;
  end;
  if ReadUninstValue(NSIS_UNINST_KEY, 'DisplayVersion', NsisVer) and not WizardSilent then
    MsgBox('检测到用另一种安装包（NSIS 版）装过 {#MyAppName} ' + NsisVer + '。' + #13#10 +
           '建议先在「应用和功能」里把它卸载（选择保留用户数据），避免列表里出现两个条目。' + #13#10 +
           '点「确定」继续安装。', mbInformation, MB_OK);
end;

// 卸载收尾：询问是否同时删除用户数据（翻译历史数据库、设置、离线语言包）。
//   选「是」：整个数据目录删除，无法恢复；
//   选「否」（默认按钮）：保留，以后重装能接着用；
//   静默卸载（/SILENT /VERYSILENT）：一律保留；加 /DELDATA 才删；/KEEPDATA 不问不删。
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir, Msg: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;
  DeleteFile(ExpandConstant('{%TEMP}\RealtimeTranslate_tray.log'));
  DataDir := ExpandConstant('{userappdata}\RealtimeTranslate');
  if not DirExists(DataDir) then
    Exit;
  if HasSwitch('/KEEPDATA') then
    Exit;
  if HasSwitch('/DELDATA') then
  begin
    DelTree(DataDir, True, True, True);
    Exit;
  end;
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
