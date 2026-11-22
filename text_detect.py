"""文本识别 —— 纯逻辑模块（只用标准库，不碰 Tk / 网络 / Windows，可单测）。

把原来散在 desktop_translator.py / typing_detect.py 里又粗又重复的识别逻辑收到一处：

  1. 语种识别 detect_lang()
     - 先按文字脚本数占比（CJK 每字按 2 计，信息量比字母大），再在脚本内细分：
       假名 → 日语；谚文 → 韩语；纯汉字按「简体专有字 / 繁体专有字 / 日语专有汉字」判
       简体、繁体、日语；西里尔字母里有 і ї є ґ → 乌克兰语，否则俄语。
     - 拉丁字母语种（英 / 西 / 法 / 德 / 意 / 葡 / 荷 / 波 / 土 / 印尼 / 瑞典 / 越南）用
       「常用停用词命中 + 特征字母 + 常见短词」打分；分数相同或没有证据时回落英语，
       并给出较低的置信度，调用方可以据此决定要不要改走在线引擎的自动检测。
     - 先去掉网址 / 邮箱再判断，避免 https://example.com/中文 这类内容把结果带偏。
  2. 文本类型识别 analyze()：空 / 敏感 / 网址 / 邮箱 / 路径 / 纯数字 / 纯符号 /
     代码 / 标识符 / 单词 / 短语 / 句子 / 段落，并给出「值不值得自动翻译」。
  3. 敏感信息识别 sensitive_kind() / is_sensitive()：验证码、身份证号、银行卡号（Luhn 校验）、
     API 密钥（sk- / ghp_ / AKIA / AIza / xox / JWT 等）、密码 / 令牌键值对、私钥、
     带账号密码的连接串、长串高熵 token。desktop_translator 与 typing_detect 共用这一份。

所有函数都是纯函数，任何输入（None、超长、乱码）都不抛异常。
"""
import math
import re
from collections import Counter, namedtuple

SAMPLE_CHARS = 600           # 语种识别只看开头这么多字符，够准又快

Detection = namedtuple("Detection", "lang confidence script")
Info = namedtuple("Info", "kind lang confidence translatable reason")

# ---------------------------------------------------------------- 脚本
_CJK_GROUPS = ("han", "kana", "hangul")


def _script(ch):
    """一个字符属于哪种文字脚本；标点 / 数字 / 空白返回 None。"""
    o = ord(ch)
    if o < 0x250:
        return "latin" if ch.isalpha() else None
    if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or 0xF900 <= o <= 0xFAFF or 0x20000 <= o <= 0x2A6DF:
        return "han"
    if 0x3040 <= o <= 0x30FF or 0x31F0 <= o <= 0x31FF or 0xFF66 <= o <= 0xFF9F:
        return "kana"
    if 0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or 0x3130 <= o <= 0x318F:
        return "hangul"
    if 0x0400 <= o <= 0x052F:
        return "cyrillic"
    if 0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF:
        return "arabic"
    if 0x0E00 <= o <= 0x0E7F:
        return "thai"
    if 0x0590 <= o <= 0x05FF:
        return "hebrew"
    if 0x0900 <= o <= 0x097F:
        return "devanagari"
    if 0x0370 <= o <= 0x03FF:
        return "greek"
    if 0x1E00 <= o <= 0x1EFF or 0x0250 <= o <= 0x02AF:     # 越南语带调符号 / 扩展拉丁
        return "latin" if ch.isalpha() else None
    return None


_SCRIPT_LANG = {"thai": "th", "hebrew": "he", "devanagari": "hi", "greek": "el", "arabic": "ar"}

# ---------------------------------------------------------------- 汉字：简 / 繁 / 日
# 只收「只在简体 / 只在繁体里出现」的字（用 OpenCC 开发期校验过，两集合无交集）。
_SIMPLIFIED = set("万与专业东两严个为丽举义乐习乡书买乱争亏产亲仅从们价优会传体儿党兰关养兽写军农冲决况净减击创别剧办务动劳势华协单卖卫厅历压县参双变号叹后听员团园围国图圆场坏块坚备够头夺奋妇妈孙学宁宝实审对导将尔尝尽层属岁岛币帅师带帮并广庆库应庙开异弃张弹强归当录彻忆忧怀态总恋惊惯愿懒战户扑执扩扫扬换摄摆摇数断无旧时显晓暂术机杀杂权条来极构标样检楼欢欧毁毕气汉汤沟没浅测济浓涂涛润涨涩渐渔温湾湿滚滞满滤潜灭灯灵灾点烂烦热爱爷犹独狭猎猪献环现琐电画畅疗疯盖盘矿码础确礼祸离种积称窃竞笔笼筑签简类粮约级纪纯纱纲纳纵纷纸线练组细织终绍经结绕绘给络绝统继续维综绿编缘缩网罗罚职联聪肠肤胜脏脑脚腊艰艺节芦苏苹茧药莱获营萧蓝虑虫虽虾蚁补装见观规视览觉计订认讨让训议讯记讲许论设访证评识诉词译试诗话该详语误说请诸读课谁调谈谊谋谢谱贝负贡财责贤败账货质贩贪贫贬购贯贱贴贵贷贸费贺资赏赔赖赛赞赠赶趋跃踪车轨轩转轮软轰轻载较辅辆辈辑输辞边达迁过迈运还这进远违连迟适选递逻遗邓邮邻郑酱释钉钓钙钟钢钥钦钱钻铁铃铅铜银铺链销锁锅锈锋错锚锡锦键锯锻镇镜长门闪闭问闯闲间闷闹闻阀阅队阳阴阵阶际陆陈险随隐隶难雾静页顶项顺须顾顿预领频题颜额风飞饭饮饱饼馆马驱驶驻驾骂骄骆验骑骗骤鱼鲜鸟鸡鸣鸭鸿麦黄齐齿龄龙龟")
_TRADITIONAL = set("並亂來個們備傳僅價優兒兩別創劇動務勝勞勢協參員問單嘆嘗嚴國圍園圓圖團執堅場塊塗壓壞夠奪奮婦媽孫學實寧審寫寶將專對導層屬島帥師帶幣幫幹庫廟廣廳張強彈後從徹悶愛態慣慮慶憂憶應懶懷戀戰戶掃揚換搖撲擊擴擺攝敗數斷時暢暫曉書會東條棄業極構樂樓標樣機檢權欽歐歡歲歷歸殺毀氣決沒況淨淺減測湯溝溫滅滯滾滿漁漢漲漸潛潤澀濃濕濟濤濾灣災為無煩熱燈營爛爭爺爾狹猶獨獲獵獸獻現瑣環產畢畫異當瘋療發盡盤確碼礎礦禍禮種稱穀積竊競筆節築簡簽籠糧紀約納純紗紙級紛細紹終組結絕絡給統經綜綠維綱網線緣編練縣縮縱總織繞繪繭繼續罰罵羅義習聞聯聰職聽腦腳腸膚臘與舉舊艱華萊萬蓋蕭藍藝藥蘆蘇蘋蘭號虧蝦蟲蟻術衛衝裏補裝裡見規視親覺覽觀訂計訊討訓記訪設許訴評詞試詩話該詳認語誤說誰課誼調談請論諸謀講謝證識譜譯議讀變讓豬貝負財貢貧貨販貪貫責貴貶買貸費貼貿賀資賞賠賢賣賤質賬賴購賽贈贊趕趨蹤躍車軌軍軒軟較載輔輕輛輩輪輯輸轉轟辦辭農這連進運過達違遞遠適遲遷選遺邁還邊邏郵鄉鄧鄭鄰醬釋釘釣鈣鈴鉛銀銅銷鋒鋪鋸鋼錄錢錦錨錫錯鍋鍛鍵鎖鎮鏈鏡鏽鐘鐵鑰鑽長門閃閉開閒間閥閱闖關陣陰陳陸陽隊階際隨險隱隸雖雙雜雞離難電霧靈靜頁頂項順須預頓領頭頻題額顏願類顧顯風飛飯飲飽餅養館馬駐駕駛駱騎騙驅驕驗驚驟髒體髮鬧魚鮮鳥鳴鴨鴻麗麥麼黃點黨齊齒齡龍龜")
# 日语专有汉字（新字体 / 国字）：简体和繁体里都不用这个写法。
_JA_KANJI = set("経続働込畑峠辻枠駅険験売読説辺浜帰戦変気発図労権様桜歳円県圧鉄総価")
_JA_KANJI -= _SIMPLIFIED
_JA_KANJI -= _TRADITIONAL
_SIMPLIFIED -= _TRADITIONAL
_TRADITIONAL -= _SIMPLIFIED

# ---------------------------------------------------------------- 拉丁字母语种
_STOP = {
    "en": "the and of to in is are was were it that this with for on as at by be have has not you we they he she "
          "will would can from or but what which there if do does my your his her our their been than then them "
          "these those would could should about into over just also don isn doesn didn ll re ve",
    "es": "el la los las de que y en un una es por con para se no su al lo como más pero sus le ya este esta "
          "porque entre cuando muy sin sobre también hay está están son del yo mi tu qué cómo dónde ese eso nos "
          "ser fue tiene tengo puede",
    "fr": "le la les des du et en un une est que qui dans pour pas sur au aux avec ce cet cette il elle je nous "
          "vous ne se son sa ses mais ou où être avoir très plus sont ont suis fait comme tout bien aussi même "
          "ces leur leurs été était qu",
    "de": "der die das und ist nicht ein eine zu den von mit sich auf für dem des im auch es ich sie wir er als "
          "wie aber oder wenn nur noch bei nach aus wird werden hat haben sind war dass dieser diese einen "
          "einem einer kann mehr sehr schon über",
    "it": "il lo gli di che è un una per con non sono del della dei delle da si come ma anche più questo questa "
          "io tu noi loro al alla nel nella ho ha hanno essere molto quando dove perché cosa tutto sul sulla "
          "degli nei",
    "pt": "os as do da dos das que em um uma para com não nao por mais se na no nos nas como mas foi ao ele ela "
          "eu você voce são sao está tem muito também isso esse essa seu sua meu minha ser estar foram pelo "
          "pela",
    "nl": "de het een en van ik te dat die in is niet zijn op aan met als voor er maar om dan ook nog wel bij "
          "naar uit hij zij we je dit wat of worden heeft hebben wordt deze zou kan meer geen over",
    "pl": "nie na że się jest jak ale po co tak za od czy już tylko być ma są był jego jej ich mnie dla przez "
          "który która które to jestem będzie bardzo może tego tym przy",
    "tr": "ve bir bu için ile da çok ne ben sen biz siz mi mı mu değil var yok gibi daha ama kadar olarak sonra "
          "her ki şey evet hayır nasıl neden bunu olan oldu",
    "id": "yang dan di ke dari ini itu untuk dengan tidak ada pada adalah saya kamu kami mereka akan juga atau "
          "sudah bisa karena apa bagaimana satu dalam oleh lebih sangat harus tetapi dapat belum",
    "sv": "och att det som en ett är på för av med den har inte till jag du vi de om men så var kan från eller "
          "ska vara här nu mycket också sig vad hur",
    "vi": "và của là có không được một những cho trong tôi bạn chúng với này đã các để khi người rất cũng",
}
_STOPWORDS = {lang: {w for w in words.split() if len(w) > 1} for lang, words in _STOP.items()}
_PRIORITY = ("en", "es", "fr", "de", "it", "pt", "nl", "pl", "tr", "id", "sv", "vi")

# 单个词也能认的常见招呼 / 高频词（单词没有停用词可命中时用）。
_SHORT = {
    "es": "hola gracias adiós adios amigo señor señora buenos buenas bienvenido",
    "fr": "bonjour merci bonsoir salut bienvenue oui madame monsieur",
    "de": "hallo danke bitte tschüss tschuss guten willkommen entschuldigung",
    "it": "ciao grazie buongiorno buonasera prego benvenuto arrivederci",
    "pt": "olá obrigado obrigada bom tchau bem-vindo",
    "nl": "dank alstublieft goedemorgen welkom tot ziens",
    "pl": "cześć dziękuję proszę witam dzień dobry",
    "tr": "merhaba teşekkürler lütfen günaydın hoşgeldiniz",
    "id": "terima kasih selamat pagi halo",
    "sv": "tack hej välkommen",
}
_SHORT_WORDS = {w: lang for lang, ws in _SHORT.items() for w in ws.split() if " " not in w}

# 特征字母 → {语种: 权重}
_CHAR_HINTS = {
    "ñ": {"es": 2.0}, "¿": {"es": 3.0}, "¡": {"es": 3.0},
    "ã": {"pt": 2.0}, "õ": {"pt": 2.0},
    "ß": {"de": 2.0},
    "å": {"sv": 1.5},
    "ł": {"pl": 2.0}, "ą": {"pl": 2.0}, "ę": {"pl": 2.0},
    "ć": {"pl": 1.5}, "ń": {"pl": 1.5}, "ś": {"pl": 1.5}, "ź": {"pl": 1.5}, "ż": {"pl": 1.5},
    "ş": {"tr": 2.0}, "ğ": {"tr": 2.0}, "ı": {"tr": 2.0}, "İ": {"tr": 2.0},
    "œ": {"fr": 2.0}, "î": {"fr": 0.8}, "û": {"fr": 0.8},
    "ä": {"de": 0.8, "sv": 0.6}, "ö": {"de": 0.8, "sv": 0.6, "tr": 0.8}, "ü": {"de": 0.8, "tr": 0.8},
    "ç": {"fr": 0.6, "pt": 0.6, "tr": 0.5},
    "è": {"fr": 0.5, "it": 0.5}, "ù": {"fr": 0.5, "it": 0.5}, "à": {"fr": 0.4, "it": 0.4, "pt": 0.4},
    "ê": {"fr": 0.6, "pt": 0.5}, "ô": {"fr": 0.5, "pt": 0.4}, "â": {"fr": 0.4, "pt": 0.4},
    "ï": {"fr": 0.5, "nl": 0.5}, "ë": {"fr": 0.4, "nl": 0.5},
    "é": {"fr": 0.4, "es": 0.3, "pt": 0.3, "it": 0.3},
    "á": {"es": 0.4, "pt": 0.4}, "í": {"es": 0.4, "pt": 0.4}, "ú": {"es": 0.4, "pt": 0.4},
    "ó": {"es": 0.3, "pt": 0.3, "it": 0.3, "pl": 0.6},
}
_VI_ONLY = set("ăđơư")                # 越南语专有；另外 U+1EA0–U+1EF9 的带调字母也算
_UK_LETTERS = set("іїєґІЇЄҐ")
_RU_LETTERS = set("ыэъёЫЭЪЁ")

_URL_STRIP = re.compile(r"(?:[a-z][a-z0-9+.\-]*://|www\.)\S+|\b[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+", re.I)
_WORD_RE = re.compile(r"[^\W\d_]+")
_APOS_EN = re.compile(r"[A-Za-z][’'](?:s|t|ll|re|ve|m|d)\b", re.I)
_APOS_FR = re.compile(r"\b[ldjnstmc][’']|\bqu[’']", re.I)
_APOS_IT = re.compile(r"\b(?:dell|nell|sull|all|un|quest|c)[’']", re.I)


def _is_vi_char(ch):
    return ch in _VI_ONLY or 0x1EA0 <= ord(ch) <= 0x1EF9


def _detect_latin(text):
    """拉丁字母文本的语种：(语种, 置信度)。"""
    low = text.lower()
    score = Counter()
    toks = _WORD_RE.findall(low)
    for tok in toks:
        for lang, words in _STOPWORDS.items():
            if tok in words:
                score[lang] += 1.0
        lang = _SHORT_WORDS.get(tok)
        if lang:
            score[lang] += 2.0
    for ch in low:
        hint = _CHAR_HINTS.get(ch)
        if hint:
            for lang, w in hint.items():
                score[lang] += w
        elif _is_vi_char(ch):
            score["vi"] += 2.0
    score["en"] += 1.0 * len(_APOS_EN.findall(text))
    score["fr"] += 0.7 * len(_APOS_FR.findall(text))
    score["it"] += 0.7 * len(_APOS_IT.findall(text))

    ranked = sorted(score.items(), key=lambda kv: (-kv[1], _PRIORITY.index(kv[0])))
    if not ranked or ranked[0][1] < 1.0:
        return "en", 0.0                        # 没证据：回落英语，置信度 0
    best_lang, best = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    if best - second < 0.5:                     # 平局：证据不足以区分
        tied = [lg for lg, sc in ranked if best - sc < 0.5]
        pick = "en" if "en" in tied else tied[0]
        return pick, round(min(0.4, best / (best + second + 3.0)), 2)
    return best_lang, round(min(0.99, (best - second) / (best + 1.0) + 0.2), 2)


def _detect_han(text):
    """只有汉字（没有假名 / 谚文）时分简体、繁体、日语。"""
    s = sum(1 for ch in text if ch in _SIMPLIFIED)
    t = sum(1 for ch in text if ch in _TRADITIONAL)
    j = sum(1 for ch in text if ch in _JA_KANJI)
    if j and not s and j >= t:
        return "ja", 0.6
    if t > s:
        return "zh-TW", round(min(0.95, 0.55 + 0.1 * (t - s)), 2)
    if s:
        return "zh-CN", round(min(0.95, 0.55 + 0.1 * (s - t)), 2)
    return "zh-CN", 0.5                         # 简繁通用字：按简体


def detect_lang(text):
    """识别语种，返回 Detection(lang, confidence, script)。

    lang 是 'zh-CN' / 'zh-TW' / 'ja' / 'ko' / 'en' / 'es' ... ；confidence 0~1；
    没有任何文字（纯数字 / 符号）时返回 ('en', 0.0, 'none')。"""
    try:
        t = _URL_STRIP.sub(" ", str(text or "")[:SAMPLE_CHARS])
    except Exception:       # noqa: BLE001
        return Detection("en", 0.0, "none")
    cnt = Counter()
    for ch in t:
        s = _script(ch)
        if s:
            cnt[s] += 1
    if not cnt:
        return Detection("en", 0.0, "none")
    han, kana, hangul = cnt["han"], cnt["kana"], cnt["hangul"]
    weight = {g: (n * 2 if g in _CJK_GROUPS else n) for g, n in cnt.items()}
    total = float(sum(weight.values()))
    cjk_w = sum(weight[g] for g in _CJK_GROUPS if g in weight)

    if cjk_w / total >= 0.3:                    # CJK 占一定比例就按 CJK 判
        if hangul and hangul >= kana and hangul * 2 >= han:
            return Detection("ko", round(min(0.99, 0.6 + cjk_w / total * 0.4), 2), "hangul")
        if kana >= 2 or (kana and kana / float(kana + han) >= 0.2):
            return Detection("ja", round(min(0.99, 0.7 + kana / float(kana + han) * 0.3), 2), "kana")
        if han:
            lang, conf = _detect_han(t)
            return Detection(lang, conf, "han")
        if kana:                                # 只有 1 个假名且没有汉字
            return Detection("ja", 0.6, "kana")
        return Detection("ko", 0.6, "hangul")

    others = [(g, w) for g, w in weight.items() if g not in _CJK_GROUPS]
    top = max(others, key=lambda gw: gw[1])[0] if others else "latin"
    if top == "cyrillic":
        uk = sum(1 for ch in t if ch in _UK_LETTERS)
        ru = sum(1 for ch in t if ch in _RU_LETTERS)
        if uk > ru:
            return Detection("uk", 0.85, "cyrillic")
        return Detection("ru", 0.9 if ru else 0.7, "cyrillic")
    if top in _SCRIPT_LANG:
        return Detection(_SCRIPT_LANG[top], 0.9, top)
    lang, conf = _detect_latin(t)
    return Detection(lang, conf, "latin")


def guess_lang(text):
    """语种粗判，返回基础语言代码（'zh' 不分简繁），供离线引擎「自动检测」/ MyMemory 用。
    与旧版 desktop_translator.guess_lang 同一返回约定，但识别更准。"""
    return detect_lang(text).lang.split("-")[0]


# ---------------------------------------------------------------- 敏感信息
_SENS_KW = re.compile(
    r"(password|passwd|pwd|token|secret|api[-_]?key|access[-_]?key|private[-_]?key|client[-_]?secret)"
    r"\s*[:=]\s*\S+", re.I)
_SENS_KW_ZH = re.compile(
    r"(密码|口令|密钥|秘钥|令牌|验证码|校验码|动态码)\s*(?:[:：=]\s*\S+|(?:是|为)\s*[A-Za-z0-9!@#$%^&*_\-]{4,})")
_SENS_OTP = re.compile(
    r"(?:otp|passcode|one[- ]time|verification code|security code|auth(?:entication)? code|验证码|校验码|动态码)"
    r"\D{0,12}\d{4,8}(?!\d)", re.I)
_SENS_ANYWHERE = (
    ("API 密钥", re.compile(r"\bsk-[A-Za-z0-9\-_]{16,}")),
    ("API 密钥", re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{16,}")),
    ("API 密钥", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|glpat-[A-Za-z0-9\-_]{20,})")),
    ("API 密钥", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("API 密钥", re.compile(r"\bAIza[0-9A-Za-z\-_]{30,}")),
    ("API 密钥", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("令牌", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}")),
    ("令牌", re.compile(r"\bbearer\s+[A-Za-z0-9\-._~+/]{16,}=*", re.I)),
    ("私钥", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("连接串", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s/:@]+:[^\s/@]+@", re.I)),
)
_SENS_WHOLE = (
    ("验证码 / 数字串", re.compile(r"^\d{6,}$")),
    ("身份证号", re.compile(r"^\d{17}[\dXx]$")),
    ("身份证号", re.compile(r"^\d{6}[ -]?\d{8}[ -]?\d{3}[\dXx]$")),
)
_TOKEN32 = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z0-9\-_+/=]{32,}$")
_CARD_RE = re.compile(r"^(?:\d[ -]?){12,18}\d$")
_TOKENISH = re.compile(r"^[A-Za-z0-9\-_+/=]{24,}$")


def _class_change_ratio(s):
    """相邻字符「大写 / 小写 / 数字 / 符号」类别变化的比例：随机密钥约 0.6，驼峰 / 下划线命名只有 0.3~0.45。"""
    def cls(ch):
        return 0 if ch.isupper() else 1 if ch.islower() else 2 if ch.isdigit() else 3
    if len(s) < 2:
        return 0.0
    return sum(1 for a, b in zip(s, s[1:]) if cls(a) != cls(b)) / float(len(s) - 1)


def _luhn(digits):
    total, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def _entropy(s):
    n = float(len(s))
    return -sum(c / n * math.log(c / n, 2) for c in Counter(s).values()) if n else 0.0


def sensitive_kind(text):
    """文本像不像敏感信息：像就返回一个简短的类别名，不像返回 None。"""
    try:
        t = (text or "").strip()
    except Exception:       # noqa: BLE001
        return None
    if not t:
        return None
    if _SENS_KW.search(t) or _SENS_KW_ZH.search(t):
        return "密码 / 令牌"
    if _SENS_OTP.search(t):
        return "验证码"
    for label, rx in _SENS_ANYWHERE:
        if rx.search(t):
            return label
    lines = [ln for ln in t.splitlines() if ln.strip()]
    if len(lines) != 1:
        return None
    s = lines[0].strip()
    for label, rx in _SENS_WHOLE:
        if rx.match(s):
            return label
    # 32 位以上、大小写 + 数字混合的长串：再看字符类别跳变（随机密钥 ~0.6，长驼峰命名 ~0.3），
    # 避免把 InternationalizationConfigManager2026 这类长标识符当成密钥
    if _TOKEN32.match(s) and _class_change_ratio(s) >= 0.4:
        return "令牌"
    if _CARD_RE.match(s):
        digits = re.sub(r"[ -]", "", s)
        if 13 <= len(digits) <= 19 and _luhn(digits):
            return "银行卡号"
    # 24 位以上、大小写和数字都有、熵高、字符类别跳变频繁的单个词：多半是密钥，不是驼峰 / 下划线命名
    if (_TOKENISH.match(s) and re.search(r"[a-z]", s) and re.search(r"[A-Z]", s)
            and re.search(r"\d", s) and _entropy(s) >= 4.0 and _class_change_ratio(s) >= 0.5):
        return "令牌"
    return None


def is_sensitive(text):
    return sensitive_kind(text) is not None


# ---------------------------------------------------------------- 文本类型
_TLDS = ("com|net|org|edu|gov|io|co|cn|uk|de|jp|fr|ru|me|ai|app|dev|xyz|top|info|biz|tv|cc|us|ca|au|in|kr|hk|tw|eu")
_URL_RES = (
    re.compile(r"^(?:[a-z][a-z0-9+.\-]*://|www\.)\S+$", re.I),
    re.compile(r"^(?:mailto|tel|magnet|data):\S+$", re.I),
    re.compile(r"^(?:[a-z0-9\-]+\.)+(?:%s)(?::\d+)?(?:[/?#]\S*)?$" % _TLDS, re.I),
)
_EMAIL_RE = re.compile(r"^[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+$")
_PATH_RES = (
    re.compile(r"^[A-Za-z]:\\[^\r\n]+$"),                                  # C:\Users\x\a b.txt
    re.compile(r"^[A-Za-z]:/[^\s]+$"),
    re.compile(r"^\\\\[^\s\\]+\\[^\r\n]*$"),                                # \\server\share
    re.compile(r"^(?:~|\.{1,2})/[\w.\-@+~%/]+$"),
    re.compile(r"^/[\w.\-@+~%]+(?:/[\w.\-@+~%]+)+/?$"),
    re.compile(r"^[\w\-.]+\.(?:txt|md|docx?|xlsx?|pptx?|pdf|png|jpe?g|gif|bmp|zip|rar|7z|exe|msi|py|js|ts|json|xml"
               r"|csv|html?|css|log|ini|cfg|ya?ml|mp[34]|avi|mkv|dll|bat|sh|amd)$", re.I),
)
_NUMERIC_RE = re.compile(r"^[\s\d.,:;/%+\-−–()$€£¥￥#*^~=<>°]*$")
_IDENT_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_DOTTED_RE = re.compile(r"^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*){2,}$")
_SENT_END = re.compile(r"[。！？…]|[.!?]+(?=\s|$)")
_ABBREV = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof|St|vs|etc|Inc|Ltd|Co|No|Fig|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
    r"|e\.g|i\.e|U\.S|U\.K)\.", re.I)
_CODE_LINE = re.compile(
    r"^\s*(?:def|class|import|from|function|const|let|var|public|private|protected|static|return|if|else|elif|for"
    r"|while|switch|case|try|catch|using|namespace|package|struct|enum|interface)\b.*[:{(;]\s*$"
    r"|^\s*#include\b|^\s*@\w+(?:\(.*\))?\s*$")
_HTML_TAG = re.compile(r"</?[A-Za-z][\w\-]*(?:\s[^<>]*)?/?>")
_CODE_SIGNALS = (
    re.compile(r"[;{}]\s*$", re.M),
    re.compile(r"=>|->\s*\w|::\w|\+\+|--\w|&&|\|\||[!=]==?\s*\S"),
    re.compile(r"\b\w+\.\w+\([^)]*\)"),
    re.compile(r"</?[A-Za-z][\w\-]*(?:\s[^<>]*)?/?>"),
    re.compile(r"\b\w+\([^()\n]*\)\s*[;{:]"),
    re.compile(r"^\s*(?:#|//|/\*)\s*\S", re.M),
    re.compile(r"^\s*[\[{].*\"\s*:\s*.*[\]}]\s*,?\s*$", re.M),
)


def _looks_like_code(t):
    lines = [ln for ln in t.splitlines() if ln.strip()]
    if not lines:
        return False
    if len(lines) > 1:
        hits = sum(1 for ln in lines if _CODE_LINE.match(ln) or ln.rstrip().endswith((";", "{", "}")))
        if hits >= 2 and hits / float(len(lines)) >= 0.4:
            return True
    signals = sum(1 for rx in _CODE_SIGNALS if rx.search(t))
    if len(_HTML_TAG.findall(t)) >= 2:
        signals += 1
    if _CODE_LINE.match(lines[0]):
        signals += 1
    return signals >= 2


def _is_identifier(t):
    if " " in t or "\t" in t:
        return False
    if _DOTTED_RE.match(t):
        return True
    if not _IDENT_RE.match(t):
        return False
    return "_" in t.strip("_") or bool(re.search(r"[a-z][A-Z]", t))


def _size_kind(t, det):
    """单词 / 短语 / 句子 / 段落（按语种分别计量：CJK 数字符，其余数词）。"""
    ends = len(_SENT_END.findall(_ABBREV.sub(" ", t)))
    if det.script in ("han", "kana", "hangul"):
        n = sum(1 for ch in t if _script(ch) in _CJK_GROUPS)
        han_only = det.script == "han"
        if n <= (4 if han_only else 8) and ends == 0 and "\n" not in t:
            return "word"
        if n <= 12 and ends == 0 and "\n" not in t:
            return "phrase"
        if n <= 120 and ends <= 3 and "\n" not in t:
            return "sentence"
        return "paragraph"
    words = len(t.split())
    if words <= 1 and "\n" not in t:
        return "word"
    if words <= 4 and ends == 0 and "\n" not in t:
        return "phrase"
    if words <= 40 and ends <= 3 and "\n" not in t:
        return "sentence"
    return "paragraph"


def analyze(text):
    """文本类型 + 语种 + 值不值得自动翻译。返回 Info(kind, lang, confidence, translatable, reason)。

    kind：empty / sensitive / url / email / path / number / symbols / code / identifier /
          word / phrase / sentence / paragraph。
    translatable：网址、邮箱、路径、纯数字、纯符号、敏感内容、空文本为 False（自动翻译没意义或不安全）；
    代码和标识符仍为 True（命名格式 / 注释翻译有用），调用方想跳过可以按 kind 判断。"""
    try:
        t = (text or "").strip()
    except Exception:       # noqa: BLE001
        t = ""
    if not t:
        return Info("empty", "en", 0.0, False, "没有内容")
    label = sensitive_kind(t)
    if label:
        return Info("sensitive", "en", 0.0, False, "疑似敏感信息（%s）" % label)
    single = "\n" not in t
    if single and _EMAIL_RE.match(t):
        return Info("email", "en", 0.0, False, "邮箱地址")
    if single and any(rx.match(t) for rx in _URL_RES):
        return Info("url", "en", 0.0, False, "网址")
    if single and len(t) <= 260 and any(rx.match(t) for rx in _PATH_RES):
        return Info("path", "en", 0.0, False, "文件路径")
    if not any(ch.isalpha() for ch in t):
        if any(ch.isdigit() for ch in t) and _NUMERIC_RE.match(t):
            return Info("number", "en", 0.0, False, "只有数字")
        return Info("symbols", "en", 0.0, False, "只有符号")
    det = detect_lang(t)
    if single and _is_identifier(t):
        return Info("identifier", det.lang, det.confidence, True, "变量名 / 标识符")
    if _looks_like_code(t):
        return Info("code", det.lang, det.confidence, True, "代码")
    return Info(_size_kind(t, det), det.lang, det.confidence, True, "")


def is_translatable(text):
    """值不值得自动翻译（剪贴板监听用）：网址 / 邮箱 / 路径 / 纯数字 / 纯符号 / 敏感内容不翻。"""
    return analyze(text).translatable


# ---------------------------------------------------------------- 词典 / 生词本判定
_DICT_PUNCT = re.compile(r"[,;，；。！？!?]")


def is_dict_candidate(text):
    """值不值得查词典：单个词或短词组。

    去空白后 <=20 字符、1~3 个词、无换行、中间没有句子标点；网址 / 数字 / 敏感内容不查；
    汉字连写最多 6 个字，假名 / 谚文最多 10 个字（再长就是句子，查不出词条）。"""
    t = (text or "").strip()
    if not t or "\n" in t or len(t) > 20:
        return False
    core = t.rstrip(".。!！?？,，;；:：")
    if not core or _DICT_PUNCT.search(core):
        return False
    if not 1 <= len(core.split()) <= 3:
        return False
    info = analyze(core)
    if info.kind in ("empty", "sensitive", "url", "email", "path", "number", "symbols"):
        return False
    han = sum(1 for ch in core if _script(ch) == "han")
    syl = sum(1 for ch in core if _script(ch) in ("kana", "hangul"))
    if han > 6 or syl > 10:
        return False
    return True


def is_word_entry(text):
    """历史记录的原文是不是适合进生词本的单词：单个词、无空白、1~30 字符，并且必须含字母，
    不是网址 / 邮箱 / 路径 / 敏感内容。"""
    t = (text or "").strip()
    if not (1 <= len(t) <= 30) or any(c.isspace() for c in t):
        return False
    if not any(c.isalpha() for c in t):
        return False
    return analyze(t).kind not in ("sensitive", "url", "email", "path")
