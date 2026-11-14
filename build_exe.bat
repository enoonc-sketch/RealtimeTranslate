@echo off
chcp 65001 >nul
setlocal
title 构建 RealtimeTranslate 独立 exe
cd /d "%~dp0"

echo ========================================
echo   实时翻译 v2.4 - 标准版 exe 一键构建
echo   (需在 Windows 上运行)
echo ========================================
echo.

rem ---- 找 Python（要求 3.9+） ----
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY goto :nopython
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 goto :nopython

echo [1/5] 检查环境
%PY% -c "import sys; print('    Python', sys.version.split()[0])"
%PY% -c "import tkinter" >nul 2>&1
if errorlevel 1 goto :notk

echo.
echo [2/5] 检查源码语法
%PY% -m py_compile desktop_translator.py tray_win32.py screen_win.py ocr_win.py
if errorlevel 1 goto :syntax

echo.
echo [3/5] 准备独立构建环境 (.buildenv) 并安装 PyInstaller
if not exist ".buildenv\Scripts\python.exe" %PY% -m venv .buildenv
if exist ".buildenv\Scripts\python.exe" (set "BPY=.buildenv\Scripts\python.exe") else (set "BPY=%PY%")
%BPY% -m pip install -q --disable-pip-version-check "pyinstaller>=6.0"
if errorlevel 1 goto :pipfail

echo.
echo [4/5] 打包中 (约 1~3 分钟) ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
%BPY% -m PyInstaller --noconfirm --clean realtime_translate.spec
if errorlevel 1 goto :buildfail
if not exist "dist\RealtimeTranslate.exe" goto :buildfail

echo.
echo [5/5] 生成完成
copy /Y "dist\RealtimeTranslate.exe" "RealtimeTranslate.exe" >nul
for %%A in ("RealtimeTranslate.exe") do echo     文件: %%~fA
for %%A in ("RealtimeTranslate.exe") do echo     大小: %%~zA 字节
echo     SHA256:
certutil -hashfile "RealtimeTranslate.exe" SHA256 | findstr /v /c:"hash of" /c:"CertUtil"

echo.
echo ========================================
echo  可直接双击 RealtimeTranslate.exe 运行，无需安装 Python
echo ========================================
echo.
echo 若还要做安装向导 (Setup.exe)，请安装 Inno Setup 6 后运行 build_installer.bat
echo.
if not defined NOPAUSE pause
exit /b 0

:nopython
echo [错误] 未找到可用的 Python 3.9+。
echo   请安装 https://www.python.org/downloads/ 并勾选 Add python.exe to PATH
echo   (若装过但仍提示此错误：可能命中了 Microsoft Store 的占位 python，请改用官网安装包)
if not defined NOPAUSE pause
exit /b 1

:notk
echo [错误] 当前 Python 缺少 tkinter。请重新运行 Python 安装程序，
echo   选择 Modify，并勾选 tcl/tk and IDLE。
if not defined NOPAUSE pause
exit /b 1

:syntax
echo [错误] desktop_translator.py 语法检查未通过，已中止。
if not defined NOPAUSE pause
exit /b 1

:pipfail
echo [错误] 安装 PyInstaller 失败，请检查网络或代理后重试。
if not defined NOPAUSE pause
exit /b 1

:buildfail
echo.
echo [失败] 打包出错，请查看上方日志。可尝试最简命令:
echo   %BPY% -m PyInstaller --noconsole --onefile --name RealtimeTranslate desktop_translator.py
if not defined NOPAUSE pause
exit /b 1
