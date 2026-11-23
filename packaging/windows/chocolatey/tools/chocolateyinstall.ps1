$ErrorActionPreference = 'Stop'
$packageArgs = @{
  packageName    = 'realtime-translate'
  fileType       = 'exe'
  url64bit       = 'https://github.com/OWNER/RealtimeTranslate/releases/download/v2.15.7/RealtimeTranslate_Setup_v2.15.7.exe'
  checksum64     = '0000000000000000000000000000000000000000000000000000000000000000'
  checksumType64 = 'sha256'
  silentArgs     = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /ALLUSERS'
  validExitCodes = @(0)
}
Install-ChocolateyPackage @packageArgs
