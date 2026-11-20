# 实时翻译2 P3 验证报告（悬停取词 / 截图翻译 / OCR / TTS-STT）

- 版本：`2.0.0-p3`
- 日期：2026-11-20
- 基线：P2 已完成并经复核（`P2-VERIFICATION.md`）
- 决策：`docs/adr/ADR-0010-p3-hover-ocr-tts.md`
- 约束：不推仓库、不发 Release、不建 tag（用户 2026-11-20 定的发布纪律）

## P3 做了什么

| # | 功能 | 实现位置 | 说明 |
|---|---|---|---|
| 6 | 指针取词（按热键） | `internal/ui/lookup.go` | 热键 Ctrl+Alt+D（P2 已注册）；I-beam 下等按键松开 → 双击选词 → Ctrl+C 复制（剪贴板保存恢复）；复制不到 OCR 回退（按 PointerScope 取词/行/段）；终端窗口里不取词；结果走气泡/小窗（PopupMode=main 时进主窗口） |
| 7 | 悬停取词 | `internal/ui/lookup.go` | 指针停住 HoverMs 后 OCR 取词，2 秒缓存去重；默认关（H-01），打开时弹一次明确提示；悬停是“只看不碰”，不点鼠标、不复制；重启后按上次的开关恢复 |
| 8 | 截图翻译 | `internal/ui/{lookup,shotselect}.go` | 热键 Ctrl+Alt+S / 按钮 / 托盘；全屏截图 → Fyne 窗口里拖出矩形框选（红框实时跟随）→ OCR → 段落分组 → 逐段翻译（4 路并发）→ 覆盖层 |
| 9 | 整窗翻译 | `internal/ui/lookup.go` | 热键 Ctrl+Alt+W / 设置窗口“3 秒后翻指针下的窗口”；窗口面积 ≤1,400,000 像素时 2 倍放大截（OCR 坐标再除以 2 还原）；UI 行分组（短行按菜单/按钮归组） |
| 10 | 悬停整窗翻译 + 实时刷新 | `internal/ui/lookup.go` | 热键 6 切换（HoverWindow 开 = 实时刷新，关 = 翻一次整窗）；按 LiveInterval（下限 5 秒）重截，BGRA 的 CRC32 没变就不重翻，文字没变也不重翻；覆盖层内容原地更新 |
| 19 | 朗读发音 TTS | `internal/ui/speech.go` + `internal/sidecar` + `sidecar/Program.cs` | C# 边车（ADR-0010 决策 1）；文本走 stdin、不落盘；超时按文本长度算（每 1,000 字 60 秒，封顶 10 分钟），边车自杀 + 主程序 kill 双闸；再点一次停；语音下拉来自边车 voices |
| 21 | 语音输入 STT | 同上 | C# 边车；15 秒超时；认到的文字填进主窗口自动翻译（kind=main）；没听到声音报超时 |
| 24 | 图片文件翻译 | `internal/ui/lookup.go` | 文件对话框选图 → 读内容写临时文件再 OCR（不用 URI.Path，Windows 上 file:// 的 Path 是 "/C:/..."）→ 填进主窗口自动翻译（kind=main） |
| 25 | 粘贴图片翻译 | 同上 | 热键 Ctrl+Shift+V；剪贴板 CF_DIB → BMP 临时文件（0600）→ OCR → 填进主窗口自动翻译（kind=clipboard，默认不入库） |

另：热键 2/3/5/6 全部接上真实功能（P2 只注册、按了只提示所属阶段）；
托盘“截图翻译”“整窗翻译”同样接上；设置窗口 S2（语音下拉）、S3
（指针/悬停/整窗/实时刷新/间隔/预览）全部接上；历史窗口“朗读译文”接上；
Esc 先关气泡/小窗/覆盖层，再隐藏主窗口；退出时停悬停循环、实时刷新、
朗读，关气泡与覆盖层。

### 新增代码

| 文件 | 行数 | 内容 |
|---|---|---|
| `internal/ui/popup.go` | 322 | 气泡/小窗（单击复制、双击朗读、右键/Esc 关闭；140px 离开 / 20 秒 / 15 秒自动关闭；小窗 200ms 跟随） |
| `internal/ui/lookup.go` | 1,068 | 指针/悬停/截图/整窗/实时刷新/覆盖层/图片翻译/临时文件清理 |
| `internal/ui/shotselect.go` | 158 | 框选窗口（自写 Draggable 框选 widget） |
| `internal/ui/speech.go` | 127 | TTS 切换朗读、STT、语音清单 |
| `internal/sidecar/` | 843 | Go 调用层（哈希钉死、超时、stdin 传文、语音白名单）+ 10 个测试 |
| `internal/ocr/` | 823 | OCR 纯逻辑移植（取词/分组/段落）+ 严格 JSON 解析 + 12 个测试 |
| `internal/win32/`（改） | — | `lockedPtr` 修 4 处 GlobalLock 的 vet 误报（见下） |
| `sidecar/Program.cs` | 380 | C# 边车（ocr/tts/stt/voices，.NET Framework 4.7.2） |
| `sidecar/build_sidecar.bat` | 77 | csc 编译 + sha256 钉死 + voices 冒烟 |
| 合计新增 | 3,798 | Go 3,341 行 + C# 380 行 + bat 77 行 |

### 安全修复（P3 分期 7 项全部落地）

| 编号 | 修法 |
|---|---|
| M-01 | PowerShell 彻底不用：三处 PS 侧车（ocr/tts/stt）全由 C# 边车替代，M-01 随之消失 |
| L-03 | 语音名只在已安装清单里才透传（`AllowedVoice`）；OCR 语言走 `OCRTagFor` 白名单，未知语言回 `auto` |
| L-05 | OCR 超时 60→20 秒；全局 OCR 信号量最多 2 个；`live_interval` 下限 2→5 秒（默认 3→5 秒，旧配置 Load 时钳制到 5；冒烟配置实测 `live_interval: 5`） |
| L-07 | 边车只认 exe 旁边与数据目录两个固定位置，绝不沿 PATH 找；执行前验 `sidecar.sha256` |
| L-08 | TTS/STT 文字走 stdin/stdout，不落盘；启动时清数据目录下 24 小时以上的旧临时图（只删 `rt_clip_*` / `hover.*` / `shot.*`） |
| L-09 | TTS 超时按文本长度算（每 1,000 字 60 秒，封顶 10 分钟），边车自杀 + 主程序超时 kill 双闸；退出时 Stop() |
| L-10 | OCR 子进程 stdout 限流 10MB（超了按失败处理）+ 严格 schema 校验（行 ≤10,000、词 ≤100,000、坐标整数 ±1,000,000） |

## 验证（实测输出）

```text
$ go build ./...
BUILD_EXIT:0
$ go vet ./...
VET_EXIT:0
$ go test ./... -count=1
ok  internal/config  ok  internal/glossary  ok  internal/history
ok  internal/lang    ok  internal/netcheck  ok  internal/ocr
ok  internal/offline ok  internal/sensitive ok  internal/sidecar
ok  internal/theme   ok  internal/translate ok  internal/ui
ok  internal/update  ok  internal/win32
（cmd/realtime 无测试文件；共 108 个测试通过，0 失败）
$ gofmt -l internal/ cmd/ sidecar/
（无输出：格式干净）
$ GOOS=windows go vet ./internal/win32/ ./internal/sidecar/ ./internal/ocr/ ./internal/config/ ./internal/history/
WIN_VET_TOUCHED:0
$ GOOS=windows go vet ./internal/ui/
WIN_VET_UI:0
```

Xvfb 冒烟（与 P2 同款 8 秒跑法，隔离 HOME）：
```text
$ timeout 8 xvfb-run -a env HOME=/tmp/rt2-smoke-home /tmp/rt2-p3
EXIT:124（timeout 杀掉，预期内——P2 同款）
config.json 已生成：live_interval: 5，hover: false（新默认值已生效）
crash.log 只有一行 P2 的降级记录：
  [2026-11-20 04:31:43] tray start failed, fallback to taskbar minimize
  （Linux 无托盘，预期内）
```
Linux 二进制 **38,948,832 字节 ≈ 38.9MB**（P2 是 38,872,696 字节，P3 +76KB），
远低于 100MB 上限。Go 总行数 14,713 行。

### vet 误报的纠正（P2 报告写错了，P3 实测纠正）

P2 报告写“`GOOS=windows go vet ./internal/win32/` exit 0，3 处警告”。
P3 重跑发现实际是 **exit 1，4 处** "possible misuse of unsafe.Pointer"
（`clipboard.go:35/68`、`replace_windows.go:135` 三处 P2 遗留，
加 P3 新写的 `screen.go:376` 一处）。原因：`GlobalLock` 返回的数值
（uintptr）直接转 `unsafe.Pointer`，vet 的 unsafeptr 检查认不出来。
修法：`internal/win32/win32.go` 加 `lockedPtr` 辅助函数
（把 uintptr 值 reinterpret 成指针，不经过 uintptr→unsafe.Pointer 的
直接转换；注释写明 GlobalLock 内存是系统拥有的、锁住期间复制、用完
GlobalUnlock、不经过 Go 堆）。四处替换后，
`GOOS=windows go vet ./internal/win32/` **exit 0**，这次是真的 0。

### C# 边车的自查（沙箱无 csc，只能做静态检查）

- 括号平衡：`{}` 58/58、`[]` 9/9、`()` 的 -1 是检查脚本把 `case '"':`
  里的字符常量当成字符串起点了，文件本身是平衡的；
- 关键 API 拼写全对：`OcrEngine.TryCreateFromLanguage` /
  `TryCreateFromUserProfileLanguages` / `AvailableRecognizerLanguages` /
  `MaxImageDimension` / `BitmapDecoder.CreateAsync` / `GetSoftwareBitmapAsync` /
  `SpeechSynthesizer.GetInstalledVoices` / `SelectVoice` /
  `SpeechRecognitionEngine` / `DictationGrammar` / `SetInputToDefaultAudioDevice` /
  `AsTask()`；
- 只用 C# 7.3 以内语法（无 switch 表达式、无元组、无 record），无 NuGet 依赖；
- **边车在沙箱里编不出来、跑不起来**（无 dotnet/csc/mono），
  `sidecar.sha256` 是占位文件，主程序在哈希生成前拒绝运行边车（fail-closed）。
  边车的编译与 OCR/TTS/STT 行为待真 Windows 验证。

### 已知限制（与 P1/P2 相同，P3 没变）

```text
$ GOOS=windows go build ./cmd/realtime/
package github.com/enoonc-sketch/realtime-translate-2/cmd/realtime
    imports fyne.io/fyne/v2/app
    imports fyne.io/fyne/v2/internal/driver/glfw
    ...
    imports github.com/go-gl/gl/v2.1/gl: build constraints exclude all Go files ...
```
沙箱无 MinGW，Fyne 的 go-gl 要 CGO，Windows .exe 编不出来。
Windows 下的托盘/热键/OCR/TTS/气泡定位一律是“待真 Windows 验证”，
不要说成已验证。

## 追踪矩阵更新

功能 43 项：P1 已实现 23、**P2 已实现 5、P3 已实现 9**、
已预留接口 4（#15 离线语言包管理、#22 文档 txt/md/srt、#23 文档 docx、#26 PDF）、
后续阶段 2（#14 离线翻译、#38 桌面小宠物）、删除 0。
安全 29 项：已修 **23**、后续阶段 5（M-05、L-01、L-04、L-06、L-11）、不适用 1。

复刻清单更新：M5（P3 按钮已实现，剩离线/文档）、M7（指针/悬停/小窗已实现）、
M11（Esc 先关气泡/小窗/覆盖层）、S2（语音下拉已实现）、S3（取词页全部已实现）、
H4（朗读译文已实现）、W1–W4（全部已实现，带三处如实偏差：
定位走 Win32、覆盖层不能点透、刷新间隔下限 5 秒）。

## 待真 Windows 验证（P3 新增 + P1/P2 遗留）

1. `sidecar/build_sidecar.bat` 在真 Windows 上编译出 `rt-sidecar.exe`，
   生成 `sidecar.sha256`，`voices` 冒烟通过；
2. OCR/TTS/STT 在真 Windows 上的行为（识别、朗读、语音输入、语音清单）；
3. 气泡/小窗/覆盖层的 Win32 定位（MoveOwnWindow）与托盘/热键联动；
4. P1/P2 遗留：Google 端点（沙箱出口 IP 被挡）、微软 auth 端点（沙箱 curl 曾 404），
   在真机网络上重验。
