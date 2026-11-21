@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0\..\..\.."
rem MSIX：需要 Windows SDK（makeappx / signtool）。先运行 build_exe.bat。
rem 签名证书 Subject 必须等于 AppxManifest.xml 里的 Publisher；没签名的 MSIX 只能在开发者模式下旁加载。
if not exist RealtimeTranslate.exe ( echo [错误] 先运行 build_exe.bat & exit /b 1 )
for /f "usebackq delims=" %%V in (`python -c "import re;print(re.search(r'__version__ = \"([^\"]+)\"',open('desktop_translator.py',encoding='utf-8').read()).group(1))"`) do set "VER=%%V"
set "STAGE=build\msix"
if exist "%STAGE%" rmdir /s /q "%STAGE%"
mkdir "%STAGE%\Assets"
copy /Y RealtimeTranslate.exe "%STAGE%\" >nul
copy /Y packaging\windows\msix\AppxManifest.xml "%STAGE%\" >nul
python packaging\windows\msix\make_assets.py "%STAGE%\Assets" || exit /b 1
set "MA="
for /f "delims=" %%S in ('dir /b /s "%ProgramFiles(x86)%\Windows Kits\10\bin\*\x64\makeappx.exe" 2^>nul') do set "MA=%%S"
if not defined MA ( echo [错误] 找不到 makeappx.exe（安装 Windows SDK） & exit /b 1 )
if not exist Output mkdir Output
"%MA%" pack /o /d "%STAGE%" /p "Output\RealtimeTranslate_v%VER%.msix" || exit /b 1
call packaging\windows\sign.bat "Output\RealtimeTranslate_v%VER%.msix"
echo 完成：Output\RealtimeTranslate_v%VER%.msix
