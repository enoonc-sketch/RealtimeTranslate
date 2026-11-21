"""离线激活码 —— 纯标准库，无 OS 依赖，可单测。

码格式：RT2-XXXX-XXXX-XXXX-XXXX（Crockford Base32，16 位有效字符 = 80 bit）
位布局（高位在前）：
  version  4 bit  = 2
  tier     2 bit  0=标准版 1=支持者版
  batch   10 bit  批次号 0..1023
  serial  16 bit  序列号 0..65535
  sig     48 bit  HMAC-SHA256(secret, 前 4 字节) 的前 48 bit

签名密钥绝不能进公开仓库：验证时按这个顺序找密钥——
  1) 调用方显式传入的 secret 参数；
  2) 构建时注入的 license_secret 模块（只在打包后的 exe 里有，源码仓库里没有）；
  3) 环境变量 RT_LICENSE_SECRET_HEX（测试 / 本地生成脚本用）。
找不到密钥时，generate/verify 无法做密码学验证：generate 抛错，
verify 返回 (False, {"error": "no-secret"})；status_of 回落到信任
config.json 里存的 license_status（只影响源码运行，exe 里密钥一定在）。

诚实说明：仓库是公开的，验证逻辑也在公开代码里，防的是“随手分享”，
防不住有心破解；离线方案也做不到远程作废旧码。这是轻量离线方案的
固有上限（见 PREP.md 第二节）。
"""

import hashlib
import hmac
import os
import re
import time

# Crockford Base32：去掉易混的 0/O、1/I/L、U。
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_CROCKFORD_MAP = {c: i for i, c in enumerate(_CROCKFORD)}
# 用户手抄时容易写错的字符：O 当 0、I/L 当 1 接受。
_ALIASES = {"O": "0", "I": "1", "L": "1"}

CODE_VERSION = 2
CODE_PREFIX = "RT2"
TRIAL_DAYS = 7
TRIAL_SECONDS = TRIAL_DAYS * 86400
MAX_MACHINES = 2          # 每码默认 2 台（主力 + 笔记本），离线无法强制执行

TIER_STANDARD = 0
TIER_SUPPORTER = 1
TIER_NAMES = {TIER_STANDARD: "standard", TIER_SUPPORTER: "supporter"}
TIER_CODES = {"standard": TIER_STANDARD, "supporter": TIER_SUPPORTER}

# config.json 里的授权键（照 proxy_pass 的模式：只存本机，绝不进
# settings_io 的导出白名单、导入时也明确跳过）。
LICENSE_KEYS = ("license_key", "license_status", "license_trial_start",
                "license_machines")

STATUS_FREE = "free"
STATUS_TRIAL = "trial"
STATUS_PRO = "pro"


def _as_bytes(secret):
    """secret 可以是 bytes 或 hex 字符串；其他类型返回 None。"""
    if isinstance(secret, (bytes, bytearray)):
        return bytes(secret)
    if isinstance(secret, str):
        try:
            return bytes.fromhex(secret.strip())
        except Exception:
            return None
    return None


def resolve_secret(explicit=None):
    """按优先级解析签名密钥，找不到返回 None（不抛错、不打日志）。"""
    s = _as_bytes(explicit)
    if s:
        return s
    try:
        import license_secret  # 打包时注入的本地模块，源码仓库里没有
        s = _as_bytes(getattr(license_secret, "SECRET", None))
        if s:
            return s
    except Exception:
        pass
    env = os.environ.get("RT_LICENSE_SECRET_HEX")
    if env:
        s = _as_bytes(env)
        if s:
            return s
    return None


def normalize_code(code):
    """去空白/短横线、大写、易混字符归一；非法返回 None。"""
    if not isinstance(code, str):
        return None
    s = re.sub(r"[\s\-]", "", code).upper()
    s = "".join(_ALIASES.get(c, c) for c in s)
    if s.startswith(CODE_PREFIX):
        s = s[len(CODE_PREFIX):]
    if len(s) != 16 or any(c not in _CROCKFORD_MAP for c in s):
        return None
    return s


def _encode(n):
    chars = []
    for _ in range(16):
        chars.append(_CROCKFORD[n & 31])
        n >>= 5
    chars.reverse()
    return "".join(chars)


def generate_code(secret, tier, batch, serial):
    """生成一个激活码。tier: 0=标准版 1=支持者版；batch 0..1023；
    serial 0..65535。secret 缺失时抛 RuntimeError（绝不能生成无签名的码）。"""
    key = resolve_secret(secret)
    if not key:
        raise RuntimeError("no signing secret available")
    if tier not in TIER_NAMES:
        raise ValueError("bad tier: %r" % (tier,))
    if not 0 <= batch <= 1023:
        raise ValueError("batch out of range: %r" % (batch,))
    if not 0 <= serial <= 65535:
        raise ValueError("serial out of range: %r" % (serial,))
    payload = (CODE_VERSION << 28) | (tier << 26) | (batch << 16) | serial
    payload_bytes = payload.to_bytes(4, "big")
    sig = hmac.new(key, payload_bytes, hashlib.sha256).digest()
    sig_int = int.from_bytes(sig[:6], "big")          # 前 48 bit
    full = (payload << 48) | sig_int
    body = _encode(full)
    return "%s-%s-%s-%s-%s" % (CODE_PREFIX, body[0:4], body[4:8],
                              body[8:12], body[12:16])


def parse_code(code, secret=None):
    """验证激活码。返回 (ok, info)：ok 时 info 含 version/tier/batch/serial；
    失败时 info 只有 error（格式错 / 签名错 / 密钥缺失 / 版本不对）。"""
    body = normalize_code(code)
    if body is None:
        return False, {"error": "bad-format"}
    n = 0
    for c in body:
        n = (n << 5) | _CROCKFORD_MAP[c]
    payload = n >> 48
    sig_int = n & ((1 << 48) - 1)
    version = (payload >> 28) & 0xF
    if version != CODE_VERSION:
        return False, {"error": "bad-version", "version": version}
    tier = (payload >> 26) & 0x3
    if tier not in TIER_NAMES:
        return False, {"error": "bad-tier", "tier": tier}
    batch = (payload >> 16) & 0x3FF
    serial = payload & 0xFFFF
    key = resolve_secret(secret)
    if not key:
        return False, {"error": "no-secret"}
    expect = hmac.new(key, payload.to_bytes(4, "big"),
                      hashlib.sha256).digest()
    expect_int = int.from_bytes(expect[:6], "big")
    if not hmac.compare_digest(str(sig_int), str(expect_int)):
        return False, {"error": "bad-signature"}
    return True, {"version": version, "tier": tier,
                  "tier_name": TIER_NAMES[tier],
                  "batch": batch, "serial": serial}


def verify_code(code, secret=None):
    """parse_code 的别名（语义上更顺）。"""
    return parse_code(code, secret)


def machine_fingerprint():
    """本机指纹哈希（SHA-256 hex，只存哈希不存原始值）。
    Windows 读 MachineGuid，失败则回落到主机名 + 用户名；绝不抛错。"""
    raw = ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Microsoft\Cryptography") as k:
            raw = winreg.QueryValueEx(k, "MachineGuid")[0]
    except Exception:
        pass
    if not raw:
        try:
            import getpass
            import platform
            raw = "%s|%s" % (platform.node(), getpass.getuser())
        except Exception:
            raw = "unknown-machine"
    return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()


def _trial_start(cfg):
    try:
        v = float(cfg.get("license_trial_start") or 0)
    except Exception:
        v = 0.0
    return v if v > 0 else 0.0


def _stored_key_valid(cfg, secret=None):
    """config.json 里存的 license_key 现在还验得过吗。"""
    key = cfg.get("license_key") or ""
    if not isinstance(key, str) or not key.strip():
        return False
    ok, _info = parse_code(key, secret=secret)
    return ok


def status_of(cfg, now=None, secret=None):
    """当前授权状态：'pro' / 'trial' / 'free'。
    有合法激活码就是 pro；没有则看 7 天试用是否还在期内；都没有就是 free。
    密钥不在（源码运行）时信任存盘的 license_status（exe 里密钥一定在）。"""
    if now is None:
        now = time.time()
    if _stored_key_valid(cfg, secret=secret):
        return STATUS_PRO
    if resolve_secret(secret) is None and cfg.get("license_status") == STATUS_PRO:
        return STATUS_PRO
    start = _trial_start(cfg)
    if start > 0 and start <= now < start + TRIAL_SECONDS:
        return STATUS_TRIAL
    return STATUS_FREE


def typing_allowed(cfg, now=None, secret=None):
    """打字检测翻译现在能不能开：专业版或试用期内。"""
    return status_of(cfg, now=now, secret=secret) in (STATUS_PRO, STATUS_TRIAL)


def trial_available(cfg, now=None):
    """还能不能开始 7 天试用：没买过、试用也没开始过。"""
    if now is None:
        now = time.time()
    if _stored_key_valid(cfg):
        return False
    return _trial_start(cfg) <= 0


def trial_days_left(cfg, now=None):
    """试用剩余天数（未开始返回 7.0，过期返回 0.0）。"""
    if now is None:
        now = time.time()
    start = _trial_start(cfg)
    if start <= 0:
        return float(TRIAL_DAYS)
    left = (start + TRIAL_SECONDS - now) / 86400.0
    return max(0.0, left)


def start_trial(cfg, now=None):
    """开始 7 天试用：把开始时间写进 cfg。已开始过 / 已是专业版返回 False。"""
    if now is None:
        now = time.time()
    if not trial_available(cfg, now=now):
        return False
    cfg["license_trial_start"] = now
    cfg["license_status"] = STATUS_TRIAL
    return True


def activate(cfg, code, secret=None, now=None, fingerprint=None):
    """用激活码激活。返回 (ok, message, info)。
    码合法就一定成功：换机只提醒、不硬锁（重装系统 / 换硬件不能误杀正版用户）；
    每码默认 2 台，离线无法强制执行，靠台账 + 人工售后兜底。"""
    if now is None:
        now = time.time()
    ok, info = parse_code(code, secret=secret)
    if not ok:
        return False, "激活码无效（%s），请检查后重新输入。" % info.get("error", "?"), info
    fp = fingerprint or machine_fingerprint()
    machines = cfg.get("license_machines")
    if not isinstance(machines, list):
        machines = []
    machines = [m for m in machines if isinstance(m, str)]
    note = ""
    if fp not in machines:
        if machines:
            note = "提示：这个激活码已在另一台电脑上激活过（每码默认 2 台）；换电脑后请联系作者免费重置。"
        machines.append(fp)
    cfg["license_key"] = code.strip()
    cfg["license_status"] = STATUS_PRO
    cfg["license_machines"] = machines
    tier_name = {"standard": "标准版", "supporter": "支持者版"}.get(
        info.get("tier_name"), "专业版")
    msg = "已激活%s，打字检测翻译已解锁。" % tier_name
    if note:
        msg += "\n" + note
    return True, msg, info
