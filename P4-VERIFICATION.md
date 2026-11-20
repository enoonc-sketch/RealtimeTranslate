# 实时翻译2 P4 验收（版本 2.0.0-p4，2026-11-20）

P4 是 P0 §15 的最后一阶段：离线翻译、文档翻译、离线语言包管理、桌面小宠物。
做完 43 项功能与 29 项安全全部有结论（见 `docs/FUNCTIONALITY-TRACEABILITY.md` 末尾合计）。

## P4 做了什么

### 离线翻译（#14，ADR-0011）
- `internal/offline/engine.go`：Argos 引擎——按行切句（`SplitSentences`，期望值用基线
  Python `offline_engine.split_sentences` 实测算出，含超 300 字软切的长度分布
  [299, 199] 与 [298, 108]）、直达/经英语中转路由、同一语言对只留最高版、
  最多 3 个边车 LRU、单请求 120 秒超时、输出 10MB 上限、加载前按安装清单验哈希。
- `internal/offline/sidecar.go`：C++ 边车 `rt-offline.exe` 调用层——只认 exe 旁边与
  数据目录两个固定位置（L-07 同款），执行前验 `offline.sha256`（没生成或对不上就
  拒绝运行，fail-closed）；行协议（`READY` / `TRANSLATE n <prefix>` + n 行 + `END` /
  `OK n` + n 行 / `ERR`）；模型路径白名单断言（必须在语言包搜索目录内）。
- `offline-rt/`：C++ 边车源码（`main.cpp` + `CMakeLists.txt` + `vcpkg.json` +
  `build_offline_sidecar.bat` + `README.md`）。CTranslate2 4.6.0 原生 + SentencePiece；
  推理参数与原版一致（beam_size=4、length_penalty=0.2、replace_unknowns=true、
  num_hypotheses=1、max_decoding_length=512、max_batch_size=1024、batch_type=Tokens）；
  句切分在 Go 侧做，边车只翻“分词后的句子”。
  2026-11-20 实查：CTranslate2 无预编译 Windows 二进制（v4.6.0 Release 附件为空）、
  vcpkg 无 `ctranslate2` 包，必须从源码编；SentencePiece 有 vcpkg 包（0.2.1）。
  钉死：CTranslate2 v4.6.0 源码包 sha256
  `9421d846668573466ceb713b27f71fb16fed8486ed7bdb654583c48c3c20621b`、
  vcpkg builtin-baseline `9d764a2d1be71c010cc4fc246de6b3b1d1787ef0`。
- `translate.Service` 接入：引擎下拉“离线”（有离线组件才显示，原版 ENGINES 同款）；
  断网自动兜底（连通性故障记 30 秒熔断，熔断期内直接走离线；语言对不可离线翻译时
  不兜底、原样返回在线错误；兜底译文不进在线缓存；兜底次数可查 `FallbackCount`；
  网络检查窗口“重试”清熔断）；自动兜底开关（设置/托盘）实时同步到服务。

### 文档翻译（#22/#23/#26，`internal/doc/` + `internal/ui/doc.go`）
- `internal/doc/`（2,167 行，19 个测试）：txt/md 段落切分/重建字节一致（随机测试）、
  SRT 只翻正文（索引/时间戳保留）、docx 只翻 document.xml 文本节点
  （样式/图片原样保留）、PDF 纯 Go 提取器（FlateDecode + ToUnicode CMap）。
  上限：文本 50MB、docx 100MB、document.xml 50MB（M-05 收紧）、zip 解压总量 400MB、
  PDF 200MB、流 32MB/总量 256MB、bfrange 跨度 10,000、可提取字符 ≥10。
  `DocxRebuild`：用已翻好的段落一次性重建整包（不翻两遍）；重建逻辑抽成
  `rebuildDocxZip`（`DocxTranslateBytes` 与 `DocxRebuild` 共用，重构后测试仍全过）。
- `internal/ui/doc.go`：文件选择（txt/md/srt/docx/pdf）→ 只在界面线程看大小 →
  后台 goroutine 读/解析/翻译 → 0.25 秒进度节流 + ETA → 段数 ≥2000 或预估 ≥60 秒
  先确认 → 取消走 context → 完成载入主窗口 + 历史 kind="doc"（原文/译文各存前
  2000 字）+ 保存框（默认 `原文-译文.扩展名`，PDF → `-译文.txt`）。

### 离线语言包管理（#15，`internal/ui/packs.go`）
- 语言包窗口：Argos 索引三源轮询（白名单域名 + https + 5MB 上限，1 小时缓存）、
  每对只留最高版、已安装/可更新/未安装三态；下载走 `offline.DownloadAndVerify`
  （钉死表验 sha256，未知对警告 + 二次确认）；安装走 `offline.InstallPackage`；
  本地 .argosmodel 导入；卸载只删用户导入目录（realpath 前缀校验）+ 清清单；
  装/卸后重载引擎、刷新引擎下拉；镜像输入框（只认白名单域名）。

### 桌面小宠物（#38，`internal/pet/` + `internal/win32/pet.go` + `internal/ui/pet.go`）
- `internal/pet/`（18 只 `.pet` 内嵌，5.4MB；14 个测试）：RTPET1 解码 + 大脑状态机
  （busy/think、done→happy 2.2 秒、fail→sad、90 秒空闲睡觉、气泡截断 60 字）。
- `internal/win32/pet.go`：分层透明窗口（WS_EX_LAYERED | TOOLWINDOW | TOPMOST，
  `UpdateLayeredWindow` 送 BGRA 预乘帧，独占消息循环线程，CS_DBLCLKS）：
  拖动（>4px 才算拖，拖完保存 PetX/PetY）/单击（260ms 判双击）/双击翻译剪贴板/
  右键菜单（菜单项与原版 `_menu` 一字不差：打开翻译窗口/翻译剪贴板/截图翻译/
  换个小宠物 18 只/显示模式/气泡开关/隐藏/退出）；DIB 节 + 兼容 DC 只属于循环线程，
  UI 线程只改共享状态 + PostMessage。
- `internal/ui/pet.go`：45ms 心跳、发呆眨眼（3.5–6.5 秒一次，眨 0.15 秒）、
  大脑只属于 tick 循环（事件走 channel，大脑无锁）；大脑事件接翻译开始/完成/失败；
  气泡只在主窗口隐藏 + 气泡开时显示；分层窗口失败退回 Fyne 窗口（只有图、能点，
  无右键菜单，见复刻清单 W7）。

### 安全：剩下 5 项全部有结论
- M-05 已修：docx 条目名白名单、document.xml 50MB、总量 400MB、流式输出。
- L-01 已修：.pet 载入校验（w/h 1..512、7 动画齐全、帧索引合法、zlib 限流、单文件 2MB、头 64KB）。
- L-04 已修：docx 不用正则（encoding/xml 流式）、PDF 纯 Go 提取器、句切分纯 rune 扫描。
- L-06 不适用：用户 2026-11-20 定先不打包，无安装器就不存在卸载残留；要求记在 ADR-0011。
- L-11 已修：语言包永不打进安装包 + 不打包纪律（P4 不产出任何安装包/发行 EXE）。

### 顺手修（P4 做的时候发现的，不在 P4 清单里，改动小、风险低）
- 退出时 `fyne.Do` 关窗口会 panic（GLFW 已析构）：`Shutdown` 立 `shuttingDown` flag，
  宠物 Fyne 窗口/气泡/取词弹窗/覆盖层的关闭在退出时跳过 `fyne.Do`（进程退出即销毁窗口）。
  详见“本次发现的真 bug”。
- P2 遗留：设置页“开机自启”复选框 getter 恒 false、点了只弹占位提示；现在直连
  `setAutostart`（注册表为准）。
- “断网自动改用离线”复选框（设置/托盘）之前只改配置，服务仍用启动时的值；
  现在实时同步到 `translate.Service`。

## 验证输出（实测）

```text
$ gofmt -l internal/ cmd/
（无输出）

$ go build ./...
BUILD_OK

$ go vet ./...
VET_OK

$ GOOS=windows go vet ./internal/win32/ ./internal/sidecar/ ./internal/ocr/ ./internal/config/ ./internal/history/ ./internal/ui/ ./internal/offline/ ./internal/doc/ ./internal/pet/ ./internal/translate/
WIN_VET_OK

$ go test ./... -count=1
ok  github.com/enoonc-sketch/realtime-translate-2/internal/config
ok  github.com/enoonc-sketch/realtime-translate-2/internal/doc
ok  github.com/enoonc-sketch/realtime-translate-2/internal/glossary
ok  github.com/enoonc-sketch/realtime-translate-2/internal/history
ok  github.com/enoonc-sketch/realtime-translate-2/internal/lang
ok  github.com/enoonc-sketch/realtime-translate-2/internal/netcheck
ok  github.com/enoonc-sketch/realtime-translate-2/internal/ocr
ok  github.com/enoonc-sketch/realtime-translate-2/internal/offline
ok  github.com/enoonc-sketch/realtime-translate-2/internal/pet
ok  github.com/enoonc-sketch/realtime-translate-2/internal/sensitive
ok  github.com/enoonc-sketch/realtime-translate-2/internal/sidecar
ok  github.com/enoonc-sketch/realtime-translate-2/internal/theme
ok  github.com/enoonc-sketch/realtime-translate-2/internal/translate
ok  github.com/enoonc-sketch/realtime-translate-2/internal/ui
ok  github.com/enoonc-sketch/realtime-translate-2/internal/update
ok  github.com/enoonc-sketch/realtime-translate-2/internal/win32
（cmd/realtime 无测试文件；16 个包全过，顶层测试 153 通过、0 失败、0 跳过；
定义了 157 个测试函数，其中 4 个只在 Windows 编译，未计入本次 Linux 运行）

$ g++ -std=c++17 -fsyntax-only -I/tmp/rt-stub offline-rt/main.cpp
CPP_SYNTAX_OK
（桩头文件只声明本程序实际用到的 API，签名逐项对照实查的 CTranslate2 4.6.0 源码；
只验语法，不验链接、不验真实推理行为）

$ go build -o /tmp/rt2-p4 ./cmd/realtime/
-rwxrwx--- 1 root root 45193352 Nov 20 05:00 /tmp/rt2-p4
（45,193,352 字节 ≈ 43.1MB；P3 是 38,948,832 字节 ≈ 38.9MB；
增加约 4.3MB：18 只宠物资源 5.35MB 内嵌 + 文档/离线/宠物代码，低于 100MB 上限）

$ Xvfb 冒烟（8 秒，timeout 杀进程；另一次 SIGTERM 杀进程测退出路径）
crash.log（两次）：
[2026-11-20 05:02:55] tray start failed, fallback to taskbar minimize
（只有 P2 已知的托盘降级记录；修退出 panic 后，SIGTERM 退出不再多 panic，
out.log 里 panic 计数 0）
config.json 已写入新字段 pet_x: -1、pet_y: -1（0600）。
启动后 5 秒 RSS：242,792 kB ≈ 237MB（Xvfb + Mesa 软渲染；
P3 只测过后端探针 ≈10MB，没测过整机 Fyne 应用，不可直接对比；
真机 Windows 以硬件渲染为准，待实测）
```

## 本次发现的真 bug（已修，诚实记录）

**退出时 panic（P4 新代码引入，冒烟时抓到）。**
现象：SIGTERM 杀进程（或正常退出）后 `crash.log` 多一条
`panic: NotInitialized: The GLFW library is not initialized`，堆栈：
`main.main` → `Shutdown` → `stopPetController` → `fyne.Do(w.Close())` →
GLFW `Window.SetShouldClose`。
原因：`ShowAndRun` 返回后 Fyne 驱动已析构，`fyne.Do` 里再调 `win.Close`
会进已析构的 GLFW。在 Linux 上 100% 复现（分层窗口起不来，Fyne 退回窗口
一定存在）；在 Windows 上不触发（宠物走 Win32 窗口，关闭是 PostMessage）。
修复：`Shutdown` 开头立 `shuttingDown` flag；宠物 Fyne 窗口/气泡、
取词弹窗、覆盖层在退出时跳过 `fyne.Do` 关窗（进程退出即销毁窗口）。
同款隐患也存在于 P3 的 `popup.Close` 与 `shotOverlay.Close`
（退出那一刻正好有弹窗/覆盖层开着时），顺手用同一 flag 修了。
复测：SIGTERM 退出后 crash.log 只有托盘降级记录，panic 计数 0。

**另外三处 P4 写的时候自己改掉的（不是外部反馈）：**
- `doTranslate` 的 done 事件一开始绑在 `HistoryOn` 分支里：历史关着时
  翻译成功也不发 done，大脑会一直 think；已改成与历史开关无关的成功/失败分支。
- `doTranslate` 的 busy 事件一开始放在翻译记忆检查之前：记忆命中也发 busy，
  随后没有 done/fail，大脑卡 think 到 60 秒超时；已移到记忆检查之后。
- 测试文件里 `stubEngine` 与 `writeManifest` 与旧测试文件重名（vet 报错）；
  已改名 `stubOnlineEngine` / `writePackManifest`。

## 没做的事（按纪律）

- 没有推仓库、没有发 Release、没有建 tag。
- 没有写 NSIS/Inno 安装脚本、没有出 EXE 发行包（用户 2026-11-20 定先不打包）。
- `GOOS=windows go build ./cmd/realtime/` 整包仍编不出（Fyne go-gl 的 CGO 限制，
  沙箱无 MinGW；P1–P3 同样，已知限制，本次只跑了 `GOOS=windows go vet`，
  没有反复试同一条路）。
- C# 边车与 C++ 边车在沙箱里编不出来（无 dotnet/csc、无 MSVC/vcpkg），
  只做了 C++ 语法检查；`internal/offline/offline.sha256` 仍是占位注释，
  哈希必须由 `build_offline_sidecar.bat` 在真 Windows 上编译后写入，绝不手写。

## 待真 Windows 验证（P4 新增）

1. `offline-rt/build_offline_sidecar.bat` 在真 Windows 上跑通：下 CTranslate2 源码
   （sha256 钉死）、vcpkg 装 SentencePiece、CMake + MSVC 编出 `rt-offline.exe`、
   生成 `offline.sha256`、冒烟（无参数应打印用法、exit 2）。
2. 离线翻译端到端：下载 en↔zh 两对语言包（钉死表验哈希）→ 引擎下拉出现“离线” →
   离线翻译出结果；断网自动兜底（拔网线/断代理后翻译走离线，30 秒熔断）。
3. 文档翻译端到端：txt/md/srt/docx/PDF 各一份真实文件（含一份几千段的大文档，
   验确认框、进度、取消、保存框与 `-译文` 文件）。
4. 语言包窗口端到端：索引拉取、下载、安装、更新、卸载、本地导入各走一遍。
5. 宠物分层窗口真机行为：透明、分层、置顶、拖动、单击/双击、右键菜单 18 只逐只看、
   位置保存后重启还在；气泡在主窗口隐藏时显示。
6. 边车体积重算：`rt-sidecar.exe` + `rt-offline.exe` + 主程序 + 宠物资源一起
   计入 100MB 预算；超了先报上来、不自行定夺。
7. P1–P3 遗留仍未验：Google 端点沙箱 IP 被挡、微软 auth 端点曾 404、托盘/热键/
   悬停/截图/OCR/TTS/STT 真机行为、Fyne 窗口真机显示。
