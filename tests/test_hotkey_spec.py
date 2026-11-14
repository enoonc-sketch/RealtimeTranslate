"""自定义全局快捷键：parse_hotkey / hotkey_label / pynput_spec /
validate_hotkey_cfg / 坏配置回落到默认。不需要 xvfb。"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import desktop_translator as dt

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


def raises(spec):
    try:
        dt.parse_hotkey(spec)
        return False
    except ValueError:
        return True


# ---- 1. 合法组合 ----
mods, vk, label = dt.parse_hotkey("ctrl+alt+t")
ok("ctrl+alt+t mods+vk+label", mods == (0x2 | 0x1) and vk == ord("T") and label == "Ctrl+Alt+T")
ok("order-insensitive", dt.parse_hotkey("alt+ctrl+t") == (mods, vk, label))
ok("case-insensitive", dt.parse_hotkey("CTRL+ALT+T") == (mods, vk, label))
ok("spaces tolerated", dt.parse_hotkey("ctrl + alt + t") == (mods, vk, label))
m2, v2, l2 = dt.parse_hotkey("shift+win+f5")
ok("shift+win+f5", m2 == (0x4 | 0x8) and v2 == 0x74 and l2 == "Shift+Win+F5")
ok("digit key", dt.parse_hotkey("ctrl+alt+1")[1] == ord("1"))
ok("f12", dt.parse_hotkey("ctrl+f12") == (0x2, 0x7B, "Ctrl+F12"))
ok("single modifier ok", dt.parse_hotkey("alt+q")[2] == "Alt+Q")

# ---- 2. 非法组合 ----
for bad in ("t", "ctrl", "alt", "", "   ", "ctrl+alt", "ctrl+alt+t+d",
            "ctrl+alt+xyz", "ctrl+alt+f13", "ctrl+alt+f0", "ctrl+alt+tt",
            "ctrl+alt+ ", "meta+t", "ctrl++t"):
    ok("reject %r" % bad, raises(bad))
ok("reject non-string", raises(None) and raises(123))

# ---- 3. 显示文字 / pynput 写法 ----
ok("label alt+shift+q", dt.hotkey_label("alt+shift+q") == "Alt+Shift+Q")
ok("label win+alt+t", dt.hotkey_label("win+alt+t") == "Alt+Win+T")
ok("pynput ctrl+alt+t", dt.pynput_spec("ctrl+alt+t") == "<ctrl>+<alt>+t")
ok("pynput shift+f1", dt.pynput_spec("ctrl+shift+f1") == "<ctrl>+<shift>+<f1>")
ok("pynput win", dt.pynput_spec("win+alt+d") == "<cmd>+<alt>+d")

# ---- 4. 配置校验：非法 / 重复回默认，合法自定义保留 ----
out = dt.validate_hotkey_cfg({"hotkey_main": "ctrl+shift+t",
                              "hotkey_pointer": "ctrl+alt+d",
                              "hotkey_shot": "ctrl+alt+s"})
ok("valid custom kept", out["hotkey_main"] == "ctrl+shift+t")
out = dt.validate_hotkey_cfg({"hotkey_main": "bogus", "hotkey_pointer": "t",
                              "hotkey_shot": ""})
ok("invalid fall back to defaults",
   out == {"hotkey_main": "ctrl+alt+t", "hotkey_pointer": "ctrl+alt+d",
           "hotkey_shot": "ctrl+alt+s", "hotkey_replace": "ctrl+alt+r"})
out = dt.validate_hotkey_cfg({"hotkey_main": "ctrl+alt+t",
                              "hotkey_pointer": "ctrl+alt+t",
                              "hotkey_shot": "ctrl+alt+s"})
ok("duplicate falls back to its default",
   out["hotkey_main"] == "ctrl+alt+t" and out["hotkey_pointer"] == "ctrl+alt+d")
out = dt.validate_hotkey_cfg({})
ok("missing keys get defaults", out == dt.DEFAULT_HOTKEYS)

# ---- 5. 坏配置经 _load_cfg 回落，程序照常能起 ----
tmp = tempfile.mkdtemp()
dt.CONFIG_PATH = os.path.join(tmp, "c.json")
dt.OLD_CONFIG_PATH = dt.CONFIG_PATH + ".old"
json.dump({"hotkey_main": "nonsense", "hotkey_pointer": "ctrl+alt+t",
           "hotkey_shot": "ctrl+alt+s", "tts_rate": 99, "auto_copy": "yes"},
          open(dt.CONFIG_PATH, "w"))
c = dt.App._load_cfg()
ok("load_cfg: bad main -> default", c["hotkey_main"] == "ctrl+alt+t")
ok("load_cfg: duplicate pointer -> default", c["hotkey_pointer"] == "ctrl+alt+d")
ok("load_cfg: tts_rate clamped", c["tts_rate"] == 10)
ok("load_cfg: auto_copy bool", c["auto_copy"] is True)
json.dump({"hotkey_main": "ctrl+shift+q", "tts_rate": -5, "auto_copy": False},
          open(dt.CONFIG_PATH, "w"))
c = dt.App._load_cfg()
ok("load_cfg: good custom kept", c["hotkey_main"] == "ctrl+shift+q"
   and c["tts_rate"] == -5 and c["auto_copy"] is False)

# ---- 6. 托盘菜单用配置里的快捷键文字 ----
items = dt.tray_menu_items({"pointer": True, "hotkey_pointer": "Ctrl+Shift+D",
                            "hotkey_shot": "Ctrl+Shift+S"}, True)
by = {i.get("id"): i for i in items if i.get("id")}
ok("tray shot label follows config", "Ctrl+Shift+S" in by["shot"]["label"])
ok("tray pointer label follows config", "Ctrl+Shift+D" in by["pointer"]["label"])
items = dt.tray_menu_items({"pointer": True}, True)
by = {i.get("id"): i for i in items if i.get("id")}
ok("tray labels fall back to defaults", "Ctrl+Alt+S" in by["shot"]["label"]
   and "Ctrl+Alt+D" in by["pointer"]["label"])

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
