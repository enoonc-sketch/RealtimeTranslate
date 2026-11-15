"""设置导出 / 导入：export_settings / import_settings（纯函数）。"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import settings_io as sio
from desktop_translator import DEFAULTS

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def sample_config():
    cfg = dict(DEFAULTS)
    cfg.update({
        "sl": "en", "tl": "ja", "top": False, "smart": False,
        "geometry": "800x600", "engine": "Argos",
        "hover_ms": 1200, "font_size": 14, "tts_rate": -3,
        "history_max": 500, "mini_w": 400, "mini_h": 150,
        "dark_mode": True, "hotkey_main": "ctrl+alt+q",
        "pack_mirror": "https://example.com", "update_last_check": "2026-11-14",
        "glossary": [["Maxum II", "Maxum II"], ["cat", "猫"]],
    })
    return cfg


# ---- 导出格式 ----
sample = sample_config()
text = sio.export_settings(sample)
data = json.loads(text)
ok("export is valid JSON with app/version", data.get("app") == "RealtimeTranslate"
   and data.get("version") == 1)
ok("export does not duplicate glossary inside config",
   "glossary" not in data["config"])
ok("export glossary is a list of {src, dst} dicts",
   data["glossary"] == [{"src": "Maxum II", "dst": "Maxum II"},
                        {"src": "cat", "dst": "猫"}])
ok("export keeps non-ASCII (ensure_ascii=False)", "猫" in text)

# ---- 往返 ----
cfg2, ignored, err = sio.import_settings(text, DEFAULTS)
ok("round-trip has no error", err is None)
ok("round-trip ignored nothing", ignored == 0)
ok("round-trip reproduces the config", cfg2 == sample)

# ---- 导出容错：坏输入也不抛错 ----
ok("export None gives minimal valid JSON",
   json.loads(sio.export_settings(None)) == {"app": "RealtimeTranslate",
                                             "version": 1, "config": {}, "glossary": []})
ok("export drops unknown keys and wrong-typed values",
   json.loads(sio.export_settings({"font_size": "big", "nope": 1,
                                   "top": True}))["config"] == {"top": True})

# ---- 导入： malformed JSON / 顶层不是 dict ----
cfg, ignored, err = sio.import_settings("{not json", DEFAULTS)
ok("malformed JSON -> error, empty cfg", err is not None and cfg == {} and ignored == 0)
cfg, ignored, err = sio.import_settings("[1, 2, 3]", DEFAULTS)
ok("top-level list -> error, empty cfg", err is not None and cfg == {} and ignored == 0)
cfg, ignored, err = sio.import_settings("42", DEFAULTS)
ok("top-level number -> error, empty cfg", err is not None and cfg == {})

# ---- 导入：未知键忽略并计数 ----
cfg, ignored, err = sio.import_settings(json.dumps(
    {"app": "RealtimeTranslate", "version": 1,
     "config": {"sl": "en", "mystery_key": 1, "another": "x"}, "glossary": []}),
    DEFAULTS)
ok("unknown keys ignored and counted",
   err is None and ignored == 2 and cfg["sl"] == "en"
   and "mystery_key" not in cfg and "another" not in cfg)

# ---- 导入：类型错误忽略并计数 ----
cfg, ignored, err = sio.import_settings(json.dumps(
    {"app": "RealtimeTranslate", "version": 1,
     "config": {"font_size": "big", "top": "yes", "tl": "ja"}, "glossary": []}),
    DEFAULTS)
ok("wrong-typed values ignored and counted",
   err is None and ignored == 2 and cfg["tl"] == "ja"
   and cfg["font_size"] == DEFAULTS["font_size"] and cfg["top"] == DEFAULTS["top"])

# ---- bool 不能当 int ----
cfg, ignored, err = sio.import_settings(json.dumps(
    {"app": "RealtimeTranslate", "version": 1,
     "config": {"history_max": True, "mini_w": False}, "glossary": []}),
    DEFAULTS)
ok("bool is not accepted as int",
   err is None and ignored == 2
   and cfg["history_max"] == DEFAULTS["history_max"]
   and cfg["mini_w"] == DEFAULTS["mini_w"])

# ---- 数值夹紧（算应用，不计 ignored） ----
cfg, ignored, err = sio.import_settings(json.dumps(
    {"app": "RealtimeTranslate", "version": 1,
     "config": {"font_size": 99, "hover_ms": 5, "tts_rate": 99,
                "history_max": -5, "mini_w": 0}, "glossary": []}),
    DEFAULTS)
ok("numeric values clamped, not ignored",
   err is None and ignored == 0 and cfg["font_size"] == 18
   and cfg["hover_ms"] == 100 and cfg["tts_rate"] == 10
   and cfg["history_max"] == 0 and cfg["mini_w"] == 1)

# ---- 热键空字符串不接受；其他字符串键空串可以 ----
cfg, ignored, err = sio.import_settings(json.dumps(
    {"app": "RealtimeTranslate", "version": 1,
     "config": {"hotkey_main": "", "pack_mirror": ""}, "glossary": []}),
    DEFAULTS)
ok("empty hotkey ignored, empty pack_mirror kept",
   err is None and ignored == 1
   and cfg["hotkey_main"] == DEFAULTS["hotkey_main"] and cfg["pack_mirror"] == "")

# ---- 术语表：导入时清洗（去重 + 超长丢掉） ----
cfg, ignored, err = sio.import_settings(json.dumps(
    {"app": "RealtimeTranslate", "version": 1, "config": {},
     "glossary": [["a", "A"], ["a", "A2"], ["z" * 41, "Z"], ["cat", "猫"]]}),
    DEFAULTS)
ok("glossary sanitized on import (dedup + over-long dropped)",
   err is None and ignored == 0
   and cfg["glossary"] == [["a", "A"], ["cat", "猫"]])
cfg, ignored, err = sio.import_settings(json.dumps(
    {"app": "RealtimeTranslate", "version": 1, "config": {},
     "glossary": [{"src": "a", "dst": "A"}, {"src": "cat", "dst": "猫"}]}),
    DEFAULTS)
ok("glossary accepts exported {src, dst} dict form",
   err is None and ignored == 0
   and cfg["glossary"] == [["a", "A"], ["cat", "猫"]])
cfg, ignored, err = sio.import_settings(json.dumps(
    {"app": "RealtimeTranslate", "version": 1, "config": {},
     "glossary": "not a list"}),
    DEFAULTS)
ok("non-list glossary ignored and counted",
   err is None and ignored == 1 and cfg["glossary"] == DEFAULTS["glossary"])

# ---- 导入不改动传入的 defaults ----
before = copy.deepcopy(DEFAULTS)
cfg, ignored, err = sio.import_settings(json.dumps(
    {"app": "RealtimeTranslate", "version": 1,
     "config": {"sl": "en", "font_size": 99, "top": False},
     "glossary": [["x", "X"]]}),
    DEFAULTS)
ok("import never mutates the passed defaults", DEFAULTS == before)
ok("import result is independent of defaults (deep copy)",
   cfg["glossary"] == [["x", "X"]] and DEFAULTS["glossary"] == [])

# ---- v2.8 粘贴图片翻译快捷键也要能导出/导入 ----
blob = sio.export_settings(dict(DEFAULTS, hotkey_clip="ctrl+alt+v"))
cfg, ignored, err = sio.import_settings(blob, DEFAULTS)
ok("hotkey_clip survives export->import round-trip",
   err is None and cfg["hotkey_clip"] == "ctrl+alt+v")
ok("hotkey_clip empty string is ignored on import",
   sio.import_settings(json.dumps(
       {"app": "RealtimeTranslate", "version": 1,
        "config": {"hotkey_clip": ""}, "glossary": []}),
       DEFAULTS)[0]["hotkey_clip"] == DEFAULTS["hotkey_clip"])

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
