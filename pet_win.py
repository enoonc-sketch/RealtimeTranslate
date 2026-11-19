"""桌面小宠物窗口。

- Windows：用"逐像素透明"的分层窗口（UpdateLayeredWindow，纯 ctypes），边缘平滑、透明处点击会穿过去；
- 其它系统 / 分层窗口失败：退回普通 Tk 画布（Windows 上用 -transparentcolor 抠色），功能不变；
- 整个模块出任何错都不应该影响翻译主程序（调用方把它包在 try 里，出错就关掉宠物）。

交互：拖动换位置；单击 → 打开翻译窗口；双击 → 翻译剪贴板；右键 → 菜单（换宠物 / 显示方式 / 气泡 / 退出）。
"""
import random
import sys
import time
import tkinter as tk

import pet_catalog
import pet_pack
import pet_state

IS_WIN = sys.platform == "win32"
KEY = "#ff00fe"                       # 抠色用的"透明色"（Windows 回退路径）
# 每个动画每帧停留多久（毫秒）：做成"逐帧动画"的可爱节奏
FRAME_MS = {"idle": 430, "blink": 130, "sleep": 650, "think": 300, "happy": 105, "sad": 480, "alert": 150}
IDLE_PINGPONG = (0, 1, 2, 3, 2, 1)
MARGIN = 28


# ---------------------------------------------------------------- Windows 分层窗口（逐像素透明）
class LayeredWindow:
    """把一个 Tk 顶层窗口变成逐像素透明的分层窗口。任何一步失败都抛异常，由调用方退回普通画布。"""

    def __init__(self, win, w, h):
        import ctypes
        from ctypes import wintypes as wt
        self.ct, self.wt = ctypes, wt
        self.w, self.h = w, h
        u32, g32 = ctypes.windll.user32, ctypes.windll.gdi32
        self.u32, self.g32 = u32, g32
        win.update_idletasks()
        u32.GetParent.argtypes = [wt.HWND]
        u32.GetParent.restype = wt.HWND
        child = win.winfo_id()
        hwnd = u32.GetParent(child) or child
        self.hwnd = hwnd

        class BIH(ctypes.Structure):
            _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                        ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                        ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                        ("biClrImportant", wt.DWORD)]

        class BMI(ctypes.Structure):
            _fields_ = [("bmiHeader", BIH), ("bmiColors", wt.DWORD * 1)]

        class BLEND(ctypes.Structure):
            _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                        ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

        class SIZE(ctypes.Structure):
            _fields_ = [("cx", wt.LONG), ("cy", wt.LONG)]

        self._BLEND, self._SIZE = BLEND, SIZE
        u32.GetWindowLongW.restype = wt.LONG
        u32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
        u32.SetWindowLongW.restype = wt.LONG
        u32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, wt.LONG]
        GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TOOLWINDOW = -20, 0x00080000, 0x00000080
        style = u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        u32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TOOLWINDOW)
        g32.CreateCompatibleDC.restype = wt.HDC
        g32.CreateDIBSection.restype = wt.HBITMAP
        g32.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
        g32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
        g32.SelectObject.restype = wt.HGDIOBJ      # 64 位下句柄要用指针宽度，不能用默认的 int
        u32.GetParent.argtypes = [wt.HWND]
        u32.GetParent.restype = wt.HWND
        self.memdc = g32.CreateCompatibleDC(None)
        if not self.memdc:
            raise OSError("CreateCompatibleDC 失败")
        bmi = BMI()
        bmi.bmiHeader.biSize = ctypes.sizeof(BIH)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h              # 负数 = 自上而下
        bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount, bmi.bmiHeader.biCompression = 1, 32, 0
        bits = ctypes.c_void_p()
        self.hbmp = g32.CreateDIBSection(self.memdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        if not self.hbmp or not bits.value:
            raise OSError("CreateDIBSection 失败")
        self.bits = bits.value
        self.old = g32.SelectObject(self.memdc, self.hbmp)
        self.alive = True

    def update(self, bgra, x, y):
        """把一帧（BGRA 预乘）画到屏幕 (x, y)。"""
        ct, wt = self.ct, self.wt
        if not self.alive:
            return
        ct.memmove(self.bits, bgra, len(bgra))
        pt, src, size = wt.POINT(int(x), int(y)), wt.POINT(0, 0), self._SIZE(self.w, self.h)
        blend = self._BLEND(0, 0, 255, 1)        # AC_SRC_OVER, 255, AC_SRC_ALPHA
        self.u32.UpdateLayeredWindow.argtypes = [wt.HWND, wt.HDC, ct.POINTER(wt.POINT), ct.POINTER(self._SIZE), wt.HDC,
                                                 ct.POINTER(wt.POINT), wt.COLORREF, ct.POINTER(self._BLEND), wt.DWORD]
        ok = self.u32.UpdateLayeredWindow(self.hwnd, None, ct.byref(pt), ct.byref(size), self.memdc,
                                          ct.byref(src), 0, ct.byref(blend), 2)   # ULW_ALPHA
        if not ok:
            raise OSError("UpdateLayeredWindow 失败")

    def close(self):
        if not self.alive:
            return
        self.alive = False
        try:
            self.g32.SelectObject(self.memdc, self.old)
            self.g32.DeleteObject(self.hbmp)
            self.g32.DeleteDC(self.memdc)
        except Exception:
            pass


# ---------------------------------------------------------------- 气泡
class Bubble:
    """宠物头顶的对话气泡（显示译文）。Tk 画布画圆角框；Windows 用抠色透明。"""

    def __init__(self, root, get_theme):
        self.root, self.get_theme = root, get_theme
        self.win = None
        self.text = None

    def _ensure(self):
        if self.win is not None:
            return
        w = tk.Toplevel(self.root)
        w.withdraw()
        w.overrideredirect(True)
        try:
            w.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.cv = tk.Canvas(w, highlightthickness=0, bd=0)
        self.cv.pack()
        self.cv.bind("<Button-1>", lambda e: self.hide())
        self.win = w

    def show(self, text, pet_x, pet_y, pet_w):
        if not text:
            self.hide()
            return
        self._ensure()
        th = self.get_theme()
        bg, fg, edge = th.get("bubble_bg", "#fffdf6"), th.get("bubble_fg", "#111"), th.get("border", "#c9ced6")
        if self.text != text or getattr(self, "_theme", None) != (bg, fg, edge):
            self.text, self._theme = text, (bg, fg, edge)
            cv = self.cv
            cv.delete("all")
            cv.configure(bg=KEY if IS_WIN else th.get("bg", "#f0f0f0"))
            t = cv.create_text(14, 10, text=text, anchor="nw", width=220, fill=fg, font=("Microsoft YaHei UI", 10))
            x0, y0, x1, y1 = cv.bbox(t)
            bw, bh = x1 - x0 + 28, y1 - y0 + 20
            r, tail = 12, 10
            pts = [r, 0, bw - r, 0, bw, 0, bw, r, bw, bh - r, bw, bh, bw - r, bh, bw // 2 + 8, bh, bw // 2, bh + tail,
                   bw // 2 - 8, bh, r, bh, 0, bh, 0, bh - r, 0, r, 0, 0]
            cv.create_polygon(pts, smooth=True, fill=bg, outline=edge, width=1, tags="bg")
            cv.tag_lower("bg")
            cv.configure(width=bw + 2, height=bh + tail + 2)
            self._size = (bw + 2, bh + tail + 2)
            if IS_WIN:
                try:
                    self.win.attributes("-transparentcolor", KEY)
                except tk.TclError:
                    pass
        bw, bh = self._size
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = max(4, min(sw - bw - 4, pet_x + pet_w // 2 - bw // 2))
        y = pet_y - bh + 6
        if y < 4:
            y = pet_y + pet_w - 6
        self.win.geometry("%dx%d+%d+%d" % (bw, bh, x, y))
        self.win.deiconify()
        self.win.lift()

    def hide(self):
        self.text = None
        if self.win is not None:
            try:
                self.win.withdraw()
            except tk.TclError:
                pass

    def destroy(self):
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None


# ---------------------------------------------------------------- 宠物窗口
class PetWindow:
    """hooks: show_main() 打开翻译窗口 | translate_clip() 翻译剪贴板 | shot() 截图翻译 | quit() 退出
              main_visible() 主窗口现在看得见吗 | get_theme() 当前配色 | save() 保存设置
       cfg: 程序的配置字典（读 pet_mode / pet_id / pet_bubble / pet_x / pet_y，写 pet_x / pet_y / 设置项）"""

    def __init__(self, root, pets_dir, cfg, hooks, clock=time.monotonic):
        self.root, self.pets_dir, self.cfg, self.hooks, self.clock = root, pets_dir, cfg, hooks, clock
        self.brain = pet_state.PetBrain(clock)
        self.pack = None
        self.pack_id = None
        self.win = self.canvas = self.layered = None
        self.bubble = Bubble(root, hooks["get_theme"])
        self.visible = False
        self.anim, self.pos, self.frame_i = "idle", 0, 0
        self.next_at = 0.0
        self.next_blink = clock() + 4
        self.blink_until = 0.0
        self._photos = {}
        self._premul = {}
        self._drag = None
        self._click_job = None
        self._after = None
        self.x = self.y = None
        self.closed = False
        self.fallback_reason = None

    # ---------- 对外接口
    def start(self):
        self._tick()

    def event(self, kind, text="", bubble=True):
        self.brain.event(kind, text, bubble=bubble and bool(self.cfg.get("pet_bubble", True)))

    def refresh_pet(self):
        """换了宠物 / 配色：重新载入动画包并重画。"""
        self.pack = None
        self._photos.clear()
        self._premul.clear()
        self._draw(force=True)

    def close(self):
        self.closed = True
        if self._after is not None:
            try:
                self.root.after_cancel(self._after)
            except Exception:
                pass
        if self.layered is not None:
            self.layered.close()
        self.bubble.destroy()
        if self.win is not None:
            try:
                self.win.destroy()
            except tk.TclError:
                pass
            self.win = None

    # ---------- 载入动画包
    def _load_pack(self):
        pid = self.cfg.get("pet_id", pet_catalog.DEFAULT_PET)
        if pid not in pet_catalog.pet_ids():
            pid = pet_catalog.DEFAULT_PET
        if self.pack is not None and self.pack_id == pid:
            return self.pack
        try:
            self.pack = pet_pack.PetPack(pet_pack.pack_path(self.pets_dir, pid))
        except pet_pack.PetPackError:
            self.pack = pet_pack.PetPack(pet_pack.pack_path(self.pets_dir, pet_catalog.DEFAULT_PET))
            pid = pet_catalog.DEFAULT_PET
        self.pack_id = pid
        self._photos.clear()
        self._premul.clear()
        return self.pack

    # ---------- 窗口
    def _default_pos(self):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        return sw - 112 - 48, sh - 112 - 96

    def _clamp(self, x, y):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w = self.pack.w if self.pack else 112
        return max(-w + MARGIN, min(sw - MARGIN, int(x))), max(0, min(sh - MARGIN, int(y)))

    def _create(self):
        pack = self._load_pack()
        w = tk.Toplevel(self.root)
        w.withdraw()
        w.overrideredirect(True)
        try:
            w.attributes("-topmost", True)
        except tk.TclError:
            pass
        px, py = self.cfg.get("pet_x"), self.cfg.get("pet_y")
        if not isinstance(px, int) or not isinstance(py, int):
            px, py = self._default_pos()
        self.x, self.y = self._clamp(px, py)
        w.geometry("%dx%d+%d+%d" % (pack.w, pack.h, self.x, self.y))
        self.win = w
        self.canvas = tk.Canvas(w, width=pack.w, height=pack.h, highlightthickness=0, bd=0, bg=KEY if IS_WIN else self.hooks["get_theme"]().get("bg", "#f0f0f0"))
        self.canvas.pack()
        self.img_item = self.canvas.create_image(0, 0, anchor="nw")
        for seq, fn in (("<ButtonPress-1>", self._press), ("<B1-Motion>", self._motion), ("<ButtonRelease-1>", self._release),
                        ("<Double-Button-1>", self._double), ("<Button-3>", self._menu)):
            self.canvas.bind(seq, fn)
        w.deiconify()
        if IS_WIN:
            try:
                self.layered = LayeredWindow(w, pack.w, pack.h)
                self.canvas.pack_forget()      # 分层窗口不用 Tk 画布画画面
            except Exception as e:             # 任何一步失败：退回抠色画布
                self.layered = None
                self.fallback_reason = "分层窗口不可用：%s" % e
                try:
                    w.attributes("-transparentcolor", KEY)
                except tk.TclError:
                    pass
        self._draw(force=True)

    def _show(self):
        if self.win is None:
            self._create()
        else:
            self.win.deiconify()
            self.win.lift()
        self.visible = True

    def _hide(self):
        self.visible = False
        self.bubble.hide()
        if self.win is not None:
            self.win.withdraw()

    # ---------- 画面
    def _draw(self, force=False):
        if self.win is None:
            return
        pack = self._load_pack()
        frames = pack.frames("blink" if self.anim == "blink" else self.anim)
        idx = frames[self._frame_slot(frames) % len(frames)]
        if self.layered is not None:
            bgra = self._premul.get(idx)
            if bgra is None:
                bgra = self._premul[idx] = pet_pack.rgba_to_bgra_premul(pack.rgba(idx))
            try:
                self.layered.update(bgra, self.x, self.y)
            except Exception as e:             # 画不了了：永久退回画布
                self.fallback_reason = "分层窗口更新失败：%s" % e
                self.layered.close()
                self.layered = None
                self.canvas.pack()
                try:
                    self.win.attributes("-transparentcolor", KEY)
                except tk.TclError:
                    pass
                return self._draw(force=True)
        else:
            ph = self._photos.get(idx)
            if ph is None:
                ph = self._photos[idx] = tk.PhotoImage(data=pet_pack.rgba_to_b64png(pack.w, pack.h, pack.rgba(idx)))
            self.canvas.itemconfig(self.img_item, image=ph)

    def _frame_slot(self, frames):
        if self.anim == "idle":
            return IDLE_PINGPONG[self.pos % len(IDLE_PINGPONG)]
        return self.pos

    # ---------- 主循环
    def _want_visible(self):
        mode = self.cfg.get("pet_mode", "minimized")
        if mode == "always":
            return True
        if mode == "minimized":
            return not self.hooks["main_visible"]()
        return False

    def _tick(self):
        if self.closed:
            return
        try:
            now = self.clock()
            want = self._want_visible()
            if want and not self.visible:
                self._show()
            elif not want and self.visible:
                self._hide()
            if self.visible:
                anim, text = self.brain.state(now)
                if anim == "idle":                     # 发呆时偶尔眨一下眼
                    if now >= self.next_blink:
                        self.blink_until = now + 0.15
                        self.next_blink = now + 3.5 + random.random() * 3
                    if now < self.blink_until:
                        anim = "blink"
                if anim != self.anim:
                    self.anim, self.pos, self.next_at = anim, 0, 0.0
                if now >= self.next_at:
                    self.next_at = now + FRAME_MS.get(self.anim, 300) / 1000.0
                    self._draw()
                    self.pos += 1
                if text and self.cfg.get("pet_bubble", True) and not self.hooks["main_visible"]():
                    self.bubble.show(text, self.x, self.y, self.pack.w)
                else:
                    self.bubble.hide()
        except Exception as e:                 # 宠物出任何问题都不能影响翻译主程序
            self.fallback_reason = "宠物出错已停用：%s" % e
            self.closed = True
            try:
                self.close()
            except Exception:
                pass
            return
        self._after = self.root.after(45, self._tick)

    # ---------- 鼠标
    def _press(self, e):
        self.brain.wake()
        self._drag = {"sx": e.x_root, "sy": e.y_root, "x": self.x, "y": self.y, "moved": False}

    def _motion(self, e):
        d = self._drag
        if not d:
            return
        dx, dy = e.x_root - d["sx"], e.y_root - d["sy"]
        if abs(dx) + abs(dy) > 4:
            d["moved"] = True
        if d["moved"]:
            self.x, self.y = self._clamp(d["x"] + dx, d["y"] + dy)
            self.win.geometry("+%d+%d" % (self.x, self.y))
            if self.layered is not None:
                self._draw()

    def _release(self, e):
        d, self._drag = self._drag, None
        if not d:
            return
        if d["moved"]:
            self.cfg["pet_x"], self.cfg["pet_y"] = self.x, self.y
            self.hooks["save"]()
        else:                                   # 单击：等一下，看是不是双击
            if self._click_job is not None:
                self.root.after_cancel(self._click_job)
            self._click_job = self.root.after(260, self._single)

    def _single(self):
        self._click_job = None
        self.brain.event("poke")
        self.hooks["show_main"]()

    def _double(self, e):
        if self._click_job is not None:
            self.root.after_cancel(self._click_job)
            self._click_job = None
        self.brain.event("curious")
        self.hooks["translate_clip"]()

    def _menu(self, e):
        m = tk.Menu(self.win, tearoff=0)
        m.add_command(label="打开翻译窗口", command=self.hooks["show_main"])
        m.add_command(label="翻译剪贴板", command=self.hooks["translate_clip"])
        m.add_command(label="截图翻译", command=self.hooks["shot"])
        m.add_separator()
        sub = tk.Menu(m, tearoff=0)
        cur = tk.StringVar(master=self.root, value=self.cfg.get("pet_id", pet_catalog.DEFAULT_PET))
        self._menu_vars = [cur]
        for pid, _, _ in pet_catalog.PETS:
            sub.add_radiobutton(label=pet_catalog.pet_display(pid), variable=cur, value=pid, command=lambda p=pid: self.set_pet(p))
        m.add_cascade(label="换个小宠物", menu=sub)
        mode = tk.StringVar(master=self.root, value=self.cfg.get("pet_mode", "minimized"))
        self._menu_vars.append(mode)
        for code, name in pet_catalog.PET_MODES.items():
            if code != "off":
                m.add_radiobutton(label=name, variable=mode, value=code, command=lambda c=code: self.set_mode(c))
        bub = tk.BooleanVar(master=self.root, value=bool(self.cfg.get("pet_bubble", True)))
        self._menu_vars.append(bub)
        m.add_checkbutton(label="用气泡显示译文", variable=bub, command=lambda: self.set_bubble(bub.get()))
        m.add_separator()
        m.add_command(label="隐藏小宠物", command=lambda: self.set_mode("off"))
        m.add_command(label="退出翻译软件", command=self.hooks["quit"])
        try:
            self.win.focus_force()
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    # ---------- 设置
    def set_pet(self, pid):
        self.cfg["pet_id"] = pid
        self.hooks["save"]()
        self.brain.event("curious")
        self.refresh_pet()

    def set_mode(self, mode):
        self.cfg["pet_mode"] = mode
        self.hooks["save"]()
        if self.hooks.get("mode_changed"):
            self.hooks["mode_changed"](mode)

    def set_bubble(self, on):
        self.cfg["pet_bubble"] = bool(on)
        self.hooks["save"]()
        if not on:
            self.bubble.hide()
