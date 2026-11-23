# -*- mode: python ; coding: utf-8 -*-
# Linux PyInstaller spec → dist/RealtimeTranslate/（onedir，启动快）
#   python3 -m PyInstaller --noconfirm --clean packaging/linux/realtime_translate_linux.spec
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(SPEC), '..', '..'))
a = Analysis(
    [os.path.join(ROOT, 'desktop_translator.py')],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, 'app.ico'), '.'), (os.path.join(ROOT, 'pets'), 'pets')],
    # tray_win32 / tts_win / stt_win 在非 Windows 上 import 安全（功能自动关闭），主程序启动时会 import，不能排除
    hiddenimports=['tray_win32', 'tts_win', 'stt_win', 'pack_downloader', 'runtime_installer', 'screen_win', 'ocr_win', 'ocr_backends', 'history_store',
    'doc_translate', 'glossary', 'update_check', 'pdf_translate', 'clip_image', 'single_instance', 'settings_io',
    'runtime_stdlib', 'ui_platform', 'sqlite3', 'typing_detect', 'translator_tools', 'text_detect', 'license', 'netcheck', 'offline_engine',
    'pet_win', 'pet_state', 'pet_pack', 'pet_catalog',
    'pynput', 'pynput.keyboard', 'pynput.mouse'] + ['pynput.keyboard._xorg', 'pynput.mouse._xorg'],
    excludes=[ 'ctranslate2', 'sentencepiece', 'numpy',
              'matplotlib', 'pandas', 'PIL', 'pytest', 'unittest', 'tkinter.test', 'idlelib'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='realtime-translate', console=False, strip=True, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=True, upx=False, name='RealtimeTranslate')
