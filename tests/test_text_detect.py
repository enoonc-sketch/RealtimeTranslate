"""v2.15.5 文本识别（text_detect.py）：语种 / 文本类型 / 敏感信息 / 词典与生词本判定。纯逻辑，不需要界面。"""
import os
import random
import string
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
import text_detect as td

res = []


def ok(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    res.append(bool(cond))


# ---------------------------------------------------------------- 语种
LANG_CASES = [
    ("你好", "zh-CN"), ("我今天去商店买东西了", "zh-CN"), ("我今天去商店買東西了", "zh-TW"),
    ("こんにちは", "ja"), ("東京タワーに行きます", "ja"), ("経済", "ja"), ("안녕하세요", "ko"),
    ("Привет", "ru"), ("Україна — це країна в Європі, і ми її любимо.", "uk"),
    ("مرحبا بكم في هذا البرنامج", "ar"), ("שלום עולם", "he"), ("สวัสดีครับ", "th"), ("नमस्ते दुनिया", "hi"),
    ("hello", "en"), ("The quick brown fox jumps over the lazy dog", "en"), ("It's a beautiful day, isn't it?", "en"),
    ("Hola, ¿cómo estás? Me gusta mucho este libro.", "es"),
    ("Bonjour, je voudrais réserver une table pour ce soir.", "fr"),
    ("Ich habe keine Zeit, aber wir können morgen sprechen.", "de"),
    ("Non ho capito cosa vuoi dire, puoi ripetere?", "it"),
    ("Eu não sei o que você quer dizer com isso.", "pt"),
    ("Dit is een heel mooie dag, en ik ben blij.", "nl"),
    ("Nie wiem, co chcesz powiedzieć, ale to jest ważne.", "pl"),
    ("Bu çok güzel bir gün ve ben çok mutluyum.", "tr"),
    ("Saya tidak tahu apa yang kamu maksud dengan itu.", "id"),
    ("Jag vet inte vad du menar med det här.", "sv"),
    ("Tôi không biết bạn muốn nói gì với điều này.", "vi"),
    ("hola", "es"), ("bonjour", "fr"), ("danke", "de"), ("ciao", "it"),
    # 混合文本：按占比，不是「出现一个汉字就算中文」
    ("Please translate 你好 this sentence for me", "en"), ("我喜欢 iPhone 15", "zh-CN"),
    ("https://example.com/中文/页面", "en"),
]
for text, want in LANG_CASES:
    got = td.detect_lang(text).lang
    ok("lang %r -> %s (got %s)" % (text[:24], want, got), got == want)

ok("guess_lang keeps old contract",
   [td.guess_lang(x) for x in ("こんにちは", "안녕하세요", "Привет", "你好", "hello")] == ["ja", "ko", "ru", "zh", "en"])
ok("guess_lang zh-TW -> zh", td.guess_lang("我今天去商店買東西了") == "zh")
ok("no letters -> en, confidence 0", td.detect_lang("12345 !!!") == ("en", 0.0, "none"))
ok("unknown latin word -> en with low confidence", td.detect_lang("xyzzy").confidence == 0.0)
ok("bad input never raises", all(td.detect_lang(x).lang for x in (None, "", " ", 123, "\x00\x01")))

# ---------------------------------------------------------------- 文本类型
KIND_CASES = [
    ("", "empty"), ("   ", "empty"),
    ("https://example.com/a?b=1", "url"), ("www.baidu.com", "url"), ("example.com", "url"),
    ("a.b@c.com", "email"),
    ("C:\\Users\\me\\My Docs\\a.txt", "path"), ("/usr/local/bin", "path"), ("~/x/y", "path"), ("report.docx", "path"),
    ("2026-11-23 12:30", "number"), ("$1,234.50", "number"), ("+86 138 0013 8000", "number"), ("***", "symbols"),
    ("getUserName", "identifier"), ("user_login_count", "identifier"), ("a.b.c", "identifier"),
    ("MyProjectConfig2026Final", "identifier"),
    ("hello", "word"), ("hello world", "phrase"), ("This is a test.", "sentence"),
    ("你好", "word"), ("我今天去商店买东西了。", "sentence"),
    ("Hello world, this is a test.", "sentence"), ("Dr. Smith went to the U.S. on Jan. 5.", "sentence"),
    ("def f(x):\n    return x;\n", "code"), ("if (a == b) { run(); }", "code"), ("<div class=\"a\">hi</div>", "code"),
    ("my password: hunter2", "sensitive"), ("Your verification code is 483920", "sensitive"),
    ("密码是什么", "phrase"),
]
for text, want in KIND_CASES:
    got = td.analyze(text).kind
    ok("kind %r -> %s (got %s)" % (text[:24], want, got), got == want)

ok("url/email/path/number not auto-translated",
   not any(td.is_translatable(x) for x in ("https://a.com", "a@b.com", "/usr/bin/env", "12345", "***", "")))
ok("code / identifier / sentences still translatable",
   all(td.is_translatable(x) for x in ("getUserName", "def f(): pass", "Hello world.", "你好")))
ok("multi-line paragraph", td.analyze("First sentence here.\nSecond sentence here.").kind == "paragraph")

# ---------------------------------------------------------------- 敏感信息
POS = ["483920", "sk-abcdefghijklmnop1234", "110101199001011234", "110101 19900101 1234", "my password: hunter2",
       "4111 1111 1111 1111", "4111-1111-1111-1111", "AKIAIOSFODNN7EXAMPLE",
       "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijk",
       "ghp_" + "a1B2c3D4e5" * 4, "-----BEGIN RSA PRIVATE KEY-----", "postgres://user:pw123@db.host/x",
       "Authorization: Bearer abcdef0123456789ABCDEF", "密码：abc123", "验证码是 482913",
       "Your verification code is 483920", "export API_KEY=abc123xyz"]
NEG = ["Hello world, this is a test.", "第一行文字\n第二行文字\n第三行文字", "The password policy requires 8 characters.",
       "密码是什么", "4111 1111 1111 1112", "Item 12345 costs 20 dollars", "InternationalizationConfigManager2026",
       "MyProjectConfig2026Final", "README_v2_final_20261120_backup", "node_modules", "requirements-runtime-lock",
       "com.example.myapp.MainActivity", "2026", "hello"]
for t in POS:
    ok("sensitive: %r" % t[:30], td.is_sensitive(t))
for t in NEG:
    ok("not sensitive: %r" % t[:30], not td.is_sensitive(t))
ok("sensitive_kind labels", td.sensitive_kind("4111 1111 1111 1111") == "银行卡号"
   and td.sensitive_kind("sk-abcdefghijklmnop1234") == "API 密钥" and td.sensitive_kind("hello") is None)
random.seed(7)
alphabet = string.ascii_letters + string.digits
hit = sum(td.is_sensitive("".join(random.choice(alphabet) for _ in range(32))) for _ in range(500))
ok("random 32-char keys are caught (>=95%%, got %d/500)" % hit, hit >= 475)

# ---------------------------------------------------------------- 词典 / 生词本
for t, want in (("hello", True), ("hello world", True), ("one two three", True), ("one two three four", False),
                ("a" * 21, False), ("hello\nworld", False), ("", False), ("   ", False),
                ("你好", True), ("你好世界", True), ("hello.", True), ("Hello, world", False),
                ("12345", False), ("https://a.b", False), ("我今天去商店买东西了", False)):
    ok("dict candidate %r -> %s" % (t, want), td.is_dict_candidate(t) is want)
for t, want in (("hello", True), ("你好", True), ("hello world", False), ("hello-world", True), ("", False),
                ("a" * 31, False), ("12345", False), ("a@b.com", False)):
    ok("word entry %r -> %s" % (t, want), td.is_word_entry(t) is want)

# ---------------------------------------------------------------- 随机压测：任何输入都不抛异常
random.seed(11)
pool = string.printable + "你好こんにちは안녕Привет\u200b\x00\U0001F600éñß"
crash = 0
for _ in range(2000):
    s = "".join(random.choice(pool) for _ in range(random.randint(0, 80)))
    try:
        td.detect_lang(s)
        td.analyze(s)
        td.is_dict_candidate(s)
        td.is_word_entry(s)
    except Exception:       # noqa: BLE001
        crash += 1
ok("2000 random inputs, no exception", crash == 0)
big = "word " * 200000
ok("1 MB input is fast and safe", td.analyze(big).kind == "paragraph" and td.is_sensitive(big) is False)

print("\n%d/%d passed" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
