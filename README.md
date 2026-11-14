# 实时翻译 RealtimeTranslate

Windows 桌面翻译工具 v2.4：输入即译、全局热键取词、监听剪贴板、长文档翻译、在线 / 离线引擎。

## v2.4 新功能

- **托盘图标（Windows）**：只用 Python 标准库 `ctypes` 调 `Shell_NotifyIconW`，不依赖 pystray / Pillow。点 × / Esc 藏到托盘，右键菜单：显示主窗口 / 截图翻译 / 退出。
- **悬停取词（Windows，默认开）**：鼠标在文字上停住约 0.8 秒自动取词。先截光标周围一小块，用系统 OCR 定位最近的单词，图片、游戏、扫描 PDF 里也能取；认不到且光标是「I」形时退回双击取词。
- **截图翻译（Windows，Ctrl+Alt+S）**：框选屏幕任意区域 → 系统 OCR 认字 → 翻译。截图用 GDI `BitBlt`，OCR 用系统自带的 `Windows.Media.Ocr`，全程不装第三方库。需要安装对应语言的 OCR 语言包。

## 构建（Windows）

```bat
build_exe.bat        :: 标准版：单个 exe，约 13 MB
build_offline.bat    :: 离线版：内置 ctranslate2 + 离线语言包
build_installer.bat  :: 安装向导（需 Inno Setup 6）
```

需要 Python 3.9+（离线版要 64 位）。详细说明见 [README_BUILD.md](README_BUILD.md)。

## 快捷键

| 快捷键 | 作用 |
|---|---|
| Ctrl+Alt+T | 翻译选中的文字 |
| Ctrl+Alt+D | 指针取词，在指针旁显示译文 |
| Ctrl+Alt+S | 截图翻译 |

## 文件

- `desktop_translator.py` — 主程序
- `tray_win32.py` — Windows 托盘（纯 ctypes）
- `screen_win.py` — Windows 截图（ctypes GDI）
- `ocr_win.py` + `winocr.ps1` — Windows 自带 OCR
- `offline_engine.py` — 离线引擎（Argos 语言包 + ctranslate2）
- `tests/` — 测试

## 说明

Windows 专有部分（托盘、悬停、截图 OCR）尚未在真实 Windows 机器上实测，见 [README_BUILD.md](README_BUILD.md) 的“未能验证”一节。
