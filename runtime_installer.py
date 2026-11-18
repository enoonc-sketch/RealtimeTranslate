"""
离线翻译运行库的在线安装：标准版 exe 里没有 ctranslate2 / sentencepiece，这里从 PyPI 下载它们的
「预编译轮子（.whl）」解压到 %APPDATA%\\RealtimeTranslate\\runtime\\site，再加进 sys.path 即可 import。

只用标准库，不依赖 tkinter，可单独测试。
"""
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import zipfile

import offline_engine as oe
import pack_downloader as pd

try:                                     # v2.13：让 PyInstaller 把运行库要用的标准库（glob 等）全收进 exe
    import runtime_stdlib                # noqa: F401
except Exception:      # noqa: BLE001
    runtime_stdlib = None

# 安装顺序即下载顺序：ctranslate2 依赖 numpy 与 pyyaml，翻译还需要 sentencepiece
PKGS = ["numpy", "pyyaml", "sentencepiece", "ctranslate2"]
INDEX = "https://pypi.org/pypi/%s/json"
SIZE_HINT_MB = 35                      # 提示用户的大致下载量


def py_tag():
    return "cp%d%d" % sys.version_info[:2]


def platform_ok(plat):
    if sys.platform.startswith("win"):
        return "win_amd64" in plat
    if sys.platform.startswith("linux"):
        return "x86_64" in plat and "manylinux" in plat
    return False


def supported():
    """(能否在本机自动安装, 不能时的原因)。"""
    if struct.calcsize("P") * 8 != 64:
        return False, "当前程序是 32 位，而 ctranslate2 只有 64 位版本。请换用 64 位 Python 构建。"
    if not (sys.platform.startswith("win") or sys.platform.startswith("linux")):
        return False, "本系统请手动安装：pip install ctranslate2 sentencepiece numpy"
    return True, ""


# ---------------------------------------------------------------- 选轮子
def _wheel_ok(fn, tag):
    if not fn.endswith(".whl"):
        return False
    parts = fn[:-4].split("-")
    if len(parts) < 5:
        return False
    py, abi, plat = parts[-3], parts[-2], parts[-1]
    ok_py = ((py == tag and abi in (tag, "abi3", "none")) or
             (abi == "abi3" and py.startswith("cp3") and py[3:].isdigit() and int(py[3:]) <= int(tag[3:])))
    return ok_py and any(platform_ok(p) for p in plat.split("."))


def pick_wheel(data, tag):
    """在 PyPI 的 JSON 里找「版本最高、且与当前 Python / 系统匹配」的轮子；没有返回 None。"""
    rel = data.get("releases") or {}
    versions = sorted((v for v in rel if re.fullmatch(r"\d+(\.\d+)*", v)), key=oe._ver_tuple, reverse=True)
    for v in versions:
        for f in rel[v]:
            if f.get("packagetype") == "bdist_wheel" and not f.get("yanked") and _wheel_ok(f.get("filename", ""), tag):
                return {"version": v, "filename": f["filename"], "url": f["url"], "size": f.get("size", 0),
                        "sha256": (f.get("digests") or {}).get("sha256", "")}
    return None


def find_wheel(pkg, tag, replace="", index=None, timeout=30):
    try:
        with pd._open(pd.apply_replace((index or INDEX) % pkg, replace), timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:      # noqa: BLE001
        raise oe.OfflineError("无法从 PyPI 查询 %s：%s\n网络不通时可在「镜像」栏填写（格式 旧域名=新域名，多组用分号隔开）。" % (pkg, e))
    w = pick_wheel(data, tag)
    if not w:
        raise oe.OfflineError("PyPI 上没有适合当前程序（Python %s.%s）的 %s 安装包。"
                              % (sys.version_info[0], sys.version_info[1], pkg))
    return w


# ---------------------------------------------------------------- 安装
def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _extract(wheel, dest):
    root = os.path.realpath(dest)
    with zipfile.ZipFile(wheel) as z:
        for info in z.infolist():
            name = info.filename
            if "/tests/" in name or name.endswith("/"):      # 测试目录不需要，省几十 MB
                continue
            target = os.path.realpath(os.path.join(root, name))
            if not target.startswith(root + os.sep):         # 防 zip-slip
                raise oe.OfflineError("安装包含非法路径，已拒绝：%s" % name)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)


def _site(runtime):
    return os.path.join(runtime, "site")


def _manifest(runtime):
    return os.path.join(runtime, "manifest.json")


def installed(runtime, tag=None):
    """已装好且与当前 Python 匹配 → 返回 {包名: 版本}，否则 None。"""
    try:
        with open(_manifest(runtime), "r", encoding="utf-8") as f:
            m = json.load(f)
        if m.get("tag") == (tag or py_tag()) and os.path.isdir(_site(runtime)):
            return m.get("versions") or {}
    except Exception:      # noqa: BLE001
        pass
    return None


def activate(runtime):
    """把 runtime\\site 加进 sys.path（追加在最后：自带的运行库优先）。启动时调用，几乎零开销。"""
    site = _site(runtime)
    if not os.path.isdir(site):
        return False
    if site not in sys.path:
        sys.path.append(site)
    if hasattr(os, "add_dll_directory"):                      # Windows：让 DLL 能被找到
        for sub in ("numpy.libs", "ctranslate2", "ctranslate2.libs", "sentencepiece"):
            p = os.path.join(site, sub)
            if os.path.isdir(p):
                try:
                    os.add_dll_directory(p)
                except OSError:
                    pass
    import importlib
    importlib.invalidate_caches()
    return True


def verify_import():
    """真正 import 一次，确认装好的组件能用；失败抛 OfflineError（含原因）。"""
    try:
        import ctranslate2          # noqa: F401
        import sentencepiece        # noqa: F401
    except ModuleNotFoundError as e:      # noqa: BLE001
        name = getattr(e, "name", "") or ""
        if name and name.split(".")[0] in getattr(sys, "stdlib_module_names", ()):
            raise oe.OfflineError("程序自带的标准库缺少「%s」（这是打包问题，不是你的电脑问题）。\n"
                                  "请升级到 v2.13 及以上；或改用「离线版」安装包。" % name)
        raise oe.OfflineError("组件已下载但缺少依赖「%s」，请在「离线与网络」里重新下载组件。" % name)
    except Exception as e:      # noqa: BLE001
        raise oe.OfflineError("组件已下载但无法加载：%s\n（Windows 上常见原因：缺少 Visual C++ 运行库，\n"
                              "请安装「Microsoft Visual C++ 2015-2022 Redistributable (x64)」后重启程序）" % e)


def install(runtime, tag=None, replace="", progress=None, cancelled=None, timeout=60, index=None):
    """下载并安装全部组件。progress(第几个, 共几个, 文件名, 已下字节, 总字节)。返回 {包名: 版本}。"""
    ok, why = supported()
    if not ok:
        raise oe.OfflineError(why)
    tag = tag or py_tag()
    wheels = [(pkg, find_wheel(pkg, tag, replace, index)) for pkg in PKGS]
    work, new = os.path.join(runtime, "_downloads"), os.path.join(runtime, "_new")
    os.makedirs(work, exist_ok=True)
    shutil.rmtree(new, ignore_errors=True)
    os.makedirs(new)
    n = len(wheels)
    try:
        for i, (pkg, w) in enumerate(wheels):
            dest = os.path.join(work, w["filename"])
            if not (os.path.isfile(dest) and (not w["sha256"] or _sha256(dest) == w["sha256"])):
                def prog(done, total, i=i, w=w):
                    if progress:
                        progress(i, n, w["filename"], done, total or w["size"])
                pd.download(pd.apply_replace(w["url"], replace), dest, prog, cancelled, timeout)
                if w["sha256"] and _sha256(dest) != w["sha256"]:
                    os.remove(dest)
                    raise oe.OfflineError("%s 校验失败（文件损坏或被篡改），请重试。" % w["filename"])
            _extract(dest, new)
    except BaseException:
        shutil.rmtree(new, ignore_errors=True)
        raise
    site, old = _site(runtime), _site(runtime) + ".old"
    shutil.rmtree(old, ignore_errors=True)
    if os.path.isdir(site):
        os.replace(site, old)
    os.replace(new, site)
    shutil.rmtree(old, ignore_errors=True)
    versions = {pkg: w["version"] for pkg, w in wheels}
    with open(_manifest(runtime), "w", encoding="utf-8") as f:
        json.dump({"tag": tag, "versions": versions}, f)
    shutil.rmtree(work, ignore_errors=True)            # 轮子装好后不留，省 30 多 MB
    return versions
