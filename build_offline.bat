@echo off
chcp 65001 >nul
setlocal
title 构建 RealtimeTranslate 离线版
cd /d "%~dp0"

echo ========================================
echo   实时翻译 v2.9 - 离线版 一键构建
echo   内置 ctranslate2 本地推理 + 离线语言包
echo   (需在 Windows 上运行，首次需联网下载语言包)
echo ========================================
echo.

rem ---- 找 Python（要求 3.9+） ----
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY goto :nopython
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if errorlevel 1 goto :nopython

echo [1/6] 检查环境
%PY% -c "import sys; print('    Python', sys.version.split()[0], '(64-bit)' if sys.maxsize > 2**32 else '(32-bit，不支持！)')"
%PY% -c "import sys; sys.exit(0 if sys.maxsize > 2**32 else 1)"
if errorlevel 1 goto :not64
%PY% -c "import tkinter" >nul 2>&1
if errorlevel 1 goto :notk

echo.
echo [2/6] 检查源码语法
%PY% -m py_compile desktop_translator.py tray_win32.py screen_win.py ocr_win.py history_store.py tts_win.py doc_translate.py stt_win.py glossary.py update_check.py offline_engine.py netcheck.py prepare_offline_models.py
if errorlevel 1 goto :syntax

echo.
echo [3/6] 准备独立构建环境 (.buildenv_offline) 并安装依赖
if not exist ".buildenv_offline\Scripts\python.exe" %PY% -m venv .buildenv_offline
if not exist ".buildenv_offline\Scripts\python.exe" goto :venvfail
set "BPY=.buildenv_offline\Scripts\python.exe"
%BPY% -m pip install -q --disable-pip-version-check "pyinstaller>=6.0" ctranslate2 sentencepiece numpy
if errorlevel 1 goto :pipfail
%BPY% -c "import ctranslate2, sentencepiece, numpy; print('    ctranslate2', ctranslate2.__version__, '/ sentencepiece', sentencepiece.__version__, '/ numpy', numpy.__version__)"
if errorlevel 1 goto :pipfail

echo.
echo [4/6] 准备离线语言包 (见 offline_models.txt，约每对 50~120 MB)
%BPY% prepare_offline_models.py
if errorlevel 2 goto :nomodels
if errorlevel 1 (
    echo.
    echo [警告] 部分语言包未能获取，将只打包已就绪的。
    echo        可手动下载 .argosmodel 放入 offline_models\ 后重新运行本脚本补齐。
    echo.
)

echo.
echo [5/6] 打包中 (约 2~5 分钟) ...
if exist build rmdir /s /q build
if exist dist\RealtimeTranslateOffline rmdir /s /q dist\RealtimeTranslateOffline
%BPY% -m PyInstaller --noconfirm --clean realtime_translate_offline.spec
if errorlevel 1 goto :buildfail
if not exist "dist\RealtimeTranslateOffline\RealtimeTranslate.exe" goto :buildfail

echo.
echo [6/6] 自检（实际加载模型并翻译一句，结果写入 %%APPDATA%%\RealtimeTranslate\selftest.txt）
start /wait "" "dist\RealtimeTranslateOffline\RealtimeTranslate.exe" --selftest
set "SELF=%ERRORLEVEL%"
if exist "%APPDATA%\RealtimeTranslate\selftest.txt" type "%APPDATA%\RealtimeTranslate\selftest.txt"
if not "%SELF%"=="0" goto :selffail

echo.
powershell -NoProfile -Command "'    离线版文件夹大小: {0:N0} MB' -f ((Get-ChildItem 'dist\RealtimeTranslateOffline' -Recurse | Measure-Object Length -Sum).Sum/1MB)"
echo.
echo ========================================
echo  完成！可直接运行（免安装、可整个文件夹复制给别人）：
echo    dist\RealtimeTranslateOffline\RealtimeTranslate.exe
echo.
echo  要做成安装向导 (Setup.exe)：安装 Inno Setup 6 后运行
echo    build_installer.bat offline
echo ========================================
echo.
if not defined NOPAUSE pause
exit /b 0

:nopython
echo [错误] 未找到可用的 Python 3.9+ ^(64 位^)。
echo   请安装 https://www.python.org/downloads/ 并勾选 Add python.exe to PATH
if not defined NOPAUSE pause
exit /b 1

:not64
echo [错误] 需要 64 位 Python：ctranslate2 没有 32 位 Windows 版本。
if not defined NOPAUSE pause
exit /b 1

:notk
echo [错误] 当前 Python 缺少 tkinter。请重新运行 Python 安装程序，Modify 里勾选 tcl/tk and IDLE。
if not defined NOPAUSE pause
exit /b 1

:syntax
echo [错误] 源码语法检查未通过，已中止。
if not defined NOPAUSE pause
exit /b 1

:venvfail
echo [错误] 创建虚拟环境失败。
if not defined NOPAUSE pause
exit /b 1

:pipfail
echo [错误] 依赖安装失败。请检查网络/代理；ctranslate2 需要 64 位 Python 3.9~3.13。
if not defined NOPAUSE pause
exit /b 1

:nomodels
echo.
echo [错误] 没有任何可用的离线语言包，无法构建离线版。
echo   原因多半是 argos-net.com 在当前网络下不通。解决办法：
echo   1) 用浏览器 / 代理下载 .argosmodel （链接见 https://github.com/argosopentech/argospm-index 的 index.json）
echo   2) 放进本目录的 offline_models\ 文件夹，重新运行本脚本
echo   3) 或指定镜像：  %BPY% prepare_offline_models.py --replace argos-net.com=镜像域名
if not defined NOPAUSE pause
exit /b 1

:buildfail
echo.
echo [失败] 打包出错，请查看上方日志。
echo   若提示 DLL load failed：安装「Microsoft Visual C++ 2015-2022 Redistributable (x64)」后重试。
if not defined NOPAUSE pause
exit /b 1

:selffail
echo.
echo [失败] 自检未通过，请把上方输出发给开发者。常见原因：缺少 VC++ 运行库 / 语言包损坏。
if not defined NOPAUSE pause
exit /b 1
