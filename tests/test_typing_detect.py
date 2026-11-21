"""打字检测翻译：TypingBuffer 纯逻辑测试（无 OS 依赖，Linux 上就能跑）。

pytest 风格：python3 -m pytest tests/test_typing_detect.py -v
直接跑也行：python3 tests/test_typing_detect.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import typing_detect as td


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def feed_text(buf, text, clock):
    """逐字喂进去，收集立即触发的 word 事件。"""
    events = []
    for ch in text:
        ev = buf.feed(ch, now=clock.now())
        if ev is not None and ev.get("kind") == "word":
            events.append(ev)
            buf.mark_translated(ev["text"], now=clock.now())
        clock.advance(0.05)
    return events


def test_append_and_backspace():
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    b.feed("h", now=clock.now())
    b.feed("e", now=clock.now())
    assert b.current_fragment() == "he"
    b.feed("\b", now=clock.now())
    assert b.current_fragment() == "h"
    b.feed("i", now=clock.now())
    assert b.current_fragment() == "hi"


def test_space_triggers_word_immediately():
    """主触发：打词过程中按空格立即翻，不等停顿。"""
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    evs = feed_text(b, "hello ", clock)
    assert len(evs) == 1 and evs[0]["kind"] == "word" and evs[0]["text"] == "hello"


def test_punctuation_and_enter_trigger_words():
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    evs = feed_text(b, "world,hi\n", clock)
    assert [e["text"] for e in evs] == ["world", "hi"]


def test_live_update_follows_current_word():
    """连续打字时当前词实时更新（防抖后 tick 出 live，且是最新词）。"""
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    for ch in "hell":
        b.feed(ch, now=clock.now())
        clock.advance(0.05)
    clock.advance(0.3)
    ev = b.tick(now=clock.now())
    assert ev is not None and ev["kind"] == "live" and ev["text"] == "hell"
    b.feed("o", now=clock.now())
    clock.advance(0.3)
    ev = b.tick(now=clock.now())
    assert ev is not None and ev["text"] == "hello"


def test_no_live_inside_debounce():
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    b.feed("h", now=clock.now())
    b.feed("i", now=clock.now())
    assert b.tick(now=clock.now()) is None


def test_rate_limit_does_not_lose_last():
    """防抖节流不丢最后一次：限速内 tick 不发，下一轮补发。"""
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    for ch in "ab":
        b.feed(ch, now=clock.now())
        clock.advance(0.05)
    clock.advance(0.3)
    ev = b.tick(now=clock.now())
    assert ev is not None and ev["text"] == "ab"
    b.mark_translated("ab", now=clock.now())
    b.feed("c", now=clock.now())
    clock.advance(0.26)  # 防抖已过（0.26 秒）但距上次请求 <300ms
    assert b.tick(now=clock.now()) is None
    clock.advance(0.1)
    ev = b.tick(now=clock.now())
    assert ev is not None and ev["text"] == "abc"


def test_pause_fallback_still_works():
    """停顿兜底仍有效：打完停住满 1 秒，翻当前片段；之前不触发。"""
    clock = Clock()
    b = td.TypingBuffer(pause_ms=1000, now_fn=clock.now)
    for ch in "hello":
        b.feed(ch, now=clock.now())
        clock.advance(0.05)
    clock.advance(0.1)
    assert b.tick(now=clock.now()) is None
    clock.advance(1.0)
    ev = b.tick(now=clock.now())
    assert ev is not None and ev["kind"] == "pause" and ev["text"] == "hello"


def test_sentence_scope_fragment():
    clock = Clock()
    b = td.TypingBuffer(scope="sentence", now_fn=clock.now)
    evs = feed_text(b, "hello world", clock)
    assert evs == []
    ev = b.feed(".", now=clock.now())
    assert ev is not None and ev["text"] == "hello world."


def test_duplicate_not_retranslated():
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    evs = feed_text(b, "hello hello ", clock)
    assert len(evs) == 1


def test_sensitive_suppression():
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    assert feed_text(b, "123456 ", clock) == []
    b = td.TypingBuffer(now_fn=clock.now)
    assert feed_text(b, "sk-abcdefghijklmnopqrst ", clock) == []
    assert td.is_sensitive_text("110101199001011234")
    assert not td.is_sensitive_text("hello")


def test_password_suppression():
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    b.feed("h", now=clock.now())
    b.set_suppressed(True)
    assert b.text == ""
    assert b.feed("i", now=clock.now()) is None
    assert b.tick(now=clock.now()) is None
    b.set_suppressed(False)
    b.feed("h", now=clock.now())
    assert b.current_fragment() == "h"


def test_length_cap():
    assert not td.is_eligible("a" * 201)
    assert td.is_eligible("a" * 200)


def test_min_chars():
    assert not td.is_eligible("a")
    assert td.is_eligible("ab")


def test_pure_digits_and_symbols_not_eligible():
    assert not td.is_eligible("12345")
    assert not td.is_eligible("!!!")


def test_escape_clears_buffer():
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    b.feed("h", now=clock.now())
    ev = b.feed("\x1b", now=clock.now())
    assert ev is not None and ev["kind"] == "clear" and b.text == ""


def test_pause_ms_clamped():
    clock = Clock()
    b = td.TypingBuffer(pause_ms=100, now_fn=clock.now)
    assert b.pause_ms == 500
    b.set_pause_ms(9999)
    assert b.pause_ms == 3000


def test_sensitive_key_value_suppressed():
    """B-1：键: 值按词拆开后也不翻 —— 键名跟了 :/= 时键名不翻，紧跟的值也不翻。"""
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    assert feed_text(b, "password: abc123 ", clock) == []
    b = td.TypingBuffer(now_fn=clock.now)
    assert feed_text(b, "token: sk-abcdefghijklmnopqrst ", clock) == []
    b = td.TypingBuffer(now_fn=clock.now)
    assert feed_text(b, "账号：zhangsan ", clock) == []
    b = td.TypingBuffer(now_fn=clock.now)
    assert feed_text(b, "api-key=abcdef123456 ", clock) == []
    b = td.TypingBuffer(now_fn=clock.now)
    assert feed_text(b, "密码：abc123 ", clock) == []


def test_sensitive_key_value_space_before_colon():
    """B-1：键名与冒号之间隔了空格（password : abc123）——值仍抑制；
    键名本身在冒号到之前已打完，无法撤回，只断言值不翻。"""
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    evs = feed_text(b, "password : abc123 ", clock)
    assert [e["text"] for e in evs] == ["password"]


def test_sensitive_key_pending_clears_after_value():
    """B-1：抑制只针对紧跟的那个值，之后正常词照常翻。"""
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    evs = feed_text(b, "password: abc123 hello ", clock)
    assert [e["text"] for e in evs] == ["hello"]


def test_sensitive_key_live_suppressed_while_typing_value():
    """B-1：正在打值的时候，live 跟进与停顿兜底都不出事件。"""
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    feed_text(b, "password:", clock)
    for ch in "ab":
        b.feed(ch, now=clock.now())
        clock.advance(0.05)
    clock.advance(0.3)
    assert b.tick(now=clock.now()) is None
    clock.advance(1.0)
    assert b.tick(now=clock.now()) is None
    assert feed_text(b, "c123 ", clock) == []


def test_sensitive_key_backspace_clears_pending():
    """B-1：值被退格删空后，待命解除，后面的正常词照常翻。"""
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    feed_text(b, "password: ab", clock)
    b.feed("\b", now=clock.now())
    b.feed("\b", now=clock.now())
    evs = feed_text(b, "hello ", clock)
    assert [e["text"] for e in evs] == ["hello"]


def test_normal_keyword_without_colon_still_translates():
    """B-1 反向：键名后面没跟 :/= 时照常翻，不误杀正常句子。"""
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    evs = feed_text(b, "my password is strong ", clock)
    assert [e["text"] for e in evs] == ["my", "password", "is", "strong"]
    b = td.TypingBuffer(now_fn=clock.now)
    evs = feed_text(b, "the token expires soon ", clock)
    assert [e["text"] for e in evs] == ["the", "token", "expires", "soon"]


def test_word_scope_live_is_current_word_only():
    """word 模式下 live 只跟当前词，不带上已打完的词。"""
    clock = Clock()
    b = td.TypingBuffer(now_fn=clock.now)
    feed_text(b, "hello ", clock)
    for ch in "wor":
        b.feed(ch, now=clock.now())
        clock.advance(0.05)
    clock.advance(0.3)
    ev = b.tick(now=clock.now())
    assert ev is not None and ev["text"] == "wor"


if __name__ == "__main__":
    try:
        import pytest
    except ImportError:
        pytest = None
    if pytest is not None:
        sys.exit(pytest.main([__file__, "-v"]))
    # 无 pytest 时退回手工跑一遍关键断言
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS " + name)
    print("ALL OK")
