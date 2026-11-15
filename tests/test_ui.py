import sys, os, time, tempfile, json
import os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import desktop_translator as dt
dt.DATA_DIR = tempfile.mkdtemp(); dt.CONFIG_PATH = os.path.join(dt.DATA_DIR, "config.json")
dt.g_translate = lambda t, sl, tl: ("译:" + t[:20], "en")
app = dt.App()
r = app.root
def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        r.update(); time.sleep(0.02)
app._set_src("Hello world"); app.translate_now(); pump(1.0)
print("result:", repr(app.plain_result()), "| status:", app.status.cget("text"))
ok1 = app.plain_result().startswith("译:")
# typing triggers debounce translate
app.src.insert("end", " more"); pump(1.2)
ok2 = "more" in app.plain_result() or app.plain_result().startswith("译:")
# Esc must hide: withdraw when tray is running, iconify when there is no tray
# (old behavior was always iconify, because withdraw with no tray lost the window)
hits = []
app.hide_window = lambda: hits.append(1)      # Xvfb 无窗口管理器，无法真实最小化 -> 改验证绑定
r.focus_force(); pump(0.2); r.event_generate("<Escape>"); pump(0.3)
import inspect
_src = inspect.getsource(dt.App.hide_window)
_tray_src = inspect.getsource(dt.App._hide_to_tray)      # v2.10：藏到托盘的 withdraw 挪进了 _hide_to_tray
ok3 = bool(hits) and "iconify" in _src and "root.withdraw()" in _tray_src and "tray" in _src
print("Esc -> hide_window called:", bool(hits))
app.show_window(); pump(0.3)
# engine list / error path
dt.g_translate = lambda t, sl, tl: (_ for _ in ()).throw(RuntimeError("boom"))
dt.CACHE.clear(); app._set_src("fail me"); app.translate_now(); pump(2.5)
ok4 = "翻译失败" in app.dst.get("1.0", "end")
app.quit()
print("config saved:", os.path.exists(dt.CONFIG_PATH))
print("ALL OK" if all([ok1, ok2, ok3, ok4]) else "FAILED %s" % [ok1, ok2, ok3, ok4])
