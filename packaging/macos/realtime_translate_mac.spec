# -*- mode: python ; coding: utf-8 -*-
# macOS PyInstaller spec → dist/实时翻译.app
#   在 macOS 上：python3 -m PyInstaller --noconfirm --clean packaging/macos/realtime_translate_mac.spec
#   一般直接用 packaging/macos/build_macos.sh（会顺带做 .icns、签名、公证、DMG）
import os, plistlib, re
ROOT = os.path.abspath(os.path.join(os.path.dirname(SPEC), '..', '..'))
HERE = os.path.dirname(os.path.abspath(SPEC))
VERSION = re.search(r'__version__ = "([^"]+)"', open(os.path.join(ROOT, 'desktop_translator.py'), encoding='utf-8').read()).group(1)
ICNS = os.path.join(HERE, 'app.icns')
plist = plistlib.load(open(os.path.join(HERE, 'Info.plist'), 'rb'))
plist['CFBundleShortVersionString'] = plist['CFBundleVersion'] = VERSION

a = Analysis(
    [os.path.join(ROOT, 'desktop_translator.py')],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, 'app.ico'), '.'), (os.path.join(ROOT, 'pets'), 'pets')],
    # tray_win32 / tts_win / stt_win 在非 Windows 上 import 安全（功能自动关闭），主程序启动时会 import，不能排除
    hiddenimports=['tray_win32', 'tts_win', 'stt_win', 'pack_downloader', 'runtime_installer', 'screen_win', 'ocr_win', 'ocr_backends', 'history_store',
    'doc_translate', 'glossary', 'update_check', 'pdf_translate', 'clip_image', 'single_instance', 'settings_io',
    'runtime_stdlib', 'ui_platform', 'sqlite3', 'typing_detect', 'translator_tools', 'text_detect', 'license', 'netcheck', 'offline_engine',
    'pet_win', 'pet_state', 'pet_pack', 'pet_catalog',
    'pynput', 'pynput.keyboard', 'pynput.mouse'],
    excludes=[ 'ctranslate2', 'sentencepiece', 'numpy',
              'matplotlib', 'pandas', 'PIL', 'pytest', 'unittest', 'tkinter.test', 'idlelib'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='RealtimeTranslate', console=False,
          argv_emulation=False, target_arch=os.environ.get('MAC_ARCH') or None,
          codesign_identity=os.environ.get('MAC_SIGN_ID') or None,
          entitlements_file=os.path.join(HERE, 'entitlements.plist'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='RealtimeTranslate')
app = BUNDLE(coll, name='实时翻译.app', icon=ICNS if os.path.exists(ICNS) else None,
             bundle_identifier=plist['CFBundleIdentifier'], info_plist=plist)
