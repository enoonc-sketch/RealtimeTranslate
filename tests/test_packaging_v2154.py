"""v2.15.4 打包系统文件检查：格式能解析、版本号一致、各平台 spec 语法正确、关键约束不被改坏。无需任何打包工具。"""
import json, os, re, plistlib, xml.dom.minidom
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(BASE, "packaging")
rd = lambda *p: open(os.path.join(BASE, *p), encoding="utf-8").read()
ver = re.search(r'__version__ = "([^"]+)"', rd("desktop_translator.py")).group(1)
res = []
def ok(n, c): print(("PASS " if c else "FAIL ") + n); res.append(bool(c))

ok("Info.plist parses + version", plistlib.loads(rd("packaging", "macos", "Info.plist").encode())["CFBundleShortVersionString"] == ver)
plistlib.loads(rd("packaging", "macos", "entitlements.plist").encode()); ok("entitlements.plist parses", True)
for f in (("windows", "msix", "AppxManifest.xml"), ("windows", "chocolatey", "realtime-translate.nuspec"),
          ("linux", "realtime-translate.metainfo.xml")):
    xml.dom.minidom.parseString(rd("packaging", *f).encode()); ok("XML parses: " + f[-1], True)
ok("MSIX version", 'Version="%s.0"' % ver in rd("packaging", "windows", "msix", "AppxManifest.xml"))
sc = json.loads(rd("packaging", "windows", "scoop", "realtime-translate.json"))
ok("scoop json + version", sc["version"] == ver and "64bit" in sc["architecture"])
for f in os.listdir(os.path.join(P, "windows", "winget")):
    t = rd("packaging", "windows", "winget", f)
    ok("winget %s version" % f, "PackageVersion: %s" % ver in t and "ManifestVersion:" in t)
ok("deb control fields", all(k in rd("packaging", "linux", "debian", "control") for k in ("Package:", "Version: " + ver, "Depends:", "Description:")))
de = rd("packaging", "linux", "realtime-translate.desktop")
ok(".desktop has required keys", de.startswith("[Desktop Entry]") and all(k in de for k in ("Type=Application", "Name=", "Exec=", "Icon=")))
ok("pyproject version + entry point", 'version = "%s"' % ver in rd("pyproject.toml") and 'realtime-translate = "desktop_translator:main"' in rd("pyproject.toml"))
mods = re.findall(r'"(\w+)"', rd("pyproject.toml").split("py-modules = [")[1].split("]")[0])
ok("pyproject modules all exist", all(os.path.exists(os.path.join(BASE, m + ".py")) for m in mods if m != "license_secret"))
for spec in (("packaging", "macos", "realtime_translate_mac.spec"), ("packaging", "linux", "realtime_translate_linux.spec")):
    src = rd(*spec)
    compile(src, spec[-1], "exec")
    excl = src.split("excludes=[")[1].split("]")[0]
    ok("%s compiles, keeps tray_win32 importable" % spec[-1], "tray_win32" not in excl and "'tray_win32'" in src)
for sh in ("macos/build_macos.sh", "linux/build_linux.sh", "linux/build_deb.sh", "linux/build_appimage.sh",
           "linux/install.sh", "linux/AppRun", "linux/debian/postinst", "linux/debian/prerm", "linux/debian/postrm"):
    t = rd("packaging", *sh.split("/"))
    ok("shebang + LF: " + sh, t.startswith("#!/") and "\r\n" not in t)
ok("deb never touches $HOME data", "rm -rf" not in rd("packaging", "linux", "debian", "postrm"))
ok("linux install.sh keeps data unless asked", "--purge" in rd("packaging", "linux", "install.sh"))
wf = rd(".github", "workflows", "release.yml")
ok("release workflow covers all platforms", all(j in wf for j in ("windows:", "windows-offline:", "macos:", "linux:", "release:")))
ok("old workflow no longer fires on tags", "tags:" not in rd(".github", "workflows", "build-exe.yml"))
import subprocess  # noqa: F401  (仅确认标准库可用)
assert all(res), "%d 项失败" % res.count(False)
