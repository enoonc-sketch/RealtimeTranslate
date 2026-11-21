# 打包系统文件（v2.15.4）

所有平台的打包都从**同一份源码**出包，版本号统一读 `desktop_translator.__version__`
（`packaging/bump_version.py` 一键改全）。

| 平台 | 产物 | 构建命令（在对应系统上运行） | 文件 |
|---|---|---|---|
| Windows | 单文件 exe（标准版） | `build_exe.bat` | `realtime_translate.spec` |
| Windows | 文件夹（离线版） | `build_offline.bat` | `realtime_translate_offline.spec` |
| Windows | 安装包（Inno Setup） | `build_installer.bat [offline]` | `installer.iss` |
| Windows | 安装包（NSIS） | `build_nsis.bat [offline]` | `RealtimeTranslate_Setup*.nsi` |
| Windows | 免安装 zip | `packaging\windows\make_portable.bat` | `make_portable.bat` |
| Windows | MSIX（应用商店 / 企业分发） | `packaging\windows\msix\build_msix.bat` | `AppxManifest.xml` |
| Windows | winget / Scoop / Chocolatey 清单 | 发版后 `python packaging/make_manifests.py` 填 sha256 | `windows/winget|scoop|chocolatey` |
| macOS | `.app` + `.dmg` | `bash packaging/macos/build_macos.sh` | `realtime_translate_mac.spec`、`Info.plist` |
| Linux | 可执行文件夹 + `.tar.gz` | `bash packaging/linux/build_linux.sh` | `realtime_translate_linux.spec` |
| Linux | `.deb`（Debian / Ubuntu / UOS / 麒麟） | `bash packaging/linux/build_deb.sh` | `linux/debian/` |
| Linux | AppImage（任意发行版） | `bash packaging/linux/build_appimage.sh` | `AppRun`、`.desktop` |
| 源码 | `pip install` / `pipx` | `python -m build` | `pyproject.toml` |
| 全平台 CI | 推 `v*` 标签自动出全部包 | GitHub Actions | `.github/workflows/release.yml` |

## 各平台功能差异（程序本身决定，打包只是如实声明依赖）

| 功能 | Windows | macOS | Linux |
|---|---|---|---|
| 主窗口翻译 / 在线引擎 / 离线引擎 | ✔ | ✔ | ✔ |
| 全局快捷键 | ✔（系统热键） | ✔（pynput，需在「隐私与安全 → 辅助功能」授权） | ✔（pynput，仅 X11；Wayland 下不可用） |
| 托盘图标 | ✔ | ✘（关窗口改为最小化） | ✘ |
| 截图 / 悬停 OCR | ✔ Windows OCR | ✔ 需 `brew install tesseract` | ✔ 需 `tesseract-ocr` |
| 朗读 / 语音输入 | ✔ | ✘ | ✘ |

## 发版流程
1. `python packaging/bump_version.py 2.15.5` —— 改程序、安装脚本、清单、spec 里的全部版本号
2. 更新 `CHANGELOG.md`
3. `git tag v2.15.5 && git push --tags` —— CI 在三个平台上并行出包、自检、挂到 Release
4. `python packaging/make_manifests.py --from-release v2.15.5` —— 用 Release 上的文件算 sha256，
   生成 winget / Scoop / Chocolatey 清单，提交到各自仓库

## 签名（可选，强烈建议）
- **Windows**：设置环境变量 `SIGN_PFX`（证书路径）和 `SIGN_PFX_PASS`，`packaging/windows/sign.bat` 会给 exe、安装包、
  卸载程序签名。未签名的 exe 首次运行会被 SmartScreen 拦（点「更多信息 → 仍要运行」）。
- **macOS**：设置 `MAC_SIGN_ID="Developer ID Application: …"`、`MAC_NOTARY_PROFILE`（`xcrun notarytool store-credentials` 存的名字），
  `build_macos.sh` 会自动签名 + 公证 + staple。未签名的 .app 需要右键「打开」。
- CI 里把这些放进仓库 Secrets（见 `release.yml` 注释），没配就跳过签名，照样出包。
