# 实时翻译2（RealtimeTranslate 2）

Go 版实时翻译。基线 v2.14.0（GitHub 公开仓库 `enoonc-sketch/RealtimeTranslate`，
main HEAD `93fb43f`），P0–P4 全部完成（版本 2.0.0-p4）。

- **定名**：实时翻译2（用户 2026-11-20 定），与 AIMS2、ASTA2 一个路子。
  工程目录 `workspace/realtime-go-edition/` 不改名，改的只是项目名。
- **桌面 UI**：Fyne 纯 Go，不用 WebView / WebView2；Tkinter 界面
  1:1 照旧复刻（布局、控件、按钮、历史窗口、设置窗口、深色/萌系主题、
  字号），不许重新设计。复刻清单见 `docs/UI-REPLICA-CHECKLIST.md`。
- **功能不能删**：最终覆盖全部 43 项功能，追踪矩阵见
  `docs/FUNCTIONALITY-TRACEABILITY.md`。
- **发布纪律**：从 P1 做到 PN，中途不发；全部做完、核对通过、用户说发
  再发之前，不推仓库、不发 Release、不建 tag，只在本地做。

## 目录结构

```
cmd/realtime/          入口（数据目录沿用 %APPDATA%\RealtimeTranslate）
internal/
  lang/                语言表、检测、词典候选、字数统计
  glossary/            术语表（占位符保护/还原、JSON 导入导出）
  translate/           在线翻译（Google/微软 HTTP、分块/智能互译/术语表/800 条 LRU 缓存/并发分批）+ 离线接入（P4：引擎“离线”、断网自动兜底 30 秒熔断）
  history/             SQLite 历史（modernc.org/sqlite，表结构与原版逐字一致）
  config/              JSON 配置（全量 DEFAULTS、校验/夹紧、热键解析、导入导出）
  netcheck/            网络检查（IP 直连/DNS/代理/引擎探测）
  update/              更新检查（GitHub latest 版本比对）
  theme/               三套主题 token + 层次 token + 阴影档位
  sensitive/           敏感内容启发式拦截（H-01）
  offline/             离线翻译引擎（P4：Argos 切句/路由/3 边车 LRU/C++ 边车协议）+ 语言包安全底座（安装/下载校验/模型缓存，H-02/H-03/H-04/H-05/H-06/M-11/M-12）
  win32/               托盘/热键/单实例/替换/截图/指针/宠物分层窗口（P2–P4，直调 Win32 API）
  doc/                 文档翻译包（P4：txt/md/srt/docx/PDF 解析与重建，M-05/L-04）
  pet/                 桌面小宠物包（P4：18 只 .pet 内嵌 + 大脑状态机，L-01）
  ocr/                 OCR 纯逻辑（取词/分组/段落）+ 严格 JSON 解析（P3，L-10）
  sidecar/             C# 边车调用层（哈希钉死/超时/stdin 传文/语音白名单，P3）
  ui/                  Fyne 界面（主窗口/历史窗口/设置窗口/FlowLayout）+ 文档翻译（P4）+ 语言包窗口（P4）+ 宠物控制器（P4）
sidecar/               C# 边车源码（Program.cs）+ 编译脚本（build_sidecar.bat，P3）
offline-rt/            C++ 离线推理边车源码（main.cpp + CMakeLists.txt + vcpkg.json + build_offline_sidecar.bat，P4，ADR-0011）
docs/
  P0-现状审计报告.md
  UI-REPLICA-CHECKLIST.md
  FUNCTIONALITY-TRACEABILITY.md
  安全评估报告.md
  adr/                 ADR-0001 ~ ADR-0011
P1-VERIFICATION.md     P1 验收实测输出
P2-VERIFICATION.md     P2 验收实测输出
P3-VERIFICATION.md     P3 验收实测输出
P4-VERIFICATION.md     P4 验收实测输出
RT2-完成总结.md       实时翻译2 全量完成总结（43 项功能 + 29 项安全最终数字）
```

## P1 范围

在线翻译主流程：Go 后端（Google/微软 HTTP 翻译、分块/智能互译/术语表、
SQLite 历史、JSON 配置、网络检查、更新检查）+ Fyne 主窗口（输入即译、
剪贴板监听、历史窗口、设置窗口、深色/萌系主题、字号）。
不含热键、托盘、悬停、截图、OCR、离线、宠物、TTS/STT、整窗（P2–P4）。

## P2/P3 范围

- P2：托盘、六个全局热键、单实例、翻译并替换、开机自启、最小化到任务栏。
- P3：指针取词、悬停取词、截图翻译、整窗翻译、实时刷新、OCR、TTS、STT、
  图片文件翻译、粘贴图片翻译。OCR/TTS/STT 走 C# 边车 `rt-sidecar.exe`
 （见 `sidecar/README.md` 与 `docs/adr/ADR-0010-p3-hover-ocr-tts.md`；
  边车在真 Windows 上编译，`sidecar.sha256` 钉死哈希后主程序才肯运行）。
## P4 范围

- P4：离线翻译（C++ 边车 `rt-offline.exe`，CTranslate2 原生推理，ADR-0011）、
  文档翻译（txt/md/srt/docx/PDF，`internal/doc`）、离线语言包管理
  （`internal/ui/packs.go`）、桌面小宠物 18 只（`internal/pet` +
  Win32 分层透明窗口）。43 项功能与 29 项安全至此全部有结论，
  详见 `RT2-完成总结.md`。
- 用户 2026-11-20 定：**先不打包**——不写 NSIS/Inno 安装脚本、不出 EXE 发行包，
  只做代码开发和验证；等用户说打再打。`go build` 验证编译不受影响。

## 构建与测试

Go 1.25.4：`~/workspace/local-build/go/go/bin/go`。
构建时必须设 `GOTMPDIR=$HOME/.cache/go-tmp`（/tmp 是 512M tmpfs，
`go vet` 曾因磁盘满失败）。

```sh
export PATH=$HOME/workspace/local-build/go/go/bin:$PATH
export GOTMPDIR=$HOME/.cache/go-tmp
cd ~/workspace/realtime-go-edition
gofmt -l .
go vet ./...
go test ./...
go build -o /tmp/rt2-p1 ./cmd/realtime
```

沙箱无显示，Fyne 窗口跑不起来，只能编译检查与无头测试
（`test.NewApp()`）；窗口验证必须在真 Windows 机器上做，
待验证清单见 `P1-VERIFICATION.md`。

## 下载体积

标准版 Linux 二进制 P4 实测 45,193,352 字节 ≈ 43.1MB（P3 是 38.9MB，
增加约 4.3MB：18 只宠物资源 5.35MB 内嵌 + 文档/离线/宠物代码），
低于用户定的 100MB 上限；离线语言包不打进安装包，按需下载
（默认两对约 145MB，整包 170–189MB，超了上限）。
边车体积待真 Windows 编译后重算：`rt-sidecar.exe`（C#）+ `rt-offline.exe`（C++）
+ 主程序 + 宠物资源一起计入 100MB 预算，超了先报上来、不自行定夺。
