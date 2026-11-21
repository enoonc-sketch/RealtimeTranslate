"""v2.15.4 需要 Key 的引擎：签名算法、错误码、模拟响应、密钥不导出。无需外网。"""
import os, sys, json, urllib.error, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import desktop_translator as dt, settings_io
# 百度官方文档示例
assert dt.baidu_sign("2015063000000001", "apple", "1435660288", "12345678") == "f89f9594663708c1605f3d736d01d2d4"
assert dt.youdao_input("a" * 10 + "b" * 5 + "c" * 10) == "a" * 10 + "25" + "c" * 10
assert dt.deepl_lang("zh-CN", True) == "ZH-HANS" and dt.deepl_lang("auto") is None
dt.set_engine_keys({})
try:
    dt.deepl_translate("hi", "en", "zh-CN"); raise AssertionError
except dt.EngineKeyError:
    pass
class R:
    def __init__(s, b): s.b = b
    def __enter__(s): return s
    def __exit__(s, *a): pass
resp = {}
def fake(req, timeout=None):
    for k, v in resp.items():
        if k in req.full_url:
            return R(json.dumps(v).encode())
    raise OSError("no route")
dt._urlopen = fake; dt._read_capped = lambda r, n: r.b
dt.set_engine_keys({"deepl_key": "abc:fx", "baidu_appid": "1", "baidu_key": "k", "youdao_appid": "y", "youdao_key": "s"})
resp["api-free.deepl.com"] = {"translations": [{"text": "你好", "detected_source_language": "EN"}]}
assert dt.deepl_translate("hello", "auto", "zh-CN") == ("你好", "en")
resp.clear(); resp["fanyi-api"] = {"from": "en", "trans_result": [{"dst": "甲"}, {"dst": "乙"}]}
assert dt.baidu_translate("a\nb", "auto", "zh-CN") == ("甲\n乙", "en")
resp.clear(); resp["fanyi-api"] = {"error_code": "54001"}
try:
    dt.baidu_translate("a", "en", "zh-CN"); raise AssertionError
except dt.EngineKeyError as e:
    assert "密钥" in str(e)
resp.clear(); resp["openapi.youdao"] = {"errorCode": "0", "translation": ["你好"], "l": "en2zh-CHS"}
assert dt.youdao_translate("hello", "auto", "zh-CN") == ("你好", "en")
assert dt.auto_order(None, ["DeepL"])[-1] == "DeepL"
cfg = dict(dt.DEFAULTS, deepl_key="SECRET", baidu_key="SECRET", youdao_key="SECRET", baidu_appid="1")
blob = settings_io.export_settings(cfg)
assert "SECRET" not in blob and '"baidu_appid"' not in blob, "Key 绝不能出现在导出的设置里"
evil = json.dumps({"app": "RealtimeTranslate", "version": 1, "config": {"deepl_key": "EVIL"}})
got, ignored, err = settings_io.import_settings(evil, dt.DEFAULTS)
assert got.get("deepl_key") != "EVIL", "导入不能改走本机 Key"
print("PASS test_key_engines_v2154")
