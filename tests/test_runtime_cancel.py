"""离线组件下载「取消卡住」的回归测试（2.15.8）。

背景：2.15.6 里点「取消」后界面一直停在「正在取消…」：
  1. install() 先连查 4 个包的 PyPI JSON（每个最多 30 秒），全程不查 cancelled；
  2. urlopen 连接 / 停滞的读一次等满 timeout，取消插不进来；
  3. 窗口在 busy 时关不掉（界面逻辑，见 _rt_cancel_or_close 的两段式关闭）。
本文件只测可离线验证的逻辑层（取消检查与可取消请求）；不联网、不弹窗口。
"""
import os
import socket
import sys
import tempfile
import time
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pack_downloader as pd
import runtime_installer as ri

PASSED = []
FAILED = []


def check(name, cond):
    (PASSED if cond else FAILED).append(name)
    print(("PASS " if cond else "FAIL ") + name)


class FakeResp:
    """最小的 urlopen 响应替身：headers/status/read/上下文管理。"""

    def __init__(self, body=b"", status=200, read_exc=None):
        self._body = body
        self.status = status
        self.headers = {"Content-Length": str(len(body))}
        self._read_exc = read_exc
        self.read_calls = 0

    def read(self, n=-1):
        self.read_calls += 1
        if self._read_exc is not None:
            raise self._read_exc
        if not self._body:
            return b""
        if n is None or n < 0:
            out, self._body = self._body, b""
            return out
        out, self._body = self._body[:n], self._body[n:]
        return out

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# ---------------------------------------------------------------- _open_cancellable
def test_open_cancellable_cancelled_immediately():
    """取消已置位时，不等超时、立即抛 Cancelled。"""
    orig = pd._open
    calls = []

    def fake_open(url, timeout, headers=None):
        calls.append(timeout)
        raise socket.timeout("stalled")

    pd._open = fake_open
    try:
        t0 = time.time()
        try:
            pd._open_cancellable("https://example.invalid/x", timeout=30, cancelled=lambda: True)
            check("open: 取消已置位立即抛 Cancelled", False)
        except pd.Cancelled:
            check("open: 取消已置位立即抛 Cancelled", True)
        check("open: 取消不等满 30 秒（<2 秒）", time.time() - t0 < 2.0)
        check("open: 每次连接最多等 10 秒", calls == [10])
    finally:
        pd._open = orig


def test_open_cancellable_retries_timeout_then_succeeds():
    """超时重试两次后成功（慢网络不断线，只是连接慢）。"""
    orig = pd._open
    calls = []

    def fake_open(url, timeout, headers=None):
        calls.append(1)
        if len(calls) <= 2:
            raise socket.timeout("slow")
        return FakeResp(b"ok")

    pd._open = fake_open
    try:
        r = pd._open_cancellable("https://example.invalid/x", timeout=30, cancelled=lambda: False)
        check("open: 超时重试后成功", r.read() == b"ok")
        check("open: 超时重试了 2 次", len(calls) == 3)
    finally:
        pd._open = orig


def test_open_cancellable_non_timeout_raises_at_once():
    """404 / DNS 失败这类非超时错误立即抛出，不空等到预算用完。"""
    orig = pd._open
    calls = []

    def fake_open(url, timeout, headers=None):
        calls.append(1)
        raise urllib.error.URLError("Name or service not known")

    pd._open = fake_open
    try:
        t0 = time.time()
        try:
            pd._open_cancellable("https://example.invalid/x", timeout=30, cancelled=lambda: False)
            check("open: 非超时错误立即抛出", False)
        except urllib.error.URLError:
            check("open: 非超时错误立即抛出", True)
        check("open: 非超时错误不等预算（<2 秒）", time.time() - t0 < 2.0)
        check("open: 非超时错误只试一次", len(calls) == 1)
    finally:
        pd._open = orig


# ---------------------------------------------------------------- _fetch_into
def test_fetch_into_stalled_read_cancelled():
    """读一直停滞（socket.timeout），取消后 1 秒内抛 Cancelled。"""
    orig = pd._open
    pd._open = lambda url, timeout, headers=None: FakeResp(
        b"0123456789", read_exc=socket.timeout("stalled"))
    try:
        tmp = tempfile.mkdtemp()
        start = time.time()
        cancelled = lambda: time.time() - start > 0.2     # noqa: E731
        t0 = time.time()
        try:
            pd._fetch_into("https://example.invalid/f.bin", os.path.join(tmp, "f.bin"),
                           None, cancelled, timeout=5)
            check("fetch: 停滞读中取消抛 Cancelled", False)
        except pd.Cancelled:
            check("fetch: 停滞读中取消抛 Cancelled", True)
        check("fetch: 停滞读中取消 <2 秒", time.time() - t0 < 2.0)
    finally:
        pd._open = orig


def test_fetch_into_stalled_read_times_out():
    """没人取消、连续无数据超过 timeout 秒，按中断报错（交给上层重试续传）。"""
    orig = pd._open
    pd._open = lambda url, timeout, headers=None: FakeResp(
        b"0123456789", read_exc=socket.timeout("stalled"))
    try:
        tmp = tempfile.mkdtemp()
        t0 = time.time()
        try:
            pd._fetch_into("https://example.invalid/f.bin", os.path.join(tmp, "f.bin"),
                           None, lambda: False, timeout=2)
            check("fetch: 停滞超 2 秒按中断报错", False)
        except ConnectionError as e:
            check("fetch: 停滞超 2 秒按中断报错", "停滞" in str(e))
        dt = time.time() - t0
        check("fetch: 停滞中断约 2 秒（2~5 秒）", 2.0 <= dt < 5.0)
    finally:
        pd._open = orig


def test_fetch_into_range_header_kept():
    """续传时 Range 头必须还在（2.15.8 改 _open 签名时别丢了它）。"""
    orig = pd._open
    seen = {}

    class Resp206(FakeResp):
        def __init__(self):
            super().__init__(b"world", status=206)

    def fake_open(url, timeout, headers=None):
        seen["headers"] = dict(headers or {})
        return Resp206()

    pd._open = fake_open
    try:
        tmp = tempfile.mkdtemp()
        dest = os.path.join(tmp, "f.bin")
        with open(dest, "wb") as f:
            f.write(b"hello")      # 已有 5 字节，续传应从 5 开始
        pd._fetch_into("https://example.invalid/f.bin", dest, None, lambda: False, timeout=5)
        check("fetch: 续传带 Range: bytes=5-", seen["headers"].get("Range") == "bytes=5-")
        with open(dest, "rb") as f:
            check("fetch: 续传后文件完整", f.read() == b"helloworld")
    finally:
        pd._open = orig


# ---------------------------------------------------------------- install / download_pack
def _fake_wheel(pkg):
    return {"version": "1.0", "filename": "%s-1.0-py3-none-any.whl" % pkg,
            "url": "https://example.invalid/%s.whl" % pkg, "size": 10, "sha256": ""}


def test_install_cancelled_before_query():
    """取消已置位时，install 在查任何 PyPI 之前就停下。"""
    orig = ri.find_wheel
    calls = []
    ri.find_wheel = lambda *a, **k: calls.append(a[0]) or _fake_wheel(a[0])
    try:
        tmp = tempfile.mkdtemp()
        try:
            ri.install(tmp, cancelled=lambda: True)
            check("install: 取消后查 PyPI 前停下", False)
        except pd.Cancelled:
            check("install: 取消后查 PyPI 前停下", True)
        check("install: 取消后一次 PyPI 也没查", calls == [])
    finally:
        ri.find_wheel = orig


def test_install_reports_query_status():
    """查询阶段也向界面报进度（以前只报下载，查 PyPI 时界面一直是「正在连接…」）。"""
    orig_find = ri.find_wheel
    orig_dl = pd.download
    seen = []
    ri.find_wheel = lambda *a, **k: _fake_wheel(a[0])

    def _dl(*a, **k):
        raise pd.Cancelled()

    pd.download = _dl
    try:
        tmp = tempfile.mkdtemp()
        try:
            ri.install(tmp, cancelled=lambda: False, status=lambda s: seen.append(s))
            check("install: 查询进度上报", False)
        except pd.Cancelled:
            check("install: 查询进度上报", True)
        check("install: 4 个包都报了查询进度",
              seen == ["正在查询 PyPI：%s…" % p for p in ri.PKGS])
    finally:
        ri.find_wheel = orig_find
        pd.download = orig_dl


def test_download_pack_cancelled_between_candidates():
    """语言包下载：取消已置位时，换候选地址前就停下，不再发起任何下载。"""
    orig = pd.download
    calls = []
    pd.download = lambda *a, **k: calls.append(a[0])
    try:
        tmp = tempfile.mkdtemp()
        entry = {"links": ["https://argos-net.com/v1/en-zh.argosmodel",
                           "https://argos-net.com/v1/zh-en.argosmodel"]}
        try:
            pd.download_pack(entry, tmp, tmp, cancelled=lambda: True)
            check("pack: 取消后换候选前停下", False)
        except pd.Cancelled:
            check("pack: 取消后换候选前停下", True)
        check("pack: 取消后一次下载也没发起", calls == [])
    finally:
        pd.download = orig


def test_download_pack_next_candidate_on_failure():
    """正常流程不受影响：第一个候选失败就换下一个，成功返回。"""
    orig_dl = pd.download
    orig_install = pd.oe.install_package
    calls = []

    def _dl(url, dest, *a, **k):
        calls.append(url)
        if len(calls) == 1:
            raise ConnectionError("down")

    pd.download = _dl
    pd.oe.install_package = lambda dest, d: "PKG"
    try:
        tmp = tempfile.mkdtemp()
        entry = {"links": ["https://argos-net.com/v1/en-zh.argosmodel"]}
        check("pack: 首候选失败换下一个成功",
              pd.download_pack(entry, tmp, tmp, cancelled=lambda: False) == "PKG")
        check("pack: 一共试了 2 个候选", len(calls) == 2)
    finally:
        pd.download = orig_dl
        pd.oe.install_package = orig_install


if __name__ == "__main__":
    test_open_cancellable_cancelled_immediately()
    test_open_cancellable_retries_timeout_then_succeeds()
    test_open_cancellable_non_timeout_raises_at_once()
    test_fetch_into_stalled_read_cancelled()
    test_fetch_into_stalled_read_times_out()
    test_fetch_into_range_header_kept()
    test_install_cancelled_before_query()
    test_install_reports_query_status()
    test_download_pack_cancelled_between_candidates()
    test_download_pack_next_candidate_on_failure()
    print("\n%d/%d passed" % (len(PASSED), len(PASSED) + len(FAILED)))
    if FAILED:
        print("FAILED:", FAILED)
        sys.exit(1)
