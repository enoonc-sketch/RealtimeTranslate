"""v2.15.6：键盘钩子安装失败的修复 —— 用 fake user32 / kernel32 测纯逻辑。

不碰真实 Windows：start_typing_hook_win / start_typing_poll_win 都接受
_win / _kernel 注入，fake 模拟 SetWindowsHookExW 成功 / 失败重试 /
一直失败、GetAsyncKeyState 按键边沿。Linux 上直接跑。
"""
import os
import queue
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import desktop_translator as dt

PASSED = []
FAILED = []


def check(name, cond):
    (PASSED if cond else FAILED).append(name)
    print(("PASS " if cond else "FAIL ") + name)


class FakeKernel:
    def __init__(self, hmod=0x12340000):
        self.hmod = hmod
        self.calls = []

    def GetModuleHandleW(self, name):
        self.calls.append(name)
        return self.hmod


class FakeUser32:
    """模拟 user32：钩子安装可配置失败次数 + 错误码；按键状态可拨动。"""

    def __init__(self, fail_times=0, err=5):
        self.fail_times = fail_times
        self.err = err
        self.install_calls = []
        self.unhook_calls = []
        self.last_error = 0
        self.key_state = {}
        self.to_unicode = {0x41: "a", 0x42: "b", 0x43: "c"}

    def SetWindowsHookExW(self, id_hook, proc, hmod, tid):
        self.install_calls.append((id_hook, proc, hmod, tid))
        if len(self.install_calls) <= self.fail_times:
            self.last_error = self.err
            return 0
        self.last_error = 0
        return 0x1000000AB  # 64 位句柄：代码绝不能把它截成 32 位 int

    def UnhookWindowsHookEx(self, hook):
        self.unhook_calls.append(hook)
        return True

    def GetMessageW(self, msg, hwnd, lo, hi):
        # 真实 GetMessageW 会阻塞等消息；这里睡 0.3 秒再返回 0 退出循环，
        # 否则主线程还没来得及看到已装好的钩子，循环就已经跑完并卸了钩。
        time.sleep(0.3)
        return 0

    def TranslateMessage(self, msg):
        return True

    def DispatchMessageW(self, msg):
        return 0

    def PostThreadMessageW(self, tid, msg, w, l):
        return True

    def GetCurrentThreadId(self):
        return 1234

    def CallNextHookEx(self, hook, code, w, l):
        return 0

    def GetAsyncKeyState(self, vk):
        return 0x8000 if self.key_state.get(vk) else 0

    def GetKeyboardState(self, kb):
        return True

    def GetKeyboardLayout(self, tid):
        return 0

    def ToUnicodeEx(self, vk, scan, kb, buf, n, flags, layout):
        ch = self.to_unicode.get(vk)
        if ch:
            buf.value = ch
            return 1
        return 0


def drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


def test_hook_success_first_try():
    q = queue.Queue()
    win = FakeUser32(fail_times=0)
    kern = FakeKernel()
    stop = dt.start_typing_hook_win(q, _win=win, _kernel=kern)
    check("hook: 首次安装成功返回 stop", stop is not None)
    check("hook: 传了 WH_KEYBOARD_LL(13) + 全局线程 0", win.install_calls and win.install_calls[0][0] == 13 and win.install_calls[0][3] == 0)
    check("hook: hMod 传的是 GetModuleHandleW(None) 而不是 None", win.install_calls and win.install_calls[0][2] == 0x12340000)
    check("hook: last_error 清零", dt.start_typing_hook_win.last_error == 0)
    if stop is not None:
        stop()
        check("hook: stop() 调 Unhook 且句柄没被截断", win.unhook_calls == [0x1000000AB])


def test_hook_retry_then_success():
    q = queue.Queue()
    win = FakeUser32(fail_times=2, err=5)
    stop = dt.start_typing_hook_win(q, _win=win, _kernel=FakeKernel())
    check("hook: 前两次失败、第三次成功（重试生效）", stop is not None and len(win.install_calls) == 3)
    if stop is not None:
        stop()


def test_hook_always_fails_reports_code():
    q = queue.Queue()
    win = FakeUser32(fail_times=99, err=5)
    stop = dt.start_typing_hook_win(q, _win=win, _kernel=FakeKernel())
    check("hook: 一直失败返回 None", stop is None)
    check("hook: 失败 3 次就停，不无限重试", len(win.install_calls) == 3)
    check("hook: last_error 是真实错误码 5", dt.start_typing_hook_win.last_error == 5)
    msgs = drain(q)
    check("hook: 队列收到带错误码的 typing_hook_error", ("typing_hook_error", 5) in msgs)


def test_error_text():
    check("err text: 5 含拒绝访问", "拒绝访问" in dt._typing_hook_error_text(5))
    check("err text: 1428 含模块句柄", "模块句柄" in dt._typing_hook_error_text(1428))
    check("err text: 未知码只报数字", dt._typing_hook_error_text(9999) == "错误码 9999")
    check("err text: 0 报未知错误", dt._typing_hook_error_text(0) == "未知错误")


def test_poll_fallback():
    q = queue.Queue()
    win = FakeUser32()
    stop = dt.start_typing_poll_win(q, _win=win, _interval=0.005)
    check("poll: 启动返回 stop", stop is not None)
    win.key_state[0x41] = True  # 按下 A
    time.sleep(0.05)
    win.key_state[0x41] = False  # 松开
    time.sleep(0.03)
    win.key_state[0x42] = True  # 再按下 B
    time.sleep(0.05)
    win.key_state[0x42] = False
    time.sleep(0.03)
    msgs = drain(q)
    check("poll: 按下边沿各转发一次", ("typing_key", "a", 0x41) in msgs and ("typing_key", "b", 0x42) in msgs)
    check("poll: 按住不放不重复转发", sum(1 for m in msgs if m == ("typing_key", "a", 0x41)) == 1)
    # 按住 Ctrl 再按 C：修饰键组合不转发
    win.key_state[0x11] = True
    win.key_state[0x43] = True
    time.sleep(0.05)
    win.key_state[0x43] = False
    win.key_state[0x11] = False
    time.sleep(0.03)
    msgs = drain(q)
    check("poll: 修饰键组合不转发", ("typing_key", "c", 0x43) not in msgs)
    # 空格是特殊键，不走 ToUnicodeEx
    win.key_state[0x20] = True
    time.sleep(0.05)
    win.key_state[0x20] = False
    time.sleep(0.03)
    msgs = drain(q)
    check("poll: 空格转发", ("typing_key", " ", 0x20) in msgs)
    if stop is not None:
        stop()


if __name__ == "__main__":
    test_hook_success_first_try()
    test_hook_retry_then_success()
    test_hook_always_fails_reports_code()
    test_error_text()
    test_poll_fallback()
    print("\n%d/%d passed" % (len(PASSED), len(PASSED) + len(FAILED)))
    if FAILED:
        print("FAILED:", FAILED)
        sys.exit(1)
