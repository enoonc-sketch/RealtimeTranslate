# 实时翻译2 P2 验证报告

- **日期**：2026-11-20
- **范围**：P2 托盘 / 热键 / 系统集成 + 安全 M-02、M-03
- **环境**：Go 1.25.4（`~/workspace/local-build/go/go/bin/go`），Linux 沙箱，
  无 MinGW。`GOTMPDIR=$HOME/.cache/go-tmp`。
- **版本**：`2.0.0-p2`

## 1. 实测输出

```
$ gofmt -l cmd internal
（无输出）
$ go vet ./...
VET_EXIT:0
$ go test ./...
?   	github.com/enoonc-sketch/realtime-translate-2/cmd/realtime	[no test files]
ok  	github.com/enoonc-sketch/realtime-translate-2/internal/config
ok  	github.com/enoonc-sketch/realtime-translate-2/internal/glossary
ok  	github.com/enoonc-sketch/realtime-translate-2/internal/history
ok  	github.com/enoonc-sketch/realtime-translate-2/internal/lang
ok  	github.com/enoonc-sketch/realtime-translate-2/internal/netcheck
ok  	github.com/enoonc-sketch/realtime-translate-2/internal/offline
ok  	github.com/enoonc-sketch/realtime-translate-2/internal/sensitive
ok  	github.com/enoonc-sketch/realtime-translate-2/internal/theme
ok  	github.com/enoonc-sketch/realtime-translate-2/internal/translate
ok  	github.com/enoonc-sketch/realtime-translate-2/internal/ui
ok  	github.com/enoonc-sketch/realtime-translate-2/internal/update
ok  	github.com/enoonc-sketch/realtime-translate-2/internal/win32
TEST_EXIT:0
$ go build ./internal/...        （Linux）
LINUX_INTERNAL_BUILD_OK
$ GOOS=windows go build ./internal/...
WIN_INTERNAL_BUILD_OK
$ GOOS=windows go vet ./internal/win32/
（只有 3 处 GlobalLock 的 "possible misuse of unsafe.Pointer" 警告，exit 0；
是已知误报，见 §5）
$ go build -o /tmp/rt2-p2 ./cmd/realtime
BUILD_OK
-rwxrwx--- 1 root root 38872696 ... /tmp/rt2-p2
```

代码规模：Go 源码 8,716 行（P1 是 7,523 行，P2 +1,193 行），
其中新包 `internal/win32` 1,979 行（非测试）；测试代码 1,656 行。
新增测试：win32 7 个（菜单对照、替换决策、终端类名、热键编号、互斥体名、
ACL 布局）+ ui 1 个（`TestP2SystemIntegrationLinux`，托盘/热键桩行为），全过。

## 2. 标准版体积（单列）

Linux 二进制 **38,872,696 字节 ≈ 38.9MB**（P1 是 38,853,304 字节，
P2 只多了约 19KB），远低于用户定的 100MB 上限。
Windows 二进制体积待真 Windows 打包后实测（沙箱无 MinGW，见 §4）。

## 3. Xvfb 无头冒烟（Linux 真跑，不是只编译）

```
$ HOME=/tmp/rt2-smoke-home xvfb-run -a timeout 8 /tmp/rt2-p2
RUN_EXIT=124（timeout 杀掉，程序 8 秒一直在跑，没有崩溃）
```

- 程序正常启动、建窗口、跑事件循环；退出是 `timeout` 杀的，不是崩溃。
- `crash.log` 里只有一行 P2 预期的降级记录：
  `[2026-11-20 04:07:52] tray start failed, fallback to taskbar minimize`
  （Linux 上托盘本就起不来，P2 的降级路径在真运行时走了，且只记日志、不弹框）。
- Fyne 打了几条环境噪音（新 HOME 下 `.cache/fyne` 不存在、缺 dbus-launch、
  XDG_RUNTIME_DIR 未设），与 P2 代码无关。
- `config.json` 正常落盘，权限 0600。

## 4. 沙箱限制（实测确认，不是推测）

1. **Windows .exe 在沙箱里编不出来**：`GOOS=windows go build ./...`
   到 `cmd/realtime` 时失败——Fyne 的 go-gl 依赖要 CGO，
   沙箱无 MinGW（`which x86_64-w64-mingw32-gcc` 无结果）。
   `internal/...`（含 win32 的全部 Windows 代码）交叉编译通过，
   见 §1。Windows 二进制体积、Fyne 窗口、托盘/热键真机行为待真 Windows 验证。
2. **Linux 链接曾失败，后已恢复**：沙箱里只有 X11/GL 的运行库
   （`libGL.so.1`、`libXrandr.so.2`…），缺 `-dev` 的无版本号链接
   （`libGL.so` 等），`go build ./cmd/realtime` 链接报错
   `cannot find -lGL/-lXrandr/-lXxf86vm/-lXi/-lXcursor`。
   apt 无源装不上，已在沙箱内手动补了 6 条符号链接
   （`/usr/lib/x86_64-linux-gnu/libGL.so → libGL.so.1` 等，仅沙箱环境，
   不动工程；重启/重建沙箱后可能又要补）。
3. **P1 遗留仍待真机**：Google 端点沙箱出口 IP 被挡（HTTP 200 + Sorry HTML，
   代码已按失败处理 + 429 回退微软）；微软 auth 端点沙箱曾返回 404；
   Fyne 主窗口实际打开与主题切换。

## 5. 已知的 vet 警告（3 处，exit 0，不是错误）

`GOOS=windows go vet ./internal/win32/` 报 3 处
"possible misuse of unsafe.Pointer"，都在剪贴板 GlobalLock 的
uintptr → `unsafe.Pointer` 转换上（`clipboard.go:35,68`、
`replace_windows.go:135`）。是 vet 的误报：GlobalLock 返回的是系统拥有的
全局内存指针，锁住期间使用、用完 GlobalUnlock，不经过 Go 堆；
x/sys v0.33 里没有 GlobalLock 的高层封装，只能直调。
已在 `win32.go` 注释里写明，vet 退出码仍为 0。

## 6. 追踪矩阵更新（43 项功能 / 29 项安全）

- 功能：P1 已实现 23 项 → **P2 已实现 5 项**（#4 全局热键翻译选中文字、
  #11 翻译并替换原文、#31 托盘图标、#32 最小化到任务栏、#33 单实例），
  已预留接口 15 → 10 项，后续阶段 5 项不变，删除 0 项。
  热键 2/3/5/6 已在 P2 注册，按了只提示 P3（指针取词/截图/粘贴图片/整窗的
  抓取与显示仍在 P3）。
- 安全：已修 14 项 → **16 项**（M-02 单实例抢占 + M-03 替换竞态），
  后续阶段 14 → 12 项，不适用 1 项不变。
- 复刻清单：M12（点 ×）✅、M5（— 最小化）/M7（开机自启）/M9（热键生效）/
  M11（Esc）/S5（托盘）/S7（热键一览）已更新；W1 指针气泡改到 P3。

## 7. 待真 Windows 验证（P2 新增 + P1 遗留）

- [ ] 托盘图标出现、右键菜单 22 项与原版一致、单击显示、双击显示、退出；
  首次隐藏到托盘弹一次气泡；资源管理器重启后图标重加
- [ ] 六个热键逐个按：Ctrl+Alt+T 翻译选中文字、Ctrl+Alt+R 翻译并替换、
  Ctrl+Alt+D/S/W、Ctrl+Shift+V 在 P3 阶段只提示不执行
- [ ] 热键被占用时 hint 写清楚哪个被占、其余照常用；关于页注册状态一览
- [ ] 点 × 默认最小化到任务栏（任务栏图标可还原）；改成藏托盘后点 × 藏托盘；
  Esc 同款；— 最小化按钮同款；`--minimized` 启动缩到任务栏
- [ ] 开机自启勾选后重启电脑，程序自动缩在任务栏；取消勾选后注册表值消失
- [ ] 单实例：开第二个实例，第一个窗口被提到前台，第二个直接退出
- [ ] 翻译并替换：正常替换、终端里不粘贴只留剪贴板、翻译中切换窗口后只留剪贴板、
  密码框里按热键拒绝、替换后用户原来的剪贴板内容还在
- [ ] Windows 二进制体积与内存（目标：安装包 ≤100MB）
- [ ] P1 遗留：Fyne 主窗口实际打开与主题切换；Google/微软端点真机网络重验
