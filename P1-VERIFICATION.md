# 实时翻译2 P1 验证报告

- **日期**：2026-11-20
- **范围**：P1 在线翻译主流程 + 安全评估前 5 项与顺手修的中低项
- **环境**：Go 1.25.4（`~/workspace/local-build/go/go/bin/go`），Linux 沙箱，
  无显示、无 MinGW。`GOTMPDIR=$HOME/.cache/go-tmp`。

## 1. 实测输出

```
$ gofmt -l .
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
TEST_EXIT:0
$ go build -o /tmp/rt2-p1 ./cmd/realtime
BUILD_OK
-rwxrwx--- 1 root root 38853304 ... /tmp/rt2-p1
```

代码规模：Go 源码 7,523 行（18 个非测试文件 + 11 个测试文件）。

## 2. 标准版体积（单列）

Linux 二进制 **38,853,304 字节 ≈ 38MB**（Fyne + modernc.org/sqlite），
远低于用户定的 100MB 上限。原版标准版约 18MB，Go 版大一倍
（Fyne 运行时 + 纯 Go SQLite），但仍在这个量级、不引重型依赖。
离线语言包不打进安装包，按需下载（默认两对约 145MB，整包 170–189MB）。
Windows 版体积待真机交叉编译后实测。

## 3. 四项质量要求（单列）

- **稳定**：不 panic；翻译失败给明确提示并保留原文和已翻好的分块；
  历史写库失败不影响翻译主流程；配置损坏恢复默认；关键路径
  （分块、术语表、历史存取）有测试；敏感内容拦截（H-01）。
  本次修测试时发现并修掉的真实 bug：① `InstallDir` 未校验 metadata
  字段就拼 version，`../../x` 会走出 root——改为先 `ValidateMetadata`
  再拼；② `ApplyMirror` 空 mirror 时直接返回、不校验 scheme——
  改为先校验 https 再看 mirror；③ zip-slip 校验不能先 Clean 再 Join
  （`Clean("/../x")` 会把 `..` 归一化掉）——改为原始名 Join 后前缀检查；
  ④ `extractEntry` 用 `io.CopyN` 限长会静默截断超大条目——改为
  `LimitReader` + 超限报错；⑤ 报告建议的白名单会把真实版本号 `1.9`
  也拒掉——版本号单独 `SafeVersion`（点分段，禁 `..`）；
  ⑥ 敏感测试用例里的高熵串只有 30 字、不到 32 字阈值——测试改成 32 字。
- **占内存小**：离线语言包按需加载（P1 在线版不加载任何模型）；
  历史分页查（limit 钳制 1–1000）、导出流式分页（pageSize=200）；
  剪贴板截断到 MaxLen、翻译入口超 MaxLen 直接拒绝；内存缓存上限 800 条；
  只引 Fyne 与 modernc.org/sqlite 两个第三方库。
  **实测**（后端探针，临时程序已删）：启动后 RSS 约 10MB；
  100 条历史写入 + 一次翻译后 RSS 约 15MB，Go 堆 Alloc 约 0.4MB。
  完整 Fyne 界面的内存沙箱测不了，待真 Windows 验证。
- **后期维护小**：单语言 Go 到底；后端 10 个包与前端 `ui` 包接口分开，
  最大的 `app.go` 823 行（原版 App 类约 4,700 行）；离线/OCR 边车
  决策写进 ADR-0002/ADR-0003/ADR-0006。
- **交互性好**：输入即译走 goroutine 回来更新界面，有“正在翻译”状态、
  能取消；剪贴板监听、历史搜索（200ms 防抖）、设置改动即时反馈；
  字号、主题切换立即生效；P2–P4 按钮保留原位、点按明示阶段。

## 4. 主题 token 清单与视觉对照

见 ADR-0007：三套主题共用 token（BG/FG/Gray/TextBG/TextFG/BubbleBG/
BubbleFG/BubbleGray/BubbleFoot/Border/Error + 层次 Surface/Surface2/
Primary/OnPrimary/Shadow/Accent + 状态 Success/Warning）；层次 L0 背景 /
L1 卡片与面板 / L2 输入框与按钮 / L3 弹窗；圆角 6/8、间距 12/8；
渐变只用在 2px 顶栏点缀条；原生阴影档位已实查（Menu/Card/PopUp/Dialog）。
逐项对照见 `docs/UI-REPLICA-CHECKLIST.md`。

## 5. 安全修复（按编号，详见 ADR-0008）

已修 14 项：H-01、H-02、H-03、H-04、H-05、H-06、M-04、M-06、M-08、
M-09、M-10、M-11（随 H-03）、M-12（随 H-03）、L-02。
未修 14 项：M-01（P3）、M-02（P2）、M-03（P2）、M-05（P4）、
L-01（P4）、L-03（P3）、L-04（P4）、L-05（P3）、L-06（P4）、
L-07（P2–P3）、L-08（P3）、L-09（P3）、L-10（P3）、L-11（P4）。
不适用 1 项：M-07（go.mod + go.sum 已钉死）。

## 6. 待真 Windows 验证（沙箱做不了）

1. Fyne 主窗口实际打开、置顶、0.35 秒防抖翻译、Ctrl+Enter 立即翻译。
2. 剪贴板监听（250ms 轮询）在真机上的表现与敏感拦截提示。
3. 主题/字号切换立即生效、深色/萌系层次在真机上的观感。
4. **Google 端点**：2026-11-20 当日沙箱 curl 可用（hello world → 你好世界）；
   本次复核（2026-11-20 晚）沙箱出口 IP 被 Google 挡，HTTP 200 返回
   “Sorry...” HTML（用 Go 客户端完全相同的请求头复核过两次）。
   代码侧已按失败处理（解析失败 → 明确报错 + 429 时回退微软），
   但端点本身必须在真 Windows/真机网络上重验。
5. **微软引擎**：auth 端点沙箱 curl 曾返回 HTTP 404，Go 代码仍按 P0
   记录的流程实现（token 失败时重试并报错，不静默标可用），
   待真 Windows 重验。
6. 点 × / 点 – 行为（Fyne 无最小化 API，P1 点 × 保存配置后退出，
   P2 托盘实现后恢复原版默认最小化到任务栏）。
7. 历史窗口、设置窗口 7 个页签在真机上的布局与折行。
8. Windows 版二进制体积与空闲/翻译时内存。
9. `config.json` / `history.db` 与 v2.14.0 原版文件的直接沿用
   （表结构与配置键已逐项对齐，未在真机上用原版文件跑过）。
