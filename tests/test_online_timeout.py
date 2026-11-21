"""B-4：在线链路总时限 —— 代理拖沓时单次在线翻译最多等 ONLINE_TOTAL_TIMEOUT
（默认 10 秒），超时直接走离线回退；熔断器照常工作。

跑法：python3 tests/test_online_timeout.py（需 xvfb 吗？不需要，无 Tk）。
打桩 dt._urlopen：慢代理（按 timeout 睡满再报 TimeoutError）/ 快 429。
"""
import os
import sys
import time
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import desktop_translator as dt

res = []


def ok(name, cond, detail=""):
    res.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + (" | " + str(detail) if detail else ""))


real_urlopen = dt._urlopen
saved_auto_offline = dt.AUTO_OFFLINE


def slow_urlopen(req, timeout=None):
    """模拟拖沓代理：按调用方给的 timeout 睡满，再报 socket 超时。"""
    time.sleep(timeout if timeout else 10)
    raise TimeoutError("slow proxy")


def rate_limit_urlopen(req, timeout=None):
    """Google 立即 429；微软取 token 立即 404（接口已下线）。"""
    url = getattr(req, "full_url", "") or ""
    if "translate/auth" in url:
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)


try:
    # ---- 1. Google 单链：拖沓代理下总耗时有上限，不再 3 次 × 12 秒 ----
    dt._urlopen = slow_urlopen
    dt.reset_online_state()
    t0 = time.monotonic()
    try:
        dt.g_translate("hello", "en", "zh-CN")
        raised = None
    except TimeoutError as e:
        raised = e
    except Exception as e:  # noqa: BLE001
        raised = e
    el = time.monotonic() - t0
    ok("google 拖沓代理：总耗时有上限（<12 秒）",
       isinstance(raised, TimeoutError) and el < 12, "耗时 %.1fs，异常 %r" % (el, raised))

    # ---- 2. 整条链路：拖沓代理 → 10 秒内走离线回退，且熔断后第二次很快 ----
    if dt.OFFLINE.available():
        dt._urlopen = slow_urlopen
        dt.AUTO_OFFLINE = True
        dt.reset_online_state()
        fb0 = dt.fallback_count()
        t0 = time.monotonic()
        out = dt.do_translate("Hello world", "en", "zh-CN", "Google")
        el = time.monotonic() - t0
        txt = out[0] if isinstance(out, tuple) else out  # do_translate 返回 (译文, 语言)
        ok("拖沓代理：约 10 秒内走离线回退并出结果",
           isinstance(txt, str) and len(txt) > 0 and el < 15
           and dt.fallback_count() > fb0,
           "耗时 %.1fs，结果 %r" % (el, txt))
        t0 = time.monotonic()
        out2 = dt.do_translate("Hello world", "en", "zh-CN", "Google")
        el2 = time.monotonic() - t0
        txt2 = out2[0] if isinstance(out2, tuple) else out2
        ok("熔断期内第二次直接走离线（<3 秒）",
           isinstance(txt2, str) and len(txt2) > 0 and el2 < 3, "耗时 %.1fs" % el2)
    else:
        print("SKIP 离线回退断言：本机无离线运行时（OFFLINE.available() 为假）")
        res.append(True)

    # ---- 3. 正常 429 快路径：Google 429 → 微软 404 → 离线，仍在预算内 ----
    if dt.OFFLINE.available():
        dt._urlopen = rate_limit_urlopen
        dt.AUTO_OFFLINE = True
        dt.reset_online_state()
        t0 = time.monotonic()
        out = dt.do_translate("Hello world", "en", "zh-CN", "Google")
        el = time.monotonic() - t0
        txt = out[0] if isinstance(out, tuple) else out
        ok("快 429 路径：Google 429 → 微软下线 → 离线，<10 秒出结果",
           isinstance(txt, str) and len(txt) > 0 and el < 10,
           "耗时 %.1fs，结果 %r" % (el, txt))
    else:
        print("SKIP 快 429 断言：本机无离线运行时")
        res.append(True)
finally:
    dt._urlopen = real_urlopen
    dt.AUTO_OFFLINE = saved_auto_offline
    dt.reset_online_state()
    dt.set_proxy_url(None)

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
