# -*- mode: python ; coding: utf-8 -*-
# 「离线版」PyInstaller spec（onedir：启动快，不用每次解压几百 MB 到临时目录）
# 前置：已运行 prepare_offline_models.py，offline_models\ 下有语言包；
#       环境里已 pip install ctranslate2 sentencepiece numpy pyinstaller
import os
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

HERE = os.path.dirname(os.path.abspath(SPEC))
ICON = os.path.join(HERE, 'app.ico')
VERSION = os.path.join(HERE, 'version_info.txt')
MODELS = os.path.join(HERE, 'offline_models')

# sentencepiece 的 Windows 轮子用 delvewheel 把 msvcp140/vcomp140 放在
# site-packages/sentencepiece.libs/ 里（文件名带 hash），PyInstaller 不会自动收；
# 不收的话 _sentencepiece.pyd 加载时报 "DLL load failed"。
# 把这两个 DLL 收到打包根目录（onedir 的 exe 目录在 DLL 搜索路径上）。
sp_dlls = []
try:
    import sentencepiece
    _sp_dir = os.path.dirname(sentencepiece.__file__)
    _libs = os.path.join(os.path.dirname(_sp_dir), 'sentencepiece.libs')
    if os.path.isdir(_libs):
        sp_dlls = [(os.path.join(_libs, f), '.')
                   for f in sorted(os.listdir(_libs)) if f.lower().endswith('.dll')]
except Exception:
    sp_dlls = []

# 语言包：每个含 metadata.json 的子目录原样带入（跳过 _downloads 等下划线目录）
model_datas = []
if os.path.isdir(MODELS):
    for name in sorted(os.listdir(MODELS)):
        p = os.path.join(MODELS, name)
        if not name.startswith('_') and os.path.isfile(os.path.join(p, 'metadata.json')):
            model_datas.append((p, os.path.join('offline_models', name)))
if not model_datas:
    raise SystemExit('offline_models 里没有语言包，请先运行 prepare_offline_models.py')

a = Analysis(
    ['desktop_translator.py'],
    pathex=[HERE],
    binaries=collect_dynamic_libs('ctranslate2') + collect_dynamic_libs('sentencepiece') + sp_dlls,
    datas=model_datas + ([(ICON, '.')] if os.path.exists(ICON) else []) + ([('winocr.ps1', '.')] if os.path.exists('winocr.ps1') else []) + [('pets', 'pets')],  # v2.14：桌面小宠物动画包
    hiddenimports=['pack_downloader', 'runtime_installer', 'tray_win32', 'screen_win', 'ocr_win', 'history_store', 'tts_win', 'doc_translate', 'stt_win', 'glossary', 'update_check', 'pdf_translate', 'clip_image', 'single_instance', 'settings_io', 'runtime_stdlib', 'ocr_backends', 'ui_platform', 'glob', 'sqlite3', 'ctypes.wintypes', 'ctranslate2', 'sentencepiece', 'numpy', 'typing_detect', 'translator_tools', 'text_detect', 'license', 'netcheck', 'offline_engine',
                   'pet_win', 'pet_state', 'pet_pack', 'pet_catalog'],  # v2.15.4：补齐（以前漏了 license 等）
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 离线引擎只需 ctranslate2 + sentencepiece，下面这些很重且用不到
        'argostranslate', 'stanza', 'spacy', 'minisbd', 'torch', 'torchvision', 'tensorflow',
        'transformers', 'onnxruntime', 'scipy', 'pandas', 'matplotlib', 'PIL', 'cv2', 'sklearn',
        'pynput', 'pystray', 'yaml.tests',
        'pytest', 'unittest', 'doctest', 'pydoc', 'test', 'lib2to3', 'distutils',
        'setuptools', 'pkg_resources', 'pip', 'wheel', 'xmlrpc',
        'tkinter.test', 'idlelib', 'turtle', 'turtledemo',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RealtimeTranslate',            # 与标准版同名：快捷键 / 开机自启 / 升级安装互通
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON if os.path.exists(ICON) else None,
    version=VERSION if os.path.exists(VERSION) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='RealtimeTranslateOffline',
)
