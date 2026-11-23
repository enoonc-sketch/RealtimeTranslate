"""离线组件下载「太慢 / 镜像不好使」的回归测试（2.15.7）。

背景：2.15.6 的下载走 PyPI 官方，国内常年很慢；对话框虽有「镜像」栏，
但直接换 pypi.org 并不管用 —— 2026-11-23 沙箱实测：
  * 阿里云、中科大的 JSON API 是 404；
  * 清华的 JSON 数据滞后（numpy 只有 2.0.1）；
  * 但三家镜像的轮子文件本身都在（simple 索引 + packages 路径均 200）。
修法：
  1. find_wheel 查不到 / 版本对不上钉死版本时，改走 simple 索引（/simple/<包>/）
     再找一次 —— 各家镜像都有 simple 索引，且数据比 JSON 新；
  2. 对话框加镜像预设下拉框（默认 / 清华 / 中科大），只换轮子下载地址。
钉死校验（H-05）不受影响：版本、文件名、哈希仍以钉死表为准。
不联网：_open 用本地替身。
"""
import json
import os
import sys
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pack_downloader as pd
import runtime_installer as ri

PASSED = []
FAILED = []


def check(name, cond):
    (PASSED if cond else FAILED).append(name)
    print(("PASS " if cond else "FAIL ") + name)


PINNED_NUMPY = "numpy-2.5.5-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
PINNED_SHA = "704d819265e5d1064d932968e9ee85fff2103ccc78c05b878c06943ba27b8507"


class FakeResp:
    def __init__(self, body):
        self._body = body
        self.status = 200
        self.headers = {"Content-Length": str(len(body))}

    def read(self, n=-1):
        if n is None or n < 0:
            out, self._body = self._body, b""
            return out
        out, self._body = self._body[:n], self._body[n:]
        return out

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _json_bytes(versions):
    rel = {}
    for v, fn in versions:
        rel[v] = [{"packagetype": "bdist_wheel", "filename": fn,
                   "url": "https://files.pythonhosted.org/packages/xx/" + fn, "size": 10,
                   "digests": {"sha256": "deadbeef"}}]
    return json.dumps({"releases": rel}).encode("utf-8")


def _simple_html(links):
    """links: [(href, 文本, 是否被撤回)]。"""
    out = ["<html><body>"]
    for href, text, yanked in links:
        out.append('<a href="%s"%s>%s</a><br/>' % (
            href, ' data-yanked="reason"' if yanked else "", text))
    out.append("</body></html>")
    return "".join(out).encode("utf-8")


def _run_find_wheel(json_resp, simple_resp):
    """json_resp / simple_resp：FakeResp 或要抛的异常；返回 (结果或异常, _open 调用次数)。"""
    orig = pd._open
    calls = []

    def fake_open(url, timeout, headers=None):
        calls.append(url)
        if "/simple/" in url:
            if isinstance(simple_resp, Exception):
                raise simple_resp
            return simple_resp
        if isinstance(json_resp, Exception):
            raise json_resp
        return json_resp

    pd._open = fake_open
    try:
        try:
            return ri.find_wheel("numpy", "cp312"), calls
        except Exception as e:      # noqa: BLE001
            return e, calls
    finally:
        pd._open = orig


def test_simple_fallback_on_json_failure():
    """JSON 查询失败时走 simple 索引，拿到钉死的轮子。"""
    simple = _simple_html([
        ("../../packages/d1/71/x/" + PINNED_NUMPY, PINNED_NUMPY, False)])
    w, calls = _run_find_wheel(urllib.error.URLError("boom"), FakeResp(simple))
    check("simple 兜底：JSON 失败后拿到钉死版本",
          isinstance(w, dict) and w["version"] == "2.5.5")
    check("simple 兜底：哈希以钉死表为准",
          isinstance(w, dict) and w["sha256"] == PINNED_SHA)
    check("simple 兜底：相对链接拼成镜像绝对地址",
          isinstance(w, dict) and w["url"].startswith("https://pypi.org/packages/"))
    check("simple 兜底：JSON、simple 各查一次", len(calls) == 2)


def test_simple_fallback_on_stale_json():
    """JSON 数据滞后（只有 2.0.1）时，simple 索引里有钉死的 2.5.5 就用它。"""
    stale = FakeResp(_json_bytes([("2.0.1", "numpy-2.0.1-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl")]))
    simple = _simple_html([
        ("https://pypi.mirrors.ustc.edu.cn/packages/d1/71/x/" + PINNED_NUMPY, PINNED_NUMPY, False)])
    w, _calls = _run_find_wheel(stale, FakeResp(simple))
    check("simple 兜底：JSON 滞后时用 simple 的钉死版本",
          isinstance(w, dict) and w["version"] == "2.5.5")
    check("simple 兜底：simple 的轮子地址原样采用（镜像域名）",
          isinstance(w, dict) and w["url"].startswith("https://pypi.mirrors.ustc.edu.cn/packages/"))


def test_json_good_no_simple_fetch():
    """JSON 正常且版本对得上时，不多查 simple。"""
    good = FakeResp(_json_bytes([("2.5.5", PINNED_NUMPY)]))
    w, calls = _run_find_wheel(good, FakeResp(b""))
    check("JSON 正常：直接拿到钉死版本",
          isinstance(w, dict) and w["version"] == "2.5.5" and w["sha256"] == PINNED_SHA)
    check("JSON 正常：只查一次，不碰 simple", len(calls) == 1)


def test_simple_finds_pinned_when_json_newer():
    """JSON 给了比钉死更新的版本时，去 simple 索引找钉死的旧版轮子（2026-11-23 真实报错：
    ctranslate2 在 PyPI 已是 4.9.1，程序只信任钉死的 4.9.0 —— JSON API 只返回最新版
    的文件，旧版轮子只能在 simple 索引里按版本找）。"""
    newer = FakeResp(_json_bytes([("2.6.0", "numpy-2.6.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl")]))
    simple = _simple_html([
        ("../../packages/aa/bb/numpy-2.6.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl",
         "numpy-2.6.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", False),
        ("../../packages/d1/71/x/" + PINNED_NUMPY, PINNED_NUMPY, False)])
    w, _calls = _run_find_wheel(newer, FakeResp(simple))
    check("simple 兜底：JSON 更新时用 simple 里的钉死旧版",
          isinstance(w, dict) and w["version"] == "2.5.5")
    check("simple 兜底：旧版轮子哈希以钉死表为准",
          isinstance(w, dict) and w["sha256"] == PINNED_SHA)


def test_simple_no_pinned_when_json_newer_still_refused():
    """JSON 更新、simple 里又没有钉死的旧版时，照样拒绝（不偷换成新版）。"""
    newer = FakeResp(_json_bytes([("2.6.0", "numpy-2.6.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl")]))
    simple = _simple_html([
        ("../../packages/aa/bb/numpy-2.6.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl",
         "numpy-2.6.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", False)])
    w, _calls = _run_find_wheel(newer, FakeResp(simple))
    check("simple 兜底：JSON 更新且无旧版时照样拒绝",
          isinstance(w, Exception) and "只信任钉死的" in str(w))


def test_simple_newer_than_pinned_still_refused():
    """simple 里最高版本比钉死的新，照样拒绝（钉死校验没绕过去）。"""
    simple = _simple_html([
        ("../../packages/aa/bb/numpy-2.6.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl",
         "numpy-2.6.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl", False)])
    w, _calls = _run_find_wheel(urllib.error.URLError("boom"), FakeResp(simple))
    check("simple 兜底：比钉死新的版本照样拒绝",
          isinstance(w, Exception) and "只信任钉死的" in str(w))


def test_simple_yanked_skipped():
    """simple 里被撤回（data-yanked）的轮子不算；simple 也没拿到时报 JSON 查不到。"""
    simple = _simple_html([
        ("../../packages/d1/71/x/" + PINNED_NUMPY, PINNED_NUMPY, True)])
    w, _calls = _run_find_wheel(urllib.error.URLError("boom"), FakeResp(simple))
    check("simple 兜底：被撤回的轮子不算",
          isinstance(w, Exception) and "无法从 PyPI 查询" in str(w))


def test_both_fail_reports_json_error():
    """JSON 和 simple 都失败时，报错仍说 JSON 查不到（主因）。"""
    w, _calls = _run_find_wheel(urllib.error.URLError("dns fail"),
                                urllib.error.URLError("also fail"))
    check("JSON、simple 都失败：报无法查询",
          isinstance(w, Exception) and "无法从 PyPI 查询 numpy" in str(w))


def test_mirror_presets():
    """预设只换轮子下载地址，不动查询地址；默认预设不动任何地址。"""
    wheel = "https://files.pythonhosted.org/packages/d1/71/x/" + PINNED_NUMPY
    labels = [label for label, _ in ri.MIRROR_PRESETS]
    check("镜像预设：三档，默认在第一位，选项里带网址",
          labels == ["默认（PyPI 官方）", "清华镜像（pypi.tuna.tsinghua.edu.cn）",
                     "中科大镜像（pypi.mirrors.ustc.edu.cn）"])
    by_label = dict(ri.MIRROR_PRESETS)
    check("镜像预设：默认不动地址",
          pd.apply_replace(wheel, by_label["默认（PyPI 官方）"]) == wheel)
    check("镜像预设：中科大换到 pypi.mirrors.ustc.edu.cn",
          pd.apply_replace(wheel, by_label["中科大镜像（pypi.mirrors.ustc.edu.cn）"])
          == "https://pypi.mirrors.ustc.edu.cn/packages/d1/71/x/" + PINNED_NUMPY)
    check("镜像预设：清华换到 pypi.tuna.tsinghua.edu.cn",
          pd.apply_replace(wheel, by_label["清华镜像（pypi.tuna.tsinghua.edu.cn）"])
          == "https://pypi.tuna.tsinghua.edu.cn/packages/d1/71/x/" + PINNED_NUMPY)
    check("镜像预设：查询地址不受轮子预设影响",
          pd.apply_replace("https://pypi.org/pypi/numpy/json", by_label["清华镜像（pypi.tuna.tsinghua.edu.cn）"])
          == "https://pypi.org/pypi/numpy/json")


if __name__ == "__main__":
    test_simple_fallback_on_json_failure()
    test_simple_fallback_on_stale_json()
    test_simple_finds_pinned_when_json_newer()
    test_simple_no_pinned_when_json_newer_still_refused()
    test_json_good_no_simple_fetch()
    test_simple_newer_than_pinned_still_refused()
    test_simple_yanked_skipped()
    test_both_fail_reports_json_error()
    test_mirror_presets()
    print("\n%d/%d passed" % (len(PASSED), len(PASSED) + len(FAILED)))
    if FAILED:
        print("FAILED:", FAILED)
        sys.exit(1)
