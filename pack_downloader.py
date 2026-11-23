"""
离线语言包在线下载：获取 Argos 官方索引 → 列出可下载的语言对 → 下载 .argosmodel → 校验 → 安装。

只用标准库，不依赖 tkinter，可单独测试。下载走系统代理（urllib 会读取 Windows 的代理设置）。
"""
import json
import os
import re
import shutil
import socket
import time
import urllib.error
import urllib.request

import offline_engine as oe

# 依次尝试：GitHub 原始地址不通时（国内常见）换 jsDelivr 镜像。
# 后两条是第三方 GitHub 加速站（gh-proxy.com、ghproxy.net，2026-11-21 沙箱实测
# 返回 200 且内容为有效 index.json）；ghproxy.com、mirror.ghproxy.com、
# hub.gitmirror.com、ghps.cc、ghfast.top、gh-proxy.net 同日实测不通 / 返回非 JSON /
# 不稳定，未加进来。
INDEX_URLS = [
    "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json",
    "https://cdn.jsdelivr.net/gh/argosopentech/argospm-index@main/index.json",
    "https://fastly.jsdelivr.net/gh/argosopentech/argospm-index@main/index.json",
    "https://gh-proxy.com/https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json",
    "https://ghproxy.net/https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json",
]

# 语言包文件镜像（2026-11-21 沙箱实测：en-zh / zh-en 1.9 两个包都从这三处整文件
# 下载过，与钉死表里的 sha256 逐字节一致）：
#   主站 argos-net.com；Argos 官方镜像 data.argosopentech.com（LibreTranslate
#   社区帖子证实的官方镜像）；Cloudflare R2 旧官方地址。
#   注意：ghproxy 类加速站只代理 GitHub 域名，实测代理 argos-net.com 返回 404/403，
#   所以语言包文件没有 ghproxy 镜像，只有上面这三处。
MODEL_MIRROR_PREFIXES = [
    ("https://argos-net.com/v1/", "官方主站 argos-net.com"),
    ("https://data.argosopentech.com/argospm/v1/", "Argos 官方镜像 data.argosopentech.com"),
    ("https://pub-dbae765fb25a4114aac1c88b90e94178.r2.dev/v1/", "Cloudflare R2 旧官方地址"),
]
# 镜像预设（界面下拉框用，与 MODEL_MIRROR_PREFIXES 的顺序对应；0 = 自动依次尝试）。
MIRROR_PRESETS = [
    "自动：主站 → 官方镜像 → R2",
    "官方主站 argos-net.com",
    "Argos 官方镜像 data.argosopentech.com（官方）",
    "Cloudflare R2 旧官方地址（官方）",
]
UA = {"User-Agent": "RealtimeTranslate/2.3"}

# 校验拦截已按用户决定去掉（2026-11-21）：
#   H-03 哈希钉死表不再用于拦截 —— 表留着仅作记录，下载后不再验 hash，
#   不符也不拒绝；界面层也不再对未钉死语言对弹二次确认（见 unpinned_pairs，
#   函数保留供外部调用，但程序内不再凭它拦截）。
#   H-04：pack_mirror 白名单仍用于界面层自定义镜像保存前的提示，不拦截下载。
#   注意：去掉校验后，下载的语言包不再验证来源和完整性，中间人替换的包
#   也会直接装上，这是用户自己定的取舍。唯一底线是文件必须能解压、里面
#   必须有 metadata.json 且能读出 from/to/version，否则按文件损坏报错。
PINNED_PACK_SHA256 = {
    ("en", "zh", "1.9"): "433e7c4f034d87fbe2353161e05f18646d7999452f801a4e1f0378522b9850ab",
    ("zh", "en", "1.9"): "62e7af5a3a48b530e47b7b3e5c78c2de79073ecd815750d2bf3ab35b4a67da2d",
}
MIRROR_HOST_ALLOWLIST = frozenset([
    "raw.githubusercontent.com", "cdn.jsdelivr.net", "fastly.jsdelivr.net",
    "gh-proxy.com", "ghproxy.net",
    "argos-net.com", "data.argosopentech.com",
    "pub-dbae765fb25a4114aac1c88b90e94178.r2.dev",
    "pypi.org", "files.pythonhosted.org",
])

_HOST_RE = re.compile(r"[A-Za-z0-9.-]+(:\d{1,5})?$")


def is_trusted_mirror_host(host):
    """镜像域名是否在内置白名单里（供界面层：自定义域名保存前请用户二次确认）。
    本机回环地址（127.0.0.1 / localhost / ::1）也算可信 —— 那是用户自己的机器，
    不是远程服务器。"""
    h = (host or "").strip().lower()
    return h in MIRROR_HOST_ALLOWLIST or h in ("127.0.0.1", "localhost", "::1")


def _url_ok(url):
    """下载链接校验已按用户决定去掉（2026-11-21）：http 和 https 都允许下载，
    不再只接受 https（用户自己承担风险）。只排除空地址和非 http(s) 协议。"""
    u = str(url or "")
    return u.startswith("https://") or u.startswith("http://")


class Cancelled(Exception):
    pass


def apply_replace(link, replace):
    """replace 形如 'argos-net.com=镜像域名'，可用分号写多组（'a=b;c=d'）；为空或格式不对时原样返回。

    安全修复（H-04）：只接受“裸域名”替换 —— new 必须是裸域名（可带端口），
    old 里不能带 "://"（防 scheme 替换）；替换后原来是 https 的链接必须仍是 https
    （防 https→http 降级）。不合规的组直接跳过，不动原链接。
    """
    for pair in re.split(r"[;；]", replace or ""):
        if "=" in pair:
            old, new = pair.split("=", 1)
            old, new = old.strip(), new.strip()
            if not old or "://" in old or not _HOST_RE.fullmatch(new or ""):
                continue
            new_link = link.replace(old, new)
            if link.startswith("https://") and not new_link.startswith("https://"):
                continue
            link = new_link
    return link


def expand_model_links(link, preferred=0):
    """把一条语言包下载链接展开成主站 + 镜像的候选列表（按顺序试）。

    只有 argos-net.com/v1/ 开头的链接才展开（三处前缀见 MODEL_MIRROR_PREFIXES，
    文件名部分原样保留）；其他链接原样返回单条。preferred 是 MIRROR_PRESETS
    的下标：0 = 自动（主站 → 官方镜像 → R2），>0 时把选中的镜像排到最前面。
    注意下标换算：MIRROR_PRESETS[0] 是“自动”，MIRROR_PRESETS[1..3] 对应
    MODEL_MIRROR_PREFIXES[0..2]，所以要减 1（2026-11-21 修：以前直接拿
    preferred 当 cands 下标，选“官方主站”实际排了官方镜像、选 R2 根本不动）。"""
    for i, (prefix, _label) in enumerate(MODEL_MIRROR_PREFIXES):
        if link.startswith(prefix):
            rest = link[len(prefix):]
            cands = [p + rest for p, _ in MODEL_MIRROR_PREFIXES]
            if 0 < preferred <= len(cands):
                cands.insert(0, cands.pop(preferred - 1))
            return cands
    return [link]


def mirror_label(url):
    """下载链接属于哪个镜像站，返回展示用名称（主站 / 镜像名 / 原始域名）。"""
    for prefix, label in MODEL_MIRROR_PREFIXES:
        if url.startswith(prefix):
            return label
    if "//" in url:
        return url.split("/")[2]
    return url


def _open(url, timeout, headers=None):
    h = dict(UA)
    if headers:
        h.update(headers)
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)


def _is_timeout_error(e):
    """是不是「超时」类错误（可重试、也可等取消）：socket 超时，或包在 URLError 里的超时。"""
    if isinstance(e, (socket.timeout, TimeoutError)):
        return True
    if isinstance(e, urllib.error.URLError):
        return isinstance(getattr(e, "reason", None), (socket.timeout, TimeoutError))
    return False


def _open_cancellable(url, timeout, cancelled=None, headers=None):
    """可取消的 urlopen：每次连接最多等 10 秒，超时就查一次取消，没取消就继续等，
    总预算仍是 timeout 秒；非超时错误（404、DNS 失败等）立即抛出，不空等。

    修 2.15.6 的问题：以前 urlopen 一次等满 timeout（30/60 秒），这段时间里点
    「取消」毫无反应，界面一直停在「正在取消…」。"""
    deadline = time.time() + timeout
    last = None
    while True:
        try:
            return _open(url, min(timeout, 10), headers)
        except Cancelled:
            raise
        except Exception as e:      # noqa: BLE001
            last = e
            if cancelled and cancelled():
                raise Cancelled()
            if not _is_timeout_error(e) or time.time() >= deadline:
                raise last
            time.sleep(min(1.0, max(0.0, deadline - time.time())))


# ---------------------------------------------------------------- 索引
def _read_cache(cache_path):
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) and data else None
    except Exception:      # noqa: BLE001
        return None


def fetch_index(cache_path=None, urls=None, replace="", timeout=20, max_age=None):
    """返回 (条目列表, 说明, 是否来自旧缓存)。

    max_age（秒）：本地缓存没过期就直接用，不联网（打开对话框更快；「刷新列表」不传它即强制联网）。
    否则先联网取最新索引（成功则写缓存）；全部失败就读上次的缓存；都没有则抛 OfflineError。
    """
    if max_age and cache_path and os.path.isfile(cache_path):
        age = time.time() - os.path.getmtime(cache_path)
        data = _read_cache(cache_path) if age < max_age else None
        if data:
            when = "不到 1 小时" if age < 3600 else "%d 小时" % (age // 3600)
            return data, "使用 %s前保存的列表（点「刷新列表」可获取最新）" % when, False
    errors = []
    for url in (urls or INDEX_URLS):
        # 索引地址校验已按用户决定去掉（2026-11-21）：http 索引也允许。
        if not _url_ok(apply_replace(url, replace)):
            errors.append("%s：不支持的索引地址" % (url.split("/")[2] if "//" in url else url))
            continue
        try:
            with _open(apply_replace(url, replace), timeout) as r:
                # 顺手收紧：索引只是个小 JSON 列表，读上限 1MB，防异常大响应撑内存
                data = json.loads(r.read(1 << 20).decode("utf-8"))
            if not isinstance(data, list) or not data:
                raise ValueError("索引内容为空或格式不对")
            if cache_path:
                try:
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                    tmp = cache_path + ".tmp"
                    with open(tmp, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False)
                    os.replace(tmp, cache_path)
                except OSError:
                    pass
            return data, "已获取最新列表", False
        except Exception as e:      # noqa: BLE001
            errors.append("%s：%s" % (url.split("/")[2], e))
    data = _read_cache(cache_path) if cache_path and os.path.isfile(cache_path) else None
    if data:
        stamp = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(cache_path)))
        return data, "联网失败，显示的是 %s 保存的旧列表" % stamp, True
    raise oe.OfflineError("无法获取语言包列表。\n" + "\n".join(errors) +
                          "\n可在下方填写「镜像」，或点「手动下载页面」自己下载 .argosmodel 后导入。")


def best_by_pair(index):
    """每个语言对只留版本最高的翻译包 → {(from, to): 条目}。"""
    best = {}
    for p in index:
        if not isinstance(p, dict) or (p.get("type") or "translate") != "translate":
            continue
        f, t = p.get("from_code"), p.get("to_code")
        # 链接校验已去掉（2026-11-21）：http 链接也保留，见 _url_ok。
        if not f or not t or not [l for l in p.get("links", []) if _url_ok(l)]:
            continue
        cur = best.get((f, t))
        if cur is None or oe._ver_tuple(p.get("package_version")) > oe._ver_tuple(cur.get("package_version")):
            best[(f, t)] = p
    return best


def pinned_sha256(entry):
    """H-03：索引条目在钉死表里就返回期望 sha256，否则返回 None（未知语言对）。"""
    if not isinstance(entry, dict):
        return None
    return PINNED_PACK_SHA256.get((entry.get("from_code"), entry.get("to_code"),
                                   str(entry.get("package_version", ""))))


def unpinned_pairs(pairs, best):
    """H-03：pairs 里哪些语言对不在钉死表里 → [(pair, version), ...]，供界面层下载前请用户确认。"""
    out = []
    for pair in pairs:
        entry = best.get(pair)
        if entry is not None and pinned_sha256(entry) is None:
            out.append((pair, str(entry.get("package_version", ""))))
    return out


def status_of(pair, entry, engine):
    """'已安装' / '可更新' / '未安装'。"""
    have = engine._by_pair.get(pair)
    if not have:
        return "未安装"
    if oe._ver_tuple(entry.get("package_version")) > oe._ver_tuple(have.version):
        return "可更新"
    return "已安装"


def missing_for(engine, from_code, to_code, best):
    """要让 from→to 能离线翻译，还缺哪些语言包。

    返回 [(from, to), ...]：[] 表示已经可以翻译；None 表示列表里也找不到办法。
    有直达包就优先下直达（质量更好），否则经英语中转（两段都要）。
    """
    if from_code == to_code or engine.can_translate(from_code, to_code):
        return []
    if (from_code, to_code) in best:
        return [(from_code, to_code)]
    legs = [(from_code, "en"), ("en", to_code)]
    if all(l in best or l in engine._by_pair for l in legs):
        return [l for l in legs if l not in engine._by_pair]
    return None


# ---------------------------------------------------------------- 下载 / 安装
def _fetch_into(url, tmp, progress, cancelled, timeout):
    """把 url 下载到 tmp；tmp 已有内容就用 Range 续传（服务器不支持则自动从头来）。

    取消（2.15.8 修）：连接阶段走 _open_cancellable（10 秒一查取消）；传输中
    服务器停滞时，读操作按响应的超时（10 秒）抛 socket.timeout，这里接住后
    查取消、没取消就继续等，但连续无数据超过 timeout 秒就按中断报错，交给
    上层重试续传 —— 以前停滞的读一次等满 60 秒，取消根本插不进来。"""
    have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    headers = dict(UA)
    if have:
        headers["Range"] = "bytes=%d-" % have
    try:
        r = _open_cancellable(url, timeout, cancelled, headers)
    except urllib.error.HTTPError as e:
        if e.code == 416 and have:          # 服务器说「已经下完了」
            return
        raise
    with r:
        resumed = bool(have) and getattr(r, "status", 200) == 206
        if not resumed:
            have = 0
        clen = int(r.headers.get("Content-Length") or 0)
        total = have + clen if clen else 0
        if total:
            free = shutil.disk_usage(os.path.dirname(tmp)).free
            need = (total - have) * 3           # 压缩包 + 解压后的文件 + 余量
            if free < need:
                raise oe.OfflineError("磁盘空间不足：还需约 %.0f MB，现在只剩 %.0f MB" % (need / 1e6, free / 1e6))
        got = have
        last_data = time.time()
        with open(tmp, "ab" if resumed else "wb") as f:
            while True:
                if cancelled and cancelled():
                    raise Cancelled()
                try:
                    b = r.read(256 * 1024)
                except (socket.timeout, TimeoutError):
                    if cancelled and cancelled():
                        raise Cancelled()
                    if time.time() - last_data > timeout:
                        raise ConnectionError("下载停滞超过 %d 秒，已中断（已下 %d / %d 字节）"
                                              % (timeout, got, total))
                    continue
                if not b:
                    break
                last_data = time.time()
                f.write(b)
                got += len(b)
                if progress:
                    progress(got, total)
        if total and got < total:
            raise ConnectionError("下载中断（已下 %d / %d 字节）" % (got, total))


def download(url, dest, progress=None, cancelled=None, timeout=60, retries=3, backoff=1.0,
             expected_sha256=None):
    """下载到 dest（先写 .part 再改名）。progress(已下字节, 总字节)。

    中断 / 取消后 .part 会保留，下次同一链接自动续传；传输中途断线会自动重试（续传）。
    校验拦截已按用户决定去掉（2026-11-21）：不再验 zip、不再验哈希（expected_sha256
    参数保留兼容调用方，但不再凭它拦截）；文件能不能用由安装时解压 + 读 metadata.json
    决定，解不开的才按文件损坏报错。
    """
    if not _url_ok(url):
        raise oe.OfflineError("不支持的下载地址：%s" % url)
    tmp = dest + ".part"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for attempt in range(retries):
        before = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        try:
            _fetch_into(url, tmp, progress, cancelled, timeout)
            break
        except (Cancelled, oe.OfflineError):
            raise
        except Exception:      # noqa: BLE001
            after = os.path.getsize(tmp) if os.path.exists(tmp) else 0
            # 连不上 / 一个字节都没收到：不重试，交给上层换下一个链接；传到一半断了才重试续传
            if attempt == retries - 1 or after <= before:
                raise
            time.sleep(backoff * (attempt + 1))
    # zip / 哈希校验已去掉（2026-11-21，用户决定）：下到什么就留什么，安装时
    # 解压失败再按文件损坏报错。
    os.replace(tmp, dest)


def download_pack(entry, models_dir, work_dir, replace="", progress=None, cancelled=None, timeout=60,
                  preferred_mirror=0, on_mirror=None):
    """下载并安装一个语言包，成功返回 Pkg。每个下载链接依次尝试；全部失败抛 OfflineError。

    镜像（2026-11-21）：argos-net.com 的链接先展开成主站 + 两个镜像的候选列表，
    主站失败自动换镜像，不用用户手动改；preferred_mirror 是 MIRROR_PRESETS 的下标，
    选了某个镜像就把它排到最前面。on_mirror(url) 在每次换候选地址时回调，供界面
    显示当前用的是哪个镜像。同一文件名在不同镜像间可断点续传（.part + Range）。

    校验拦截已按用户决定去掉（2026-11-21）：下载后不再验哈希，安装时也不再按
    索引核对包内 metadata——包里 metadata 写什么就装什么；解不开 / 没有 metadata
    的才按文件损坏报错。
    """
    links = [l for l in entry.get("links", []) if _url_ok(l)]
    errors = []
    tried = []
    for link in links:
        for cand in expand_model_links(link, preferred_mirror):
            if cancelled and cancelled():       # 2.15.8：换候选地址前也查取消，别在失败重试里拖住
                raise Cancelled()
            url = apply_replace(cand, replace)
            if url in tried:
                continue
            tried.append(url)
            dest = os.path.join(work_dir, os.path.basename(url.split("?")[0]) or "pack.argosmodel")
            try:
                if on_mirror:
                    on_mirror(url)
                download(url, dest, progress, cancelled, timeout)
                pkg = oe.install_package(dest, models_dir)
                try:
                    os.remove(dest)          # 装好后不留安装包，省几十 MB
                except OSError:
                    pass
                return pkg
            except Cancelled:
                raise
            except Exception as e:      # noqa: BLE001
                errors.append("%s：%s" % (mirror_label(url), e))
                try:
                    os.remove(dest)  # 失败的候选不留垃圾在 work 里（拦截页/坏包），
                except OSError:      # 否则下一个候选装好后 work 里还剩坏文件
                    pass
    raise oe.OfflineError("下载失败（已依次尝试主站与镜像）。\n" + "\n".join(errors))
