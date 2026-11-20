"""设置导出 / 导入 — 纯函数，只用标准库，不碰界面、不碰文件、不碰网络。

配置是一份扁平 dict（键与类型以 desktop_translator.DEFAULTS 为准）。
导出格式：{"app": "RealtimeTranslate", "version": 1,
           "config": {...}, "glossary": [{"src": .., "dst": ..}, ...]}
术语表只在顶层 "glossary" 出现一次，不在 "config" 里重复。
"""
import copy
import json

import glossary

APP_NAME = "RealtimeTranslate"
FORMAT_VERSION = 1

_STR_KEYS = frozenset([
    "sl", "tl", "geometry", "engine", "pack_mirror", "pointer_scope",
    "close_action", "minimize_action", "popup_mode", "shot_mode",
    "hotkey_main", "hotkey_pointer", "hotkey_shot", "hotkey_replace",
    "hotkey_clip", "hotkey_window",
    "update_last_check",
    "proxy_host", "proxy_user", "tts_voice",
])
_BOOL_KEYS = frozenset([
    "top", "watch", "smart", "bilingual", "reflow", "show_src",
    "auto_offline", "pointer", "hover", "tray_tip",
    "history_on", "history_reuse", "auto_copy", "dark_mode", "update_auto",
    "proxy_enabled", "hover_window",
])
_INT_KEYS = frozenset([
    "history_max", "mini_w", "mini_h", "hover_ms", "tts_rate", "font_size",
    "proxy_port", "live_interval",
])
# 热键只要求是非空字符串，这里不解析组合键。
_HOTKEY_KEYS = frozenset([
    "hotkey_main", "hotkey_pointer", "hotkey_shot", "hotkey_replace",
    "hotkey_clip", "hotkey_window",
])
# 注意：proxy_pass（代理密码）刻意不在上面任何一张表里——设置导出时
# _check_value 认不出它，永远不写进导出的 JSON；导入时 import_settings
# 也明确跳过它（安全修复 H-04：别人给的设置文件不能悄悄改走本机代理密码，
# 否则流量可被引到攻击者的代理上）。密码只存本机 config.json。
# 数值键的合法范围；mini_w / mini_h 只有下限（正整数）。
_CLAMPS = {
    "font_size": (10, 18),
    "hover_ms": (100, 5000),
    "tts_rate": (-10, 10),
    "history_max": (0, 10000),
    "mini_w": (1, None),
    "mini_h": (1, None),
    "proxy_port": (0, 65535),
    # L-05：实时翻译间隔最短 5 秒——2 秒一轮高频 OCR 会把窗口卡住、CPU 占满。
    "live_interval": (5, 30),
}

# H-04：导入设置时涉及网络出口的敏感键 —— 界面层在应用前把这些变化
# 列给用户确认（见 sensitive_import_changes），不在这里悄悄应用。
SENSITIVE_IMPORT_KEYS = frozenset([
    "pack_mirror", "proxy_host", "proxy_port", "proxy_enabled", "proxy_user",
])

_TOP_KEYS = frozenset(["app", "version", "config", "glossary"])


def _kind(key, defaults):
    """返回键的期望类型：'str' / 'bool' / 'int' / 'glossary'，未知键返回 None。"""
    if key == "glossary":
        return "glossary"
    if key in _BOOL_KEYS:
        return "bool"
    if key in _INT_KEYS:
        return "int"
    if key in _STR_KEYS:
        return "str"
    # 不在静态表里的键：按 defaults 里对应值的类型判断（bool 先于 int 查，
    # 因为 bool 是 int 的子类）。
    if isinstance(defaults, dict) and key in defaults:
        v = defaults[key]
        if isinstance(v, bool):
            return "bool"
        if isinstance(v, int):
            return "int"
        if isinstance(v, str):
            return "str"
        if isinstance(v, list):
            return "glossary"
    return None


def _clamp_int(key, value):
    lo, hi = _CLAMPS.get(key, (None, None))
    if lo is not None and value < lo:
        value = lo
    if hi is not None and value > hi:
        value = hi
    return value


def _check_value(key, value, defaults):
    """校验单个值。返回 (ok, 清洗后的值)；ok 为 False 表示应计入 ignored。"""
    kind = _kind(key, defaults)
    if kind == "bool":
        # type() 精确比较：bool 不是 int，这里也不接受 0/1。
        if type(value) is bool:
            return True, value
        return False, None
    if kind == "int":
        # type() 精确比较：True/False 是 bool，不是合法 int。
        if type(value) is int:
            return True, _clamp_int(key, value)
        return False, None
    if kind == "str":
        if not isinstance(value, str):
            return False, None
        if key in _HOTKEY_KEYS and value == "":
            return False, None
        return True, value
    if kind == "glossary":
        if not isinstance(value, list):
            return False, None
        # 接受两种写法：导出格式 {"src": .., "dst": ..}，以及 [src, dst] 词对。
        norm = []
        for item in value:
            if isinstance(item, dict) and "src" in item and "dst" in item:
                norm.append([item.get("src"), item.get("dst")])
            else:
                norm.append(item)
        return True, glossary.sanitize_pairs(norm)
    return False, None


def _minimal_json():
    try:
        return json.dumps({"app": APP_NAME, "version": FORMAT_VERSION,
                           "config": {}, "glossary": []},
                          ensure_ascii=False, indent=2)
    except Exception:
        return '{"app": "RealtimeTranslate", "version": 1, "config": {}, "glossary": []}'


def export_settings(cfg):
    """把配置导出为 JSON 字符串。输入异常时也不抛错：尽量导出能导出的
    部分，实在不行返回一份最小合法 JSON。"""
    try:
        if not isinstance(cfg, dict):
            return _minimal_json()
        config = {}
        for key, value in cfg.items():
            if key == "glossary":
                continue  # 术语表只放顶层，不在 config 里重复
            ok, clean = _check_value(key, value, None)
            if ok:
                config[key] = clean
        raw_glossary = cfg.get("glossary")
        if isinstance(raw_glossary, (list, tuple)):
            pairs = glossary.sanitize_pairs(list(raw_glossary))
        else:
            pairs = []
        payload = {"app": APP_NAME, "version": FORMAT_VERSION,
                   "config": config,
                   "glossary": [{"src": s, "dst": d} for s, d in pairs]}
        return json.dumps(payload, ensure_ascii=False, indent=2)
    except Exception:
        return _minimal_json()


def import_settings(text, defaults):
    """解析导出的 JSON，返回 (cfg, ignored, error)。

    error 非 None 时解析失败，cfg 为 {}、ignored 为 0。
    成功时从 defaults 的深拷贝出发，只应用已知键且类型正确的值；
    未知键、类型错误的值计入 ignored；数值键按范围夹紧（夹紧算应用，
    不计 ignored）。全程先校验再组装结果，不会半应用；
    传入的 defaults 不会被改动。
    """
    try:
        data = json.loads(text)
    except Exception as exc:
        return {}, 0, "invalid JSON: %s" % (exc,)
    if not isinstance(data, dict):
        return {}, 0, "top level is not an object"

    base = copy.deepcopy(defaults) if isinstance(defaults, dict) else {}
    known = set(base) | {"glossary"}

    updates = {}
    ignored = 0

    config = data.get("config", {})
    if "config" in data and not isinstance(config, dict):
        ignored += 1
        config = {}
    for key, value in config.items():
        if key not in known:
            ignored += 1
            continue
        # H-04：导入的设置文件永远不接受 proxy_pass —— 别人给的文件不能悄悄
        # 改走本机代理密码；要改密码请在界面「代理密码」栏里自己填。
        if key == "proxy_pass":
            ignored += 1
            continue
        ok, clean = _check_value(key, value, base)
        if ok:
            updates[key] = clean
        else:
            ignored += 1

    if "glossary" in data:
        ok, clean = _check_value("glossary", data["glossary"], base)
        if ok:
            updates["glossary"] = clean  # 顶层优先于 config 里的同名键
        else:
            ignored += 1

    for key in data:
        if key not in _TOP_KEYS:
            ignored += 1

    result = copy.deepcopy(base)
    result.update(updates)
    return result, ignored, None


def sensitive_import_changes(text, current_cfg, defaults):
    """H-04：算出「这次导入会改动的敏感键」→ [(key, 旧值, 新值), ...]。

    只看导入文件里明确写了的敏感键（SENSITIVE_IMPORT_KEYS：镜像域名、
    代理地址/端口/开关/账号 —— 改了这些等于改了程序的网络出口），
    文件里没提的键不算改动。界面层在应用导入前把这份清单列给用户，
    用户点头才应用；没变化返回 []。解析失败返回 []（由 import_settings 报错）。
    proxy_pass 不在这里出现：它永远不被导入（见 import_settings）。
    """
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return []
        config = data.get("config", {})
        if not isinstance(config, dict):
            return []
        current = current_cfg if isinstance(current_cfg, dict) else {}
        base = defaults if isinstance(defaults, dict) else current
        out = []
        for key in sorted(SENSITIVE_IMPORT_KEYS):
            if key not in config:
                continue
            ok, clean = _check_value(key, config[key], base)
            if not ok:
                continue
            old = current.get(key)
            if old != clean:
                out.append((key, old, clean))
        return out
    except Exception:      # noqa: BLE001
        return []
