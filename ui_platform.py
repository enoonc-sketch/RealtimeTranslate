"""跨系统界面适配（v2.13）：让所有面板在 Windows / macOS / Linux、不同分辨率与缩放下都能用。

做了五件事：
  1. 字体：按系统给候选名单，用 tkinter.font.families() 实际挑一个本机有的（以前写死
     "Microsoft YaHei UI" / "PingFang SC" / "Noto Sans CJK SC"，没有就回退到难看的默认字体）。
  2. 窗口：fit_window / clamp_geometry 把窗口尺寸夹到屏幕可用范围内并居中，
     换了显示器、导入别的电脑的设置、小屏笔记本都不会出现窗口一半在屏幕外。
  3. 换行：FlowFrame 让一排按钮 / 复选框放不下时自动折到下一行（以前是一整行横排，
     窗口一窄右边的按钮就被裁掉；为了不裁，最小宽度被撑得很宽，小屏放不下）。
  4. 滚动：ScrollFrame 让设置页内容比窗口高时可以滚（大字号 / 小屏 / 高缩放时不再被截断）。
  5. 样式：按系统选 ttk 主题（Windows vista、macOS aqua、Linux clam），表格行高跟字体走。

纯 tkinter / 标准库；除 pick_family 需要 Tk 之外，其余计算函数不依赖 Tk，可以单独测试。
"""
import re
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

# 界面字体候选（前面的优先）：中文显示好看、各系统常见
UI_FONT_CANDIDATES = {
    "win": ["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "SimHei", "Arial"],
    "mac": ["PingFang SC", "Hiragino Sans GB", "Helvetica Neue", "Arial Unicode MS", "Helvetica"],
    "linux": ["Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans SC", "WenQuanYi Micro Hei",
              "WenQuanYi Zen Hei", "Droid Sans Fallback", "DejaVu Sans", "Liberation Sans"],
}
MONO_FONT_CANDIDATES = {
    "win": ["Consolas", "Cascadia Mono", "Courier New"],
    "mac": ["Menlo", "SF Mono", "Monaco", "Courier"],
    "linux": ["DejaVu Sans Mono", "Noto Sans Mono", "Liberation Mono", "monospace"],
}
BASE_SIZE = {"win": 11, "mac": 13, "linux": 11}
SCREEN_MARGIN = 60          # 窗口离屏幕边缘至少留这么多像素（任务栏 / Dock / 菜单栏）


def os_key():
    return "win" if IS_WIN else ("mac" if IS_MAC else "linux")


def pick_family(root, candidates, fallback="TkDefaultFont"):
    """从候选里挑第一个本机装了的字体；都没有就用 Tk 的默认字体名。"""
    try:
        have = {f.lower() for f in tkfont.families(root)}
    except Exception:      # noqa: BLE001
        have = set()
    for name in candidates:
        if name.lower() in have:
            return name
    return fallback


def ui_family(root):
    return pick_family(root, UI_FONT_CANDIDATES[os_key()])


def mono_family(root):
    return pick_family(root, MONO_FONT_CANDIDATES[os_key()], fallback="TkFixedFont")


def base_size():
    return BASE_SIZE[os_key()]


# ---------------------------------------------------------------- 窗口尺寸 / 位置
_GEOM = re.compile(r"^(\d+)x(\d+)(?:([+-])(-?\d+)([+-])(-?\d+))?$")


def parse_geometry(s):
    """'620x760+100+50' -> (620, 760, 100, 50)；没有位置时后两项是 None；格式不对返回 None。"""
    m = _GEOM.match(str(s or "").strip())
    if not m:
        return None
    w, h = int(m.group(1)), int(m.group(2))
    if m.group(3) is None:
        return w, h, None, None
    x, y = int(m.group(4)), int(m.group(6))
    if m.group(3) == "-":
        x = -x
    if m.group(5) == "-":
        y = -y
    return w, h, x, y


def clamp_geometry(geom, sw, sh, margin=SCREEN_MARGIN, min_w=360, min_h=300):
    """把窗口几何字符串夹进 (sw × sh) 的屏幕：尺寸不超过屏幕减边距，位置保证窗口主体可见。

    位置若让窗口大半跑到屏幕外（换显示器 / 导入别的电脑的设置），就丢掉位置交给系统居中。
    返回新的几何字符串。解析不了返回 None（调用方用默认值）。
    """
    p = parse_geometry(geom)
    if p is None:
        return None
    w, h, x, y = p
    w = max(min_w, min(w, max(min_w, sw - margin)))
    h = max(min_h, min(h, max(min_h, sh - margin)))
    if x is None or y is None:
        return "%dx%d" % (w, h)
    # 窗口至少 1/2 宽、标题栏附近要在屏幕内；否则丢弃位置
    off_screen = (x + w // 2 < 0 or x > sw - w // 2 or y < -10 or y > sh - 60)
    if off_screen:
        return "%dx%d" % (w, h)
    return "%dx%d%+d%+d" % (w, h, x, y)


def centered_geometry(w, h, sw, sh, parent_rect=None, margin=SCREEN_MARGIN):
    """给出居中（相对 parent_rect=(x,y,w,h) 或整个屏幕）的几何字符串，尺寸已夹进屏幕。"""
    w = max(1, min(w, sw - margin))
    h = max(1, min(h, sh - margin))
    if parent_rect:
        px, py, pw, ph = parent_rect
        x, y = px + (pw - w) // 2, py + (ph - h) // 2
    else:
        x, y = (sw - w) // 2, (sh - h) // 3
    x = max(0, min(x, sw - w))
    y = max(0, min(y, sh - h - 30))
    return "%dx%d%+d%+d" % (w, h, x, y)


def fit_window(win, w, h, min_w=None, min_h=None, parent=None):
    """给 Toplevel 设大小：按屏幕可用范围收缩，并居中在父窗口（或屏幕）上；minsize 也夹进屏幕。"""
    try:
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    except Exception:      # noqa: BLE001
        return
    rect = None
    if parent is not None:
        try:
            if parent.winfo_viewable():
                rect = (parent.winfo_rootx(), parent.winfo_rooty(), parent.winfo_width(), parent.winfo_height())
        except Exception:      # noqa: BLE001
            rect = None
    try:
        win.geometry(centered_geometry(w, h, sw, sh, rect))
        if min_w or min_h:
            win.minsize(min(min_w or 1, sw - SCREEN_MARGIN), min(min_h or 1, sh - SCREEN_MARGIN))
    except Exception:      # noqa: BLE001
        pass


# ---------------------------------------------------------------- ttk 样式
def pick_theme(style):
    """Windows 用原生 vista，macOS 用 aqua，Linux 用 clam（默认 'default' 在 Linux 上很丑）。"""
    want = {"win": ("vista", "xpnative", "clam"), "mac": ("aqua", "clam"),
            "linux": ("clam", "alt", "default")}[os_key()]
    try:
        have = set(style.theme_names())
        for t in want:
            if t in have:
                style.theme_use(t)
                return t
    except Exception:      # noqa: BLE001
        pass
    return None


def apply_styles(root, family, size):
    """按字体大小设置 ttk 样式：控件内边距、表格行高（以前固定 20px，大字号 / 高缩放会把字切掉）。"""
    style = ttk.Style(root)
    try:
        f = tkfont.Font(root=root, family=family, size=size)
        line = int(f.metrics("linespace"))
    except Exception:      # noqa: BLE001
        line = size * 2
    try:
        style.configure("Treeview", rowheight=max(20, line + 8), font=(family, max(8, size - 1)))
        style.configure("Treeview.Heading", font=(family, max(8, size - 1), "bold"))
        style.configure("TCombobox", padding=2)
        style.configure("TButton", padding=(8, 3))
        style.configure("TCheckbutton", padding=2)
        style.configure("TLabel", font=(family, max(8, size - 1)))
        style.configure("TCheckbutton", font=(family, max(8, size - 1)))
        style.configure("TButton", font=(family, max(8, size - 1)))
        style.configure("TRadiobutton", font=(family, max(8, size - 1)))
        style.configure("TLabelframe.Label", font=(family, max(8, size - 1)))
        style.configure("TNotebook.Tab", font=(family, max(8, size - 1)), padding=(10, 4))
    except Exception:      # noqa: BLE001
        pass
    return style


# ---------------------------------------------------------------- 自动换行的一排控件
def flow_layout(widths, avail, hgap=6):
    """贪心换行：widths 是每个控件的宽度，avail 是可用宽度。返回 [(行, 列), ...]。纯函数。"""
    pos, row, col, used = [], 0, 0, 0
    for w in widths:
        need = w + (hgap if col else 0)
        if col and used + need > avail:
            row, col, used, need = row + 1, 0, 0, w
        pos.append((row, col))
        used += need
        col += 1
    return pos


class FlowFrame(ttk.Frame):
    """一排控件，放不下时自动折行。用法：f = FlowFrame(parent); f.add(widget); ...

    控件的父窗口必须是这个 FlowFrame。宽度变化时自动重排；字号变了可手动 relayout()。
    """

    def __init__(self, parent, hgap=6, vgap=3, **kw):
        super().__init__(parent, **kw)
        self._items = []
        self._hgap, self._vgap = hgap, vgap
        self._last_w = -1
        self.bind("<Configure>", self._on_configure)

    def add(self, widget, **_ignored):
        self._items.append(widget)
        self._place_all(max(self.winfo_width(), 1) if self.winfo_ismapped() else 100000)
        return widget

    def min_width(self):
        """最宽那个控件的宽度（窗口最小宽度参考：再窄就有控件放不下一整行了）。"""
        try:
            self.update_idletasks()
            return max([w.winfo_reqwidth() for w in self._items] or [0])
        except Exception:      # noqa: BLE001
            return 0

    def relayout(self):
        self._last_w = -1
        self._place_all(max(self.winfo_width(), 1))

    def _on_configure(self, e):
        if e.width != self._last_w:
            self._place_all(e.width)

    def _place_all(self, avail):
        self._last_w = avail
        try:
            widths = [w.winfo_reqwidth() for w in self._items]
        except tk.TclError:
            return
        pos = flow_layout(widths, avail - 4, self._hgap)
        # 用 place 逐个摆（grid 的同一列会按全部行里最宽的撑开，折行后会把行撑出窗口）
        try:
            heights = [w.winfo_reqheight() for w in self._items]
        except tk.TclError:
            return
        rowh = max(heights or [0])
        xs, cur_row, x = [], -1, 0
        for w, wd, (r, c) in zip(self._items, widths, pos):
            if r != cur_row:
                cur_row, x = r, 0
            w.place(x=x, y=r * (rowh + self._vgap))
            x += wd + self._hgap
        nrows = (pos[-1][0] + 1) if pos else 0
        self.configure(height=max(1, nrows * rowh + max(0, nrows - 1) * self._vgap))
        if getattr(self, "_widths", None) != widths:      # 控件宽度还在变（主题 / 字体刚应用）：空闲时再排一次
            self._widths = widths
            try:
                self.after(30, lambda: self._place_all(max(self.winfo_width(), 1)))
            except tk.TclError:
                pass


# ---------------------------------------------------------------- 可滚动的页面
def wheel_units(event):
    """跨系统的鼠标滚轮：Windows delta 是 120 的倍数，macOS 是 1~几，Linux(X11) 用 Button-4/5。"""
    if getattr(event, "num", None) == 4:
        return -1
    if getattr(event, "num", None) == 5:
        return 1
    d = getattr(event, "delta", 0)
    if not d:
        return 0
    if IS_MAC:
        return -1 if d > 0 else 1
    return -1 if d > 0 else 1 if d < 0 else 0


class ScrollFrame(ttk.Frame):
    """内容比窗口高时出现滚动条的容器。往 .body 里放控件（pack / grid 都行）。"""

    def __init__(self, parent, padding=14, **kw):
        super().__init__(parent, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._on_yscroll)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas, padding=padding)
        self._win = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._on_body)
        self.canvas.bind("<Configure>", self._on_canvas)
        for w in (self.canvas, self.body):
            w.bind("<Enter>", self._bind_wheel)
            w.bind("<Leave>", self._unbind_wheel)
        self._needs_bar = False

    def _on_yscroll(self, lo, hi):
        self.vsb.set(lo, hi)
        need = not (float(lo) <= 0.0 and float(hi) >= 1.0)
        if need != self._needs_bar:
            self._needs_bar = need
            if need:
                self.vsb.pack(side="right", fill="y", before=self.canvas)
            else:
                self.vsb.pack_forget()

    def _on_body(self, _e=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, e):
        self.canvas.itemconfigure(self._win, width=e.width)

    def _bind_wheel(self, _e=None):
        top = self.winfo_toplevel()
        top.bind_all("<MouseWheel>", self._on_wheel)
        top.bind_all("<Button-4>", self._on_wheel)
        top.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self, _e=None):
        top = self.winfo_toplevel()
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            try:
                top.unbind_all(seq)
            except Exception:      # noqa: BLE001
                pass

    def _on_wheel(self, e):
        if not self._needs_bar:
            return
        u = wheel_units(e)
        if u:
            self.canvas.yview_scroll(u * 2, "units")


def autowrap(label, pad=24, minimum=200):
    """让 Label 的换行宽度跟着窗口宽度走（以前 wraplength 写死 520~660，窗口收窄就溢出）。"""
    def _fit(e):
        try:
            label.configure(wraplength=max(minimum, e.width - pad))
        except tk.TclError:
            pass
    label.bind("<Configure>", _fit)
    return label
