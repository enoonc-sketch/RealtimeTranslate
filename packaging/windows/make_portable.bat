@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0\..\.."
rem 免安装 zip：标准版 exe（+ 离线版文件夹，如果有）各打一个 zip，并写 portable.txt 标记
for /f "usebackq delims=" %%V in (`python -c "import re;print(re.search(r'__version__ = \"([^\"]+)\"',open('desktop_translator.py',encoding='utf-8').read()).group(1))"`) do set "VER=%%V"
if not exist Output mkdir Output
if exist "RealtimeTranslate.exe" (
  if exist _portable rmdir /s /q _portable
  mkdir _portable\RealtimeTranslate
  copy /Y RealtimeTranslate.exe _portable\RealtimeTranslate\ >nul
  copy /Y CHANGELOG.md _portable\RealtimeTranslate\ >nul 2>nul
  > _portable\RealtimeTranslate\portable.txt echo 免安装版：直接运行 RealtimeTranslate.exe。删除本文件夹即卸载；设置和历史在 %%APPDATA%%\RealtimeTranslate。
  powershell -NoProfile -Command "Compress-Archive -Force -Path '_portable\RealtimeTranslate' -DestinationPath 'Output\RealtimeTranslate_v%VER%_portable.zip'"
  rmdir /s /q _portable
  echo 已生成 Output\RealtimeTranslate_v%VER%_portable.zip
) else (
  echo [跳过] 没有 RealtimeTranslate.exe，先运行 build_exe.bat
)
if exist "dist\RealtimeTranslateOffline\RealtimeTranslate.exe" (
  powershell -NoProfile -Command "Compress-Archive -Force -Path 'dist\RealtimeTranslateOffline' -DestinationPath 'Output\RealtimeTranslate_v%VER%_portable_Offline.zip'"
  echo 已生成 Output\RealtimeTranslate_v%VER%_portable_Offline.zip
)
if not defined NOPAUSE pause
