$ErrorActionPreference = 'Stop'
# 静默卸载：用户数据（%APPDATA%\RealtimeTranslate）默认保留
$key = Get-UninstallRegistryKey -SoftwareName '实时翻译*'
foreach ($k in $key) {
  $exe = ($k.UninstallString -replace '"', '')
  Uninstall-ChocolateyPackage -PackageName 'realtime-translate' -FileType 'exe' -SilentArgs '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART' -File $exe
}
