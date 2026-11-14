"""【需要联网】真实验证：从 PyPI 下载真实轮子（本机平台），装进临时目录，再用「不带任何已装第三方包」的
纯净 Python（-S）去 import ctranslate2/sentencepiece 并真正翻译一句；同时列出它们实际用到的标准库模块，
用来核对标准版 exe 的打包清单。Windows 轮子无法在 Linux 执行，这里验证的是同一套下载→解压→加路径→导入机制。"""
import json, os, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, HERE)
import runtime_installer as ri
from make_fake_model import make_pkg

rt = os.path.join(tempfile.mkdtemp(), "runtime")
t0 = time.time(); last = [-1]
def prog(i, n, fn, d, t):
    if i != last[0]:
        last[0] = i; print("  下载 (%d/%d) %s  %.1f MB" % (i + 1, n, fn, (t or 0) / 1e6), flush=True)
vers = ri.install(rt, progress=prog)
print("安装完成 %.0fs：%s" % (time.time() - t0, vers))
print("installed():", ri.installed(rt))
site = os.path.join(rt, "site")
sz = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(site) for f in fs) / 1e6
print("解压后占用 %.0f MB；残留下载目录：%s" % (sz, os.path.isdir(os.path.join(rt, "_downloads"))))

en = ["hello world this is a test", "good morning everyone"] * 8; zh = ["你好世界这是一个测试", "大家早上好"] * 8
pk = os.path.join(tempfile.mkdtemp(), "models"); make_pkg(pk, "en", "zh", en + zh)
code = r'''
import sys, json
sys.path.insert(0, %r); sys.path.insert(0, %r)
import runtime_installer as ri, offline_engine as oe
ri.activate(%r)
assert oe.runtime_present(), "runtime_present False"
import ctranslate2, sentencepiece, numpy, yaml
assert ctranslate2.__file__.startswith(%r), ctranslate2.__file__
eng = oe.Engine([(%r, "x")])
out = eng.translate("hello world", "en", "zh")
std = sorted(m for m in sys.modules if m.split(".")[0] in sys.stdlib_module_names)
print(json.dumps({"out": out, "ver": [ctranslate2.__version__, numpy.__version__], "std": std}))
''' % (os.path.dirname(HERE), HERE, rt, site, pk)
r = subprocess.run([sys.executable, "-S", "-c", code], capture_output=True, text=True, timeout=120)
print("纯净 Python 加载结果：", r.stdout.strip()[:200] if r.returncode == 0 else r.stderr[-800:])
if r.returncode == 0:
    d = json.loads(r.stdout.strip().splitlines()[-1])
    open(os.path.join(HERE, "stdlib_needed.json"), "w").write(json.dumps(d["std"]))
    print("用到的标准库顶层模块：", " ".join(d["std"]))
    print("ALL OK" if d["out"] else "FAILED")
else:
    print("FAILED"); sys.exit(1)
