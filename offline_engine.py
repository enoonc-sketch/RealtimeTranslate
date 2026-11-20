"""
轻量离线翻译引擎 —— 直接读取 Argos Translate 语言包（.argosmodel），
运行时只依赖 ctranslate2 + sentencepiece（+ numpy），不需要 argostranslate / torch / stanza，
所以打进独立 exe 后体积小得多。

语言包格式（与 Argos 官方一致）：一个目录，内含
    metadata.json          from_code / to_code / package_version / target_prefix ...
    model/                 CTranslate2 模型
    sentencepiece.model    分词模型

本模块不依赖 tkinter，可单独测试。
"""
import importlib.util
import json
import os
import re
import shutil
import sys
import threading
import zipfile

MAX_LOADED = 3          # 同时驻留内存的翻译模型数（每个约 100~300 MB），超出则淘汰最久未用
MAX_SENT_CHARS = 300    # 单句超过此长度时按逗号/空格再切，避免模型对超长句质量骤降
NO_SPACE_LANGS = ("zh", "ja", "th")

# 安全修复（2026-11-20，按安全评估报告）：
#   H-02：metadata.json 里的 from_code / to_code / package_version 直接拼安装路径，
#         未校验可导致目录遍历 + 任意目录删除 —— 只接受白名单字符，拼完再断言落点。
#   H-06：ASCII 缓存原先落在 %PUBLIC% / ProgramData（全用户可写），跨用户可投毒模型
#         —— 改成本用户专属目录。
#   M-12：模型加载时不验完整性 —— 安装时留 sha256 清单，加载前比对（无清单的老包首次
#         加载时按现状建清单，即信任首次使用，之后每次比对）。
_CODE_RE = re.compile(r"[A-Za-z0-9_-]{1,32}")
_VER_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]{0,31}")
_TOP_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]{0,63}")
_MANIFEST_DIRNAME = ".integrity"       # 哈希清单目录（与模型目录分离存放，不放在模型目录里）


class OfflineError(RuntimeError):
    """面向用户的错误，message 已是中文说明。"""


# ---------------------------------------------------------------- 运行环境
def runtime_present():
    """ctranslate2 与 sentencepiece 是否可用（不真正导入，几乎零开销）。"""
    try:
        return all(importlib.util.find_spec(m) is not None for m in ("ctranslate2", "sentencepiece"))
    except Exception:
        return False


def _ver_tuple(v):
    out = []
    for part in re.split(r"[.\-_]", str(v or "0")):
        out.append(int(part) if part.isdigit() else 0)
    return tuple(out)


# ---------------------------------------------------------------- 语言包
class Pkg:
    def __init__(self, path, source):
        self.path = path
        self.source = source
        with open(os.path.join(path, "metadata.json"), "r", encoding="utf-8") as f:
            m = json.load(f)
        self.from_code = m.get("from_code")
        self.to_code = m.get("to_code")
        self.version = str(m.get("package_version", "0"))
        self.target_prefix = m.get("target_prefix", "") or ""
        self.type = m.get("type", "translate")
        self.model_dir = os.path.join(path, "model")
        self.sp_path = os.path.join(path, "sentencepiece.model")
        self.name = os.path.basename(path)

    @property
    def usable(self):
        return (self.type in ("translate", None) and self.from_code and self.to_code
                and os.path.isdir(self.model_dir) and os.path.isfile(self.sp_path))

    @property
    def problem(self):
        if self.usable:
            return ""
        if os.path.isfile(os.path.join(self.path, "bpe.model")):
            return "旧版 BPE 分词语言包，暂不支持"
        return "语言包不完整"

    def label(self):
        return "%s → %s  v%s  [%s]" % (self.from_code, self.to_code, self.version, self.source)


def scan_dirs(dirs):
    """扫描若干目录（按优先级从高到低），返回 [Pkg]。同一语言对只保留版本最高者，版本相同取靠前目录。"""
    found = []
    for d, source in dirs:
        if not d or not os.path.isdir(d):
            continue
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for n in names:
            p = os.path.join(d, n)
            if n.startswith("_") or not os.path.isfile(os.path.join(p, "metadata.json")):
                continue
            try:
                found.append(Pkg(p, source))
            except Exception:
                continue
    best = {}
    for idx, pkg in enumerate(found):
        if not pkg.usable:
            continue
        key = (pkg.from_code, pkg.to_code)
        score = (_ver_tuple(pkg.version), -idx)
        if key not in best or score > best[key][0]:
            best[key] = (score, pkg)
    return [v[1] for v in best.values()], [p for p in found if not p.usable]


def _check_code(value, what):
    """H-02：metadata.json 里的语言代码 / 版本只接受白名单字符，否则拒绝安装。
    语言代码只允许字母数字 - _；版本号还允许 .（如 1.9），但不许含 ..。"""
    rx = _VER_RE if what == "package_version" else _CODE_RE
    if not isinstance(value, str) or not rx.fullmatch(value) or ".." in value:
        raise OfflineError("%s 不合法（只允许字母、数字、-、_，版本号还可含 .）：%r" % (what, value))
    return value


def _check_top(top):
    """H-02：zip 里 metadata.json 所在的顶层目录只取一层，且必须是安全目录名。"""
    if not top:
        return ""
    if not _TOP_RE.fullmatch(top) or top in (".", "..") or ".." in top:
        raise OfflineError("语言包顶层目录名不合法，已拒绝：%s" % top)
    return top


def _sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _manifest_path(pkg_path):
    """模型完整性清单的存放位置：与模型目录分离（模型目录的父目录下）。"""
    return os.path.join(os.path.dirname(pkg_path), _MANIFEST_DIRNAME,
                        os.path.basename(pkg_path) + ".sha256.json")


def _hash_tree(root, prefix=""):
    """对 root 下全部文件算 sha256，键为 prefix + 相对路径（统一用 / 作分隔符）。"""
    out = {}
    for r, _dirs, files in os.walk(root):
        for fn in files:
            p = os.path.join(r, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            try:
                out[prefix + rel] = _sha256_file(p)
            except OSError:
                return None
    return out


def _hash_model_files(pkg):
    """M-12：对原生库加载的文件算哈希：model/ 下全部文件 + sentencepiece.model。"""
    out = _hash_tree(pkg.model_dir, prefix="model/")
    if out is None:
        return None
    try:
        out["sentencepiece.model"] = _sha256_file(pkg.sp_path)
    except OSError:
        return None
    return out


def _write_manifest(pkg):
    """M-12：安装成功后把模型文件哈希写进清单（下次加载前比对）。写失败不阻安装。"""
    try:
        hashes = _hash_model_files(pkg)
        if not hashes:
            return False
        mp = _manifest_path(pkg.path)
        os.makedirs(os.path.dirname(mp), exist_ok=True)
        tmp = mp + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(hashes, f, sort_keys=True)
        os.replace(tmp, mp)
        return True
    except Exception:
        return False


def _verify_manifest(pkg):
    """M-12：加载前比对清单。返回 True（通过）/ False（被改动）/ None（无清单，老包）。"""
    try:
        mp = _manifest_path(pkg.path)
        if not os.path.isfile(mp):
            return None
        with open(mp, "r", encoding="utf-8") as f:
            want = json.load(f)
        if not isinstance(want, dict) or not want:
            return None
        got = _hash_model_files(pkg)
        if got is None:
            return False
        return got == want
    except Exception:
        return False


def install_package(archive, dest_dir, expected=None):
    """把 .argosmodel（zip）安全解压到 dest_dir，返回 Pkg。出错抛 OfflineError。

    expected（可选）：(from_code, to_code, package_version)，与索引条目一致才安装
    （H-03：防止下载的包与索引条目不符、被掉包后仍装上）。"""
    if not zipfile.is_zipfile(archive):
        raise OfflineError("不是有效的语言包文件（应为 .argosmodel）：%s" % os.path.basename(archive))
    os.makedirs(dest_dir, exist_ok=True)
    root = os.path.realpath(dest_dir)
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        metas = [n for n in names if n.endswith("metadata.json") and n.count("/") <= 1]
        if not metas:
            raise OfflineError("语言包里没有 metadata.json，文件可能已损坏")
        top = _check_top(metas[0].rsplit("/", 1)[0] if "/" in metas[0] else "")
        for n in names:                                   # 防 zip-slip
            target = os.path.realpath(os.path.join(root, n))
            if not (target == root or target.startswith(root + os.sep)):
                raise OfflineError("语言包包含非法路径，已拒绝：%s" % n)
        tmp_root = os.path.join(root, "_installing")
        shutil.rmtree(tmp_root, ignore_errors=True)
        z.extractall(tmp_root)
    src = os.path.join(tmp_root, top) if top else tmp_root
    try:
        probe = Pkg(src, "tmp")
    except Exception as e:
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise OfflineError("读取语言包信息失败：%s" % e)
    if not probe.usable:
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise OfflineError("%s（%s→%s）" % (probe.problem, probe.from_code, probe.to_code))
    # H-02：安装目录拼装前先校验 metadata 字段，拼完再断言落点在 dest_dir 内，
    # 然后再 rmtree / move —— 字段里再也藏不进 ../。
    _check_code(probe.from_code, "from_code")
    _check_code(probe.to_code, "to_code")
    _check_code(probe.version, "package_version")
    if expected is not None:
        exp_f, exp_t, exp_v = expected
        if (probe.from_code, probe.to_code, probe.version) != (exp_f, exp_t, str(exp_v)):
            shutil.rmtree(tmp_root, ignore_errors=True)
            raise OfflineError("语言包与索引条目不符（包内 %s→%s v%s，索引要求 %s→%s v%s），"
                               "已拒绝安装" % (probe.from_code, probe.to_code, probe.version,
                                             exp_f, exp_t, exp_v))
    final = os.path.join(root, top or "translate-%s_%s-%s" % (probe.from_code, probe.to_code, probe.version.replace(".", "_")))
    final_real = os.path.realpath(final)
    if not (final_real == root or final_real.startswith(root + os.sep)):
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise OfflineError("语言包安装目标超出安装目录，已拒绝：%s" % final)
    shutil.rmtree(final, ignore_errors=True)
    shutil.move(src, final)
    shutil.rmtree(tmp_root, ignore_errors=True)
    pkg = Pkg(final, "已安装")
    _write_manifest(pkg)          # M-12：安装时留哈希清单
    return pkg


# ---------------------------------------------------------------- 分句
_SENT_SPLIT = re.compile(r"(?<=[。！？])|(?<=[.!?])\s+|(?<=[…])\s*")
_SOFT_SPLIT = re.compile(r"(?<=[,，;；、:：])\s*|\s+")


def split_sentences(text):
    out = []
    for s in _SENT_SPLIT.split(text):
        s = s.strip()
        if not s:
            continue
        if len(s) <= MAX_SENT_CHARS:
            out.append(s)
            continue
        cur = ""
        for piece in _SOFT_SPLIT.split(s):
            if not piece:
                continue
            joiner = "" if (not cur or ord(cur[-1]) > 0x2E80) else " "
            if cur and len(cur) + len(piece) + 1 > MAX_SENT_CHARS:
                out.append(cur)
                cur = piece
            else:
                cur = cur + joiner + piece
        if cur:
            out.append(cur)
    return out


def _join(parts, to_code):
    sep = "" if (to_code or "").split("-")[0] in NO_SPACE_LANGS else " "
    return sep.join(p for p in parts if p)


# ---------------------------------------------------------------- 引擎
def _ascii_cache_root():
    # H-06：必须用本用户专属目录。原先用 %PUBLIC% / ProgramData（全用户可写），
    # 同机低权限用户可替换其中的模型文件，下次受害用户启动即加载被篡改的模型。
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return os.path.join(local, "RealtimeTranslate", "modelcache")
    # 非 Windows / 无 LOCALAPPDATA：用本用户临时目录下的隔离子目录（仍是本用户专属）。
    import tempfile
    return os.path.join(tempfile.gettempdir(), "RealtimeTranslate-modelcache")


class Engine:
    def __init__(self, dirs):
        """dirs: [(目录, 来源名)]，优先级从高到低。"""
        self.dirs = dirs
        self._lock = threading.RLock()
        self._loaded = {}          # path -> (translator, sp)；按插入顺序，末尾最新
        self.packs = []
        self.broken = []
        self.reload()

    # —— 目录扫描 ——
    def reload(self):
        with self._lock:
            self.packs, self.broken = scan_dirs(self.dirs)
            self._by_pair = {(p.from_code, p.to_code): p for p in self.packs}
            self._unload_all()

    def _unload_all(self):
        for tr, _ in self._loaded.values():
            try:
                tr.unload_model()
            except Exception:
                pass
        self._loaded.clear()

    def pairs(self):
        return sorted(self._by_pair)

    def available(self):
        return runtime_present() and bool(self._by_pair)

    def route(self, from_code, to_code):
        """返回需要依次使用的语言包列表；直达优先，否则经英语中转；没有则返回 []。"""
        if from_code == to_code:
            return []
        direct = self._by_pair.get((from_code, to_code))
        if direct:
            return [direct]
        a, b = self._by_pair.get((from_code, "en")), self._by_pair.get(("en", to_code))
        return [a, b] if (a and b) else []

    def can_translate(self, from_code, to_code):
        return from_code == to_code or bool(self.route(from_code, to_code))

    def describe(self):
        if not self._by_pair:
            return "未找到任何离线语言包"
        return "、".join("%s→%s" % k for k in self.pairs())

    # —— 加载 ——
    def _load(self, pkg):
        with self._lock:
            hit = self._loaded.pop(pkg.path, None)
            if hit:
                self._loaded[pkg.path] = hit
                return hit
            # M-12：原生库加载模型前先比对安装时留下的哈希清单；被改动就拒绝加载。
            # 无清单的老包（本修复之前装好的）首次加载时按现状建清单（信任首次使用），
            # 之后每次比对 —— 既不断掉老用户，也堵住“装好后悄悄换权重”的口子。
            verified = _verify_manifest(pkg)
            if verified is False:
                raise OfflineError("离线模型已被改动（%s），已拒绝加载。\n"
                                   "请在「离线语言包…」里重新下载 / 导入该语言对。" % pkg.name)
            if verified is None:
                _write_manifest(pkg)
            try:
                import ctranslate2
                import sentencepiece as spm
            except Exception as e:
                name = getattr(e, "name", "") or ""
                if (isinstance(e, ModuleNotFoundError) and name
                        and name.split(".")[0] in getattr(sys, "stdlib_module_names", ())):
                    # v2.13：标准版 exe 漏打包了某个标准库（例如 glob）——这是打包问题，给明确说法
                    raise OfflineError(
                        "离线引擎运行库加载失败：程序自带的标准库缺少「%s」。\n"
                        "请升级到 v2.13 及以上（已补齐）；或改用「离线版」安装包。" % name)
                raise OfflineError(
                    "离线引擎运行库加载失败：%s\n"
                    "（独立版请使用「离线版」安装包；从源码运行请 pip install ctranslate2 sentencepiece numpy）" % e)
            tr = None
            try:
                tr = ctranslate2.Translator(pkg.model_dir, device="cpu", inter_threads=1,
                                            intra_threads=0, compute_type="auto")
            except Exception as e:
                # 部分 Windows 版本的 ctranslate2 打不开含中文的路径：复制到纯英文目录再试
                if sys.platform.startswith("win") and not pkg.model_dir.isascii():
                    safe = os.path.join(_ascii_cache_root(), pkg.name)
                    # H-06/M-12：缓存副本也要验——不存在或被改动就重新复制，不直接信任旧缓存。
                    want = _hash_model_files(pkg)
                    want_model = ({k: v for k, v in want.items() if k != "sentencepiece.model"}
                                  if want else None)
                    got = _hash_tree(safe, prefix="model/") if os.path.isdir(safe) else None
                    if want_model is None or got != want_model:
                        shutil.rmtree(safe, ignore_errors=True)
                        shutil.copytree(pkg.model_dir, safe)
                    tr = ctranslate2.Translator(safe, device="cpu", inter_threads=1,
                                                intra_threads=0, compute_type="auto")
                else:
                    raise OfflineError("加载离线模型失败（%s）：%s" % (pkg.name, e))
            with open(pkg.sp_path, "rb") as f:            # 读字节再加载，规避 Windows 中文路径问题
                sp = spm.SentencePieceProcessor(model_proto=f.read())
            self._loaded[pkg.path] = (tr, sp)
            while len(self._loaded) > MAX_LOADED:
                oldest = next(iter(self._loaded))
                old_tr, _ = self._loaded.pop(oldest)
                try:
                    old_tr.unload_model()
                except Exception:
                    pass
            return tr, sp

    def warmup(self, pkgs):
        """提前把模型载入内存（首次翻译就不用再等 1~3 秒）。出错静默跳过，真正翻译时再报错。"""
        for pkg in list(pkgs)[:MAX_LOADED]:
            try:
                self._load(pkg)
            except Exception:
                pass

    # —— 翻译 ——
    def translate(self, text, from_code, to_code, cancelled=None):
        if from_code == to_code:
            return text
        legs = self.route(from_code, to_code)
        if not legs:
            have = self.describe()
            raise OfflineError(
                "没有 %s → %s 的离线语言包。\n已安装：%s\n"
                "可在「离线语言包…」里导入 .argosmodel，或重新构建离线版并在 offline_models.txt 加上该语言对。"
                % (from_code, to_code, have))
        for pkg in legs:
            text = self._run(pkg, text, cancelled)
        return text

    def _run(self, pkg, text, cancelled):
        tr, sp = self._load(pkg)
        lines = text.split("\n")
        # 收集所有句子，一次批量送入模型（比逐句调用快得多）
        plan, batch = [], []
        for ln in lines:
            sents = split_sentences(ln)
            plan.append(len(sents))
            batch.extend(sents)
        if not batch:
            return text
        if cancelled and cancelled():
            raise RuntimeError("cancelled")
        tokenized = [sp.encode(s, out_type=str) for s in batch]
        kw = dict(replace_unknowns=True, max_batch_size=1024, batch_type="tokens",
                  beam_size=4, num_hypotheses=1, length_penalty=0.2, max_decoding_length=512)
        if pkg.target_prefix:
            kw["target_prefix"] = [[pkg.target_prefix]] * len(tokenized)
        results = tr.translate_batch(tokenized, **kw)
        outs = []
        for r in results:
            toks = list(r.hypotheses[0])
            if pkg.target_prefix and toks and toks[0] == pkg.target_prefix:
                toks = toks[1:]
            outs.append(sp.decode_pieces(toks).replace("\u2581", " ").strip())
        out_lines, i = [], 0
        for n in plan:
            out_lines.append(_join(outs[i:i + n], pkg.to_code))
            i += n
        return "\n".join(out_lines)
