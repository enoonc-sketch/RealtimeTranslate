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
    configure_common_labels(style, family, size)
    return style


def configure_common_labels(style, family, size, gray="#5b6676", accent="#0a64d8"):
    """v2.15.4：设置窗口用的说明文字 / 分组标题 / 搜索命中高亮样式，所有主题都要有。"""
    small = max(8, size - 2)
    try:
        style.configure("Note.TLabel", foreground=gray, font=(family, small))
        style.configure("Section.TLabel", foreground=gray, font=(family, max(8, size - 1), "bold"))
        style.configure("Found.TCheckbutton", foreground=accent)
        style.configure("Found.TLabel", foreground=accent, font=(family, max(8, size - 1), "bold"))
    except Exception:      # noqa: BLE001
        pass


# ---------------------------------------------------------------- v2.15.1 苹果风格（macOS 质感）
APPLE_LIGHT = {"bg": "#f5f5f7", "card": "#ffffff", "fg": "#1d1d1f", "gray": "#6e6e73",
               "border": "#d2d2d7", "hover": "#e8e8ed", "press": "#dcdce1",
               "accent": "#0071e3", "accent_hover": "#0077ed", "accent_press": "#006edb",
               "accent_fg": "#ffffff", "select": "#b3d7ff", "error": "#d70015"}
APPLE_DARK = {"bg": "#1c1c1e", "card": "#2c2c2e", "fg": "#f5f5f7", "gray": "#a1a1a6",
              "border": "#3a3a3c", "hover": "#3a3a3c", "press": "#48484a",
              "accent": "#0a84ff", "accent_hover": "#409cff", "accent_press": "#0071e3",
              "accent_fg": "#ffffff", "select": "#1f4f8f", "error": "#ff453a"}
APPLE_FONT_CANDIDATES = {
    "win": ["Microsoft YaHei UI", "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei"],
    "mac": ["PingFang SC", "SF Pro Text", "Helvetica Neue"],
    "linux": UI_FONT_CANDIDATES["linux"],
}


def apple_palette(dark=False):
    return dict(APPLE_DARK if dark else APPLE_LIGHT)


def apply_apple_style(root, family, size, dark=False):
    """苹果风格：浅灰底 + 白色卡片输入框 + 扁平按钮 + 系统蓝强调色 + 细分隔线。

    Windows 原生 vista 主题不让改按钮颜色，所以这里切到 clam（可完全自定义），
    macOS 上本来就是 aqua，同样切 clam 以保证两端外观一致。失败时静默保持原样。
    返回调色板 dict。
    """
    p = apple_palette(dark)
    style = ttk.Style(root)
    try:
        if "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:      # noqa: BLE001
        return p
    small = max(8, size - 1)
    try:
        style.configure(".", background=p["bg"], foreground=p["fg"], font=(family, small),
                        bordercolor=p["border"], lightcolor=p["bg"], darkcolor=p["bg"],
                        troughcolor=p["bg"], focuscolor=p["accent"],
                        selectbackground=p["select"], selectforeground=p["fg"],
                        fieldbackground=p["card"], insertcolor=p["fg"])
        for s in ("TFrame", "TLabelframe"):
            style.configure(s, background=p["bg"])
        style.configure("TLabelframe", bordercolor=p["border"], relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=p["bg"], foreground=p["gray"],
                        font=(family, small, "bold"))
        style.configure("TLabel", background=p["bg"], foreground=p["fg"], font=(family, small))
        style.configure("Secondary.TLabel", background=p["bg"], foreground=p["gray"])
        style.configure("Title.TLabel", background=p["bg"], foreground=p["fg"],
                        font=(family, small, "bold"))
        # 按钮：白色卡片 + 细边，悬停/按下变灰；Accent 是系统蓝主按钮
        style.configure("TButton", background=p["card"], foreground=p["fg"], relief="flat",
                        borderwidth=1, bordercolor=p["border"], lightcolor=p["card"],
                        darkcolor=p["card"], padding=(12, 5), font=(family, small),
                        focusthickness=0)
        style.map("TButton",
                  background=[("pressed", p["press"]), ("active", p["hover"]),
                              ("disabled", p["bg"])],
                  foreground=[("disabled", p["gray"])],
                  lightcolor=[("pressed", p["press"]), ("active", p["hover"])],
                  darkcolor=[("pressed", p["press"]), ("active", p["hover"])],
                  bordercolor=[("focus", p["accent"])])
        style.configure("Accent.TButton", background=p["accent"], foreground=p["accent_fg"],
                        bordercolor=p["accent"], lightcolor=p["accent"], darkcolor=p["accent"])
        style.map("Accent.TButton",
                  background=[("pressed", p["accent_press"]), ("active", p["accent_hover"])],
                  lightcolor=[("pressed", p["accent_press"]), ("active", p["accent_hover"])],
                  darkcolor=[("pressed", p["accent_press"]), ("active", p["accent_hover"])],
                  foreground=[("disabled", p["gray"])])
        # 下拉框 / 输入框
        for s in ("TCombobox", "TEntry", "TSpinbox"):
            style.configure(s, fieldbackground=p["card"], background=p["card"],
                            foreground=p["fg"], bordercolor=p["border"],
                            lightcolor=p["card"], darkcolor=p["card"], arrowcolor=p["gray"],
                            padding=(6, 4), relief="flat")
            style.map(s, bordercolor=[("focus", p["accent"])],
                      lightcolor=[("focus", p["accent"])],
                      fieldbackground=[("readonly", p["card"]), ("disabled", p["bg"])],
                      foreground=[("disabled", p["gray"])],
                      selectbackground=[("readonly", p["card"])],
                      selectforeground=[("readonly", p["fg"])])
        try:     # 下拉列表本身是 Tk Listbox，用 option 数据库换色
            root.option_add("*TCombobox*Listbox.background", p["card"])
            root.option_add("*TCombobox*Listbox.foreground", p["fg"])
            root.option_add("*TCombobox*Listbox.selectBackground", p["accent"])
            root.option_add("*TCombobox*Listbox.selectForeground", p["accent_fg"])
            root.option_add("*TCombobox*Listbox.font", (family, small))
        except Exception:      # noqa: BLE001
            pass
        # 勾选 / 单选：蓝色指示器
        for s in ("TCheckbutton", "TRadiobutton"):
            style.configure(s, background=p["bg"], foreground=p["fg"], padding=3,
                            indicatorbackground=p["card"], indicatorforeground=p["accent_fg"],
                            font=(family, small))
            style.map(s, background=[("active", p["bg"])],
                      indicatorbackground=[("selected", p["accent"]), ("pressed", p["hover"])],
                      foreground=[("disabled", p["gray"])])
        # 分段式标签页（类似 macOS 偏好设置）
        style.configure("TNotebook", background=p["bg"], borderwidth=0, tabmargins=(8, 6, 8, 0))
        style.configure("TNotebook.Tab", background=p["bg"], foreground=p["gray"],
                        bordercolor=p["bg"], lightcolor=p["bg"], padding=(14, 6),
                        font=(family, small))
        style.map("TNotebook.Tab",
                  background=[("selected", p["card"]), ("active", p["hover"])],
                  foreground=[("selected", p["fg"])],
                  lightcolor=[("selected", p["card"])],
                  bordercolor=[("selected", p["border"])])
        # 细滚动条
        for s in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
            style.configure(s, background=p["border"], troughcolor=p["card"],
                            bordercolor=p["card"], lightcolor=p["border"], darkcolor=p["border"],
                            arrowcolor=p["gray"], relief="flat", arrowsize=10)
            style.map(s, background=[("active", p["gray"]), ("pressed", p["gray"])])
        # 表格：白底、无竖线、选中系统蓝
        style.configure("Treeview", background=p["card"], fieldbackground=p["card"],
                        foreground=p["fg"], bordercolor=p["border"], relief="flat")
        style.map("Treeview", background=[("selected", p["accent"])],
                  foreground=[("selected", p["accent_fg"])])
        style.configure("Treeview.Heading", background=p["bg"], foreground=p["gray"],
                        relief="flat", bordercolor=p["border"], lightcolor=p["bg"],
                        darkcolor=p["bg"])
        style.map("Treeview.Heading", background=[("active", p["hover"])])
        style.configure("TPanedwindow", background=p["bg"])
        style.configure("Sash", sashthickness=6, gripcount=0, background=p["bg"],
                        lightcolor=p["bg"], bordercolor=p["bg"])
        style.configure("TSeparator", background=p["border"])
        style.configure("Horizontal.TProgressbar", background=p["accent"], troughcolor=p["hover"],
                        bordercolor=p["hover"], lightcolor=p["accent"], darkcolor=p["accent"])
        style.configure("TScale", background=p["bg"], troughcolor=p["hover"])
        style.configure("TEntry", padding=(6, 4))
    except Exception:      # noqa: BLE001
        pass
    configure_common_labels(style, family, size, gray=p["gray"], accent=p["accent"])
    for s_ in ("Note.TLabel", "Section.TLabel", "Found.TLabel", "Found.TCheckbutton"):
        try:
            style.configure(s_, background=p["bg"])
        except Exception:      # noqa: BLE001
            pass
    return p


def style_text_apple(widget, p, family=None, size=None):
    """tk.Text 换成苹果式「白色卡片」：无粗边框，1px 细边，聚焦时变系统蓝，内边距加大。"""
    try:
        widget.configure(background=p["card"], foreground=p["fg"], insertbackground=p["accent"],
                         relief="flat", borderwidth=0, highlightthickness=1,
                         highlightbackground=p["border"], highlightcolor=p["accent"],
                         selectbackground=p["select"], selectforeground=p["fg"],
                         padx=10, pady=8, insertwidth=2, spacing1=2, spacing3=2)
    except Exception:      # noqa: BLE001
        pass


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
