@echo off
rem 给 exe / 安装包 / 卸载程序签名：packaging\windows\sign.bat 文件1 [文件2 ...]
rem 需要 Windows SDK 的 signtool，以及环境变量 SIGN_PFX（证书 .pfx 路径）、SIGN_PFX_PASS（密码）
rem 没配证书就跳过（返回 0），不阻断构建
setlocal
if not defined SIGN_PFX ( echo [签名] 未设置 SIGN_PFX，跳过 & exit /b 0 )
set "ST="
for /f "delims=" %%S in ('where signtool 2^>nul') do if not defined ST set "ST=%%S"
if not defined ST for /f "delims=" %%S in ('dir /b /s "%ProgramFiles(x86)%\Windows Kits\10\bin\*\x64\signtool.exe" 2^>nul') do set "ST=%%S"
if not defined ST ( echo [签名] 找不到 signtool.exe（安装 Windows SDK） & exit /b 1 )
"%ST%" sign /fd SHA256 /td SHA256 /tr http://timestamp.digicert.com /f "%SIGN_PFX%" /p "%SIGN_PFX_PASS%" %*
