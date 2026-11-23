"""2026-11-20 安全 + 稳定性修复的回归测试（按安全评估报告编号）。

只用标准库 + 已装的 numpy/sentencepiece/ctranslate2（fake 模型用），不联网、
不弹窗口，Linux 上可跑。风格与 tests/ 里其他脚本一致：ok() + sys.exit。
"""
import hashlib
import io
import json
import os
import stat
import struct
import subprocess
import sys
import tempfile
import threading
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import doc_translate as dt
import history_store
import offline_engine as oe
import ocr_backends
import ocr_win
import pack_downloader as pd
import pet_pack
import runtime_installer as ri
import settings_io
import single_instance
import tts_win
import update_check

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


TMP = tempfile.mkdtemp(prefix="secfix-")


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return path


def make_argos_zip(path, from_code, to_code, version="1.0"):
    """最小结构合法的 .argosmodel（模型文件是空的，只够过 Pkg 可用性检查）。"""
    meta = {"package_version": version, "argos_version": "1.9",
            "from_code": from_code, "from_name": from_code,
            "to_code": to_code, "to_name": to_code, "type": "translate"}
    return make_zip(path, {
        "p/metadata.json": json.dumps(meta).encode("utf-8"),
        "p/model/model.bin": b"",
        "p/sentencepiece.model": b"",
    })


# ---------------------------------------------------------------- H-02 安装路径遍历
evil_zip = make_argos_zip(os.path.join(TMP, "evil.argosmodel"), "../../evil", "zh")
try:
    oe.install_package(evil_zip, os.path.join(TMP, "models-evil"))
    ok("H-02 evil from_code rejected", False)
except oe.OfflineError as e:
    ok("H-02 evil from_code rejected", "from_code" in str(e) or "不合法" in str(e))
    ok("H-02 evil dir not created", not os.path.exists(os.path.join(TMP, "models-evil", "evil")))

good_zip = make_argos_zip(os.path.join(TMP, "good.argosmodel"), "en", "zh")
pkg = oe.install_package(good_zip, os.path.join(TMP, "models-good"))
ok("H-02 valid pack installs", pkg.usable and pkg.from_code == "en" and pkg.to_code == "zh")
# M-12：安装时写了哈希清单
mp = oe._manifest_path(pkg.path)
ok("M-12 manifest written on install", os.path.isfile(mp))
ok("M-12 manifest verifies", oe._verify_manifest(pkg) is True)
with open(os.path.join(pkg.model_dir, "model.bin"), "wb") as f:
    f.write(b"tampered")
ok("M-12 tampered model fails verify", oe._verify_manifest(pkg) is False)

# H-02：安装目标断言 —— version 含 ../ 时拒绝
evil_ver = make_argos_zip(os.path.join(TMP, "evil2.argosmodel"), "en", "zh", version="../../x")
try:
    oe.install_package(evil_ver, os.path.join(TMP, "models-evil2"))
    ok("H-02 evil version rejected", False)
except oe.OfflineError:
    ok("H-02 evil version rejected", True)

# ---------------------------------------------------------------- H-03 语言包下载校验
ok("H-03 pinned en-zh 1.9 hash known",
   pd.pinned_sha256({"from_code": "en", "to_code": "zh", "package_version": "1.9"})
   == "433e7c4f034d87fbe2353161e05f18646d7999452f801a4e1f0378522b9850ab")
ok("H-03 pinned zh-en 1.9 hash known",
   pd.pinned_sha256({"from_code": "zh", "to_code": "en", "package_version": "1.9"})
   == "62e7af5a3a48b530e47b7b3e5c78c2de79073ecd815750d2bf3ab35b4a67da2d")
ok("H-03 unpinned pair has no hash",
   pd.pinned_sha256({"from_code": "zh", "to_code": "en", "package_version": "1.0"}) is None)
best = {("en", "zh"): {"from_code": "en", "to_code": "zh", "package_version": "1.9"},
        ("zh", "en"): {"from_code": "zh", "to_code": "en", "package_version": "1.0"}}
ok("H-03 unpinned_pairs flags only unpinned",
   pd.unpinned_pairs([("en", "zh"), ("zh", "en")], best) == [(("zh", "en"), "1.0")])
ok("H-04 apply_replace keeps https", pd.apply_replace(
    "https://argos-net.com/a", "argos-net.com=mirror.cn") == "https://mirror.cn/a")
ok("H-04 apply_replace rejects scheme downgrade", pd.apply_replace(
    "https://argos-net.com/a", "https://argos-net.com=http://evil.cn") == "https://argos-net.com/a")
ok("H-04 apply_replace rejects non-hostname", pd.apply_replace(
    "https://argos-net.com/a", "argos-net.com=evil.cn/x?y=1") == "https://argos-net.com/a")
ok("H-04 apply_replace multi-pair (test compat)", pd.apply_replace(
    "https://pypi.org/a files.pythonhosted.org",
    "pypi.org=m1.cn;files.pythonhosted.org=m2.cn") == "https://m1.cn/a m2.cn")
# 校验拦截已按用户决定去掉（2026-11-21）：http 链接也允许下载，不再拦截。
ok("H-03 http non-loopback now allowed (user decision)", pd._url_ok("http://evil.cn/index.json"))
ok("H-03 https accepted", pd._url_ok("https://argos-net.com/x.argosmodel"))
ok("H-03 http loopback accepted (local test server)", pd._url_ok("http://127.0.0.1:9/x"))

# download() 的哈希校验：本地 HTTP 服务器
import http.server


class _H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        data = open(os.path.join(TMP, "good.argosmodel"), "rb").read()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = "http://127.0.0.1:%d/good.argosmodel" % srv.server_address[1]
dest = os.path.join(TMP, "dl.argosmodel")
# 哈希校验已按用户决定去掉（2026-11-21）：错哈希也不再拒绝，文件照常留下。
pd.download(url, dest, expected_sha256="0" * 64)
ok("H-03 download wrong hash no longer rejected (user decision)", os.path.isfile(dest))
good_sha = hashlib.sha256(open(os.path.join(TMP, "good.argosmodel"), "rb").read()).hexdigest()
pd.download(url, dest, expected_sha256=good_sha)
ok("H-03 download right hash accepted", os.path.isfile(dest))
srv.shutdown()

# ---------------------------------------------------------------- H-04 设置导入
sample = {"app": "RealtimeTranslate", "version": 1,
          "config": {"pack_mirror": "https://example.com", "proxy_host": "evil.example",
                     "proxy_port": 8080, "proxy_enabled": True, "proxy_user": "u",
                     "proxy_pass": "SECRET-should-never-import", "sl": "en"},
          "glossary": []}
text = json.dumps(sample)
defaults = {"pack_mirror": "", "proxy_host": "", "proxy_port": 0, "proxy_enabled": False,
            "proxy_user": "", "proxy_pass": "my-local-password", "sl": "auto"}
cfg, ignored, err = settings_io.import_settings(text, defaults)
ok("H-04 import drops proxy_pass", cfg.get("proxy_pass") == "my-local-password" and ignored >= 1)
ok("H-04 import keeps other keys", cfg.get("proxy_host") == "evil.example")
changes = settings_io.sensitive_import_changes(text, defaults, defaults)
keys = [c[0] for c in changes]
ok("H-04 sensitive changes list all network keys",
   keys == ["pack_mirror", "proxy_enabled", "proxy_host", "proxy_port", "proxy_user"])
ok("H-04 sensitive changes empty when nothing changes",
   settings_io.sensitive_import_changes(json.dumps({"app": "RealtimeTranslate", "version": 1,
                                                   "config": {"sl": "en"}, "glossary": []}),
                                        defaults, defaults) == [])
ok("H-04 trusted mirror host recognized",
   pd.is_trusted_mirror_host("cdn.jsdelivr.net") and not pd.is_trusted_mirror_host("evil.cn"))

# ---------------------------------------------------------------- H-05 轮子钉死
ok("H-05 pinned numpy version", ri.pinned_wheel("numpy")["version"] == "2.5.5")
ok("H-05 pinned numpy win wheel hash",
   ri.pinned_wheel("numpy")["sha256"]["numpy-2.5.5-cp312-cp312-win_amd64.whl"]
   == "919eb420662b0b4ba34889df503f3d5329775b0c1d5f7e5f5af4fba8315b1e30")
ok("H-05 pinned ctranslate2 linux wheel hash",
   ri.pinned_wheel("ctranslate2")["sha256"]
   ["ctranslate2-4.9.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"]
   == "5d9b3edd73ba665f16a19cd3a498ce74fbfb6204bc0ac321f00f2600a41e8810")


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._data).encode("utf-8")


def _fake_index(versions):
    rel = {}
    for v, fn in versions:
        rel[v] = [{"packagetype": "bdist_wheel", "filename": fn,
                   "url": "https://x/" + fn, "size": 10,
                   "digests": {"sha256": "deadbeef"}}]
    return {"releases": rel}


_orig_open = pd._open
try:
    pd._open = lambda url, timeout, headers=None: _FakeResp(_fake_index([
        ("2.6.0", "numpy-2.6.0-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"),
        ("2.5.5", "numpy-2.5.5-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl")]))
    try:
        ri.find_wheel("numpy", "cp312")
        ok("H-05 newer-than-pinned version refused", False)
    except oe.OfflineError as e:
        ok("H-05 newer-than-pinned version refused", "只信任钉死的" in str(e))
    pd._open = lambda url, timeout, headers=None: _FakeResp(_fake_index([
        ("2.5.5", "numpy-2.5.5-cp312-cp312-manylinux_2_27_x86_64.whl")]))
    try:
        ri.find_wheel("numpy", "cp312")
        ok("H-05 unlisted wheel filename refused", False)
    except oe.OfflineError as e:
        ok("H-05 unlisted wheel filename refused", "校验表" in str(e))
    pd._open = lambda url, timeout, headers=None: _FakeResp(_fake_index([
        ("2.5.5", "numpy-2.5.5-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl")]))
    w = ri.find_wheel("numpy", "cp312")
    ok("H-05 pinned wheel accepted with pinned sha",
       w["version"] == "2.5.5" and w["sha256"]
       == "704d819265e5d1064d932968e9ee85fff2103ccc78c05b878c06943ba27b8507")
finally:
    pd._open = _orig_open

# ---------------------------------------------------------------- H-06 ASCII 缓存目录
os.environ["LOCALAPPDATA"] = os.path.join(TMP, "local")
ok("H-06 cache root under LOCALAPPDATA, not PUBLIC",
   oe._ascii_cache_root().startswith(os.path.join(TMP, "local")))
del os.environ["LOCALAPPDATA"]
os.environ.pop("PUBLIC", None)
os.environ.pop("ProgramData", None)
ok("H-06 cache root fallback is user temp, not shared",
   "Public" not in oe._ascii_cache_root() and "ProgramData" not in oe._ascii_cache_root())

# ---------------------------------------------------------------- M-01 OCR 脚本校验
# v2.15.6：比对归一化后的哈希 —— Windows 检出的 CRLF 版内容没变也必须通过，
# 只比原始哈希会在云端 Windows 构建里误报“已被改动”。
real_ps = os.path.join(ROOT, "winocr.ps1")
ok("M-01 pinned winocr.ps1 hash matches tree",
   ocr_win._script_hash_ok(real_ps))

_calls = {"run": 0, "cmd": None}


class _FakeProc:
    returncode = 0
    stdout = b"hello"
    stderr = b""


def _fake_run(cmd, **kw):
    _calls["run"] += 1
    _calls["cmd"] = cmd
    return _FakeProc()


_orig = (ocr_win.IS_WIN, ocr_win.find_powershell, ocr_win._script_path, subprocess.run)
ocr_win.IS_WIN = True
ocr_win.find_powershell = lambda: "/bin/true"
ocr_win._script_path = lambda: real_ps
subprocess.run = _fake_run
try:
    out, _err = ocr_win._run_ps(os.path.join(TMP, "x.png"), lang="xx-unknown")
    ok("M-01 _run_ps works with real script", out == "hello")
    ok("L-03 unknown OCR lang maps to auto",
       _calls["cmd"][(_calls["cmd"].index("-Language") + 1)] == "auto")
    tampered = os.path.join(TMP, "bad.ps1")
    open(tampered, "w").write("evil")
    ocr_win._script_path = lambda: tampered
    before = _calls["run"]
    try:
        ocr_win._run_ps(os.path.join(TMP, "x.png"))
        ok("M-01 tampered script refused before run", False)
    except ocr_win.OcrError as e:
        ok("M-01 tampered script refused before run",
           "已被改动" in str(e) and _calls["run"] == before)
    ocr_win._script_path = lambda: real_ps
    # L-05：信号量满了就报繁忙，不再起进程
    ocr_win._OCR_SEM.acquire()
    ocr_win._OCR_SEM.acquire()
    try:
        ocr_win._run_ps(os.path.join(TMP, "x.png"))
        ok("L-05 OCR semaphore caps concurrency", False)
    except ocr_win.OcrError as e:
        ok("L-05 OCR semaphore caps concurrency", "繁忙" in str(e))
    finally:
        ocr_win._OCR_SEM.release()
        ocr_win._OCR_SEM.release()
finally:
    ocr_win.IS_WIN, ocr_win.find_powershell, ocr_win._script_path, subprocess.run = _orig

# L-10：OCR JSON 结构校验 + 坏坐标跳过
_orig_run_ps = ocr_win._run_ps
ocr_win.IS_WIN = True
ocr_win._run_ps = lambda *a, **k: (
    '{"lines": [{"text": 123, "words": "bad"}, "junk", '
    '{"text": "ok", "words": [{"text": "hi", "x": "abc", "y": 2, "w": 3, "h": 4}, '
    '{"text": "yo", "x": 1, "y": 2, "w": 3, "h": 4}]}]}', "")
try:
    data = ocr_win._ocr_json("x.png", None, 20)
    ok("L-10 _ocr_json drops malformed lines/words",
       isinstance(data.get("lines"), list) and len(data["lines"]) == 2
       and data["lines"][0]["words"] == [] and data["lines"][1]["text"] == "ok")
    words = ocr_win.ocr_words("x.png", None, 20)
    ok("L-10 ocr_words skips bad coords", words == [{"text": "yo", "x": 1, "y": 2, "w": 3, "h": 4}])
finally:
    ocr_win._run_ps = _orig_run_ps
    ocr_win.IS_WIN = False

# L-07：固定路径优先（Linux 上 tesseract 可能不存在，只验顺序逻辑不崩）
ok("L-07 tesseract_path callable", ocr_backends.tesseract_path() is None or
   isinstance(ocr_backends.tesseract_path(), str))

# ---------------------------------------------------------------- M-02 单实例
ok("M-02 mutex name unchanged (installer.iss compat)",
   single_instance.DEFAULT_MUTEX_NAME == "RealtimeTranslate_SingleInstance")
ok("M-02 no verified window on Linux", single_instance._find_existing_window() is None)
ok("M-02 bring_to_front False on Linux", single_instance.bring_existing_to_front() is False)
si = single_instance.SingleInstance()
ok("M-02 lockfile acquire works", si.acquire() is True)
si.release()

# ---------------------------------------------------------------- M-03/M-04/H-01 剪贴板与密码
import desktop_translator as dtr

ok("M-03 password-field check False on Linux",
   dtr._foreground_is_password_field_win() is False)
ok("H-01 sensitive clip: 6-digit OTP", dtr.is_sensitive_clip("483920"))
ok("H-01 sensitive clip: sk- key", dtr.is_sensitive_clip("sk-abcdefghijklmnop1234"))
ok("H-01 sensitive clip: 18-digit ID", dtr.is_sensitive_clip("110101199001011234"))
ok("H-01 sensitive clip: password= value", dtr.is_sensitive_clip("my password: hunter2"))
ok("H-01 sensitive clip: normal sentence not flagged",
   not dtr.is_sensitive_clip("Hello world, this is a test."))
ok("H-01 sensitive clip: normal multi-line not flagged",
   not dtr.is_sensitive_clip("第一行文字\n第二行文字\n第三行文字"))
ok("M-04 DPAPI protect returns None on non-Windows", dtr._dpapi_protect("secret") is None)
ok("M-04 DPAPI unprotect passes legacy plaintext through",
   dtr._dpapi_unprotect("plain-old-password") == "plain-old-password")
ok("M-04 DPAPI unprotect of dpapi: value fails closed on non-Windows",
   dtr._dpapi_unprotect("dpapi:AAAA") is None)
# L-02 Edge token 格式校验已按用户决定去掉（2026-11-21）：拿到什么 token 就
# 用什么，不再因格式拒绝；拦截页内容交给微软端点报 401/403。
ok("L-02 MS token format check removed (user decision)", not hasattr(dtr, "_MS_TOKEN_RE"))

# ---------------------------------------------------------------- M-05/L-04 docx 白名单与上限


def make_docx(paras, extra=None):
    body = "".join("<w:p>%s</w:p>" % "".join('<w:r><w:t>%s</w:t></w:r>' % r for r in runs)
                   for runs in paras)
    xml = ('<w:document xmlns:w="urn:docx"><w:body>%s</w:body></w:document>' % body)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml.encode("utf-8"))
        z.writestr("[Content_Types].xml", b"<Types/>")
        z.writestr("word/styles.xml", b"<styles/>")
        if extra:
            for k, v in extra.items():
                z.writestr(k, v)
    return buf.getvalue()


data = make_docx([["Hello"]], extra={"vbaProject.bin": b"MACRO",
                                     "../evil.txt": b"x",
                                     "customXml/item1.xml": b"<x/>"})
out = dt.docx_rebuild(data, ["你好"])
names = zipfile.ZipFile(io.BytesIO(out)).namelist()
ok("M-05 docx rebuild drops macro + traversal",
   "vbaProject.bin" not in names and "../evil.txt" not in names)
ok("M-05 docx rebuild keeps allowed parts",
   "[Content_Types].xml" in names and "word/document.xml" in names
   and "word/styles.xml" in names and "customXml/item1.xml" in names)
ok("M-05 docx entry allowlist rejects drive paths",
   not dt._docx_entry_allowed("C:\\evil\\x.exe") and not dt._docx_entry_allowed("/abs/path"))
ok("L-04 document.xml cap is 50MB", dt.MAX_DOCX_XML_BYTES == 50 * 1024 * 1024)
orig_xml_cap, orig_total_cap = dt.MAX_DOCX_XML_BYTES, dt.MAX_DOCX_TOTAL_BYTES
try:
    dt.MAX_DOCX_XML_BYTES = 10
    try:
        dt.docx_document_xml(make_docx([["0123456789ABCDEF"]]))
        ok("L-04 oversized document.xml rejected", False)
    except ValueError:
        ok("L-04 oversized document.xml rejected", True)
    dt.MAX_DOCX_XML_BYTES = orig_xml_cap
    dt.MAX_DOCX_TOTAL_BYTES = 10
    try:
        dt.docx_rebuild(make_docx([["Hi"]], extra={"word/big.bin": b"x" * 20}), ["你好"])
        ok("M-05 oversized docx total rejected", False)
    except ValueError:
        ok("M-05 oversized docx total rejected", True)
finally:
    dt.MAX_DOCX_XML_BYTES, dt.MAX_DOCX_TOTAL_BYTES = orig_xml_cap, orig_total_cap

# ---------------------------------------------------------------- M-06 历史库
hs_path = os.path.join(TMP, "history.db")
hs = history_store.HistoryStore(hs_path, max_items=3)
for i in range(5):
    hs.add("src%d" % i, "dst%d" % i, fav=True)
mode = stat.S_IMODE(os.stat(hs_path).st_mode)
ok("M-06 history.db created 0600", mode == 0o600)
orig_fav_cap = history_store.MAX_FAV_ITEMS
try:
    history_store.MAX_FAV_ITEMS = 3
    hs2 = history_store.HistoryStore(os.path.join(TMP, "history2.db"), max_items=3)
    for i in range(5):
        hs2.add("s%d" % i, "d%d" % i, fav=True)
    favs = hs2.search("", fav_only=True, limit=100)
    ok("M-06 favourites capped (oldest dropped)", len(favs) == 3
       and {r["src"] for r in favs} == {"s2", "s3", "s4"})
finally:
    history_store.MAX_FAV_ITEMS = orig_fav_cap

# ---------------------------------------------------------------- M-11 运行时清单
rt = os.path.join(TMP, "runtime")
os.makedirs(os.path.join(rt, "site", "pkg1"), exist_ok=True)
open(os.path.join(rt, "site", "pkg1", "__init__.py"), "w").write("x=1\n")
ri._write_manifest(rt, "cp312", {"pkg1": "1.0"})
ok("M-11 manifest includes file hashes",
   isinstance(json.load(open(ri._manifest(rt)))["files"], dict)
   and "pkg1/__init__.py" in json.load(open(ri._manifest(rt)))["files"])
ok("M-11 installed() ok when intact", ri.installed(rt) == {"pkg1": "1.0"})
ok("M-11 activate() ok when intact", ri.activate(rt) is True)
open(os.path.join(rt, "site", "pkg1", "__init__.py"), "w").write("x=2  # tampered\n")
ok("M-11 installed() refuses tampered", ri.installed(rt) is None)
ok("M-11 activate() refuses tampered", ri.activate(rt) is False)
ok("M-11 activate() records reason", bool(ri.LAST_VERIFY_ERROR))

# ---------------------------------------------------------------- M-12 模型清单（加载前验）
# 一个没有清单的老包目录（install_package 之外直接放进去的）：首次验返回 None（信任首次使用）
bare = os.path.join(TMP, "bare-pack")
os.makedirs(os.path.join(bare, "model"), exist_ok=True)
json.dump({"package_version": "1.0", "from_code": "en", "to_code": "zh",
           "type": "translate"}, open(os.path.join(bare, "metadata.json"), "w"))
open(os.path.join(bare, "model", "model.bin"), "wb").write(b"")
open(os.path.join(bare, "sentencepiece.model"), "wb").write(b"")
bare_pkg = oe.Pkg(bare, "x")
ok("M-12 _verify_manifest None when no manifest", oe._verify_manifest(bare_pkg) is None)
ok("M-12 TOFU writes manifest for legacy pack",
   oe._write_manifest(bare_pkg) is True and oe._verify_manifest(bare_pkg) is True)

# ---------------------------------------------------------------- L-01 .pet 包
import pet_pack as pp


def make_pet(w, h, anims, frame_bytes):
    comp = __import__("zlib").compress(frame_bytes)
    head = json.dumps({"w": w, "h": h, "anims": anims,
                       "frames": [[0, len(comp)]]}).encode("utf-8")
    return pp.MAGIC + struct.pack("<I", len(head)) + head + comp


all_anims = {a: [0] for a in pp.ANIMS}
good_pet = os.path.join(TMP, "good.pet")
open(good_pet, "wb").write(make_pet(2, 2, all_anims, bytes(16)))
p = pp.PetPack(good_pet)
ok("L-01 valid pet loads", p.w == 2 and len(p.rgba(0)) == 16)
bad_pet = os.path.join(TMP, "bad.pet")
open(bad_pet, "wb").write(make_pet(0, 2, all_anims, bytes(16)))
try:
    pp.PetPack(bad_pet)
    ok("L-01 zero-size pet rejected", False)
except pp.PetPackError:
    ok("L-01 zero-size pet rejected", True)
bad_idx = dict(all_anims)
bad_idx["idle"] = [99]
open(bad_pet, "wb").write(make_pet(2, 2, bad_idx, bytes(16)))
try:
    pp.PetPack(bad_pet)
    ok("L-01 out-of-range frame index rejected", False)
except pp.PetPackError:
    ok("L-01 out-of-range frame index rejected", True)
bomb = os.path.join(TMP, "bomb.pet")
open(bomb, "wb").write(make_pet(2, 2, all_anims, bytes(10000)))
try:
    pp.PetPack(bomb).rgba(0)
    ok("L-01 decompression bomb rejected", False)
except pp.PetPackError:
    ok("L-01 decompression bomb rejected", True)

# ---------------------------------------------------------------- L-05 实时刷新下限
ok("L-05 live_interval clamp floor is 5", settings_io._CLAMPS["live_interval"] == (5, 30))
cfg5, _ig, _err = settings_io.import_settings(json.dumps(
    {"app": "RealtimeTranslate", "version": 1,
     "config": {"live_interval": 2}, "glossary": []}), {"live_interval": 5})
ok("L-05 import clamps live_interval 2 -> 5", cfg5.get("live_interval") == 5)
ok("L-05 DEFAULTS live_interval is 5", dtr.DEFAULTS["live_interval"] == 5)

# ---------------------------------------------------------------- 稳定性：TTS/STT/更新检查/PDF
ok("L-09 TTS max chars is 20000", tts_win.MAX_TTS_CHARS == 20000)
tmp_script = tts_win._write_script_temp(tts_win._PS_SCRIPT, ".ps1")
ok("M-01 TTS script temp verified on write",
   tts_win._sha256_file(tmp_script) == tts_win._sha256_text(tts_win._PS_SCRIPT))
# 写入后被改动 → 重新验哈希能发现
with open(tmp_script, "w", encoding="utf-8") as f:
    f.write("tampered")
ok("M-01 TTS script tamper detectable",
   tts_win._sha256_file(tmp_script) != tts_win._sha256_text(tts_win._PS_SCRIPT))
tts_win._cleanup_files([tmp_script])
old_file = os.path.join(tempfile.gettempdir(), "rt-tts-old-test.txt")
open(old_file, "w").write("x")
os.utime(old_file, (1000000, 1000000))
tts_win.cleanup_stale_temp_files(max_age_seconds=86400)
ok("L-08 stale temp files cleaned", not os.path.exists(old_file))


class _BigResp:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        return b"x" * (n if n > 0 else 10)


tag, why = update_check.fetch_latest_tag(opener=lambda url, timeout: _BigResp())
ok("stability update_check caps response read", tag is None and why is not None)

import pdf_translate as pt

orig_pdf_cap = pt.MAX_PDF_BYTES
try:
    pt.MAX_PDF_BYTES = 10
    ok("stability translate_pdf refuses oversize before read",
       pt.extract_pdf_text(b"x" * 11) == "")
finally:
    pt.MAX_PDF_BYTES = orig_pdf_cap

# ---------------------------------------------------------------- M-07 lockfiles
lock = open(os.path.join(ROOT, "requirements-lock.txt")).read()
ok("M-07 lockfile pins pyinstaller", "pyinstaller==6.22.3" in lock)
rlock = open(os.path.join(ROOT, "requirements-runtime-lock.txt")).read()
ok("M-07 runtime lockfile pins all four",
   all(x in rlock for x in ("numpy==2.5.5", "pyyaml==6.0.3",
                            "sentencepiece==0.2.3", "ctranslate2==4.9.0")))
wf = open(os.path.join(ROOT, ".github", "workflows", "build-exe.yml")).read()
ok("M-07 workflow uses lockfiles",
   "-r requirements-lock.txt" in wf and "-r requirements-runtime-lock.txt" in wf
   and "pyinstaller>=6.0" not in wf)

print("---- %d/%d passed ----" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
