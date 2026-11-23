"""v2.15.6：脚本哈希校验必须容忍换行符差异（LF vs CRLF）。

根因：仓库没有 .gitattributes，Windows 上 git 检出会把 LF 转成 CRLF，
云端 Windows 构建打出来的包里 winocr.ps1 就是 CRLF 版 —— 内容没变，
原始 SHA256 却对不上，全新安装都会误报“winocr.ps1 已被改动”。
朗读的临时脚本同理：Windows 文本模式写文件会把 \\n 转成 \\r\\n。
修法：比对前先把 CRLF 归一化成 LF 再算哈希；真被改了内容照样拦得住。
"""
import hashlib
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ocr_win
import tts_win

PASSED = []
FAILED = []


def check(name, cond):
    (PASSED if cond else FAILED).append(name)
    print(("PASS " if cond else "FAIL ") + name)


def _tmp(data):
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


def test_ocr_script_hash():
    raw = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "winocr.ps1"), "rb").read()
    lf = _tmp(raw)
    crlf = _tmp(raw.replace(b"\n", b"\r\n"))
    bad = _tmp(raw + b"\n# tampered\n")
    try:
        check("ocr hash: LF 版通过", ocr_win._script_hash_ok(lf))
        check("ocr hash: CRLF 版也通过（内容没变）", ocr_win._script_hash_ok(crlf))
        check("ocr hash: 内容被改照样拦住", not ocr_win._script_hash_ok(bad))
        try:
            ocr_win._script_hash_ok("/nonexistent/winocr.ps1")
            check("ocr hash: 读不到文件抛 OSError", False)
        except OSError:
            check("ocr hash: 读不到文件抛 OSError", True)
        check("ocr hash: CRLF 版原始哈希确实和 pin 不同（确认误报成立）",
              hashlib.sha256(raw.replace(b"\n", b"\r\n")).hexdigest() != ocr_win._SCRIPT_SHA256)
    finally:
        for p in (lf, crlf, bad):
            try:
                os.remove(p)
            except OSError:
                pass


def test_tts_temp_script_crlf_write():
    # 模拟 Windows 文本模式写文件：\\n 被转成 \\r\\n。再验哈希必须通过。
    orig_write_temp = tts_win._write_temp

    def _write_temp_crlf(text, suffix):
        fd, path = tempfile.mkstemp(suffix=suffix, prefix="rt-tts-")
        with os.fdopen(fd, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(text)
        return path

    tts_win._write_temp = _write_temp_crlf
    try:
        path = tts_win._write_script_temp(tts_win._PS_SCRIPT)
        check("tts: CRLF 写入的临时脚本验哈希通过", os.path.isfile(path))
        with open(path, "rb") as f:
            data = f.read()
        check("tts: 临时脚本内容归一化后和原文一致",
              hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
              == tts_win._sha256_text(tts_win._PS_SCRIPT))
        try:
            os.remove(path)
        except OSError:
            pass
    finally:
        tts_win._write_temp = orig_write_temp

    # 被改过的临时脚本必须拒绝
    def _write_temp_tampered(text, suffix):
        return _tmp((text + "\n# tampered\n").encode("utf-8"))

    tts_win._write_temp = _write_temp_tampered
    try:
        try:
            tts_win._write_script_temp(tts_win._PS_SCRIPT)
            check("tts: 被改过的临时脚本被拒绝", False)
        except OSError:
            check("tts: 被改过的临时脚本被拒绝", True)
    finally:
        tts_win._write_temp = orig_write_temp


if __name__ == "__main__":
    test_ocr_script_hash()
    test_tts_temp_script_crlf_write()
    print("\n%d/%d passed" % (len(PASSED), len(PASSED) + len(FAILED)))
    if FAILED:
        print("FAILED:", FAILED)
        sys.exit(1)
