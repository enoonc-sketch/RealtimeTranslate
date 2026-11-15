"""自定义术语表 — 纯函数，不碰界面、不碰网络。

用户自己定的词对（原文词 -> 固定译文），翻译前先把原文里的词
用占位符保护起来，引擎翻完再把占位符换回固定译文，这样引擎
就不会把专有名词、产品名、品牌名翻走样。

占位符用 Unicode 私有区字符（\\ue000…\\ue001），正常文字里
几乎不会出现；万一原文里真有这个字符，换一对备用私有区字符，
保证不跟原文撞上。长词先替换（避免短词先把长词的一部分吃掉）。
"""
import re

MAX_PAIRS = 200
MAX_TERM_LEN = 40
_MARKERS = (("\ue000", "\ue001"), ("\ue002", "\ue003"),
            ("\ue004", "\ue005"))


def sanitize_pairs(pairs):
    """清洗用户输入的词对：去空、去重（同原文只留第一条）、截断到上限。

    输入是 [[src, dst], ...] 或 [(src, dst), ...]；返回 [[src, dst], ...]。
    词对本身超过 40 字、原文或译文为空的都丢掉。
    """
    out, seen = [], set()
    for item in pairs or []:
        try:
            src, dst = item[0], item[1]
        except Exception:
            continue
        src, dst = str(src or "").strip(), str(dst or "").strip()
        if not src or not dst:
            continue
        if len(src) > MAX_TERM_LEN or len(dst) > MAX_TERM_LEN:
            continue
        if src in seen:
            continue
        seen.add(src)
        out.append([src, dst])
        if len(out) >= MAX_PAIRS:
            break
    return out


def _pick_markers(text):
    for lo, hi in _MARKERS:
        if lo not in text and hi not in text:
            return lo, hi
    return None


def apply_glossary(text, pairs):
    """把术语换成占位符：返回 (保护后的文本, {占位符: 固定译文})。

    pairs 为空返回原文与空映射。同一词出现多次只用一个占位符。
    占位符本身与原文撞上了（极罕见）就原样返回、不做保护。
    """
    text = text or ""
    clean = sanitize_pairs(pairs)
    if not clean or not text:
        return text, {}
    markers = _pick_markers(text)
    if markers is None:
        return text, {}
    lo, hi = markers
    # 长词先换：比如先换 "Maxum II" 再换 "Maxum"，否则长词会被切碎
    ordered = sorted(clean, key=lambda p: (-len(p[0]), clean.index(p)))
    mapping, out = {}, text
    for i, (src, dst) in enumerate(ordered):
        if src not in out:
            continue
        ph = "%s%d%s" % (lo, i, hi)
        out = out.replace(src, ph)
        mapping[ph] = dst
    return out, mapping


def restore_glossary(text, mapping):
    """把占位符换回固定译文；mapping 为空时原文返回。"""
    if not mapping:
        return text or ""
    out = text or ""
    for ph, dst in mapping.items():
        out = out.replace(ph, dst)
    return out


# ---- 运行时生效的术语表（主程序在启动 / 保存设置时调用 set_active） ----
_ACTIVE = []


def set_active(pairs):
    global _ACTIVE
    _ACTIVE = sanitize_pairs(pairs)


def active():
    return list(_ACTIVE)


def protect(text):
    return apply_glossary(text, _ACTIVE)


def restore(text, mapping):
    return restore_glossary(text, mapping)


# ---- JSON 导入 / 导出（纯函数，v2.8.0 新增） ----

def load_glossary_json(text):
    """从 JSON 字符串读入术语表。

    期望顶层为 [{"src": ..., "dst": ...}, ...] 列表。
    返回 (pairs, skipped, error)：pairs 为清洗后的 [[src, dst], ...]；
    skipped 为被丢掉的条目数（重复 / 为空 / 超长 / 非对象 / 缺 src 或 dst）；
    error 成功时为 None，JSON 解析失败或顶层不是列表时为一条简短提示。
    从不抛异常。
    """
    import json
    try:
        data = json.loads(text)
    except Exception:
        return [], 0, "JSON 格式错误 (invalid JSON)"
    if not isinstance(data, list):
        return [], 0, "顶层必须是列表 (top level must be a list)"
    raw = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if "src" not in item or "dst" not in item:
            continue
        raw.append([item["src"], item["dst"]])
    try:
        pairs = sanitize_pairs(raw)
    except Exception:
        return [], 0, "术语表内容无效 (invalid glossary content)"
    skipped = len(data) - len(pairs)
    return pairs, skipped, None


def dump_glossary_json(pairs):
    """把术语表导出为 JSON 字符串（ensure_ascii=False, indent=2）。

    先经 sanitize_pairs 清洗；输入无效时返回 "[]"。从不抛异常。
    """
    import json
    try:
        clean = sanitize_pairs(pairs)
        return json.dumps([{"src": src, "dst": dst} for src, dst in clean],
                          ensure_ascii=False, indent=2)
    except Exception:
        return "[]"
