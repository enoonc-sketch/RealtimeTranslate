"""v2.15 离线激活码：license.py 纯逻辑测试（无 OS 依赖，Linux 上就能跑）。

pytest 风格：python3 -m pytest tests/test_license.py -v
直接跑也行：python3 tests/test_license.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import license as lic

SECRET = bytes.fromhex("00" * 32)
OTHER_SECRET = bytes.fromhex("ff" * 32)
T0 = 1_700_000_000.0  # 固定“现在”，试用期计算可复现


def fresh_cfg():
    return {"license_key": "", "license_status": "free",
            "license_trial_start": 0, "license_machines": []}


def test_generate_verify_roundtrip_both_tiers():
    for tier in (lic.TIER_STANDARD, lic.TIER_SUPPORTER):
        code = lic.generate_code(SECRET, tier, batch=1, serial=42)
        assert code.startswith("RT2-") and len(code) == 23  # RT2- + 16 位 + 3 个短横线
        ok, info = lic.verify_code(code, secret=SECRET)
        assert ok and info["tier"] == tier
        assert info["batch"] == 1 and info["serial"] == 42
        assert info["version"] == lic.CODE_VERSION


def test_code_format_groups():
    code = lic.generate_code(SECRET, 0, 0, 0)
    parts = code.split("-")
    assert parts[0] == "RT2" and len(parts) == 5
    assert all(len(p) == 4 for p in parts[1:])


def test_tampered_code_rejected():
    code = lic.generate_code(SECRET, 0, 5, 9)
    last = "A" if code[-1] != "A" else "B"
    ok, info = lic.verify_code(code[:-1] + last, secret=SECRET)
    assert not ok and info["error"] == "bad-signature"
    # 中间改一位也一样
    mid = list(code)
    mid[6] = "A" if mid[6] != "A" else "B"
    ok, info = lic.verify_code("".join(mid), secret=SECRET)
    assert not ok and info["error"] == "bad-signature"


def test_wrong_secret_rejected():
    code = lic.generate_code(SECRET, 0, 1, 1)
    ok, info = lic.verify_code(code, secret=OTHER_SECRET)
    assert not ok and info["error"] == "bad-signature"


def test_bad_format_rejected():
    for bad in ("", "RT2-AAAA", "RT2-AAAA-AAAA-AAAA-AAAA",
                "RT2-!!!!-!!!!-!!!!-!!!!", "RT2-0000-0000-0000-000",
                None, 12345):
        ok, info = lic.verify_code(bad, secret=SECRET)
        assert not ok, bad
        assert info["error"] in ("bad-format", "bad-version", "bad-signature")


def test_user_friendly_aliases_accepted():
    code = lic.generate_code(SECRET, 0, 2, 3)
    # 手抄时 O 当 0、I/L 当 1；去掉短横线和前缀也认
    assert lic.verify_code(code.replace("0", "O"), secret=SECRET)[0]
    assert lic.verify_code(code.replace("1", "l"), secret=SECRET)[0]
    assert lic.verify_code(code[4:], secret=SECRET)[0]
    assert lic.verify_code("  " + code.lower() + "  ", secret=SECRET)[0]


def test_generate_validates_ranges():
    for bad in (lambda: lic.generate_code(SECRET, 2, 1, 1),
                lambda: lic.generate_code(SECRET, 0, 1024, 1),
                lambda: lic.generate_code(SECRET, 0, 1, 65536),
                lambda: lic.generate_code(SECRET, 0, -1, 1)):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("应抛 ValueError")
    try:
        lic.generate_code(None, 0, 1, 1)
    except RuntimeError:
        pass
    else:
        raise AssertionError("没密钥应抛 RuntimeError")


def test_no_secret_verify_fails_closed():
    code = lic.generate_code(SECRET, 0, 1, 1)
    old = os.environ.pop("RT_LICENSE_SECRET_HEX", None)
    try:
        ok, info = lic.verify_code(code, secret=None)
        assert not ok and info["error"] == "no-secret"
    finally:
        if old is not None:
            os.environ["RT_LICENSE_SECRET_HEX"] = old


def test_trial_lifecycle():
    cfg = fresh_cfg()
    assert lic.status_of(cfg, now=T0) == "free"
    assert not lic.typing_allowed(cfg, now=T0)
    assert lic.trial_available(cfg, now=T0)
    assert lic.trial_days_left(cfg, now=T0) == 7.0
    assert lic.start_trial(cfg, now=T0) is True
    assert lic.status_of(cfg, now=T0) == "trial"
    assert lic.typing_allowed(cfg, now=T0)
    assert lic.trial_days_left(cfg, now=T0 + 3 * 86400) == 4.0
    # 试用只给一次：中途再点不重置
    assert lic.start_trial(cfg, now=T0 + 3 * 86400) is False
    assert lic.trial_days_left(cfg, now=T0 + 3 * 86400) == 4.0
    # 7 天整过期
    assert lic.status_of(cfg, now=T0 + 7 * 86400) == "free"
    assert not lic.typing_allowed(cfg, now=T0 + 7 * 86400)
    assert lic.trial_days_left(cfg, now=T0 + 7 * 86400) == 0.0
    assert not lic.trial_available(cfg, now=T0 + 7 * 86400)


def test_activate_pro_and_machine_note():
    cfg = fresh_cfg()
    code = lic.generate_code(SECRET, 1, 2, 8)
    ok, msg, info = lic.activate(cfg, code, secret=SECRET, now=T0,
                                  fingerprint="fp-machine-a")
    assert ok and info["tier_name"] == "supporter"
    assert "支持者版" in msg
    assert cfg["license_status"] == "pro"
    assert cfg["license_key"] == code
    assert cfg["license_machines"] == ["fp-machine-a"]
    assert lic.status_of(cfg, now=T0, secret=SECRET) == "pro"
    assert lic.typing_allowed(cfg, now=T0 + 365 * 86400, secret=SECRET)
    # 同一码换一台机器：只提醒、不硬锁，照样激活成功
    cfg2 = fresh_cfg()
    ok, msg, _info = lic.activate(cfg2, code, secret=SECRET, now=T0,
                                   fingerprint="fp-machine-b")
    assert ok
    # 同一台再激活不重复记、不提醒
    ok, msg, _info = lic.activate(cfg, code, secret=SECRET, now=T0,
                                   fingerprint="fp-machine-a")
    assert ok and "另一台" not in msg
    assert cfg["license_machines"] == ["fp-machine-a"]


def test_activate_bad_code_changes_nothing():
    cfg = fresh_cfg()
    lic.start_trial(cfg, now=T0)
    before = dict(cfg)
    ok, _msg, info = lic.activate(cfg, "RT2-AAAA-AAAA-AAAA-AAAA",
                                   secret=SECRET, now=T0)
    assert not ok
    assert cfg == before  # 试用状态原样保留


def test_status_trusts_stored_pro_without_secret():
    # 源码运行（密钥不在）时信任存盘状态；exe 里密钥一定在，走密码学验证。
    cfg = fresh_cfg()
    cfg["license_status"] = "pro"
    cfg["license_key"] = "RT2-XXXX-XXXX-XXXX-XXXX"
    old = os.environ.pop("RT_LICENSE_SECRET_HEX", None)
    try:
        assert lic.status_of(cfg, now=T0, secret=None) == "pro"
    finally:
        if old is not None:
            os.environ["RT_LICENSE_SECRET_HEX"] = old
