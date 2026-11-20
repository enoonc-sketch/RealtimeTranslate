# 实时翻译2 全量完成总结（P1–P4，版本 2.0.0-p4，2026-11-20）

基线：RealtimeTranslate v2.14.0（公开仓库 `enoonc-sketch/RealtimeTranslate`，main HEAD `93fb43f`），
27 个 py 文件 12,656 行。工程目录 `workspace/realtime-go-edition/`。
按 P0 §15 分四段完成：P1 在线主流程 → P2 托盘/热键/系统集成 → P3 悬停/截图/OCR/TTS/STT →
P4 离线/文档/语言包/宠物。**P4 是最后一阶段；43 项功能与 29 项安全至此全部有结论。**

> 发布纪律（用户 2026-11-20 定）：从 P1 做到 PN，中途不发；全部做完、核对通过、
> 用户说发再发之前，不推仓库、不发 Release、不建 tag。
> 另：用户同日定**先不打包**——不写 NSIS/Inno 安装脚本、不出 EXE 发行包，
> 只做代码开发和验证；等用户说打再打。`go build` 验证编译不受影响。

## 最终数字

| 维度 | 数字 |
|---|---|
| 功能 | **43 项全部实现**（P1 23 + P2 5 + P3 9 + P4 6），预留 0、后续 0、**删除 0** |
| 安全 | **29 项：已修 27，不适用 2**（M-07 依赖锁定、L-06 不打包故无安装器） |
| 代码量 | Go 源码 64 个文件、17,963 行（不含测试与 C++/C# 边车源码） |
| 测试 | 16 个包全过；顶层测试 153 通过、0 失败、0 跳过（另有 4 个只在 Windows 编译的测试） |
| 二进制 | Linux 45,193,352 字节 ≈ **43.1MB**（P3 38.9MB；+4.3MB 主因 5.35MB 宠物资源内嵌），<100MB 上限 |
| 内存 | 整机 Fyne 应用 Xvfb 下 5 秒后 RSS ≈ **237MB**（Mesa 软渲染；真机硬件渲染待测） |

### P4 的 6 项（#14/#15/#22/#23/#26/#38）
- #14 离线翻译：Argos 引擎 + C++ 边车 `rt-offline.exe`（CTranslate2 原生，ADR-0011）。
- #15 离线语言包管理：索引三源轮询、下载验哈希、安装/更新/卸载/本地导入。
- #22 文档 txt/md/srt、#23 docx、#26 PDF：纯 Go 解析与重建，进度/取消走 goroutine+channel。
- #38 桌面小宠物 18 只：RTPET1 解码 + 大脑状态机 + Win32 分层透明窗口。
- 另 #16（网络检查与断网自动切离线）在 P4 补完离线接入（30 秒熔断 + 自动兜底）。

### 安全最终数字
- 已修 27：高 6 全修（H-01 敏感内容拦截、H-02 离线路径白名单、H-03 语言包验哈希、
  H-04 轮子钉死、H-05 模型缓存目录权限、H-06 缓存改 per-user）、中 11 修
  （M-07 不适用）、低 10 修（L-06 不适用）。
- 不适用 2：M-07（go.mod + go.sum 已钉死）、L-06（不打包，无安装器就无卸载残留；
  恢复打包时安装器须含离线清理段，已记 ADR-0011）。

## 各阶段回顾

| 阶段 | 做完的事 | 关键数字 |
|---|---|---|
| P1 | 在线翻译主流程：Google/微软 HTTP、分块/智能互译/术语表、SQLite 历史（与原版表结构逐字一致）、JSON 配置、网络检查、更新检查；Fyne 主/历史/设置窗口 1:1 复刻；三套主题 token | 23 项功能；安全 14 修；二进制 38.9MB；后端探针 RSS ≈10MB |
| P2 | 托盘（Shell_NotifyIconW，22 项菜单与原版逐项核对）、6 个全局热键、单实例、翻译并替换、开机自启、最小化到任务栏；Win32 调用全部收进 `internal/win32` | +5 项功能；安全 16 修；二进制 38.9MB |
| P3 | 指针取词、悬停取词、截图翻译、整窗翻译、实时刷新、OCR、TTS、STT、图片文件/粘贴图片翻译；OCR/TTS/STT 走 C# 单边车 `rt-sidecar.exe`（ADR-0010，PowerShell 彻底不用） | +9 项功能；安全 23 修；go test 14 包 108 测试全过 |
| P4 | 离线翻译（C++ 边车）、文档翻译、语言包管理、桌面小宠物；退出时 GLFW panic 真 bug 已修 | +6 项功能；安全 27 修；go test 16 包 153 测试全过；二进制 43.1MB |

## 边车选型（两条，都有 ADR）

| 边车 | 语言 | 为什么选它 | 编译与校验 |
|---|---|---|---|
| `rt-sidecar.exe`（OCR/TTS/STT，P3，ADR-0010） | C# | WinRT OCR 在 C# 是几行 `AsTask()`；System.Speech 只在 .NET 有；csc.exe 随 .NET Framework 4.7.2 自带，无 SDK、无需另下载运行时；一个二进制覆盖三项，面最小 | `sidecar/build_sidecar.bat` 在真 Windows 编译，生成 `sidecar.sha256`；主程序执行前验哈希，fail-closed |
| `rt-offline.exe`（离线推理，P4，ADR-0011） | C++ | CTranslate2 是 C++ 原生，无成熟 Go 绑定；ONNX 重做等于重建模型管线（语言包不兼容）；Python 边车要带运行时 + 4 个轮子，面更大、供应链更重，且 numpy 2.5.4 在 Wine 下 import 即崩 | `offline-rt/build_offline_sidecar.bat` 在真 Windows 编译（CMake + MSVC + vcpkg 装 SentencePiece），生成 `internal/offline/offline.sha256`；主程序执行前验哈希，fail-closed |

钉死的值（2026-11-20 实测）：CTranslate2 v4.6.0 源码包 sha256
`9421d846668573466ceb713b27f71fb16fed8486ed7bdb654583c48c3c20621b`、
vcpkg builtin-baseline `9d764a2d1be71c010cc4fc246de6b3b1d1787ef0`；
en→zh 语言包 `433e7c4f034d87fbe2353161e05f18646d7999452f801a4e1f0378522b9850ab`、
zh→en 语言包 `62e7af5a3a48b530e47b7b3e5c78c2de79073ecd815750d2bf3ab35b4a67da2d`。

## Fyne 复刻偏差（清单 W1–W7，见 `docs/UI-REPLICA-CHECKLIST.md`）

- W1：窗口定位走 `win32.MoveOwnWindow`（Fyne 不给窗口坐标）。
- W2：覆盖层不能点透（Fyne 窗口无 click-through），是普通窗口。
- W3：截图框选在 Fyne 窗口内拖矩形（不是全屏透明遮罩）。
- W4：实时刷新间隔下限 5 秒（原版 3 秒太频繁）。
- W5（新增 P4）：宠物气泡原版是圆角画布贴在宠物窗口上方；Fyne 没有圆角气泡窗口，
  用一个小 Fyne 窗口代替（带标题栏）。
- W6（新增 P4）：保存框无“初始目录”API（原版 `asksaveasfilename` 的 initialdir），
  打开在 Fyne 上次位置；文件名默认 `原文-译文.扩展名` 不变。
- W7（新增 P4）：分层窗口起不来时退回普通 Fyne 窗口（只有宠物图、能点，
  无右键菜单、位置用 Fyne 默认）。

## 验证（实测输出见各阶段 VERIFICATION.md）

```text
gofmt -l internal/ cmd/        （无输出）
go build ./...                  BUILD_OK
go vet ./...                    VET_OK
GOOS=windows go vet <11 个包>   WIN_VET_OK
go test ./... -count=1          16 个包全过，153 通过、0 失败、0 跳过
g++ -std=c++17 -fsyntax-only offline-rt/main.cpp   CPP_SYNTAX_OK（语法-only，桩头文件）
Xvfb 冒烟（8 秒 + SIGTERM 退出） crash.log 只有 P2 已知的托盘降级记录，panic 0
```

P4 修掉的真 bug：退出时 `fyne.Do` 关窗口撞上已析构的 GLFW 而 panic
（`stopPetController`/`popup.Close`/`shotOverlay.Close`，`shuttingDown` flag 修复；
SIGTERM 退出复测后 panic 计数 0）。详见 `P4-VERIFICATION.md`。

## 待真 Windows 验证（全量清单）

1. **两个边车**：`sidecar/build_sidecar.bat` 编出 `rt-sidecar.exe`、生成
   `sidecar.sha256`、`voices` 冒烟；`offline-rt/build_offline_sidecar.bat` 编出
   `rt-offline.exe`、生成 `offline.sha256`、冒烟（无参数应打印用法、exit 2）。
2. **离线端到端**：下载 en↔zh 两对语言包 → 引擎下拉出现“离线” → 离线翻译出结果；
   断网自动兜底（拔网线/断代理后走离线，30 秒熔断）。
3. **文档端到端**：txt/md/srt/docx/PDF 各一份真实文件（含几千段大文档：
   确认框、进度、取消、保存框、`-译文` 文件）。
4. **语言包窗口端到端**：索引拉取、下载、安装、更新、卸载、本地导入。
5. **宠物真机**：分层窗口透明/置顶/拖动/单击/双击/右键菜单，18 只逐只看，
   位置保存后重启还在；气泡在主窗口隐藏时显示。
6. **在线端点**：Google 端点（沙箱 IP 被挡）、微软 auth 端点（沙箱曾 404），
   真机网络重验。
7. **托盘/热键/悬停/截图/OCR/TTS/STT** 真机行为；Fyne 窗口真机显示；
   整机 RSS（硬件渲染）；完整退出路径。
8. **体积重算**：`rt-sidecar.exe` + `rt-offline.exe` + 主程序 + 宠物资源
   一起计入 100MB 预算；超了先报上来、不自行定夺。
9. **打包**：用户说打再打（NSIS/Inno 安装脚本 + 安装器 + 发行 EXE，
   恢复打包时安装器须含离线清理段，见 ADR-0011）。

## 文件地图

```
P0-现状审计报告.md / P1-VERIFICATION.md / P2-VERIFICATION.md /
P3-VERIFICATION.md / P4-VERIFICATION.md / RT2-完成总结.md（本文件）
docs/FUNCTIONALITY-TRACEABILITY.md   43 项功能 + 29 项安全最终结论
docs/UI-REPLICA-CHECKLIST.md         复刻清单（含 W1–W7 偏差）
docs/安全评估报告.md                 29 项原始评估
docs/adr/ADR-0010-p3-hover-ocr-tts.md    C# 边车决策
docs/adr/ADR-0011-p4-offline-sidecar.md  C++ 离线边车决策
internal/{lang,glossary,translate,history,config,netcheck,update,theme,
  sensitive,offline,win32,ocr,sidecar,doc,pet,ui}
sidecar/    C# 边车源码 + build_sidecar.bat
offline-rt/ C++ 离线边车源码 + CMakeLists.txt + vcpkg.json + build_offline_sidecar.bat
```
