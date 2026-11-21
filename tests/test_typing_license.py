"""v2.15 打字检测开关的授权门禁：真 App 测试（需 xvfb）。

跑法：xvfb-run python3 tests/test_typing_license.py
（pytest 不收集：顶层 sys.exit，见 tests/ 其他脚本式测试同款形态。）

测的是：
  A. 免费版 + 试用已用完：设置里打字检测开关置灰；托盘点一下弹激活框、开关打回去。
  B. 免费版 + 试用没用过：打开开关自动开始 7 天试用，开关保持打开。
  C. 激活后：开关放开、能打开，_start_typing 能过门禁（本机无 pynput，
     监听起不来是预期内的，只断言门禁没把开关打回去）。
  D. 手改配置文件把 typing 写成 True、试用已过期：_start_typing 直接
     不启动钩子，并把开关打回 False（界面不撒谎）。
  E. settings_io：授权键不进导出、不进导入；导入设置不冲掉已激活的专业版。
"""
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

TEST_SECRET = bytes.fromhex("11" * 32)
os.environ["RT_LICENSE_SECRET_HEX"] = TEST_SECRET.hex()

import license as lic
import settings_io
import desktop_translator as dt

fails = []


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    if not cond:
        fails.append(name)


dt.DATA_DIR = tempfile.mkdtemp()
dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.HISTORY_PATH = os.path.join(dt.DATA_DIR, "history.db")
app = dt.App()
r = app.root


def pump(sec=0.2):
    end = time.time() + sec
    while time.time() < end:
        r.update()
        time.sleep(0.02)


def close_license_dialogs():
    for w in list(r.winfo_children()):
        try:
            if w.winfo_class() == "Toplevel" and w.title() == "升级到专业版":
                w.destroy()
        except Exception:
            pass
    pump(0.1)


TEST_CODE = lic.generate_code(TEST_SECRET, lic.TIER_STANDARD, batch=1, serial=1)

# ---- A. 免费版 + 试用已用完：开关置灰，托盘点一下弹激活框 ----
app.cfg["license_trial_start"] = time.time() - 8 * 86400
app.cfg["license_status"] = "free"
app.cfg["license_key"] = ""
app.cfg["typing"] = False
app.typing_var.set(False)
app._save()
app.open_settings()
pump()
check("A1 试用过期后设置里开关置灰",
      str(app.typing_check.cget("state")) == "disabled")
check("A2 状态说明含试用已结束", "试用已结束" in app._typing_status_text())
app._on_tray_cmd("typing")  # 托盘点打字检测：应打回开关并弹激活框
pump()
check("A3 托盘点一下开关仍是关", app.typing_var.get() is False
      and app.cfg.get("typing") is False)
dialogs = [w for w in r.winfo_children()
           if w.winfo_class() == "Toplevel" and w.title() == "升级到专业版"]
check("A4 托盘点一下弹出激活框", len(dialogs) == 1)
close_license_dialogs()

# ---- B. 免费版 + 试用没用过：打开开关自动开始试用 ----
app.cfg["license_trial_start"] = 0
app.cfg["license_status"] = "free"
app.cfg["license_key"] = ""
app.cfg["typing"] = False
app._save()
app._refresh_typing_ui()
check("B1 试用没用过时开关放开",
      str(app.typing_check.cget("state")) == "normal")
app.typing_var.set(True)
app._on_typing_opt()
check("B2 打开开关自动开始 7 天试用",
      app.cfg.get("typing") is True
      and lic.status_of(app.cfg) == "trial")
check("B3 状态说明含试用剩余", "试用中" in app._typing_status_text())
app.typing_var.set(False)
app._on_typing_opt()
check("B4 关掉开关后停监听（typing False）", app.cfg.get("typing") is False)

# ---- C. 激活后：开关放开、能打开，_start_typing 过门禁 ----
ok, _msg, _info = lic.activate(app.cfg, TEST_CODE, secret=TEST_SECRET,
                               fingerprint="test-machine")
assert ok
app._save()
app._refresh_typing_ui()
check("C1 激活后开关放开",
      str(app.typing_check.cget("state")) == "normal")
check("C2 状态说明含专业版已激活", "专业版已激活" in app._typing_status_text())
app.typing_var.set(True)
app._on_typing_opt()
check("C3 激活后打开开关保持打开", app.cfg.get("typing") is True)
app._start_typing()
check("C4 激活后 _start_typing 不打回开关",
      app.cfg.get("typing") is True
      and app._typing_stop is None and app._typing_listener is None)
app._stop_typing()

# ---- D. 手改配置 typing=True、试用已过期：_start_typing 不启动并打回开关 ----
app.cfg["license_key"] = ""
app.cfg["license_status"] = "free"
app.cfg["license_trial_start"] = time.time() - 8 * 86400
app.cfg["typing"] = True
app._start_typing()
check("D1 过期试用 + 手改 typing=True 时不启动钩子并打回开关",
      app.cfg.get("typing") is False
      and app._typing_stop is None and app._typing_listener is None)

# ---- E. settings_io：授权键不进导出、不进导入；导入不冲掉专业版 ----
app.cfg["license_key"] = TEST_CODE
app.cfg["license_status"] = "pro"
app.cfg["license_machines"] = ["test-machine"]
exported = settings_io.export_settings(app.cfg)
check("E1 导出设置不含任何授权键",
      "license_key" not in exported and "license_trial_start" not in exported
      and "license_machines" not in exported)
# 别人给的设置文件里塞了授权键：导入时跳过
import json
evil = json.loads(exported)
evil["config"]["license_key"] = "RT2-AAAA-AAAA-AAAA-AAAA"
evil["config"]["license_status"] = "free"
cfg2, ignored, err = settings_io.import_settings(json.dumps(evil), dt.DEFAULTS)
check("E2 导入设置跳过授权键（license_key 仍是默认值）",
      err is None and cfg2.get("license_key") == "" and ignored >= 1)
# 导入一份正常设置：已激活的专业版不受影响
app._apply_cfg_to_ui(cfg2)
check("E3 导入设置后已激活的专业版还在",
      app.cfg.get("license_key") == TEST_CODE
      and app.cfg.get("license_status") == "pro")

close_license_dialogs()
app.quit()
print("ALL OK" if not fails else "FAILED %s" % fails)
sys.exit(0 if not fails else 1)
