@echo off
chcp 65001 >nul
setlocal
title 构建 Setup 安装包 (Inno Setup)
cd /d "%~dp0"

echo ========================================
echo   生成 Windows 安装向导 Setup.exe
echo   用法：build_installer.bat           标准版
echo         build_installer.bat offline   离线版
echo ========================================
echo.

set "DEFS="
if /i "%~1"=="offline" goto :chkoffline

if exist "RealtimeTranslate.exe" goto :haveexe
if exist "dist\RealtimeTranslate.exe" (
    copy /Y "dist\RealtimeTranslate.exe" "RealtimeTranslate.exe" >nul
    goto :haveexe
)
echo [错误] 请先运行 build_exe.bat 生成 RealtimeTranslate.exe
echo        （要做离线版安装包：先运行 build_offline.bat，再用  build_installer.bat offline）
if not defined NOPAUSE pause
exit /b 1

:chkoffline
if exist "dist\RealtimeTranslateOffline\RealtimeTranslate.exe" (
    set "DEFS=/DOFFLINE=1"
    echo 模式：离线版安装包
    goto :haveexe
)
echo [错误] 请先运行 build_offline.bat 生成 dist\RealtimeTranslateOffline\
if not defined NOPAUSE pause
exit /b 1

:haveexe
rem ---- 查找 Inno Setup 编译器 ----
set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not defined ISCC goto :noinno

for %%I in ("%ISCC%") do set "ISDIR=%%~dpI"
set "HAVECN="
if exist "ChineseSimplified.isl" set "HAVECN=1"
if exist "%ISDIR%Languages\ChineseSimplified.isl" set "HAVECN=1"
if not defined HAVECN (
    echo [提示] 未找到 ChineseSimplified.isl，安装向导将使用英文界面。
    echo        需要中文向导：从 https://jrsoftware.org/files/istrans/ 下载后放在本目录。
    echo.
)

echo 使用: %ISCC%
"%ISCC%" %DEFS% installer.iss
if errorlevel 1 goto :fail

echo.
echo 安装包已生成:
dir /b Output\*.exe 2>nul
echo.
if not defined NOPAUSE pause
exit /b 0

:noinno
echo [提示] 未检测到 Inno Setup 6。
echo.
echo 请先安装免费工具 Inno Setup 6: https://jrsoftware.org/isdl.php
echo 安装后重新运行本脚本，将生成 Output\ 下的 Setup 安装包
echo.
echo 免安装版可直接分发：标准版 RealtimeTranslate.exe ，离线版 dist\RealtimeTranslateOffline\ 整个文件夹
if not defined NOPAUSE pause
exit /b 1

:fail
echo 编译失败，请查看上方 Inno Setup 的报错信息。
if not defined NOPAUSE pause
exit /b 1
