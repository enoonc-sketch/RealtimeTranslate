"""Windows 系统托盘图标 — 只用 Python 标准库 ctypes，不依赖 pystray / Pillow。

原理：直接调 shell32.Shell_NotifyIconW 往托盘加图标，图标文件就是
程序自带的 app.ico（LoadImageW 直接读 .ico，不用 Pillow 转格式）；
右键菜单用 user32.CreatePopupMenu / TrackPopupMenu，消息循环跑在
一个守护线程里。

接口（和 App 对接，见 desktop_translator.py）：
    tray = TrayIcon(icon_path, tooltip,
                    on_show=..., on_screenshot=..., on_quit=...)
    tray.start()   # 成功 True，失败 / 非 Windows 返回 False，绝不抛异常
    tray.stop()    # 删图标、关消息窗口、等线程退出
    tray.is_running()
    tray.notify(title, text)   # 托盘气泡，可选

注意：回调在托盘线程里被调用，绝不能直接碰 Tk。主程序传进来的
回调只做 queue.Queue.put，真正的 show/quit 由 App._poll 在 Tk
线程里处理（和 start_hotkey_win 的做法一样）。

非 Windows 上 import 安全：start() 直接返回 False。
"""

import os
import sys
import threading

IS_WIN = sys.platform.startswith("win")


def available():
    return IS_WIN


# 菜单项 id
_ID_SHOW = 1001
_ID_SHOT = 1002
_ID_QUIT = 1003

_WM_TRAY = 0x0401            # WM_USER + 1，托盘回调消息
_WM_COMMAND = 0x0111
_WM_DESTROY = 0x0002
_WM_CLOSE = 0x0010
_NIM_ADD = 0x00000000
_NIM_MODIFY = 0x00000001
_NIM_DELETE = 0x00000002
_NIF_MESSAGE = 0x00000001
_NIF_ICON = 0x00000002
_NIF_TIP = 0x00000004
_NIF_INFO = 0x00000010
_NIIF_INFO = 0x00000001
_IMAGE_ICON = 1
_LR_LOADFROMFILE = 0x00000010
_LR_DEFAULTSIZE = 0x00000040
_IDI_APPLICATION = 32512
_MF_STRING = 0x00000000
_MF_SEPARATOR = 0x00000800
_TPM_RIGHTBUTTON = 0x0002
_TPM_RETURNCMD = 0x0100


class TrayIcon:
    def __init__(self, icon_path=None, tooltip="实时翻译",
                 on_show=None, on_screenshot=None, on_quit=None):
        self.icon_path = icon_path
        self.tooltip = tooltip or "实时翻译"
        self.on_show = on_show
        self.on_screenshot = on_screenshot
        self.on_quit = on_quit
        self._thread = None
        self._hwnd = None
        self._hicon = None
        self._ready = threading.Event()
        self._started = False
        # 下面这些引用必须留在实例上：ctypes 回调 / 结构体被 GC 掉
        # 会导致托盘窗口收不到消息甚至崩溃。
        self._wndproc = None
        self._wndclass = None
        self._taskbar_created_msg = 0

    def is_running(self):
        return bool(self._started and self._thread is not None
                    and self._thread.is_alive())

    def start(self):
        """启动托盘。成功 True；非 Windows 或任何一步失败返回 False。"""
        if not IS_WIN or self.is_running():
            return self.is_running()
        try:
            self._ready.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            self._ready.wait(5)
            return self.is_running()
        except Exception:
            return False

    def stop(self):
        if not self._thread:
            return
        try:
            import ctypes
            if self._hwnd:
                ctypes.windll.user32.PostMessageW(self._hwnd, _WM_CLOSE, 0, 0)
        except Exception:
            pass
        try:
            self._thread.join(2)
        except Exception:
            pass
        self._thread = None
        self._hwnd = None
        self._started = False

    def set_tooltip(self, text):
        if not self.is_running() or not self._hwnd:
            return False
        try:
            import ctypes
            data = self._notify_data(tip=text)
            return bool(ctypes.windll.shell32.Shell_NotifyIconW(_NIM_MODIFY, ctypes.byref(data)))
        except Exception:
            return False

    def notify(self, title, text, timeout=5):
        """托盘气泡（Windows 10+ 显示为通知）。失败返回 False。"""
        if not self.is_running() or not self._hwnd:
            return False
        try:
            import ctypes
            import ctypes.wintypes as wt

            class NOTIFYICONDATAW(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT),
                    ("uFlags", wt.UINT), ("uCallbackMessage", wt.UINT),
                    ("hIcon", wt.HICON), ("szTip", wt.WCHAR * 128),
                    ("dwState", wt.DWORD), ("dwStateMask", wt.DWORD),
                    ("szInfo", wt.WCHAR * 256), ("uTimeout", wt.UINT),
                    ("szInfoTitle", wt.WCHAR * 64), ("dwInfoFlags", wt.DWORD),
                    ("guidItem", wt.BYTE * 16), ("hBalloonIcon", wt.HICON),
                ]

            data = NOTIFYICONDATAW()
            data.cbSize = ctypes.sizeof(data)
            data.hWnd = self._hwnd
            data.uID = 1
            data.uFlags = _NIF_INFO
            data.szInfo = (text or "")[:255]
            data.szInfoTitle = (title or "")[:63]
            data.uTimeout = int(timeout * 1000)
            data.dwInfoFlags = _NIIF_INFO
            return bool(ctypes.windll.shell32.Shell_NotifyIconW(_NIM_MODIFY, ctypes.byref(data)))
        except Exception:
            return False

    # -- 内部：消息循环线程 ---------------------------------------------
    def _notify_data(self, tip=None):
        import ctypes
        import ctypes.wintypes as wt

        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT),
                ("uFlags", wt.UINT), ("uCallbackMessage", wt.UINT),
                ("hIcon", wt.HICON), ("szTip", wt.WCHAR * 128),
                ("dwState", wt.DWORD), ("dwStateMask", wt.DWORD),
                ("szInfo", wt.WCHAR * 256), ("uTimeout", wt.UINT),
                ("szInfoTitle", wt.WCHAR * 64), ("dwInfoFlags", wt.DWORD),
                ("guidItem", wt.BYTE * 16), ("hBalloonIcon", wt.HICON),
            ]

        data = NOTIFYICONDATAW()
        data.cbSize = ctypes.sizeof(data)
        data.hWnd = self._hwnd
        data.uID = 1
        data.uFlags = _NIF_MESSAGE | _NIF_ICON | _NIF_TIP
        data.uCallbackMessage = _WM_TRAY
        data.hIcon = self._hicon
        data.szTip = (tip if tip is not None else self.tooltip)[:127]
        return data

    def _call(self, cb):
        if cb is None:
            return
        try:
            cb()
        except Exception:
            pass

    def _show_menu(self, user32):
        try:
            hmenu = user32.CreatePopupMenu()
            if not hmenu:
                return
            user32.AppendMenuW(hmenu, _MF_STRING, _ID_SHOW, "显示主窗口(&S)")
            user32.AppendMenuW(hmenu, _MF_STRING, _ID_SHOT, "截图翻译(&C)")
            user32.AppendMenuW(hmenu, _MF_SEPARATOR, 0, None)
            user32.AppendMenuW(hmenu, _MF_STRING, _ID_QUIT, "退出(&Q)")
            pt = user32.GetCursorPos
            import ctypes
            import ctypes.wintypes as wt

            class POINT(ctypes.Structure):
                _fields_ = [("x", wt.LONG), ("y", wt.LONG)]

            p = POINT()
            if pt(ctypes.byref(p)):
                user32.SetForegroundWindow(self._hwnd)
                cmd = user32.TrackPopupMenu(
                    hmenu, _TPM_RIGHTBUTTON | _TPM_RETURNCMD,
                    p.x, p.y, 0, self._hwnd, None)
                user32.PostMessageW(self._hwnd, 0, 0, 0)  # 让菜单正常消失
                if cmd == _ID_SHOW:
                    self._call(self.on_show)
                elif cmd == _ID_SHOT:
                    self._call(self.on_screenshot)
                elif cmd == _ID_QUIT:
                    self._call(self.on_quit)
            user32.DestroyMenu(hmenu)
        except Exception:
            pass

    def _loop(self):
        try:
            import ctypes
            import ctypes.wintypes as wt

            user32 = ctypes.windll.user32
            shell32 = ctypes.windll.shell32
            kernel32 = ctypes.windll.kernel32

            WNDPROC = ctypes.WINFUNCTYPE(
                wt.LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

            def wndproc(hwnd, msg, wparam, lparam):
                if msg == _WM_TRAY:
                    # lParam 是鼠标消息：左键双击 / 左键弹起显示，右键弹起出菜单
                    if lparam in (0x0203, 0x0202):      # WM_LBUTTONDBLCLK / UP
                        self._call(self.on_show)
                    elif lparam == 0x0205:              # WM_RBUTTONUP
                        self._show_menu(user32)
                    return 0
                if msg == _WM_COMMAND:
                    cmd = wparam & 0xFFFF
                    if cmd == _ID_SHOW:
                        self._call(self.on_show)
                    elif cmd == _ID_SHOT:
                        self._call(self.on_screenshot)
                    elif cmd == _ID_QUIT:
                        self._call(self.on_quit)
                    return 0
                if msg == _WM_DESTROY:
                    user32.PostQuitMessage(0)
                    return 0
                if self._taskbar_created_msg and msg == self._taskbar_created_msg:
                    # 资源管理器重启后托盘图标会丢，重新加上
                    try:
                        data = self._notify_data()
                        shell32.Shell_NotifyIconW(_NIM_ADD, ctypes.byref(data))
                    except Exception:
                        pass
                    return 0
                if msg == _WM_CLOSE:
                    user32.DestroyWindow(hwnd)
                    return 0
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            self._wndproc = WNDPROC(wndproc)
            self._taskbar_created_msg = user32.RegisterWindowMessageW("TaskbarCreated")

            class WNDCLASSW(ctypes.Structure):
                _fields_ = [
                    ("style", wt.UINT), ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                    ("hCursor", wt.HCURSOR), ("hbrBackground", wt.HBRUSH),
                    ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR),
                ]

            hinst = kernel32.GetModuleHandleW(None)
            cls_name = "RealtimeTranslateTray"
            wc = WNDCLASSW()
            wc.style = 0
            wc.lpfnWndProc = self._wndproc
            wc.hInstance = hinst
            wc.lpszClassName = cls_name
            self._wndclass = wc
            if not user32.RegisterClassW(ctypes.byref(wc)):
                # 类已注册过（比如上次没注销干净）也继续用
                if ctypes.get_last_error() not in (0, 1410):  # ERROR_CLASS_ALREADY_EXISTS
                    self._ready.set()
                    return

            hwnd = user32.CreateWindowExW(
                0, cls_name, self.tooltip, 0, 0, 0, 0, 0, None, None, hinst, None)
            if not hwnd:
                self._ready.set()
                return
            self._hwnd = hwnd

            # 图标：优先用 app.ico，没有就用系统默认应用图标，不用 Pillow 转
            hicon = None
            if self.icon_path and os.path.isfile(self.icon_path):
                user32.LoadImageW.restype = wt.HICON
                user32.LoadImageW.argtypes = [
                    wt.HINSTANCE, wt.LPCWSTR, wt.UINT,
                    ctypes.c_int, ctypes.c_int, wt.UINT]
                hicon = user32.LoadImageW(
                    None, self.icon_path, _IMAGE_ICON, 0, 0,
                    _LR_LOADFROMFILE | _LR_DEFAULTSIZE)
            if not hicon:
                user32.LoadIconW.restype = wt.HICON
                user32.LoadIconW.argtypes = [wt.HINSTANCE, wt.LPCWSTR]
                hicon = user32.LoadIconW(None, _IDI_APPLICATION)
            self._hicon = hicon

            shell32.Shell_NotifyIconW.restype = wt.BOOL
            data = self._notify_data()
            if not shell32.Shell_NotifyIconW(_NIM_ADD, ctypes.byref(data)):
                user32.DestroyWindow(hwnd)
                self._hwnd = None
                self._ready.set()
                return

            self._started = True
            self._ready.set()
            msg = wt.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except Exception:
            self._ready.set()
        finally:
            try:
                import ctypes
                if self._hwnd:
                    data = self._notify_data()
                    ctypes.windll.shell32.Shell_NotifyIconW(_NIM_DELETE, ctypes.byref(data))
            except Exception:
                pass
            self._started = False
            self._ready.set()
