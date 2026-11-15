"""单实例守卫：Windows 用命名互斥体，非 Windows 用 fcntl 锁文件。

Windows 行为与 desktop_translator.acquire_single_instance() 一致：
已有实例在运行时唤起它的主窗口并返回 False；互斥体名与
desktop_translator.MUTEX_NAME 及 installer.iss 的 AppMutex 保持一致。

任何意外出错都 fail-open（acquire() 返回 True），一次单实例检查
绝不能阻止程序启动。release() 尽力而为，永不抛错。
"""
import os
import sys
import tempfile

# 与 desktop_translator.MUTEX_NAME、installer.iss AppMutex 保持一致，勿改。
DEFAULT_MUTEX_NAME = "RealtimeTranslate_SingleInstance"
DEFAULT_WINDOW_TITLE = "实时翻译"
_FALLBACK_WINDOW_TITLE = "RealtimeTranslate"
ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9


def _default_lock_path():
    return os.path.join(tempfile.gettempdir(), "realtimetranslate.lock")


class SingleInstance:
    """单实例锁。acquire() 成功返回 True（本进程是唯一实例），否则 False。"""

    def __init__(self, name=None, lock_path=None):
        self.name = name if name is not None else DEFAULT_MUTEX_NAME
        self.lock_path = lock_path if lock_path is not None else _default_lock_path()
        self._mutex_handle = None
        self._lock_file = None
        self.acquired = False

    def acquire(self):
        """尝试取得单实例。意外异常一律返回 True（fail-open，绝不阻启动）。"""
        if self.acquired:
            return True
        try:
            if sys.platform == "win32":
                return self._acquire_windows()
            return self._acquire_lockfile()
        except Exception:
            return True

    def _acquire_windows(self):
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, self.name)
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            if handle:
                kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
                kernel32.CloseHandle(handle)
            # 已有实例：唤起它的主窗口（与旧 acquire_single_instance() 一致）。
            try:
                bring_existing_to_front()
            except Exception:
                pass
            return False
        if not handle:
            # 建互斥体失败但并非已存在：fail-open，照常启动。
            return True
        self._mutex_handle = handle
        self._kernel32 = kernel32
        self.acquired = True
        return True

    def _acquire_lockfile(self):
        try:
            import fcntl
        except ImportError:
            # 无 fcntl（如某些受限环境）：fail-open，照常启动。
            return True
        try:
            f = open(self.lock_path, "a+")
        except Exception:
            # 锁文件打不开（目录不存在、无权限等）：fail-open。
            return True
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError):
            try:
                f.close()
            except Exception:
                pass
            return False
        except Exception:
            try:
                f.close()
            except Exception:
                pass
            return True
        self._lock_file = f
        self.acquired = True
        return True

    def release(self):
        """释放单实例锁，尽力而为，永不抛错。重复调用无害。"""
        if self._mutex_handle is not None:
            try:
                import ctypes
                kernel32 = getattr(self, "_kernel32", None)
                if kernel32 is not None:
                    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
                    kernel32.CloseHandle(self._mutex_handle)
            except Exception:
                pass
            self._mutex_handle = None
        if self._lock_file is not None:
            try:
                import fcntl
                try:
                    fcntl.flock(self._lock_file, fcntl.LOCK_UN)
                except Exception:
                    pass
            except Exception:
                pass
            try:
                self._lock_file.close()
            except Exception:
                pass
            self._lock_file = None
        self.acquired = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()
        return False


def ensure_single_instance(name=None, lock_path=None):
    """取单实例：成功返回 SingleInstance 对象，已有实例在运行则返回 None。

    任何意外——包括构造 SingleInstance 本身出错（如临时目录不可用导致
    _default_lock_path() 抛错）——都 fail-open：返回一个已获取的空锁对象，
    绝不阻止程序启动（main() 里对这个调用没有再包 try/except）。
    """
    try:
        inst = SingleInstance(name=name, lock_path=lock_path)
    except Exception:
        inst = SingleInstance.__new__(SingleInstance)
        inst.name = name if name is not None else DEFAULT_MUTEX_NAME
        inst.lock_path = lock_path
        inst._mutex_handle = None
        inst._lock_file = None
        inst.acquired = True
        return inst
    if inst.acquire():
        return inst
    return None


def bring_existing_to_front():
    """尽力把已运行实例的主窗口提到前台；成功返回 True，否则 False，永不抛错。

    Windows：按标题找窗口，先试 "实时翻译"（APP_TITLE），再试
    "RealtimeTranslate"；找到就 ShowWindow(SW_RESTORE) + SetForegroundWindow。
    非 Windows：返回 False。
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL

        hwnd = None
        for title in (DEFAULT_WINDOW_TITLE, _FALLBACK_WINDOW_TITLE):
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                break
        if not hwnd:
            return False
        try:
            user32.ShowWindow(hwnd, SW_RESTORE)
        except Exception:
            pass
        return bool(user32.SetForegroundWindow(hwnd))
    except Exception:
        return False
