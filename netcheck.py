"""
网络检查：逐项检测「能不能联网、DNS、代理、Google / 微软翻译端点」，
给出原因说明和推荐引擎。不依赖 tkinter，可单独测试。
"""
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request

# 用 IP 直连测试「有没有外网」，避免 DNS 故障时误判为断网。国内外各选一个，任一通即可。
PROBE_IPS = [("223.5.5.5", 443), ("1.1.1.1", 443)]
DNS_HOSTS = ["translate.googleapis.com", "edge.microsoft.com"]


class Check:
    def __init__(self, key, name, ok=None, ms=None, detail="", hint=""):
        self.key, self.name, self.ok, self.ms, self.detail, self.hint = key, name, ok, ms, detail, hint

    def line(self):
        mark = {True: "✔", False: "✘", None: "•"}[self.ok]
        t = " — %d ms" % self.ms if (self.ms is not None and self.ok) else ""
        d = "  %s" % self.detail if self.detail else ""
        return "%s %s%s%s" % (mark, self.name, t, d)


class Recommendation:
    def __init__(self, engine, message, level):
        self.engine = engine      # "Google" / "微软" / "离线" / None
        self.message = message
        self.level = level        # "ok" / "warn" / "bad"


# ---------------------------------------------------------------- 错误解释
def explain_error(exc):
    """把各种网络异常翻译成人话，返回 (简短原因, 建议)。"""
    if isinstance(exc, urllib.error.HTTPError):
        c = exc.code
        if c == 429:
            return "被限流（HTTP 429）", "请求过于频繁：稍等几分钟，或改用另一个引擎"
        if c == 407:
            return "代理需要认证（HTTP 407）", "检查系统代理的账号密码，或在公司网络下联系 IT"
        if c in (401, 403):
            return "被拒绝（HTTP %d）" % c, "当前 IP 可能被该服务限制，换网络或换引擎"
        if c >= 500:
            return "服务端错误（HTTP %d）" % c, "对方服务暂时异常，稍后重试或换引擎"
        return "HTTP %d" % c, "服务返回了异常状态"
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, socket.gaierror):
        return "域名解析失败（DNS）", "检查网络是否连接、DNS 设置，或尝试把 DNS 改为 223.5.5.5 / 1.1.1.1"
    if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(reason):
        return "证书校验失败", "检查系统日期时间是否正确；公司网络/杀毒软件的 HTTPS 扫描也会导致此问题"
    if isinstance(reason, ssl.SSLError):
        return "TLS 握手失败", "可能被代理或防火墙干扰，尝试关闭代理/VPN 后重试"
    if isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in str(reason).lower():
        return "连接超时", "网络很慢或被防火墙丢包；如在国内，Google 通常需要代理，可改用「微软」或「离线」"
    if isinstance(reason, ConnectionRefusedError):
        return "连接被拒绝", "目标端口被拦截，或系统代理设置了但代理软件没在运行"
    if isinstance(reason, (ConnectionResetError, ConnectionAbortedError)):
        return "连接被重置", "被防火墙/代理中断，尝试换网络或换引擎"
    if isinstance(reason, OSError):
        return "网络不可达", "检查网线/Wi-Fi 是否已连接，以及是否开启了飞行模式"
    return str(reason)[:100] or type(exc).__name__, "请检查网络后重试"


def is_connectivity_error(exc):
    """纯连通性故障（没网/DNS/超时/被重置），区别于对方服务的 HTTP 错误。"""
    if isinstance(exc, urllib.error.HTTPError):
        return False
    return isinstance(exc, (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError))


# ---------------------------------------------------------------- 探针
def _run_with_timeout(fn, timeout):
    """在后台线程执行 fn，超时则放弃等待（线程是 daemon，不会阻止退出）。返回 (结果, 异常)。"""
    box = {}

    def target():
        try:
            box["r"] = fn()
        except Exception as e:      # noqa: BLE001
            box["e"] = e

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return None, TimeoutError("timed out")
    return box.get("r"), box.get("e")


def _tcp_probe(host, port, timeout=4):
    """TCP 直连一次，返回耗时 ms；失败抛 OSError。"""
    t0 = time.time()
    with socket.create_connection((host, port), timeout=timeout):
        return (time.time() - t0) * 1000


def check_connectivity():
    # v2.15.3：几个探针并行跑（旧版串行，全不通时要等 4 秒 × N）
    best, errs, lock = None, [], threading.Lock()

    def one(ip, port):
        nonlocal best
        try:
            ms = _tcp_probe(ip, port)
            with lock:
                best = ms if best is None else min(best, ms)
        except OSError as e:
            with lock:
                errs.append(e)

    ts = [threading.Thread(target=one, args=pp, daemon=True) for pp in PROBE_IPS]
    for t in ts:
        t.start()
    for t in ts:
        t.join(5)
    if best is not None:
        return Check("net", "基础联网（外网 TCP 直连）", True, best)
    why, hint = explain_error(errs[-1]) if errs else ("无法连接", "")
    return Check("net", "基础联网（外网 TCP 直连）", False, None, why,
                 "本机似乎没有联网：检查 Wi-Fi/网线、飞行模式、防火墙。" + hint)


def check_dns():
    bad, slow, parts = [], [], []
    for h in DNS_HOSTS:
        t0 = time.time()
        r, e = _run_with_timeout(lambda h=h: socket.getaddrinfo(h, 443), 6)
        ms = (time.time() - t0) * 1000
        if e is not None or not r:
            bad.append(h)
        else:
            parts.append("%s %d ms" % (h, ms))
    if bad:
        return Check("dns", "DNS 解析", False, None, "无法解析：" + "、".join(bad),
                     "DNS 异常：尝试把网卡 DNS 改为 223.5.5.5 / 1.1.1.1，或检查代理/VPN")
    return Check("dns", "DNS 解析", True, None, "；".join(parts))


def mask_proxy(url):
    """隐藏代理地址里的账号密码。"""
    if "@" in url:
        scheme, _, rest = url.partition("://")
        return "%s://***@%s" % (scheme, rest.rsplit("@", 1)[1]) if rest else url
    return url


def check_proxy():
    try:
        proxies = urllib.request.getproxies()
    except Exception:
        proxies = {}
    shown = {k: mask_proxy(v) for k, v in proxies.items() if k in ("http", "https", "all") and v}
    if not shown:
        return Check("proxy", "系统代理", None, None, "未检测到（直连）")
    txt = "；".join("%s=%s" % kv for kv in shown.items())
    return Check("proxy", "系统代理", None, None, "已检测到 " + txt,
                 "程序会自动使用系统代理；若翻译失败，请确认代理软件正在运行")


def parse_proxy_hostport(url):
    """'http://user:pw@127.0.0.1:7890' -> ('127.0.0.1', 7890)；解析不了返回 None（纯函数）。"""
    try:
        import urllib.parse as up
        u = up.urlsplit(url if "://" in url else "http://" + url)
        if not u.hostname:
            return None
        return u.hostname, int(u.port or (443 if u.scheme == "https" else 80))
    except Exception:      # noqa: BLE001
        return None


def check_proxy_alive(url):
    """v2.15.3：代理端口到底有没有在监听。国内最常见的故障是「系统 / 程序里配了代理，
    但代理软件没开」——旧版只会报 Google 超时 / 连接被拒，用户看不出原因。"""
    hp = parse_proxy_hostport(url or "")
    if not hp:
        return None
    try:
        ms = _tcp_probe(hp[0], hp[1], timeout=3)
        return Check("proxy_alive", "代理端口", True, ms, "%s:%d 正在监听" % hp)
    except OSError as e:
        why, _ = explain_error(e)
        return Check("proxy_alive", "代理端口", False, None, "%s:%d %s" % (hp[0], hp[1], why),
                     "代理软件可能没开或端口填错：打开代理软件，或在设置里关掉代理 / 改成正确端口")


def effective_proxy(app_proxy=None):
    """程序内自定义代理优先，否则系统代理；都没有返回 None。"""
    if app_proxy:
        return app_proxy
    try:
        pr = urllib.request.getproxies()
        return pr.get("https") or pr.get("http") or None
    except Exception:      # noqa: BLE001
        return None


def check_endpoint_tcp(key, name, host, port=443):
    """端点 TCP 可达性：DNS 通但 443 不通 = 被防火墙 / 运营商拦截，和「服务坏了」区分开。"""
    try:
        ms = _tcp_probe(host, port, timeout=4)
        return Check(key, name, True, ms)
    except OSError as e:
        why, hint = explain_error(e)
        return Check(key, name, False, None, why, hint)


def check_engine(key, name, fn, timeout=15, http404_reason=None):
    """fn() 应发起一次最小翻译（单次尝试），成功返回非空译文。

    http404_reason：该引擎的 404 有已知的明确原因时传进来（如微软免费接口已下线），
    404 就按这个说，不再含糊成“服务返回了异常状态”或“可能被拦截”。"""
    t0 = time.time()
    r, e = _run_with_timeout(fn, timeout)
    ms = (time.time() - t0) * 1000
    if e is None and r:
        return Check(key, name, True, ms)
    if e is None:
        return Check(key, name, False, None, "返回为空", "服务可连通但没有返回译文")
    if http404_reason and isinstance(e, urllib.error.HTTPError) and e.code == 404:
        why, hint = http404_reason
        return Check(key, name, False, None, why, hint)
    why, hint = explain_error(e)
    return Check(key, name, False, None, why, hint)


def check_offline(info):
    """info: {"runtime": bool, "pairs": str, "count": int}"""
    if not info.get("runtime"):
        return Check("offline", "离线引擎", None, None, "未包含（标准版）", "需要离线翻译请使用「离线版」安装包")
    if not info.get("count"):
        return Check("offline", "离线引擎", False, None, "已启用但没有语言包",
                     "点主界面「离线语言包…」导入 .argosmodel")
    return Check("offline", "离线引擎", True, None, "可用：" + info["pairs"])


# ---------------------------------------------------------------- 汇总
def recommend(checks, current=None):
    by = {c.key: c for c in checks}
    ok = lambda k: bool(by.get(k) and by[k].ok)   # noqa: E731
    g, m, o = ok("google"), ok("ms"), ok("offline")
    extra = [(k, n_) for k, n_ in (("lingva", "Lingva"), ("mymemory", "MyMemory")) if ok(k)]

    def faster():
        return "Google" if (by["google"].ms or 1e9) <= (by["ms"].ms or 1e9) else "微软"

    if g and m:
        eng = faster()
        return Recommendation(eng, "网络正常，Google 与微软都可用（当前最快：%s）。" % eng, "ok")
    if g:
        return Recommendation("Google", "Google 可用，微软不可用；建议使用 Google。", "ok")
    if m:
        return Recommendation("微软", "Google 不可用但微软可用；建议使用「微软」引擎。", "warn")
    if extra:
        return Recommendation(extra[0][1], "Google 和微软都不可用，但内置的「%s」可用；建议切换到它，或选「自动」。"
                              % extra[0][1], "warn")
    if o:
        return Recommendation("离线", "在线引擎都不可用，但离线引擎可用；建议使用「离线」，或开启「断网时自动改用离线」。", "warn")
    pa = by.get("proxy_alive")
    if pa is not None and pa.ok is False:
        return Recommendation(None, "配置了代理但代理端口连不上（%s）：请先打开代理软件，或关闭代理后重试。" % pa.detail, "bad")
    if not ok("net"):
        return Recommendation(None, "本机无法联网，且没有可用的离线引擎。请先恢复网络连接。", "bad")
    return Recommendation(None, "能上外网，但 Google 被限流（HTTP 429，代理出口 IP 被 Google 限流，只能等一等或换网络）、"
                          "微软免费接口已下线（HTTP 404，暂时不可用），也没有离线引擎。"
                          "建议装离线版用离线翻译，在线失败时会自动回退到离线。", "bad")


def run_all(google_fn, ms_fn, offline_info, on_item=None, cancelled=None, proxy_url=None,
            total_timeout=30, extra_engines=None):
    """extra_engines：[(key, 名称, fn), ...] 额外的内置引擎（v2.15.4：Lingva / MyMemory）。"""
    """并行执行全部检测。on_item(Check) 每完成一项回调一次（可能在后台线程）。返回 (checks, Recommendation)。"""
    jobs = [
        ("net", check_connectivity),
        ("dns", check_dns),
        ("proxy", check_proxy),
        ("google", lambda: check_engine("google", "Google 翻译", google_fn)),
        ("ms", lambda: check_engine("ms", "微软翻译", ms_fn, http404_reason=(
            "微软免费接口已下线（HTTP 404）",
            "微软免费取 token 的接口已下线，不是代理拦截；微软引擎暂时不可用，请改用 Google 或离线"))),
        ("offline", lambda: check_offline(offline_info)),
    ]
    for ek, ename, efn in (extra_engines or []):
        jobs.insert(-1, (ek, lambda ek=ek, ename=ename, efn=efn: check_engine(ek, ename, efn)))
    if proxy_url:
        jobs.insert(3, ("proxy_alive", lambda: check_proxy_alive(proxy_url)))
    results, lock = {}, threading.Lock()

    def work(key, fn):
        if cancelled and cancelled():
            return
        try:
            c = fn()
        except Exception as e:      # noqa: BLE001  一项检测出错不能拖垮整份报告
            c = Check(key, key, False, None, "检测出错：%s" % str(e)[:80])
        if c is None:
            return
        with lock:
            results[key] = c
        if on_item:
            on_item(c)

    threads = [threading.Thread(target=work, args=j, daemon=True) for j in jobs]
    for t in threads:
        t.start()
    end = time.monotonic() + total_timeout     # v2.15.3：整体最多等 total_timeout 秒（旧版每项 40 秒串着等）
    for t in threads:
        t.join(max(0.0, end - time.monotonic()))
    checks = [results[k] for k, _ in jobs if k in results]
    return checks, recommend(checks)


def format_report(checks, reco, header=""):
    lines = [header] if header else []
    for c in checks:
        lines.append(c.line())
        if c.ok is False and c.hint:
            lines.append("    ↳ " + c.hint)
        elif c.key == "proxy" and c.hint:
            lines.append("    ↳ " + c.hint)
    lines.append("")
    lines.append("结论：" + reco.message)
    return "\n".join(lines)
