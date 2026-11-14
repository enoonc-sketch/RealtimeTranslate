"""
离线语言包在线下载：获取 Argos 官方索引 → 列出可下载的语言对 → 下载 .argosmodel → 校验 → 安装。

只用标准库，不依赖 tkinter，可单独测试。下载走系统代理（urllib 会读取 Windows 的代理设置）。
"""
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
import zipfile

import offline_engine as oe

# 依次尝试：GitHub 原始地址不通时（国内常见）换 jsDelivr 镜像
INDEX_URLS = [
    "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json",
    "https://cdn.jsdelivr.net/gh/argosopentech/argospm-index@main/index.json",
    "https://fastly.jsdelivr.net/gh/argosopentech/argospm-index@main/index.json",
]
UA = {"User-Agent": "RealtimeTranslate/2.3"}


class Cancelled(Exception):
    pass


def apply_replace(link, replace):
    """replace 形如 'argos-net.com=镜像域名'，可用分号写多组（'a=b;c=d'）；为空或格式不对时原样返回。"""
    for pair in re.split(r"[;；]", replace or ""):
        if "=" in pair:
            old, new = pair.split("=", 1)
            old, new = old.strip(), new.strip()
            if old:
                link = link.replace(old, new)
    return link


def _open(url, timeout):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)


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
        try:
            with _open(apply_replace(url, replace), timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
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
        if not f or not t or not [l for l in p.get("links", []) if str(l).startswith("http")]:
            continue
        cur = best.get((f, t))
        if cur is None or oe._ver_tuple(p.get("package_version")) > oe._ver_tuple(cur.get("package_version")):
            best[(f, t)] = p
    return best


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
    """把 url 下载到 tmp；tmp 已有内容就用 Range 续传（服务器不支持则自动从头来）。"""
    have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    headers = dict(UA)
    if have:
        headers["Range"] = "bytes=%d-" % have
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)
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
        with open(tmp, "ab" if resumed else "wb") as f:
            while True:
                if cancelled and cancelled():
                    raise Cancelled()
                b = r.read(256 * 1024)
                if not b:
                    break
                f.write(b)
                got += len(b)
                if progress:
                    progress(got, total)
        if total and got < total:
            raise ConnectionError("下载中断（已下 %d / %d 字节）" % (got, total))


def download(url, dest, progress=None, cancelled=None, timeout=60, retries=3, backoff=1.0):
    """下载到 dest（先写 .part，校验是 zip 后再改名）。progress(已下字节, 总字节)。

    中断 / 取消后 .part 会保留，下次同一链接自动续传；传输中途断线会自动重试（续传）。
    """
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
    if not zipfile.is_zipfile(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise oe.OfflineError("下载内容不是有效的语言包（可能被网络拦截页替换了）")
    os.replace(tmp, dest)


def download_pack(entry, models_dir, work_dir, replace="", progress=None, cancelled=None, timeout=60):
    """下载并安装一个语言包，成功返回 Pkg。每个下载链接依次尝试；全部失败抛 OfflineError。"""
    links = [l for l in entry.get("links", []) if str(l).startswith("http")]
    errors = []
    for link in links:
        url = apply_replace(link, replace)
        dest = os.path.join(work_dir, os.path.basename(url.split("?")[0]) or "pack.argosmodel")
        try:
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
            errors.append("%s：%s" % (url.split("/")[2] if "//" in url else url, e))
    raise oe.OfflineError("下载失败。\n" + "\n".join(errors))
