@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
rem 用 NSIS 3 生成安装包
rem   build_nsis.bat           标准版  -> Output\RealtimeTranslate_Setup_v*.exe
rem   build_nsis.bat offline   离线版  -> Output\RealtimeTranslate_Setup_v*_Offline.exe
set "MAKENSIS="
if exist "%ProgramFiles(x86)%\NSIS\makensis.exe" set "MAKENSIS=%ProgramFiles(x86)%\NSIS\makensis.exe"
if exist "%ProgramFiles%\NSIS\makensis.exe" set "MAKENSIS=%ProgramFiles%\NSIS\makensis.exe"
where makensis >nul 2>nul && set "MAKENSIS=makensis"
if not defined MAKENSIS (
  echo [提示] 未检测到 NSIS 3，请先安装：https://nsis.sourceforge.io/Download
  if not defined NOPAUSE pause
  exit /b 1
)
if not exist Output mkdir Output
if /i "%~1"=="offline" goto :offline
if not exist "RealtimeTranslate.exe" if exist "dist\RealtimeTranslate.exe" copy /Y "dist\RealtimeTranslate.exe" . >nul
if not exist "RealtimeTranslate.exe" (
  echo [错误] 请先运行 build_exe.bat 生成 RealtimeTranslate.exe
  if not defined NOPAUSE pause
  exit /b 1
)
"%MAKENSIS%" /INPUTCHARSET UTF8 RealtimeTranslate_Setup.nsi || goto :fail
goto :done
:offline
if not exist "dist\RealtimeTranslateOffline\RealtimeTranslate.exe" (
  echo [错误] 请先运行 build_offline.bat
  if not defined NOPAUSE pause
  exit /b 1
)
"%MAKENSIS%" /INPUTCHARSET UTF8 RealtimeTranslate_Setup_Offline.nsi || goto :fail
:done
echo.
dir /b Output\*.exe
if not defined NOPAUSE pause
exit /b 0
:fail
echo [失败] NSIS 编译出错，见上方信息。
if not defined NOPAUSE pause
exit /b 1
