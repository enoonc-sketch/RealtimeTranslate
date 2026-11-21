"""发版后生成 / 更新 winget、Scoop、Chocolatey 清单里的 sha256 和下载地址。

  python packaging/make_manifests.py                      # 用本地 Output\ 里的文件算 sha256
  python packaging/make_manifests.py --repo 你/仓库        # 同时把 OWNER/RealtimeTranslate 换成真实仓库
清单里的下载地址指向 GitHub Release：https://github.com/<repo>/releases/download/v<版本>/<文件名>
"""
import argparse
import hashlib
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PK = os.path.join(ROOT, "packaging", "windows")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def version():
    return re.search(r'__version__ = "([^"]+)"',
                     open(os.path.join(ROOT, "desktop_translator.py"), encoding="utf-8").read()).group(1)


def patch(path, repl):
    txt = open(path, encoding="utf-8").read()
    for a, b in repl:
        txt = re.sub(a, b, txt)
    open(path, "w", encoding="utf-8", newline="\n").write(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=None, help="GitHub 仓库，例如 me/RealtimeTranslate")
    ap.add_argument("--out", default=os.path.join(ROOT, "Output"))
    a = ap.parse_args()
    v = version()
    setup = os.path.join(a.out, "RealtimeTranslate_Setup_v%s.exe" % v)
    portable = os.path.join(a.out, "RealtimeTranslate_v%s_portable.zip" % v)
    repo_fix = [(r"OWNER/RealtimeTranslate", a.repo)] if a.repo else []
    if os.path.exists(setup):
        h = sha256(setup)
        patch(os.path.join(PK, "winget", "RealtimeTranslate.RealtimeTranslate.installer.yaml"),
              [(r"InstallerSha256: \w+", "InstallerSha256: " + h.upper())] + repo_fix)
        patch(os.path.join(PK, "chocolatey", "tools", "chocolateyinstall.ps1"),
              [(r"checksum64     = '\w+'", "checksum64     = '%s'" % h)] + repo_fix)
        print("安装包 sha256:", h)
    else:
        print("[跳过] 没有", setup)
    if os.path.exists(portable):
        h = sha256(portable)
        patch(os.path.join(PK, "scoop", "realtime-translate.json"), [(r'"hash": "\w+"', '"hash": "%s"' % h)] + repo_fix)
        print("免安装 zip sha256:", h)
    else:
        print("[跳过] 没有", portable)
    for f in (os.path.join(PK, "winget", n) for n in os.listdir(os.path.join(PK, "winget"))):
        if repo_fix:
            patch(f, repo_fix)
    print("清单已更新。winget：提交到 microsoft/winget-pkgs；Scoop：放进你的 bucket；Chocolatey：choco pack + choco push")


if __name__ == "__main__":
    main()
