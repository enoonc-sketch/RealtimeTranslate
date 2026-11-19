"""小宠物的"大脑"：把翻译程序里发生的事（复制了文字、开始翻译、译好了、失败了…）变成动画 + 气泡文字。
纯逻辑，不碰界面，所以可以单独测试。

规则：
- 事件触发的短动画（惊讶 / 开心 / 难过）有固定时长，播完回到"当前基础状态"；
- 基础状态：翻译中 → 思考；空闲超过 SLEEP_AFTER 秒 → 睡觉；其余 → 发呆(idle)；
- "翻译中"超过 BUSY_TIMEOUT 秒没等到结果，就当它结束了（保护：不会一直卡在思考）。
"""
import time

SLEEP_AFTER = 90.0
BUSY_TIMEOUT = 60.0
BUBBLE_MAX = 60


def short_text(text, limit=BUBBLE_MAX):
    t = " ".join(str(text or "").split())
    return t if len(t) <= limit else t[:limit - 1] + "…"


def bubble_seconds(text):
    return min(9.0, 2.5 + len(text) * 0.12)


class PetBrain:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.busy = False
        self.busy_since = 0.0
        self.busy_text = ""
        self.transient = None      # (anim, until)
        self.bubble = None         # (text, until)
        self.last_active = clock()

    def _t(self, now):
        return self.clock() if now is None else now

    def wake(self, now=None):
        self.last_active = self._t(now)

    def event(self, kind, text="", now=None, bubble=True):
        """kind: curious 惊讶 | poke 被戳 | busy 开始/进行中 | done 完成 | fail 失败"""
        t = self._t(now)
        self.last_active = t
        if kind in ("curious", "poke"):
            self.transient = ("alert", t + (1.0 if kind == "curious" else 0.9))
        elif kind == "busy":
            if not self.busy:
                self.busy_since = t
            self.busy = True
            self.busy_text = short_text(text, 24)
        elif kind == "done":
            self.busy = False
            self.transient = ("happy", t + 2.2)
            msg = short_text(text) if text else ""
            self.bubble = (msg, t + bubble_seconds(msg)) if (bubble and msg) else None
        elif kind == "fail":
            self.busy = False
            self.transient = ("sad", t + 3.0)
            msg = short_text(text) or "没翻译成功…"
            self.bubble = (msg, t + 4.0) if bubble else None

    def state(self, now=None):
        """返回 (动画名, 气泡文字或 None)。"""
        t = self._t(now)
        if self.busy and t - self.busy_since > BUSY_TIMEOUT:
            self.busy = False
        if self.transient and t >= self.transient[1]:
            self.transient = None
        if self.bubble and t >= self.bubble[1]:
            self.bubble = None
        if self.transient:
            anim = self.transient[0]
        elif self.busy:
            anim = "think"
        elif t - self.last_active > SLEEP_AFTER:
            anim = "sleep"
        else:
            anim = "idle"
        text = self.busy_text if (self.busy and self.busy_text) else (self.bubble[0] if self.bubble else None)
        return anim, text
