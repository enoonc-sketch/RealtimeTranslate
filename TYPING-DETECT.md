# 打字检测翻译（实时翻译 Python 版 2.14.0）

日期：2026-11-21（Asia/Shanghai）
基线：`~/workspace/realtime-2.14.0-secfix/RealtimeTranslate-2.14.0/`（纯 Python 2.14.0，已推上 GitHub main）
工作目录：`~/workspace/realtime-typing/`（基线树完整复制后改的，未动 secfix 那棵树、未动远端）
版本：仍为 2.14.0，不改版本号。不推 GitHub、不发 Release、不打包（安装包见下节“打包”——用户后来要求发安装包时才打）。

## 1. 功能

在别的软件里打字时也能检测翻译（主窗口内打字翻译本来就有，这次加的是全局的）。

- **主触发是打字过程中**：每打完一个词（空格 / 标点 / 回车分隔）就立即翻译刚打完的词/句，不等停顿。
- **当前词实时跟进**：正在打的词每多打一个字符就更新候选译文，用约 250 毫秒防抖节流（避免每键都发一次网络请求；防抖只节流，不等于等停顿）。
- **停顿 1 秒只作兜底**：打完一句话停住满停顿毫秒（默认 1000，可调 500–3000）时也翻一次当前片段。
- **气泡实时更新**：同一气泡内随打字更新译文，不每翻一次弹一个新气泡；指针移远了才重定位，否则原地更新，不遮挡输入。
- **性能保护**：连续打字时最多每 300 毫秒发一次翻译请求；正在翻译的词被继续修改时用已有的 cancelled 机制取消旧请求，只保留最新一次；防抖节流绝不丢最后一次（pending 的 live 片段下一轮 tick 补发）。
- 只翻最近一段，片段上限 200 字符；太短（<2 字符）、纯数字/符号的不翻；重复内容不重复翻。
- 翻译走已有的 `translate()`，引擎、语言、术语表、离线/在线回落全部复用；结果显示复用悬停取词的 Bubble/MiniWin 气泡（`popup_mode` 为 `main` 时不弹窗，与指针取词一致）；**打字翻译的结果不进历史**（全局打字的内容不该进历史库）。

## 2. 设置项与默认值

| 设置项 | 默认值 | 说明 |
|---|---|---|
| `typing` | `False`（关） | 打字检测翻译总开关 |
| `typing_pause_ms` | `1000` | 停顿兜底毫秒，可调 500–3000 |
| `typing_scope` | `"word"` | 打字范围：`word` 单词 / `sentence` 整句 |

入口：高级设置 → 取词 →「打字检测翻译」+ 范围下拉 + 停顿兜底微调；托盘右键菜单 →「打字检测翻译」。保存后重启生效（与全局快捷键的配置方式一致）；**关闭时立即停监听、清空缓冲**（隐私优先，不等重启）。恢复默认设置、设置导入/导出都会同步这三项。

## 3. 改了哪些文件

- 新增 `typing_detect.py`（纯逻辑、无 OS 依赖）：`TypingBuffer` 类（字符追加、退格、Esc 清空、按词/按句触发、实时跟进防抖、停顿兜底、限速、去重、长度/最小字符/纯数字符号判定、敏感判定镜像），以及 `is_eligible()` / `is_sensitive_text()` 纯函数。
- 新增 `tests/test_typing_detect.py`（17 个 pytest 测试，见第 4 节）。
- 改 `desktop_translator.py`（最小接线，其余 6982 行逻辑未动）：
  - 开头功能列表追加第 20 条“打字检测翻译”；
  - `import typing_detect`；`TYPING_SCOPE_NAMES`；`DEFAULTS` 加三项；`_load_cfg` 校验（停顿夹 500–3000、范围只认单词/整句）；
  - `tray_menu_items` 加「打字检测翻译」项、`_refresh_tray_state` / `_on_tray_cmd` 接线、`_save` 保存三项；
  - 高级设置 → 取词加打字检测翻译区块（开关、范围、停顿微调、状态说明）；
  - `_on_typing_opt` / `_on_typing_pause` / `_typing_status_text`；
  - Windows 低级键盘钩子 `start_typing_hook_win`（WH_KEYBOARD_LL，标准库 ctypes，不装第三方依赖；修饰键组合与注入事件不转发）；
  - App 接线：`_start_typing`（Windows 钩子 / macOS-Linux pynput，缺 pynput 时明确提示、绝不崩溃）、`_stop_typing`、`_typing_suppressed`（主窗口焦点/密码框/终端）、`_on_typing_key`（前台窗口切换清空缓冲）、`_typing_tick`（每轮 `_poll` 约 100ms：实时跟进 + 停顿兜底）、`_typing_request` / `_typing_worker`（复用 `translate()` + cancelled，不写历史）、`_on_typing_bubble`（同一气泡更新，旧请求作废）、`quit()` 里停监听；`_apply_cfg_to_ui` / `_reset_settings` 同步三项。
- 改 `README.md`：v2.14 新增一节“打字检测翻译（默认关闭）”，写清用法、主触发、隐私说明、平台。

## 4. 验证结果（Linux 沙箱）

| 检查 | 结果 |
|---|---|
| `python3 -m py_compile` 全树 | 通过 |
| `pytest tests/test_typing_detect.py -v` | **17/17 通过**（按空格立即触发、标点/回车触发、当前词实时更新、防抖内不发、限速不丢最后一次、停顿兜底、sentence 片段、重复去重、敏感抑制、密码框抑制、长度上限、最小字符数、纯数字/符号不翻、Esc 清空、停顿夹取、word 模式 live 只跟当前词） |
| 全量测试（基线 venv `realtime-2.14.0-secfix/.venv`，xvfb 下逐文件跑脚本） | **52/52 通过**（基线 51 个文件 + 新测试 1 个）。系统 python3 下另有 5 个文件因缺 sentencepiece 失败，是基线环境问题（基线树同样失败，与本次改动无关）；`test_popup_shot.py` 在全量跑里段错误过一次，重跑 3 次全过，是偶发（基线树同样跑过） |
| `pytest tests/ -q` 全量 | 不适用：仓库旧测试是脚本式（顶层 `sys.exit`），pytest 收集时会内部错误，这是基线就有的形态，不是回归 |
| 冒烟（xvfb + 基线 venv） | 主程序能启动；高级设置 → 取词里能看到打字检测翻译开关/范围/停顿；托盘菜单快照里有 `typing` 项、默认未勾选；默认关闭时未启动任何监听 |
| 集成冒烟（xvfb，translate 打桩） | 模拟在别的软件里打字：`hello ` 按空格后气泡里出现译文“你好”，同一气泡更新 |

## 5. 隐私保护清单

- 默认关闭，用户手动开才监听；关闭时立即停钩子、清空缓冲；退出时也停监听、清空缓冲。
- 缓冲只放内存（`TypingBuffer.text`），绝不写盘、绝不写日志、绝不进历史；打字翻译的结果也不进历史。
- 前台窗口一切换、按 Esc、切到密码框时清空缓冲。
- 密码框自动停：复用 `_foreground_is_password_field_win()`，密码框里不捕获、不翻译；终端窗口也不翻译（复用 `foreground_is_terminal_win()` / `replace_decision` 的终端保护思路）。
- 敏感内容不翻：复用 `is_sensitive_clip()` 的判断（二次把关；`typing_detect` 里另有同款镜像判定），验证码、身份证号、API 密钥等不翻译、不存历史、不放输入框。
- 不捕获修饰键组合（Ctrl+C/V 等）、不捕获自己主窗口获得焦点时的输入（主窗口内已有输入即译，避免双重触发）。
- Windows 钩子回调里只转发按键，不做翻译/弹窗/读配置；注入的按键事件不转发。

## 6. 仍需真机验的项（Windows 真机）

- 在 Word / 浏览器里打字：按空格后是否立即出气泡译文；连续打字时当前词是否实时更新；停顿 1 秒兜底是否生效。
- 密码框里打字是否不触发；终端窗口里打字是否不触发；关闭开关后是否立即停止监听（再打字不出气泡）。
- 托盘菜单开关、重启后生效、恢复默认设置后三项是否回到默认值。
- 钩子被安全软件拦截时是否明确提示、主程序是否不受影响。
- v2.15.6：钩子装不上时状态栏报真实错误码（不再一律写“可能被安全软件拦截”），并自动改用 GetAsyncKeyState 轮询监听；开关打开立即启动，不用重启。
- 打字检测与悬停取词 / 指针取词同时开时气泡是否互相干扰。

## 7. 打包（2026-11-21 用户要求发安装包后补打）

路线：仓库已有的打包路线，不另发明——Wine 9.0 + Windows Python 3.12.16 + PyInstaller 6.22.3 打 exe（`realtime_translate.spec`），再用 Linux 原生 makensis + 手写 `RealtimeTranslate_Setup.nsi`（Inno Setup 6 是 32 位、沙箱跑不起来，Inno 7 拒绝 Wine 的 Windows 版本，故用 NSIS，与 2.14.0 正式版同一套流程）。

spec 改动（按打包 skill 校验后修）：删掉不存在的 hiddenimport `typing.io` / `typing.re`（上次构建日志里报了 2 行 ERROR，本次构建日志 0 行 ERROR）；`typing_detect` 加进 hiddenimports（静态分析本来也能找到，双保险）。

### 产物

| 文件 | 大小 | SHA256 |
|---|---|---|
| 安装包 `RealtimeTranslate_Setup_v2.14.0.exe`（发给用户的那份：`~/workspace/your_files/RealtimeTranslate_Setup_v2.14.0.exe`，另有一份在 `~/workspace/realtime-typing/Output/`） | 19,035,130 字节（约 19 MB） | `32171cd521b7c0ac53b1f217c7719ad0194e56a70ac7fe01c88b54dedeb16c8b` |
| 裸 exe `dist/RealtimeTranslate.exe` | 约 19 MB | `5070dfedc50d15c8a821eadb94372e5be11911c805523b2296ea73f8ffb123b3` |

版本仍为 2.14.0。安装位置：按现有 `.nsi`，每用户安装到 `%LOCALAPPDATA%\Programs\RealtimeTranslate`，开始菜单有快捷方式，可选桌面图标与开机自启，卸载时询问是否删用户数据（默认保留）。**注意：这与“装到 Program Files (x86)”的通用要求不一致**——沿用的是 2.14.0 正式版已验证的安装脚本；如要改 Program Files (x86)，需改成管理员级安装脚本，待用户定。

### Wine 下的验证（已做）

- PyInstaller 构建：退出码 0，日志 0 行 ERROR；用 PyInstaller 归档读取核对：`typing_detect` 已打进 PYZ（254 个模块条目之一），`desktop_translator` 在外层 TOC。
- `--selftest`：退出码 0，「结果：通过」——18 只小宠物动画包全部可用、标准库 106 个可用缺 0 个、系统 OCR 可运行、联网/DNS 正常。（注：窗口版 exe 在 Wine 下 stdout 重定向到文件时会报 `init_sys_streams` 致命错误而起不来，必须用 `script` 给个 PTY 才行；这是 Wine + 窗口版 exe 的已知问题，真机不受影响。）
- 主窗口启动：Wine + Xvfb 下跑满 30 秒超时才被杀（主循环正常运行，无崩溃、无 Traceback），并写出 `config.json`，里面含 `typing: False, typing_pause_ms: 1000, typing_scope: "word"`——内置 exe 的配置已带打字检测三项默认值。
- 安装包内容核对：7z 解包安装包，内嵌 `RealtimeTranslate.exe` 的 SHA256 与刚打出的 `dist/RealtimeTranslate.exe` 完全一致，另含 `Uninstall.exe`。
- **安装器本身未能在 Wine 下跑通**：它是 32 位 NSIS 安装包（与 2.14.0 正式版同格式），而沙箱 Wine 只有 64 位（无 syswow64），报 `failed to load syswow64\ntdll.dll`。这是沙箱限制，不是安装包问题——真机 64 位 Windows 的 WoW64 能正常跑 32 位安装包。真机安装验证留给用户。
- 未推 GitHub、未发 Release；安装包只发给用户本人。

### 仍需真机验的项（安装包）

- 双击安装包走完安装向导，确认装到预期位置、开始菜单快捷方式可用、卸载可用。
- 装完打开高级设置 → 取词，确认「打字检测翻译」开关在；托盘右键菜单里确认有该项；见第 6 节的打字实测。

## 8. 第二版安装包（2026-11-21 用户追加要求后重打）

相对第 7 节的安装包，本次改动（用户逐项定的）：

1. **去掉离线包下载校验拦截**（`pack_downloader.py` / `offline_engine.py` / `prepare_offline_models.py`）：哈希钉死表不再用于拦截（表留着仅作记录）、下载不再验 zip/哈希、http 链接也允许、`install_package()` 不再按索引核对包内 metadata、未钉死语言对的二次确认弹窗去掉。底线保留：文件必须能解压、有 `metadata.json` 且能读出 from/to/version，解不开的按文件损坏报错。
2. **去掉网络翻译拦截**（`desktop_translator.py`）：Edge token 格式校验（L-02）去掉，拿到什么 token 就用什么；只保留“token 为空”这一事实性检查。微软端点返回 401/403 时走正常重试/报错。
3. **安装位置改到 Program Files (x86)**（`RealtimeTranslate_Setup.nsi`）：`InstallDir` 改为 `$PROGRAMFILES32\RealtimeTranslate`，`RequestExecutionLevel` 改为 `admin`（装时会弹 UAC），安装目录注册表与卸载注册表改到 HKLM；开机自启注册表仍在 HKCU（按用户），用户数据目录 `%APPDATA%\RealtimeTranslate` 不动（配置、历史、已导入语言包都在那里，老版本数据不受影响）。
4. **加“导入语言包…”按钮**：主窗口底下按钮行里，在“离线语言包…”旁边加了“导入语言包…”按钮，不开对话框也能直接选 `.argosmodel` 导入；`_import_packs` 改成对话框没打开时也能用（文件框挂主窗口、进度与结果走状态栏，失败弹窗报明原因）。离线语言包对话框布局同步修好：表格 height=10 改为 6、窗口 680x440 改为 680x520，按钮行在默认尺寸下可见可点。
5. **没动剪贴板/打字检测的敏感内容不翻逻辑**（`is_sensitive_clip`），没动 Google 翻译请求逻辑，没打离线版、没内置语言包（离线版用户已叫停）。

### 产物（新）

| 文件 | 大小 | SHA256 |
|---|---|---|
| 安装包 `RealtimeTranslate_Setup_v2.14.0.exe`（`~/workspace/your_files/RealtimeTranslate_Setup_v2.14.0.exe`，同名覆盖上一版，SHA 变化属正常） | 19,033,056 字节（约 19 MB） | `e38c2948317b7e2db2b64c9d2ca3691e56d35857df3f4048af29ff28c63c175b` |
| 裸 exe `dist/RealtimeTranslate.exe` | 19,143,091 字节（约 19 MB） | `857a0f41515d5bd62b053556d7b920c7fddeaa5a5b3b04b28483d92c4bd32ef1` |

### 构建中的插曲

- Wine Python 里 numpy 是 2.5.5，一 import 就调 `ucrtbase.dll.crealf`（Wine 9.0 未实现）崩掉，导致 PyInstaller 的隔离子进程死掉、构建失败。用 `wheels-rt-offline/` 里已有的 `numpy-2.0.2-cp312-cp312-win_amd64.whl` 把 Wine Python 的 numpy 降到 2.0.2 后构建通过（按 AGENTS.md 既定做法；只动了 Wine 环境里的 numpy，没动程序代码和 `requirements-runtime-lock.txt`）。
- 构建日志 0 行 ERROR；`typing_detect` / `desktop_translator` / `pack_downloader` / `offline_engine` 四个模块名都在 exe 的归档目录里；7z 解包安装包，内嵌 exe 的 SHA256 与 `dist/` 的一致。

### Wine 下的验证（新）

- `--selftest` 退出码 0，「结果：通过」（18 只宠物、标准库 106 个缺 0 个、OCR、联网/DNS 正常；标准版无离线运行库属正常）。
- 主窗口 Wine + Xvfb 下跑满 30 秒无崩溃，`config.json` 含打字检测三项默认值。
- 导入流程 Linux 侧实测：用已下载的真包 `translate-en_zh-1_9.argosmodel` 走 `_import_packs` 底下同一个 `install_package`，装上后引擎认出 en→zh；损坏文件明确拒绝（“不是有效的语言包文件”）。
- 对话框按钮与主窗口新按钮只做了代码核对（按钮在默认尺寸下可见、命令已接线），Wine 下逐个点击尚未实测，需真机验。
- 安装器本身仍未能在 Wine 下跑通（32 位 NSIS、沙箱无 syswow64），真机安装与 Program Files (x86) 位置、UAC 弹窗需用户真机验。

### 用户自己定的取舍（转达）

- 去掉校验后，下载的语言包不再验证来源和完整性，中间人替换的包也会直接装上。
- 去掉 token 校验后，代理返回的拦截页内容会被当 token 发过去，失败时提示会变成认证失败。

## 9. 完整离线版 + 微软接口下线 + 镜像下载（2026-11-21）

用户说“把网络拦截解决了、离线装上就完美了”，随后又追加“在离线语言包下载里加上镜像下载网站”。真相先说清（实测，非猜测）：

- 微软 404 不是代理拦的：`https://edge.microsoft.com/translate/auth` 从沙箱直连也返回 404，微软免费取 token 的接口已经下线，谁来都 404。去掉 token 格式校验解决不了它。
- Google 429 是代理出口 IP 被 Google 限流（共享代理 IP 请求太多），程序侧修不了，只能靠重试/回退。沙箱直连 Google 当时也返回 429。
- 程序里已有回退链：Google 429 回退微软、在线整体不通时自动改用离线（`auto_offline` 默认开）。用户那边两条回退都断了（微软已死、没有离线包），所以全失败。离线版就是解法。

### 改了什么

1. **微软接口下线，按真相报错**（`desktop_translator.py`、`netcheck.py`）：
   - `_ms_get_token` 取 token 返回 404 时，报错写明“微软免费取 token 的接口已返回 404，该接口已下线，不是代理拦截；微软引擎暂时不可用，请改用 Google 或离线”；`ms_translate` 里遇到“接口已下线”不再白等三轮重试，直接报。
   - `netcheck.py`：微软 404 的检查项与最终结论都改成接口下线的说法，不再写“可能被代理/防火墙拦截”；Google 429 的重试/回退逻辑保持原样。
   - 微软引擎入口没删（用户没说删），只把报错说准。
2. **镜像下载**（`pack_downloader.py`、下载对话框）：
   - 索引新增两个第三方 GitHub 加速站：`gh-proxy.com`、`ghproxy.net`（沙箱实测返回 200 且 JSON 有效，100 条）；`ghproxy.com`、`mirror.ghproxy.com`、`hub.gitmirror.com`、`ghps.cc`、`ghfast.top`、`gh-proxy.net` 同日实测不通 / 非 JSON / 不稳定，未加。
   - 语言包文件镜像：`argos-net.com` 的链接展开成主站 + 两个镜像依次尝试，主站失败自动换镜像。`data.argosopentech.com/argospm/v1/`（Argos 官方镜像）、`pub-dbae765fb25a4114aac1c88b90e94178.r2.dev/v1/`（Cloudflare R2 旧官方地址）——两个包都整文件下载并验 sha，与钉死表逐字节一致。ghproxy 类加速站只代理 GitHub 域名，实测代理 `argos-net.com` 返回 404/403，所以语言包文件没有 ghproxy 镜像。HuggingFace 上没有 en-zh / zh-en 1.9 的 Argos 模型包，未加。
   - 下载对话框加“镜像预设”下拉：自动（主站 → 官方镜像 → R2）、官方主站、Argos 官方镜像、R2；选了就优先用该镜像，不用自己拼域名。原有“镜像”手动输入框保留。下载进度里显示当前用的镜像，下载完汇总用过哪些镜像。
   - 新增镜像域名已进 `MIRROR_HOST_ALLOWLIST`（自定义镜像保存前不再对它们弹确认）。
3. **完整离线版安装包**：`realtime_translate_offline.spec`（补上 `typing_detect`）、`RealtimeTranslate_Setup_Offline.nsi`（新写，NSIS 打包 onedir，装 `Program Files (x86)\RealtimeTranslate`、管理员级）。包里含打字检测、离线引擎、en-zh + zh-en 1.9 语言包、去掉的两道拦截、导入按钮、对话框布局修复、镜像下载。

### 产物（2026-11-21 03:42 已交付）

- 安装包 `RealtimeTranslate_Setup_v2.14.0_Offline.exe`（`~/workspace/your_files/`），**199,147,780 字节（190 MiB，未超 200MB 上限）**，SHA256 `3641c396541a0a2450a8fbdf7a5092193fd4d39381eef8cc5491e4bffd902ed5`。
- 内嵌 exe 与 `dist/RealtimeTranslateOffline/RealtimeTranslate.exe` SHA256 一致（`2873cfdb…a6dcc4d`），7z 解包确认含 `_internal/offline_models/` 下 en-zh 与 zh-en 两个语言包。
- 语言包 sha256 构建时已按钉死表核对：en→zh 1.9 `433e7c4f…9850ab`、zh→en 1.9 `62e7af5a…4a67da2d`，一致（核对只用于构建时验货，未留在程序里当拦截）。

### 验证结果（2026-11-21 03:38–03:42）

- `py_compile` 全树通过；`tests/test_typing_detect.py` 17/17 通过。
- 打包后的离线 exe 在 Wine 下 `--selftest` 通过（`frozen=True`，退出 0）：离线运行库有、内置语言包目录存在、已识别 en→zh、zh→en，真机翻译 en→zh 1318ms、zh→en 911ms；18 只小宠物、106 个标准库、系统 OCR 均通过，结论“通过”。
- 主窗口 Wine 下跑 40 秒未闪退；`typing_detect` 在 `desktop_translator.py` 顶层 import，exe 正常启动即证明已打进包；`config.json` 含打字检测默认值（`typing=false`、`typing_pause_ms=1000`、`typing_scope=word`）。
- Wine 下验证的坑（只影响沙箱验证，不影响真机）：ctranslate2 的 OpenMP 运行库在 Wine 9.0 下调 `GetNumaNodeProcessorMaskEx` 失败（Wine 未实现），进程直接退出码 3；设 `KMP_AFFINITY=disabled` 后正常。真 Windows 上该函数存在，不受影响。另：NSIS 安装器本身未在 Wine 下安装测试（32 位 NSIS、沙箱无 syswow64，与标准版同），真机安装与 Program Files 位置、UAC 需用户实测。

### 转达用户的真相

- Google 429 是代理出口 IP 被限流，程序修不了，只能等限流过去或换网络/走离线。
- 微软免费接口已下线，微软引擎暂时不可用。
- 离线版装好后在线失败会自动回退到离线，不用再手动切。
