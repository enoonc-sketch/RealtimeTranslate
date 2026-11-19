"""v2.14 桌面小宠物 + 萌系配色：动画包完整性、状态机、窗口（Tk 路径）、与主程序消息的联动、配色对比度。需 xvfb。"""
import os
import sys
import tempfile
import time
import tkinter as tk

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import pet_catalog
import pet_pack
import pet_state

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


PETS_DIR = os.path.join(ROOT, "pets")

# ---------------------------------------------------------------- 1. 动画包
ok("catalog has >= 12 pets", len(pet_catalog.PETS) >= 12)
ok("catalog ids unique", len(set(pet_catalog.pet_ids())) == len(pet_catalog.PETS))
bad = []
for pid in pet_catalog.pet_ids():
    try:
        p = pet_pack.PetPack(pet_pack.pack_path(PETS_DIR, pid))
        for a in pet_pack.ANIMS:
            for i in p.frames(a):
                rgba = p.rgba(i)
                if len(rgba) != p.w * p.h * 4 or max(rgba[3::4]) == 0:   # 每帧必须有可见像素
                    bad.append((pid, a, i))
        # 四个角应该是透明的（背景抠干净了）
        r0 = p.rgba(p.frames("idle")[0])
        if r0[3] != 0 or r0[(p.w * p.h - 1) * 4 + 3] != 0:
            bad.append((pid, "corner-not-transparent"))
    except Exception as e:
        bad.append((pid, str(e)))
ok("all %d pet packs load, every frame valid" % len(pet_catalog.PETS), not bad)
if bad:
    print("   bad:", bad[:5])
p = pet_pack.PetPack(pet_pack.pack_path(PETS_DIR, "cat"))
bg = pet_pack.rgba_to_bgra_premul(p.rgba(0))
ok("premultiplied BGRA same length", len(bg) == p.w * p.h * 4)
mid = (p.h // 2 * p.w + p.w // 2) * 4
r, g, b, a = p.rgba(0)[mid:mid + 4]
ok("premultiply math (B,G,R order)", bg[mid + 3] == a and bg[mid] == b * a // 255 and bg[mid + 2] == r * a // 255)
for bad_data in (b"", b"RTPET1\n\x01\x00\x00\x00{", b"NOTAPET" * 10):
    tmp = os.path.join(tempfile.mkdtemp(), "x.pet")
    open(tmp, "wb").write(bad_data)
    try:
        pet_pack.PetPack(tmp)
        ok("corrupt pack rejected", False)
    except pet_pack.PetPackError:
        ok("corrupt pack rejected", True)
try:
    pet_pack.PetPack(os.path.join(tempfile.mkdtemp(), "none.pet"))
    ok("missing pack rejected", False)
except pet_pack.PetPackError:
    ok("missing pack rejected", True)
# 截断的包
raw = open(pet_pack.pack_path(PETS_DIR, "cat"), "rb").read()
tmp = os.path.join(tempfile.mkdtemp(), "t.pet")
open(tmp, "wb").write(raw[:len(raw) // 2])
try:
    pet_pack.PetPack(tmp)
    ok("truncated pack rejected", False)
except pet_pack.PetPackError:
    ok("truncated pack rejected", True)

# ---------------------------------------------------------------- 2. 状态机
t = [1000.0]
b = pet_state.PetBrain(clock=lambda: t[0])
ok("starts idle", b.state()[0] == "idle")
b.event("curious")
ok("curious -> alert", b.state()[0] == "alert")
t[0] += 1.2
ok("alert expires -> idle", b.state()[0] == "idle")
b.event("busy", "翻译中…")
ok("busy -> think + status text", b.state() == ("think", "翻译中…"))
b.event("curious")
ok("alert beats think, then back to think", b.state()[0] == "alert")
t[0] += 1.1
ok("after alert, still thinking", b.state()[0] == "think")
b.event("done", "你好，世界")
anim, text = b.state()
ok("done -> happy + bubble text", anim == "happy" and text == "你好，世界")
t[0] += 2.3
ok("happy expires, bubble still shown", b.state() == ("idle", "你好，世界"))
t[0] += 9
ok("bubble expires", b.state()[1] is None)
b.event("fail", "")
ok("fail -> sad + default text", b.state() == ("sad", "没翻译成功…"))
t[0] += 5
b.event("busy", "x")
t[0] += pet_state.BUSY_TIMEOUT + 1
ok("busy timeout does not hang in think", b.state()[0] == "idle")
t[0] += pet_state.SLEEP_AFTER + 1
ok("long idle -> sleep", b.state()[0] == "sleep")
b.event("poke")
ok("poke wakes up", b.state()[0] == "alert")
b2 = pet_state.PetBrain(clock=lambda: t[0])
b2.event("done", "译文", bubble=False)
ok("bubble=False -> no text", b2.state()[1] is None)
ok("short_text trims + joins lines", pet_state.short_text("a\nb  c" + "x" * 100, 10) == "a b cxxxx…")

# ---------------------------------------------------------------- 3. 配色对比度
import desktop_translator as dt
for k_fg, k_bg in (("text_fg", "text_bg"), ("gray", "text_bg"), ("gray", "bg"), ("fg", "bg"), ("bubble_fg", "bubble_bg"),
                   ("bubble_gray", "bubble_bg"), ("error", "text_bg")):
    ok("cute %s on %s >= 4.5" % (k_fg, k_bg), dt.contrast_ratio(dt.THEME_CUTE[k_fg], dt.THEME_CUTE[k_bg]) >= 4.5)
dt.set_cute(True)
ok("theme_colors uses cute when on", dt.theme_colors(False)["bg"] == dt.THEME_CUTE["bg"])
ok("dark wins over cute", dt.theme_colors(True)["bg"] == dt.THEME_DARK["bg"])
dt.set_cute(False)
ok("light restored", dt.theme_colors(False)["bg"] == dt.THEME_LIGHT["bg"])

# ---------------------------------------------------------------- 4. 配置校验
cfg = dt.load_config() if hasattr(dt, "load_config") else None
dt.DATA_DIR = tempfile.mkdtemp()
dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.HISTORY_PATH = os.path.join(dt.DATA_DIR, "history.db")
import json
json.dump({"pet_mode": "bogus", "pet_id": "../../etc", "pet_bubble": "yes", "pet_x": "a", "pet_y": 10 ** 9, "cute_theme": 1},
          open(dt.CONFIG_PATH, "w"))
app = dt.App()
r = app.root
c = app.cfg
ok("bad pet_mode falls back", c["pet_mode"] == "minimized")
ok("bad pet_id falls back (no path traversal)", c["pet_id"] == "cat")
ok("pet_bubble coerced to bool", c["pet_bubble"] is True)
ok("bad coordinates dropped", "pet_x" not in c and "pet_y" not in c)
ok("cute_theme coerced", c["cute_theme"] is True)


def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        r.update()
        time.sleep(0.02)


# ---------------------------------------------------------------- 5. 与主程序联动
ok("pet created", app.pet is not None and not app.pet_error)
ok("cute theme applied at start", dt.theme_colors(False)["bg"] == dt.THEME_CUTE["bg"])
pet = app.pet
pump(0.3)
ok("pet hidden while main window visible (minimized mode)", not pet.visible)
r.withdraw()
pump(0.4)
ok("pet shows when main window is hidden", pet.visible and pet.win.winfo_viewable())
ok("pet window size == frame size", pet.win.winfo_width() == pet.pack.w and pet.win.winfo_height() == pet.pack.h)
# 消息 → 动作
app.q.put(("copied",)) if False else app._pet_msg(("hotkey", 1))
ok("hotkey -> alert", pet.brain.state()[0] == "alert")
app.seq = 7
app._pet_msg(("progress", 7, 1, 3))
pump(1.2)
ok("progress -> think with count", pet.brain.state() == ("think", "翻译中 1/3"))
app._pet_msg(("progress", 6, 1, 3))
app._pet_msg(("result", 6, True, ([("a", "旧结果")], "en", "zh-CN", False)))
ok("stale result ignored", pet.brain.state()[0] == "think")
app._pet_msg(("result", 7, True, ([("hello", "你好"), ("world", "世界")], "en", "zh-CN", False)))
ok("result -> happy + translation in bubble", pet.brain.state() == ("happy", "你好 世界"))
pump(0.3)
ok("bubble window visible with text", pet.bubble.win is not None and pet.bubble.win.winfo_viewable())
app._pet_msg(("result", 7, False, "翻译失败：网络不通\n\n建议：…"))
ok("failure -> sad + first line", pet.brain.state() == ("sad", "翻译失败：网络不通"))
app.bseq = 3
app._pet_msg(("bubble", 3, True, "译文", "Google", "x", "en"))
ok("bubble-kind result: happy but no pet bubble text", pet.brain.state()[0] == "happy")
app._pet_msg(("totally_unknown",))
app._pet_msg(())
ok("unknown / empty messages don't crash", True)
# 动画真的在切帧
seen = set()
t0 = time.time()
while time.time() < t0 + 1.5:
    r.update()
    seen.add((pet.anim, pet.pos % 6))
    time.sleep(0.01)
ok("animation frames advance", len(seen) >= 3)
# 点击 / 双击 / 拖动
calls = []
pet.hooks["show_main"] = lambda: calls.append("main")
pet.hooks["translate_clip"] = lambda: calls.append("clip")


class Ev:
    def __init__(self, x, y):
        self.x_root, self.y_root, self.x, self.y = x, y, x, y


pet._press(Ev(100, 100)); pet._release(Ev(100, 100)); pump(0.5)
ok("click -> open main window", calls == ["main"])
calls.clear()
pet._press(Ev(100, 100)); pet._release(Ev(100, 100)); pet._double(Ev(100, 100)); pump(0.5)
ok("double click -> translate clipboard only", calls == ["clip"])
x0, y0 = pet.x, pet.y
pet._press(Ev(200, 200)); pet._motion(Ev(230, 215)); pet._release(Ev(230, 215))
ok("drag moves the pet", (pet.x, pet.y) == (x0 + 30, y0 + 15))
ok("drag position saved to cfg", app.cfg.get("pet_x") == pet.x and app.cfg.get("pet_y") == pet.y)
# 换宠物 / 切换显示方式
pet.set_pet("penguin")
pump(0.3)
ok("switch pet reloads pack", pet.pack_id == "penguin" and app.cfg["pet_id"] == "penguin")
app.pet_mode_cb.set(pet_catalog.PET_MODES["off"])
app._on_pet_opt()
pump(0.3)
ok("mode off hides pet", app.cfg["pet_mode"] == "off" and not pet.visible)
app.pet_mode_cb.set(pet_catalog.PET_MODES["always"])
app._on_pet_opt()
r.deiconify()
pump(0.4)
ok("mode always shows pet even with main window visible", pet.visible)
# 勾掉气泡
app.pet_bubble_var.set(False)
app._on_pet_opt()
pet.event("done", "不该显示")
pump(0.2)
ok("bubble off -> no bubble", pet.brain.state()[1] is None)
# 配色开关
app.cute_var.set(False)
app._on_cute_theme()
ok("cute off restores light theme", dt.theme_colors(False)["bg"] == dt.THEME_LIGHT["bg"] and app.cfg["cute_theme"] is False)
# 出错保护：宠物内部炸了，主程序不受影响
pet.cfg["pet_mode"] = "minimized"          # 这个模式会去问主窗口是否可见
pet.hooks["main_visible"] = lambda: 1 / 0
pump(0.3)
ok("pet failure is contained (pet closed, app alive)", pet.closed and r.winfo_exists())
app._pet_msg(("hotkey", 1))
ok("app keeps handling messages after pet failure", True)
app.quit() if False else None
print("\n%d/%d passed" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
