"""
下载并解压离线语言包到 offline_models\\（供 build_offline.bat 打包进安装包）。只用标准库。

用法：
  python prepare_offline_models.py                  按 offline_models.txt 下载
  python prepare_offline_models.py en-zh zh-en ja-en   指定语言对
  python prepare_offline_models.py --from-dir D:\\pk    不联网：安装 D:\\pk 里已有的 .argosmodel 文件
  python prepare_offline_models.py --index-url URL      换索引地址（镜像）
  python prepare_offline_models.py --replace A=B        把下载链接里的 A 换成 B（镜像）

如果下载域名（argos-net.com）在你的网络下不通：用浏览器/代理手动下载 .argosmodel，
放进 offline_models\\ 或 offline_models\\_downloads\\ 目录后重新运行本脚本即可（会自动识别）。
"""
import argparse
import glob
import json
import os
import shutil
import sys
import time
import urllib.request
import zipfile

# Windows 控制台默认编码不一定是 UTF-8（如 cp1252），中文 print 会直接崩；
# 把 stdout/stderr 强制成 UTF-8（失败也不影响主流程）。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import offline_engine as oe   # noqa: E402

OUT = os.path.join(HERE, "offline_models")
DL = os.path.join(OUT, "_downloads")
INDEX = "https://raw.githubusercontent.com/argosopentech/argospm-index/main/index.json"
UA = {"User-Agent": "RealtimeTranslate-build/2.2"}


def read_pairs(path):
    pairs = []
    if os.path.exists(path):
        for ln in open(path, encoding="utf-8"):
            ln = ln.split("#", 1)[0].strip()
            if ln:
                pairs.append(ln)
    return pairs


def fetch(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)


def download(url, dest):
    tmp = dest + ".part"
    last = None
    for attempt in range(3):
        try:
            with fetch(url, 90) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                got, t0 = 0, time.time()
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
                    got += len(b)
                    if total:
                        print("\r    %.0f / %.0f MB (%d%%)" % (got / 1e6, total / 1e6, got * 100 // total), end="", flush=True)
            print()
            if not zipfile.is_zipfile(tmp):
                raise RuntimeError("下载内容不是有效的语言包（可能被网络劫持/拦截页替换）")
            os.replace(tmp, dest)
            return
        except Exception as e:      # noqa: BLE001
            last = e
            print("\n    第 %d 次失败：%s" % (attempt + 1, e))
            time.sleep(2 * (attempt + 1))
    if os.path.exists(tmp):
        os.remove(tmp)
    raise last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pairs", nargs="*")
    ap.add_argument("--from-dir")
    ap.add_argument("--index-url", default=INDEX)
    ap.add_argument("--replace", help="A=B：把下载链接里的 A 替换成 B")
    a = ap.parse_args()

    os.makedirs(DL, exist_ok=True)
    # 1) 本地已有的 .argosmodel（手动下载 / --from-dir）
    local = glob.glob(os.path.join(OUT, "*.argosmodel")) + glob.glob(os.path.join(DL, "*.argosmodel"))
    if a.from_dir:
        local += glob.glob(os.path.join(a.from_dir, "*.argosmodel"))
    installed_local = set()
    for f in local:
        try:
            pkg = oe.install_package(f, OUT)
            installed_local.add((pkg.from_code, pkg.to_code))
            print("[本地] 已安装 %s → %s  (%s)" % (pkg.from_code, pkg.to_code, os.path.basename(f)))
        except oe.OfflineError as e:
            print("[本地] 跳过 %s：%s" % (os.path.basename(f), e))

    # 2) 需要从网络获取的语言对
    wanted = a.pairs or read_pairs(os.path.join(HERE, "offline_models.txt"))
    todo = []
    for w in wanted:
        try:
            f, t = w.lower().split("-")
        except ValueError:
            sys.exit("语言对格式应为 en-zh，收到：%s" % w)
        if (f, t) not in installed_local:
            todo.append((f, t))
    failed = []
    if todo and not a.from_dir:
        print("\n获取语言包索引 …")
        try:
            with fetch(a.index_url, 30) as r:
                index = json.loads(r.read().decode("utf-8"))
        except Exception as e:      # noqa: BLE001
            sys.exit("无法下载索引：%s\n可用 --index-url 指定镜像，或手动下载 .argosmodel 放进 offline_models\\ 再重试。" % e)
        for f, t in todo:
            cands = [p for p in index if p.get("from_code") == f and p.get("to_code") == t]
            if not cands:
                print("[×] 索引里没有 %s → %s" % (f, t))
                failed.append("%s-%s" % (f, t))
                continue
            p = max(cands, key=lambda x: oe._ver_tuple(x.get("package_version")))
            links = [l for l in p.get("links", []) if l.startswith("http")]
            if a.replace and "=" in a.replace:
                old, new = a.replace.split("=", 1)
                links = [l.replace(old, new) for l in links]
            dest = os.path.join(DL, os.path.basename(links[0]) if links else "x.argosmodel")
            print("\n[下载] %s → %s  v%s" % (f, t, p.get("package_version")))
            done = False
            for link in links:
                try:
                    print("    " + link)
                    if not os.path.exists(dest):
                        download(link, dest)
                    pkg = oe.install_package(dest, OUT)
                    print("    已安装：%s" % pkg.name)
                    done = True
                    break
                except Exception as e:      # noqa: BLE001
                    print("    失败：%s" % e)
            if not done:
                failed.append("%s-%s" % (f, t))

    # 3) 汇总
    packs, broken = oe.scan_dirs([(OUT, "内置")])
    print("\n==== 已就绪的语言包 ====")
    for p in sorted(packs, key=lambda x: (x.from_code, x.to_code)):
        size = sum(os.path.getsize(os.path.join(r, fn)) for r, _, fs in os.walk(p.path) for fn in fs) / 1e6
        print("  %s → %s   v%s   %.0f MB" % (p.from_code, p.to_code, p.version, size))
    for p in broken:
        print("  ! 不可用：%s（%s）" % (p.name, p.problem))
    if failed:
        print("\n未能获取：%s" % "、".join(failed))
        print("请手动下载对应 .argosmodel（链接见索引 index.json 的 links 字段）放进 offline_models\\ 后重新运行。")
    if not packs:
        sys.exit(2)
    # 清理下载缓存可省空间：_downloads 不会被打进安装包
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
