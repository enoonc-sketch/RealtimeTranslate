# 实时翻译 v2.4 — Windows 构建说明

当前环境是 Linux，**无法交叉编译出 Windows 程序**，请在 **Windows 电脑**上按下面步骤操作。

## 两个版本怎么选

| | 标准版 | 离线版（新） |
|---|---|---|
| 构建 | `build_exe.bat` | `build_offline.bat` |
| 形态 | 单个 exe（约 13 MB） | 文件夹（运行库 + 内置语言包，约 200~500 MB，取决于语言对数量） |
| 在线翻译（Google / 微软） | ✔ | ✔ |
| 离线翻译（断网可用，文字不出本机） | ✔ 在程序里点一下下载组件（约 35 MB） | ✔ 已内置 |
| 安装包 | `build_installer.bat` | `build_installer.bat offline` |

两个版本使用同一个程序名和安装 ID，**可以互相覆盖升级**，设置和开机自启通用。

## 构建标准版

1. 安装 [Python 3.9+](https://www.python.org/downloads/)，勾选 **Add python.exe to PATH**
2. 双击 `build_exe.bat` → 得到 `RealtimeTranslate.exe`

## 构建离线版（含离线安装包）

1. 安装 **64 位** [Python 3.9+](https://www.python.org/downloads/)（ctranslate2 没有 32 位版本）
2. （可选）编辑 `offline_models.txt`，选择要内置的语言对，默认中↔英。每对约 50~130 MB
3. 双击 `build_offline.bat`（**首次需要联网**，会下载 ctranslate2 和语言包）。它会依次：
   建独立虚拟环境 → 下载语言包到 `offline_models\` → 打包 → **自动自检**（真正加载模型翻译一句）
4. 得到 `dist\RealtimeTranslateOffline\`，里面的 `RealtimeTranslate.exe` 可直接运行，整个文件夹可复制给别人
5. 做成安装向导：安装 [Inno Setup 6](https://jrsoftware.org/isdl.php)，运行 `build_installer.bat offline`
   → `Output\RealtimeTranslate_Offline_Setup_v2.3.0.exe`

**语言包下载不下来？**（`argos-net.com` 在部分网络下不通）
用浏览器 / 代理从 [索引](https://github.com/argosopentech/argospm-index)（`index.json` 的 `links` 字段）下载 `.argosmodel`，
放进 `offline_models\` 后重新运行 `build_offline.bat`，会自动识别；或用镜像：
`python prepare_offline_models.py --replace argos-net.com=镜像域名`。

**离线版运行时**：语言包在 `_internal\offline_models`（内置）和 `%APPDATA%\RealtimeTranslate\models`（用户导入）。
用户随时可在程序里点「离线语言包…」导入更多 `.argosmodel`，无需重新构建。

## v2.4 新增

### 托盘图标（Windows，纯 ctypes，不用 pystray / Pillow）
- 新模块 `tray_win32.py`：只用 Python 标准库 `ctypes` 调 `Shell_NotifyIconW`，
  图标直接读自带的 `app.ico`（`LoadImageW`，不用 Pillow 转格式），
  右键菜单用 `CreatePopupMenu` / `TrackPopupMenu`。
  装没装 pystray / Pillow 都不影响；两个 spec 都把 `pystray` 写进了排除列表。
- 点 × / 按 Esc：有托盘时隐藏到托盘（任务栏不留窗口），点托盘图标 / 双击找回；
  没托盘（比如被安全软件拦了）时退回旧行为：最小化。
  真正退出走托盘右键菜单「退出」或主界面「退出」按钮。
- 托盘右键菜单：显示主窗口 / 截图翻译 / 退出。托盘回调只往队列里放事件，
  真正的显示 / 退出由主线程处理，和全局热键的做法一样。
- 开机自启仍是 `--minimized` 启动，现在是最小化到托盘。

### 悬停取词（Windows，默认开）
- 选项里新增「悬停取词（鼠标停住自动取词）」，默认开，停住约 0.8 秒触发，
  可在配置里改 `hover_ms`（300~3000 毫秒）。
- 原理：先截光标周围一小块（420×110），用系统 OCR 认出离光标最近的单词，
  不依赖软件本身是否支持选词——图片、游戏、扫描 PDF、按钮上的文字也能取。
  OCR 没认出、且光标是「I」形时，退回原来的双击取词；光标不是「I」形
  （按钮、链接）时绝不点击，不会误触发。
- 在主窗口里悬停不触发，避免自己取自己；气泡开着、正在取词、正在截图时也不触发。

### 截图翻译（Windows，Ctrl+Alt+S）
- 主界面新增「截图翻译」按钮，托盘右键菜单里也有；按 `Ctrl+Alt+S`
  （新注册的第三个全局热键，和 Ctrl+Alt+T / Ctrl+Alt+D 一样走系统热键）。
- 框选屏幕任意区域 → 截图 → 系统 OCR 认字 → 进主窗口翻译。
  截图用 `screen_win.py`（ctypes GDI `BitBlt` / `GetDIBits`，存 32 位 BMP，
  不用 Pillow）；OCR 用 `ocr_win.py` + `winocr.ps1` 调系统自带的
  `Windows.Media.Ocr`（Photos 应用用的同一个引擎，本地运行、不联网）。
- OCR 要求：Windows 10+，且装了对应语言的 OCR 语言包
  （设置 → 语言 → 添加语言；或 PowerShell 查 `Get-WindowsCapability -Online`
  里 `Language.OCR*`）。没装会在状态栏明说原因，不会静默失败。
  注意：OCR 走的是 Windows PowerShell 5.1（`powershell.exe`），
  PowerShell 7（`pwsh`）不支持 WinRT OCR，所以脚本里写死了 5.1 才能跑。

## v2.3 新增


### 在线下载离线语言包（程序内直接下载，不用再手动找文件）
- 主界面「离线语言包…」→「下载语言包…」：自动取官方列表，可搜索（输入 日语 / ja），多选后「下载所选」
- 「下载当前翻译方向所需」：按你现在选的语言自动算出缺哪些包（没有直达包就补上经英语中转的两段），一键下载
- 显示进度，可随时取消；下载内容必须是有效语言包，被网络拦截页替换会拒绝；装好后自动删除安装包、立刻可用
- 列表取不到时依次尝试 GitHub 和 jsDelivr 镜像；全都失败则显示上次保存的旧列表；对话框里的「镜像」栏（旧域名=新域名）用于下载链接本身不通时
- 语言包装到 `%APPDATA%\RealtimeTranslate\models`，与「导入」的位置相同，下载与手动导入可混用
- 仅离线版有此功能（标准版没有离线运行库）

### 标准版也能离线：程序内下载离线翻译组件（不用重新构建）
- 标准版点「离线语言包…」→ 询问「下载约 35 MB 组件」→ 同意后自动从 PyPI 官方下载 numpy / pyyaml / sentencepiece / ctranslate2 的预编译包，
  校验 SHA-256、安全解压到 `%APPDATA%\RealtimeTranslate\runtime`；**装好无需重启**，引擎里立刻出现「离线」，并自动进入语言包下载
- 之后每次启动自动加载这些组件；换了 Python 版本重新构建 exe 时会提示重新下载（轮子与 Python 版本绑定）
- 支持取消 / 断点续传 / 失败重试；「镜像」栏可填 `pypi.org=镜像域名;files.pythonhosted.org=镜像域名`（多组用分号）
- 组件占用磁盘约 100~200 MB；删除 `runtime` 文件夹即可卸载
- `realtime_translate.spec` 已把这些组件运行时要用的标准库显式打进标准版 exe（清单来自真实组件实测：`tests\real_runtime_check.py`）
- 需要 **64 位** 程序；若提示「无法加载」，安装「Microsoft Visual C++ 2015-2022 Redistributable (x64)」后重启

### 下载与启动的优化
- **断点续传**：下载中途取消 / 断网 / 关掉程序，已下载的部分会保留，再点下载接着下；传输中途断线会自动重试并续传。服务器不支持续传时自动从头下
- **速度与剩余时间**：下载进度行显示 MB/s 和预计剩余时间
- **打开更快**：语言包列表一天内直接用本地缓存，不用每次联网；「刷新列表」强制取最新
- **磁盘空间检查**：下载前按文件大小检查剩余空间，不够会直接提示还差多少 MB，而不是下到一半失败
- **离线引擎预热**：选「离线」引擎（或启动时已是离线）后，后台提前载入当前方向的模型，第一次翻译不再卡 1~3 秒
- **下载完成提示**：告诉你把引擎切到「离线」，或保持 Google（断网会自动改用离线）

### 指针取词（Ctrl+Alt+D）
- 把鼠标放在文字上按 **Ctrl+Alt+D**，在指针旁弹出小气泡显示译文；不打开主窗口、不抢焦点
- 气泡：点一下复制译文，右键 / Esc / 把指针移开就消失
- 选项「指针取词」可关闭；「范围」可选 **单词**（双击）或 **整段**（三击）
- 原理：指针是「I」形文字光标时，才在指针处双击 / 三击选中文字，再复制翻译。
  **指针是箭头 / 手形（按钮、链接）时绝不点击**，所以不会误触发按钮或打开链接；
  终端窗口里没有选区时不会发送 Ctrl+C（避免中断正在运行的程序）
- 取词前会等 Ctrl / Alt 等键松开，避免变成 Ctrl+点击（比如在新标签页打开链接）
- `Ctrl+Alt+T`（取已选中的文字、结果在主窗口）保持不变
- 取词时会临时占用剪贴板并在取完后恢复；被取词的位置会留下选中高亮（这是双击的正常效果）
- macOS / Linux：不会自动点击，请先选中文字再按 Ctrl+Alt+D，译文同样显示在指针旁

## v2.2 新增

### 离线翻译
- 自带轻量引擎，直接读取 Argos 语言包，运行时只需 `ctranslate2 + sentencepiece`。
  **不依赖 argostranslate**（它的最新版强制依赖 stanza/torch，会让安装包膨胀到数 GB）
- 没有直达语言对时自动经英语中转（日→中 = 日→英 + 英→中）
- 「离线语言包…」对话框：查看已装语言包、导入 `.argosmodel`、打开目录
- 兼容已装过 Argos Translate 的机器：自动复用 `~/.local/share/argos-translate/packages`
- 带中文用户名的路径：自动规避 Windows 下 ctranslate2 打不开中文路径的问题
- `RealtimeTranslate.exe --selftest`：不开界面，检查运行库和语言包并写报告到 `%APPDATA%\RealtimeTranslate\selftest.txt`

### 网络检查
- 主界面「网络检查」按钮，并行检测：外网直连、DNS、系统代理、Google、微软、离线引擎
- 失败时说明原因并给出建议（DNS 失败 / 超时 / 证书错误 / 429 限流 / 代理需认证 / 连接被重置 …）
- 给出推荐引擎，一键切换；可「复制报告」发给别人排查
- 翻译失败且判断为网络问题时，错误提示里会引导点「网络检查」

### 断网自动改用离线
- 选项「断网 / 在线引擎不可用时，自动改用离线翻译」（默认开，仅离线版可见）
- 在线整体不通时进入 30 秒「熔断」：直接走离线，不再逐段等待超时；网络恢复后自动回到在线
- 回退产生的离线译文**不会缓存**到在线引擎名下，网络恢复后会重新用在线译文
- 状态栏会标注「在线不可用，已自动改用离线」

## 已验证 / 未验证（请知悉）

**已在 Linux 沙箱验证**
- 离线引擎：加载、批量推理、分句、经英语中转、LRU 淘汰、多线程、导入语言包（含 zip-slip 防护）
- 网络检查：各类故障归因、推荐逻辑、超时不阻塞；回退 / 熔断 / 不污染缓存
- 界面：网络检查对话框、语言包对话框（含导入）、自动回退状态栏
- PyInstaller：标准版与离线版都实际打包，并运行打出的二进制 `--selftest` 通过
- `tests\` 目录含全部测试（`python tests\test_offline_engine.py` 等，需 pip 装 ctranslate2 / sentencepiece）

**v2.3 已在 Linux 沙箱验证**
- 下载：索引获取（含源失效切换、缓存回退）、版本挑选、镜像替换、下载进度 / 取消 / 拦截页拒绝、多链接依次尝试、安装后引擎可用、缺口计算
- 界面：下载对话框（列表 / 搜索 / 所需 / 下载 / 取消 / 状态刷新）、气泡（翻译、定位、屏幕边缘、点击复制、移开关闭、Esc、错误提示、连续取词不串）、取词决策逻辑

**组件在线安装已验证（Linux）**：用真实 PyPI 的最新版组件，下载 → 校验 → 解压 → 加进路径，在**不带任何第三方包的纯净 Python** 里成功 import 并翻译（`tests\real_runtime_check.py`，需联网）；
本地假 PyPI 测试覆盖：选版本（跳过其他系统 / musl / 预发布 / 被撤回 / Python 不匹配）、SHA 校验失败、zip-slip、取消回滚与续传、重装整体替换、32 位拒绝；界面：询问 / 失败重试 / 取消 / 装好免重启。

**v2.4 未能验证（Windows 专有，请首次使用时实测）**
- **托盘**：`Shell_NotifyIconW` 加图标、左键双击显示、右键菜单、资源管理器重启后
  图标重建、退出时图标不残留。Linux 沙箱里只能验证“非 Windows 上 import 安全、
  start() 返回 False、不崩主程序”。
- **悬停取词**：鼠标停住 0.8 秒触发、OCR 定位光标下的单词、I 形退回双击、
  多显示器 / 高分屏下的截图区域换算。
- **截图翻译**：`Ctrl+Alt+S` 注册、框选层定位、截图不含黑框、PowerShell 5.1
  调 `Windows.Media.Ocr` 的真实识别效果（中 / 英 / 日等语言包是否已装）、
  大图识别耗时。OCR 失败时状态栏会写明原因，请把那句话发回来定位。

**v2.3 未能验证（Windows 专有，请首次使用时实测）**
- **Windows 上加载下载来的组件**：PyPI 上确有 cp39~cp313 的 win_amd64 轮子，但沙箱无法执行 Windows DLL；
  标准版 exe（PyInstaller 单文件）从 `%APPDATA%` 加载 .pyd / DLL 的实际效果、VC++ 运行库依赖，需你实测
- 指针取词的真实点击链路：热键 Ctrl+Alt+D 注册、「I」形光标识别、在指针处双击 / 三击、复制、剪贴板恢复
  某些软件用自绘光标，识别不出「I」形时会退化为只复制已有选区，提示「指针下不是可选文字」
- 气泡的「不抢焦点」（WS_EX_NOACTIVATE）与多显示器 / 高分屏下的定位
- 真实索引地址：沙箱联不上 GitHub / argos-net.com，下载测试用的是本地假服务器和微型假模型

**未能验证（v2.2 遗留）**
- **真实语言包**：沙箱无法访问 `argos-net.com`，上述离线测试用的是随机权重的**微型假模型**（译文是乱码，只验证流程）。
  真实模型的翻译质量、速度、内存占用需你构建后实测；用旧版 BPE 分词的老语言包会被识别为「暂不支持」
- **Windows 专有部分**：ctranslate2 的 Windows DLL 打包、Inno Setup 编译、DPI / 单实例 / 开机自启 / 热键取词
- **微软端点**：沙箱访问不了，未实测

首次在 Windows 构建时，`build_offline.bat` 的第 6 步自检就是为此设计的：它通过才说明模型真的能加载并翻译。

## 其他说明

| 项目 | 说明 |
|---|---|
| DLL load failed | 安装「Microsoft Visual C++ 2015-2022 Redistributable (x64)」 |
| 杀毒误报 | PyInstaller 程序可能被误报；已关闭 UPX，可添加白名单或做代码签名 |
| 热键取词 | 会临时占用剪贴板，取词后恢复；剪贴板里若是图片/文件，恢复时会丢失 |
| 在线引擎 | Google / 微软均为非官方免费端点，可能随时变更或限流 |
| 离线质量 | Argos 模型体积小、速度快，但质量不及在线引擎；适合断网兜底和隐私场景 |
| 内存 | 每个已加载的翻译模型约 100~300 MB，最多同时驻留 3 个（超出自动卸载最久未用） |

## 文件列表

- `desktop_translator.py` — 主程序
- `tray_win32.py` — Windows 托盘（纯 ctypes，不依赖 pystray / Pillow）
- `screen_win.py` — Windows 截图（ctypes GDI，不用 Pillow）
- `ocr_win.py` + `winocr.ps1` — Windows 自带 OCR（Windows.Media.Ocr，经 PowerShell 5.1 调用）
- `offline_engine.py` — 离线引擎（Argos 语言包 + ctranslate2）
- `pack_downloader.py` — 在线下载语言包（取列表 / 下载 / 校验 / 安装，仅标准库）
- `runtime_installer.py` — 在线安装离线运行库（从 PyPI 取轮子，仅标准库）
- `netcheck.py` — 网络检查
- `prepare_offline_models.py` / `offline_models.txt` — 下载并解压离线语言包
- `realtime_translate.spec` / `build_exe.bat` — 标准版
- `realtime_translate_offline.spec` / `build_offline.bat` — 离线版
- `installer.iss` / `build_installer.bat` — Inno 安装包（标准版 / `offline`）
- `version_info.txt`、`app.ico` — exe 版本信息与图标
- `tests\` — 测试
