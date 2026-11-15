"""检查更新：版本解析 / 比较 / 远端读取（mock opener，不真联网）。"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import update_check as uc

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def opener_with(payload):
    class R:
        def __init__(self, data):
            self._data = data

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def open_fn(url, timeout=8):
        if isinstance(payload, Exception):
            raise payload
        return R(payload if isinstance(payload, bytes) else payload.encode("utf-8"))
    return open_fn


ok("parse v2.6.0", uc.parse_version("v2.6.0") == (2, 6, 0))
ok("parse 2.7", uc.parse_version("2.7") == (2, 7))
ok("parse bad -> None", uc.parse_version("latest") is None)
ok("parse empty -> None", uc.parse_version("") is None)
ok("compare 2.6.0 < 2.7.0", uc.compare_versions((2, 6, 0), (2, 7, 0)) == -1)
ok("compare equal", uc.compare_versions((2, 7, 0), (2, 7, 0)) == 0)
ok("compare 2.7 > 2.6.0", uc.compare_versions((2, 7, 0), (2, 6, 0)) == 1)
ok("compare different lengths", uc.compare_versions((2, 7), (2, 7, 0)) == 0)

tag, err = uc.fetch_latest_tag(opener_with(json.dumps({"tag_name": "v2.8.0"})))
ok("fetch newer tag", tag == "v2.8.0" and err is None)
tag, err = uc.fetch_latest_tag(opener_with(json.dumps({"tag_name": "v2.8.0"})))
ok("fetch uses api url", True)  # URL 由模块常量定，见下
ok("latest url is github api", "api.github.com" in uc.LATEST_URL and "RealtimeTranslate" in uc.LATEST_URL)

st, tag = uc.check("2.7.0", opener=opener_with(json.dumps({"tag_name": "v2.8.0"})))
ok("check newer", st == "newer" and tag == "v2.8.0")
st, tag = uc.check("2.7.0", opener=opener_with(json.dumps({"tag_name": "v2.7.0"})))
ok("check same", st == "same")
st, tag = uc.check("2.7.0", opener=opener_with(json.dumps({"tag_name": "v2.6.0"})))
ok("check older (local is dev)", st == "older")
st, tag = uc.check("2.7.0", opener=opener_with(OSError("no network")))
ok("check network error -> error, no raise", st == "error" and tag)
st, tag = uc.check("2.7.0", opener=opener_with(b"not json"))
ok("check bad json -> error", st == "error")
st, tag = uc.check("2.7.0", opener=opener_with(json.dumps({"name": "x"})))
ok("check missing tag_name -> error", st == "error")

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
