"""单实例守卫：Linux 上用 fcntl 锁文件；失败时 fail-open。"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import single_instance as si

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


# 默认互斥体名必须与 desktop_translator.MUTEX_NAME、installer.iss AppMutex 一致
ok("default mutex name is RealtimeTranslate_SingleInstance",
   si.DEFAULT_MUTEX_NAME == "RealtimeTranslate_SingleInstance")
ok("SingleInstance() default name matches",
   si.SingleInstance().name == "RealtimeTranslate_SingleInstance")
ok("default lock path is realtimetranslate.lock in tempdir",
   os.path.basename(si.SingleInstance().lock_path) == "realtimetranslate.lock")

with tempfile.TemporaryDirectory() as tmp:
    lock = os.path.join(tmp, "test.lock")

    first = si.SingleInstance(lock_path=lock)
    ok("first acquire() is True", first.acquire() is True)

    second = si.SingleInstance(lock_path=lock)
    ok("second acquire() on same lock path is False", second.acquire() is False)

    first.release()
    third = si.SingleInstance(lock_path=lock)
    ok("after first release(), third acquire() is True", third.acquire() is True)
    third.release()

    # release() 重复调用不抛错
    try:
        third.release()
        ok("release() twice does not raise", True)
    except Exception:
        ok("release() twice does not raise", False)

    # 锁目录不存在：fail-open，照常启动
    bogus = si.SingleInstance(lock_path=os.path.join(tmp, "no-such-dir", "x.lock"))
    ok("bogus lock dir still returns True (fail-open)", bogus.acquire() is True)
    bogus.release()

    # 不同锁路径互不干扰
    a = si.SingleInstance(lock_path=os.path.join(tmp, "a.lock"))
    b = si.SingleInstance(lock_path=os.path.join(tmp, "b.lock"))
    ok("different lock paths both acquire", a.acquire() is True and b.acquire() is True)
    a.release()
    b.release()

    # ensure_single_instance：取到返回实例，已有返回 None，释放后又能取到
    one = si.ensure_single_instance(lock_path=os.path.join(tmp, "ens.lock"))
    ok("ensure_single_instance() returns instance when free", one is not None)
    two = si.ensure_single_instance(lock_path=os.path.join(tmp, "ens.lock"))
    ok("ensure_single_instance() returns None when held", two is None)
    if one is not None:
        one.release()
    three = si.ensure_single_instance(lock_path=os.path.join(tmp, "ens.lock"))
    ok("ensure_single_instance() works again after release", three is not None)
    if three is not None:
        three.release()

# ensure_single_instance 构造期出错也要 fail-open：_default_lock_path()
# 抛错（如临时目录不可用）时不能让 main() 崩掉
_orig_lock_path = si._default_lock_path
try:
    si._default_lock_path = lambda: (_ for _ in ()).throw(RuntimeError("no tempdir"))
    try:
        broken = si.ensure_single_instance()
        ok("ensure_single_instance() with broken tempdir does not raise", broken is not None)
        ok("fail-open instance reports acquired", bool(getattr(broken, "acquired", False)))
        if broken is not None and hasattr(broken, "release"):
            broken.release()
    except Exception as e:
        print("  got %s: %s" % (type(e).__name__, e))
        ok("ensure_single_instance() with broken tempdir does not raise", False)
        ok("fail-open instance reports acquired", False)
finally:
    si._default_lock_path = _orig_lock_path

# bring_existing_to_front：Linux 上返回 False，不抛错
try:
    ok("bring_existing_to_front() on Linux returns False",
       si.bring_existing_to_front() is False)
except Exception as e:
    print("  got %s: %s" % (type(e).__name__, e))
    ok("bring_existing_to_front() on Linux returns False", False)

print("ALL OK" if all(res) else "FAILED")
sys.exit(0 if all(res) else 1)
