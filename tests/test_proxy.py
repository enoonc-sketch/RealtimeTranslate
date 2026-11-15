"""在线翻译引擎代理设置（v2.9.0 新增）。

设计：配置里 proxy_enabled / proxy_host / proxy_port / proxy_user /
proxy_pass 五个键；proxy_url(cfg) 纯函数拼出代理 URL（没配 / 配错
返回 None）；_urlopen 是在线引擎的统一出口——配了代理就走
build_opener(ProxyHandler) 的 opener，没配就和原来一样走 urlopen。
Google（g_translate_full）和微软（_ms_get_token / ms_translate）
三处网络调用都走 _urlopen；update_check / pack_downloader /
netcheck 不在本次范围，不动。

测试用 mock 的 urlopen / build_opener 断言路由，不真联网。
"""
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import desktop_translator as dt

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


# ---- 1. proxy_url 纯函数 ----
ok("proxy disabled -> None",
   dt.proxy_url({"proxy_enabled": False, "proxy_host": "127.0.0.1", "proxy_port": 8080}) is None)
ok("proxy enabled but no host -> None",
   dt.proxy_url({"proxy_enabled": True, "proxy_host": "", "proxy_port": 8080}) is None)
ok("proxy enabled but no port -> None",
   dt.proxy_url({"proxy_enabled": True, "proxy_host": "127.0.0.1", "proxy_port": 0}) is None)
ok("proxy port out of range -> None",
   dt.proxy_url({"proxy_enabled": True, "proxy_host": "127.0.0.1", "proxy_port": 70000}) is None)
ok("proxy port non-int -> None",
   dt.proxy_url({"proxy_enabled": True, "proxy_host": "127.0.0.1", "proxy_port": "abc"}) is None)
ok("proxy host:port",
   dt.proxy_url({"proxy_enabled": True, "proxy_host": "127.0.0.1", "proxy_port": 8080})
   == "http://127.0.0.1:8080")
ok("proxy host/port whitespace trimmed",
   dt.proxy_url({"proxy_enabled": True, "proxy_host": "  proxy.example.com ", "proxy_port": "7890"})
   == "http://proxy.example.com:7890")
ok("proxy with auth",
   dt.proxy_url({"proxy_enabled": True, "proxy_host": "127.0.0.1", "proxy_port": 8080,
                 "proxy_user": "user", "proxy_pass": "p@ss:word"})
   == "http://user:p%40ss%3Aword@127.0.0.1:8080")
ok("proxy user only (no pass)",
   dt.proxy_url({"proxy_enabled": True, "proxy_host": "127.0.0.1", "proxy_port": 8080,
                 "proxy_user": "user", "proxy_pass": ""})
   == "http://user@127.0.0.1:8080")
ok("proxy missing keys -> None",
   dt.proxy_url({}) is None)

# ---- 2. set/get 往返 ----
dt.set_proxy_url("http://127.0.0.1:8080")
ok("set/get proxy url", dt.get_proxy_url() == "http://127.0.0.1:8080")
dt.set_proxy_url(None)
ok("set None clears proxy", dt.get_proxy_url() is None)
dt.set_proxy_url("")
ok("set empty clears proxy", dt.get_proxy_url() is None)


# ---- 3. _urlopen 路由（mock urlopen / build_opener） ----
class FakeResp:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeOpener:
    def __init__(self, handlers):
        self.handlers = handlers

    def open(self, req, timeout=None):
        seen["opener_open"] = (req, timeout)
        return FakeResp(seen["opener_body"])


seen = {}
real_urlopen = urllib.request.urlopen
real_build_opener = urllib.request.build_opener


def fake_urlopen(req, timeout=None):
    seen["urlopen"] = (req, timeout)
    return FakeResp(seen["urlopen_body"])


def fake_build_opener(*handlers):
    seen["build_opener"] = handlers
    return FakeOpener(handlers)


urllib.request.urlopen = fake_urlopen
urllib.request.build_opener = fake_build_opener
try:
    req = urllib.request.Request("https://example.com")
    # 没配代理：走 urlopen，不走 build_opener
    dt.set_proxy_url(None)
    seen.clear()
    seen["urlopen_body"] = b"ok"
    with dt._urlopen(req, timeout=5) as r:
        ok("_urlopen no proxy returns body", r.read() == b"ok")
    ok("no proxy -> urlopen called", "urlopen" in seen)
    ok("no proxy -> build_opener NOT called", "build_opener" not in seen)

    # 配了代理：走 opener.open，不走 urlopen；ProxyHandler 里 http/https 都是该代理
    dt.set_proxy_url("http://127.0.0.1:8080")
    seen.clear()
    seen["opener_body"] = b"via-proxy"
    with dt._urlopen(req, timeout=7) as r:
        ok("_urlopen via proxy returns body", r.read() == b"via-proxy")
    ok("proxy -> urlopen NOT called", "urlopen" not in seen)
    ok("proxy -> build_opener called", "build_opener" in seen)
    handlers = seen.get("build_opener") or []
    ok("proxy -> ProxyHandler carries http+https",
       len(handlers) == 1 and isinstance(handlers[0], urllib.request.ProxyHandler)
       and handlers[0].proxies == {"http": "http://127.0.0.1:8080",
                                   "https": "http://127.0.0.1:8080"})
    ok("proxy -> opener.open got req+timeout",
       seen.get("opener_open") == (req, 7))
finally:
    urllib.request.urlopen = real_urlopen
    urllib.request.build_opener = real_build_opener
    dt.set_proxy_url(None)


# ---- 4. Google 翻译走代理 / 不走代理 ----
google_body = json.dumps([[["你好", "hello", None, None]], None, "en"]).encode("utf-8")
urllib.request.urlopen = fake_urlopen
urllib.request.build_opener = fake_build_opener
try:
    dt.set_proxy_url(None)
    seen.clear()
    seen["urlopen_body"] = google_body
    out, det = dt.g_translate("hello", "en", "zh-CN", attempts=1)
    ok("google no proxy translates", out == "你好" and det == "en")
    ok("google no proxy -> urlopen", "urlopen" in seen and "build_opener" not in seen)

    dt.set_proxy_url("http://127.0.0.1:8080")
    seen.clear()
    seen["opener_body"] = google_body
    out, det = dt.g_translate("hello", "en", "zh-CN", attempts=1)
    ok("google via proxy translates", out == "你好" and det == "en")
    ok("google via proxy -> opener", "build_opener" in seen and "urlopen" not in seen)
finally:
    urllib.request.urlopen = real_urlopen
    urllib.request.build_opener = real_build_opener
    dt.set_proxy_url(None)


# ---- 5. 微软翻译走代理（token 预置，跳过取 token 的网络调用） ----
ms_body = json.dumps([{"translations": [{"text": "你好"}],
                       "detectedLanguage": {"language": "en"}}]).encode("utf-8")
saved_token = dict(dt._ms_token)
urllib.request.urlopen = fake_urlopen
urllib.request.build_opener = fake_build_opener
try:
    dt._ms_token.update(value="TOK", ts=time.time())
    dt.set_proxy_url("http://127.0.0.1:8080")
    seen.clear()
    seen["opener_body"] = ms_body
    out, det = dt.ms_translate("hello", "en", "zh-CN", attempts=1)
    ok("ms via proxy translates", out == "你好" and det == "en")
    ok("ms via proxy -> opener", "build_opener" in seen and "urlopen" not in seen)

    dt.set_proxy_url(None)
    seen.clear()
    seen["urlopen_body"] = ms_body
    out, det = dt.ms_translate("hello", "en", "zh-CN", attempts=1)
    ok("ms no proxy translates", out == "你好" and det == "en")
    ok("ms no proxy -> urlopen", "urlopen" in seen and "build_opener" not in seen)
finally:
    urllib.request.urlopen = real_urlopen
    urllib.request.build_opener = real_build_opener
    dt._ms_token.update(saved_token)
    dt.set_proxy_url(None)

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
