"""一键改全部版本号：python packaging/bump_version.py 2.15.5

改：desktop_translator.__version__、version_info.txt、installer.iss、NSIS 脚本、
packaging/VERSION、pyproject.toml、macOS Info.plist、deb control、MSIX 清单、
winget / Scoop / Chocolatey 清单，以及 tests 里写死的版本号。
不改：CHANGELOG.md / README.md（历史记录）。改完打印每个文件改了几处。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "build", "dist", ".buildenv", "Output", "node_modules", "pets", "offline_models"}
SKIP_FILES = {"CHANGELOG.md", "README.md"}
EXTS = (".py", ".txt", ".iss", ".nsi", ".toml", ".plist", ".xml", ".yaml", ".yml", ".json", ".nuspec",
        ".ps1", ".sh", ".bat", ".md", ".desktop", ".spec")
CONTROL = "control"
VERSION_FILE = "VERSION"  # packaging/VERSION 无扩展名，也要跟着改（v2.15.5 修复：之前漏改它，--check 会报不一致）


def current_version():
    src = open(os.path.join(ROOT, "desktop_translator.py"), encoding="utf-8").read()
    return re.search(r'__version__ = "([^"]+)"', src).group(1)


# 这些文件里「v2.15.4：」这类写法是历史注释（标明某段改动是哪一版加的），不能跟着改；
# 其余文件（清单、下载地址、文件名）里的 v 前缀是真实版本号，要改。
_COMMENT_STYLE = (".py", ".iss", ".nsi", ".yml", ".yaml", ".bat", ".sh", ".spec")
_WORKFLOWS = os.path.join(".github", "workflows")


def _pattern(old, keep_v_prefixed):
    esc = re.escape(old)
    if keep_v_prefixed:
        return re.compile(r"(?<![vV\d.])" + esc + r"(?![\d])")
    return re.compile(r"(?<![\d.])" + esc + r"(?![\d])")


def bump(old, new, dry=False):
    o4, n4 = old.split("."), new.split(".")
    tup_old, tup_new = ", ".join(o4) + ", 0", ", ".join(n4) + ", 0"
    changed = {}
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [x for x in dns if x not in SKIP_DIRS]
        for fn in fns:
            if fn in SKIP_FILES or not (fn.endswith(EXTS) or fn == CONTROL or fn == VERSION_FILE):
                continue
            fp = os.path.join(dp, fn)
            rel = os.path.relpath(fp, ROOT)
            try:
                txt = open(fp, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            # 代码 / 脚本 / 工作流里跳过 v 前缀（历史注释）；winget 等清单里的下载地址带 v，要改
            keep_v = fn.endswith(_COMMENT_STYLE) and not rel.startswith(os.path.join("packaging", "windows"))
            pat = _pattern(old, keep_v)
            n = len(pat.findall(txt)) + txt.count(tup_old)
            if not n:
                continue
            txt = pat.sub(new, txt).replace(tup_old, tup_new)
            changed[rel] = n
            if not dry:
                with open(fp, "w", encoding="utf-8", newline="") as f:
                    f.write(txt)
    return changed


def check():
    """CI 用：所有带版本号的打包文件都要和程序版本一致。"""
    v = current_version()
    must = {
        "version_info.txt": "'%s.0'" % v, "installer.iss": '"%s"' % v,
        "RealtimeTranslate_Setup.nsi": '"%s"' % v, "pyproject.toml": '"%s"' % v,
        os.path.join("packaging", "VERSION"): v,
        os.path.join("packaging", "macos", "Info.plist"): v,
        os.path.join("packaging", "linux", "debian", "control"): "Version: " + v,
        os.path.join("packaging", "windows", "msix", "AppxManifest.xml"): 'Version="%s.0"' % v,
        os.path.join("packaging", "windows", "scoop", "realtime-translate.json"): '"version": "%s"' % v,
        os.path.join("packaging", "windows", "chocolatey", "realtime-translate.nuspec"): "<version>%s</version>" % v,
        os.path.join("packaging", "windows", "winget", "RealtimeTranslate.RealtimeTranslate.yaml"): "PackageVersion: " + v,
    }
    bad = []
    for f, needle in must.items():
        try:
            if needle not in open(os.path.join(ROOT, f), encoding="utf-8").read():
                bad.append(f)
        except OSError:
            bad.append(f + "（缺文件）")
    for f in bad:
        print("版本号不一致：", f)
    print("版本 %s：%s" % (v, "全部一致" if not bad else "%d 个文件不一致" % len(bad)))
    return 1 if bad else 0


def main(argv):
    if len(argv) == 2 and argv[1] == "--check":
        return check()
    if len(argv) != 2 or not re.match(r"^\d+\.\d+\.\d+$", argv[1]):
        print("用法：python packaging/bump_version.py 主.次.修订（例如 2.15.5）")
        return 2
    old, new = current_version(), argv[1]
    if old == new:
        print("已经是 %s" % new)
        return 0
    for f, n in sorted(bump(old, new).items()):
        print("%3d  %s" % (n, f))
    print("%s → %s 完成。别忘了更新 CHANGELOG.md。" % (old, new))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
