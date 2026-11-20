"""检查更新 — 只读 GitHub Releases 的 latest，不自动下载、不自动安装。

做法：urllib 读 https://api.github.com/repos/enoonc-sketch/RealtimeTranslate/releases/latest
（8 秒超时），解析 tag_name 当版本号，与 __version__ 比大小。
断网 / 解析失败 = "error"，调用方按静默处理（不弹窗、不报错）。
"""
import json
import urllib.error
import urllib.request

LATEST_URL = ("https://api.github.com/repos/enoonc-sketch/"
              "RealtimeTranslate/releases/latest")
RELEASES_URL = ("https://github.com/enoonc-sketch/"
                "RealtimeTranslate/releases/latest")


def _read_capped(resp, limit):
    """读 HTTP 响应并限流：真实响应支持 read(n)；某些桩对象只定义了无参 read()，
    遇 TypeError 时退回无参读再截断（上限照样守住）。"""
    try:
        data = resp.read(limit)
    except TypeError:
        data = resp.read()
    return data[:limit]


def parse_version(tag):
    """'v2.6.0' / '2.6.0' -> (2, 6, 0)；解析不出返回 None。"""
    try:
        parts = str(tag or "").strip().lstrip("vV").split(".")
        if not parts or not all(p.strip().isdigit() for p in parts):
            return None
        nums = tuple(int(p) for p in parts)
        return nums if nums else None
    except Exception:
        return None


def compare_versions(local, remote):
    """版本号元组比较：local < remote 返回 -1，相等 0，大于 1。"""
    if local is None or remote is None:
        return 0
    n = max(len(local), len(remote))
    a = local + (0,) * (n - len(local))
    b = remote + (0,) * (n - len(remote))
    return (a > b) - (a < b)


def fetch_latest_tag(opener=None, timeout=8):
    """返回 (tag, None)；失败返回 (None, 原因字符串)。opener 可注入测试替身。

    opener(url, timeout=...) 应返回一个带 .read() 的上下文管理器
    （urllib.request.urlopen 就是这个形状）。
    """
    open_fn = opener or urllib.request.urlopen
    try:
        with open_fn(LATEST_URL, timeout=timeout) as r:
            # 稳定性：响应限流 1 MB —— 更新检查的 JSON 只有几百字节，
            # 服务器返回超大内容时不把它全读进内存。
            data = json.loads(_read_capped(r, 1 << 20).decode("utf-8"))
    except Exception as e:      # noqa: BLE001  断网、超时、HTTP 错误都一样处理
        return None, str(e)[:200]
    tag = data.get("tag_name") if isinstance(data, dict) else None
    if not tag or parse_version(tag) is None:
        return None, "Release 信息里没有可用的版本号"
    return tag, None


def check(current, opener=None, timeout=8):
    """与当前版本比对：返回 (status, tag_or_error)。

    status: "newer"（有新版）/ "same"（已是最新）/ "older"（当前比远端新，
    比如自己编的开发版）/ "error"（查不到，原因在第二个返回值里）。
    """
    cur = parse_version(current)
    tag, err = fetch_latest_tag(opener=opener, timeout=timeout)
    if tag is None:
        return "error", err or "检查更新失败"
    cmp = compare_versions(cur, parse_version(tag))
    if cmp < 0:
        return "newer", tag
    if cmp == 0:
        return "same", tag
    return "older", tag
