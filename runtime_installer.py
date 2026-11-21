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
DEFAULT_INDEX = "https://pypi.org/pypi/%s/json"
INDEX = DEFAULT_INDEX
SIZE_HINT_MB = 35                      # 提示用户的大致下载量

# 安全修复（2026-11-20，按安全评估报告）：
#   H-05：运行库轮子只取 PyPI 的「最新版」，无钉死 —— 下面是 2026-11-20 从 PyPI
#         JSON 实测的版本 + cp312 轮子文件名 + sha256。版本升级时随发版同步更新本表。
#         find_wheel 只在用默认 PyPI 索引时强制钉死（自定义索引 / 镜像测试走原逻辑）。
#   M-11：安装后清单只记版本不记文件哈希 —— 清单改为同时记每个文件的 sha256，
#         installed() 与 activate() 先验清单再认「已装好」/ 再加进 sys.path。
LAST_VERIFY_ERROR = ""                # M-11：最近一次 activate() 拒绝加载的原因（供界面显示）

PINNED_WHEELS = {
    "numpy": {"version": "2.5.5", "sha256": {
        "numpy-2.5.5-cp312-cp312-win_amd64.whl":
            "919eb420662b0b4ba34889df503f3d5329775b0c1d5f7e5f5af4fba8315b1e30",
        "numpy-2.5.5-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl":
            "704d819265e5d1064d932968e9ee85fff2103ccc78c05b878c06943ba27b8507",
    }},
    "pyyaml": {"version": "6.0.4", "sha256": {
        "pyyaml-6.0.4-cp312-cp312-win_amd64.whl":
            "131d11bd9b60d705a6388366d77ed67850995a4d2be85fe149785a257c17e531",
        "pyyaml-6.0.4-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl":
            "93bfb2459195406a518e2f487a9bbf01df240175f31e06f5a252ac6734c7bbf0",
    }},
    "sentencepiece": {"version": "0.2.3", "sha256": {
        "sentencepiece-0.2.3-cp312-cp312-win_amd64.whl":
            "972af959c63cde446210a8935524806820c253afa4b0a97d83c206b857085f44",
        "sentencepiece-0.2.3-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl":
            "cc3189b79c1ffda767f71b04238c27ac746f3b7abc263eab9a41c4cf46aee49e",
    }},
    "ctranslate2": {"version": "4.9.0", "sha256": {
        "ctranslate2-4.9.0-cp312-cp312-win_amd64.whl":
            "ee930e984679ad16c5fb7bc8da2eaca8c269f86d02cb9eeec087baa1837b5bd2",
        "ctranslate2-4.9.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl":
            "5d9b3edd73ba665f16a19cd3a498ce74fbfb6204bc0ac321f00f2600a41e8810",
    }},
}


def pinned_wheel(pkg):
    """H-05：返回钉死的 {version, sha256: {轮子文件名: sha256}}，未钉死返回 None。"""
    return PINNED_WHEELS.get(pkg)


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
    eff_index = index if index is not None else INDEX
    try:
        with pd._open(pd.apply_replace(eff_index % pkg, replace), timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:      # noqa: BLE001
        raise oe.OfflineError("无法从 PyPI 查询 %s：%s\n网络不通时可在「镜像」栏填写（格式 旧域名=新域名，多组用分号隔开）。" % (pkg, e))
    w = pick_wheel(data, tag)
    if not w:
        raise oe.OfflineError("PyPI 上没有适合当前程序（Python %s.%s）的 %s 安装包。"
                              % (sys.version_info[0], sys.version_info[1], pkg))
    # H-05：只有真正走默认 PyPI 索引时才强制钉死 —— 版本必须等于钉死版本，
    # 轮子文件名必须在钉死表里，哈希以钉死表为准（不信任索引自带的 digests）。
    # 自定义索引（测试 / 运维指定）不钉死。判断用替换前的生效索引，所以镜像
    # 替换（pypi.org=xxx）后仍按钉死哈希校验，换源也换不掉轮子。
    if eff_index == DEFAULT_INDEX:
        pinned = pinned_wheel(pkg)
        if pinned is not None:
            if w["version"] != pinned["version"]:
                raise oe.OfflineError("%s 在 PyPI 上已是 %s，但本程序只信任钉死的 %s。\n"
                                      "请升级到新版程序，或等新版发布后再安装组件。"
                                      % (pkg, w["version"], pinned["version"]))
            sha = pinned["sha256"].get(w["filename"])
            if sha is None:
                raise oe.OfflineError("%s 的安装包 %s 未在程序的校验表里，已拒绝安装。\n"
                                      "请升级到新版程序。" % (pkg, w["filename"]))
            w["sha256"] = sha
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


def _hash_site_files(site):
    """M-11：对 site 下全部文件算 sha256 → {相对路径: sha256}（相对路径统一用 /）。
    __pycache__ 下的 .pyc 是派生文件（随 Python 小版本变化），不计入清单。"""
    out = {}
    for root, dirs, files in os.walk(site):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in files:
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, site).replace(os.sep, "/")
            try:
                out[rel] = _sha256(p)
            except OSError:
                return None
    return out


def _manifest_files_ok(runtime):
    """M-11：清单里记了文件哈希就逐个比对。返回 (True, '') 或 (False, 原因)。
    无清单 / 清单里没记文件（老版本装好的）返回 (True, '')，由调用方决定是否补清单。"""
    try:
        with open(_manifest(runtime), "r", encoding="utf-8") as f:
            m = json.load(f)
    except Exception:      # noqa: BLE001
        return True, ""
    want = m.get("files")
    if not isinstance(want, dict) or not want:
        return True, ""
    site = _site(runtime)
    for rel, sha in want.items():
        p = os.path.join(site, *rel.split("/"))
        try:
            if not os.path.isfile(p) or _sha256(p) != sha:
                return False, "组件文件 %s 已被改动或损坏" % rel
        except OSError:
            return False, "组件文件 %s 无法读取" % rel
    return True, ""


def _write_manifest(runtime, tag, versions):
    """写清单（含文件哈希），先写临时文件再改名，避免写一半的清单。"""
    files = _hash_site_files(_site(runtime))
    m = {"tag": tag, "versions": versions}
    if files:
        m["files"] = files
    tmp = _manifest(runtime) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(m, f, sort_keys=True)
    os.replace(tmp, _manifest(runtime))


def installed(runtime, tag=None):
    """已装好且与当前 Python 匹配 → 返回 {包名: 版本}，否则 None。
    M-11：清单里记了文件哈希的，先比对通过才认「已装好」，被改动视为未装好。"""
    try:
        with open(_manifest(runtime), "r", encoding="utf-8") as f:
            m = json.load(f)
        if m.get("tag") == (tag or py_tag()) and os.path.isdir(_site(runtime)):
            ok, _why = _manifest_files_ok(runtime)
            if not ok:
                return None
            return m.get("versions") or {}
    except Exception:      # noqa: BLE001
        pass
    return None


def activate(runtime):
    """把 runtime\\site 加进 sys.path（追加在最后：自带的运行库优先）。启动时调用，几乎零开销。

    M-11：清单里记了文件哈希的，先比对 —— 被改动就拒绝加载（不加进 sys.path），
    并把原因记在 LAST_VERIFY_ERROR 供界面显示；无文件清单的老安装按现状补一份
    （信任首次使用，之后每次比对）。
    """
    global LAST_VERIFY_ERROR
    LAST_VERIFY_ERROR = ""
    site = _site(runtime)
    if not os.path.isdir(site):
        return False
    ok, why = _manifest_files_ok(runtime)
    if not ok:
        LAST_VERIFY_ERROR = why
        return False
    try:
        with open(_manifest(runtime), "r", encoding="utf-8") as f:
            m = json.load(f)
        if not isinstance(m.get("files"), dict):
            _write_manifest(runtime, m.get("tag") or py_tag(), m.get("versions") or {})
    except Exception:      # noqa: BLE001
        pass
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
    _write_manifest(runtime, tag, versions)   # M-11：清单同时记每个文件的 sha256
    shutil.rmtree(work, ignore_errors=True)            # 轮子装好后不留，省 30 多 MB
    return versions
