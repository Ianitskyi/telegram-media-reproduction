"""Класифікатор явної атрибуції джерела в Telegram-повідомленні (v3, прототип на затвердження).

Правила — docs/ATTRIBUTION_RULES.md; словники типів — src/v3/gazetteer.py.
Принцип: джерело — це те, на що адміністратор явно посилається як на ПОХОДЖЕННЯ інформації
(посилання, «— Х», «за даними Х», «Х заявив», «у Х повідомили»), а не будь-яка згадана сутність.
"""
import re
from urllib.parse import urlparse

from src.v2.detect import Detector
from src.v3 import gazetteer as G

A = "['’ʼ]"
MD_LINK = re.compile(r"\[([^\]]*)\]\(((?:https?://|tg://)[^)\s]*)\)")
BARE_URL = re.compile(r"(?<!\()\bhttps?://[^\s)\]]+", re.I)
FMT = re.compile(r"\*\*|__|~~|`")

SPEECH_UA = (r"заяви\w*|повідоми\w*|повідомля\w*|сказа\w*|пише|пишуть|написа\w*|зазнач\w*|наголоси\w*|розпові\w*|"
             r"підтверди\w*|інформу\w*|передає|передають|додав|додала|додали|уточни\w*|попереди\w*|звітує|звітують|"
             r"анонсува\w*|оголоси\w*|прокоментува\w*|відповів|відповіла|вважає|переконаний|переконана|стверджу\w*|"
             r"каже|кажуть|говорять|відреагува\w*|опублікува\w*|поскаржи\w*|попереджа\w*")
SPEECH_RU = (r"заявил\w*|сообщ\w*|сказал\w*|пишет|пишут|написал\w*|отметил\w*|подчеркнул\w*|рассказал\w*|подтвердил\w*|"
             r"передает|передают|добавил\w*|уточнил\w*|предупредил\w*|объявил\w*|прокомментировал\w*|ответил\w*|считает|утвержда\w*|"
             r"говорит|говорят|отреагировал\w*|опубликовал\w*|пожаловал\w*|предупрежда\w*")
SPEECH = f"(?:{SPEECH_UA}|{SPEECH_RU})"
ROLE_START = (r"голова|глава|очільник\w*|керівник\w*|мер|мэр|міністр\w*|министр\w*|речни\w*|спікер\w*|прес\w*|пресс\w*|"
              r"заступни\w*|командир\w*|командувач\w*|представни\w*|радни\w*|советни\w*|посол\w*|депутат\w*|нардеп\w*|"
              r"експерт\w*|эксперт\w*|аналіти\w*|аналити\w*|прем.?єр\w*|премьер\w*|президент\w*|начальни\w*|директор\w*|"
              r"генпрокурор\w*|прокурор\w*|військов\w*|военн\w*|монітор\w*|монитор\w*|місцев\w*|местн\w*|очевид\w*|"
              r"джерел\w*|источник\w*|журналіст\w*|журналист\w*|видання|издание|змі|сми|росзмі|соцмереж\w*|користувач\w*|"
              r"підписник\w*|подписчик\w*|синоптик\w*|лікар\w*|врач\w*|адвокат\w*|омбудсман\w*|губернатор\w*|канцлер\w*")
CAP = r"[A-ZА-ЯІЇЄҐ«\"“@]"

P_SIGN = re.compile(r"(?:[,\.!?»\"”…\)]\s*|\s)[—–]{1,2}\s*(?P<x>[^\n—–]{2,90}?)\s*[\.!]?\s*$")
P_SIGN_MID = re.compile(r"[,!?»\"”…]\s*[—–]{1,2}\s*(?P<x>[^\n—–.]{2,60}?)\.(?=\s+[A-ZА-ЯІЇЄҐ«\"])")
P_ROLE_BEFORE = re.compile(rf"(?:^|[\.!?…—–]\s*|\n)(?P<x>(?i:{ROLE_START})\w*(?:\s+[\w'’ʼ\-]+){{0,3}}?)\s+(?i:{SPEECH})\b")
P_IMPERSONAL = re.compile(r"(?:^|[\.!?…]\s+|\n)(?:повідомляють|кажуть|пишуть|говорять|сообщают|говорят|пишут|передают)\s*,?\s+(?:що|что)\b", re.I)
P_SIGN_HY = re.compile(r"[,»\"”]\s*-\s*(?P<x>[^\n—–\-]{2,90}?)\s*[\.!]?\s*$")
P_AFTER = re.compile(rf"(?<!\w)(?i:{SPEECH})\s+(?:(?:у|в|во)\s+)?(?P<x>(?:{CAP}|(?i:{ROLE_START})\b)[^,.;:!?\n«»\"“”]{{1,80}})")
P_BEFORE = re.compile(rf"(?:^|[\.!?…]\s+|[—–]\s*|\n)(?P<x>{CAP}[\w'’ʼ\.\-]*(?:\s+[\w'’ʼ\.\-«»\"]+){{0,5}}?)\s+{SPEECH}\b")
P_IN = re.compile(rf"(?:^|[\s,])[УВуВ]\s+(?P<x>{CAP}[^,.;:!?\n]{{1,60}}?)\s+"
                  rf"(?:повідомили|заявили|кажуть|розповіли|підтвердили|зазначили|наголосили|уточнили|відповіли|"
                  rf"сообщили|заявили|рассказали|подтвердили|отметили|уточнили|ответили)\b")
P_PREP = re.compile(r"(?:за\s+даними|за\s+інформацією|за\s+словами|з\s+посиланням\s+на|посилаючись\s+на|як\s+повідомля\w*|"
                    r"як\s+пише|як\s+пишуть|як\s+заяви\w*|як\s+розпові\w*|джерело\s*:|джерела\s*:|"
                    r"по\s+данным|по\s+информации|по\s+словам|со\s+ссылкой\s+на|ссылаясь\s+на|как\s+сообща\w*|как\s+пишет|"
                    r"как\s+пишут|как\s+заявил\w*|источник\s*:|"
                    rf"про\s+це\s+{SPEECH}|об\s+этом\s+{SPEECH})\s+(?P<x>[^,.;:!?\n]{{2,80}})", re.I)
P_EYE = re.compile(r"#\s?нам\s?пишуть|#\s?нам\s?пишут|нам\s+пишуть|нам\s+пишут|пишуть\s+підписники|пишут\s+подписчики|"
                   r"підписники\s+(?:повідомляють|надіслали|пишуть)|подписчики\s+(?:сообщают|прислали|пишут)|"
                   r"очевидці\s+(?:повідомляють|розповідають|кажуть)|очевидцы\s+(?:сообщают|рассказывают)", re.I)
P_SOCIAL = re.compile(r"(?:у|в)\s+(?:мережі|сети)\s+(?:з.явил\w*|поширю\w*|поширил\w*|появил\w*|распространя\w*|опублікува\w*|публику\w*)|користувачі\s+соцмереж|пользователи\s+соцсетей|відео\s+(?:з\s+)?соцмереж",
                      re.I)
CUT = re.compile(r"\s+(?:що|чтобы|что|про|о|об|під\s+час|во\s+время|у\s+своєму|в\s+своем|в\s+ефірі|в\s+эфире|в\s+інтерв.ю|"
                 r"в\s+интервью|на\s+брифінгу|на\s+брифинге|на\s+пресконференції|у\s+коментарі|в\s+комментарии|у\s+telegram|"
                 r"в\s+telegram|у\s+телеграм\w*|в\s+телеграм\w*|у\s+facebook|в\s+facebook|сьогодні|сегодня|вчора|вчера|"
                 r"зранку|утром|ввечері|вечером|минулої|прошлой|також|также|нібито|якобы|і\s+додав|и\s+добавил)\b.*$", re.I)

OFFICIAL_DOM = (".gov.ua", "gov.ua", "court.gov.ua", "mil.gov.ua", "president.gov.ua", "rada.gov.ua", "npu.gov.ua", "ssu.gov.ua",
                "dsns.gov.ua", "mod.gov.ua", "mfa.gov.ua", "kmu.gov.ua", "ukrenergo.energy", "dtek.com", "nbu.gov.ua")
SOCIAL_DOM = ("facebook.com", "fb.watch", "instagram.com", "youtube.com", "youtu.be", "x.com", "twitter.com", "tiktok.com",
              "threads.net", "vk.com", "reddit.com")
FOREIGN_DOM = ("reuters.com", "bloomberg.com", "nytimes.com", "ft.com", "cnn.com", "wsj.com", "washingtonpost.com", "bbc.com",
               "bbc.co.uk", "theguardian.com", "politico.com", "politico.eu", "economist.com", "apnews.com", "axios.com", "dw.com",
               "spiegel.de", "bild.de", "lemonde.fr", "lefigaro.fr", "foxnews.com", "nbcnews.com", "cbsnews.com", "news.sky.com",
               "forbes.com", "businessinsider.com", "newsweek.com", "euronews.com", "telegraph.co.uk", "thetimes.co.uk",
               "independent.co.uk", "understandingwar.org", "rmf24.pl", "onet.pl", "timesofisrael.com")
UA_OTHER_DOM = ("rbc.ua", "tsn.ua", "unian.ua", "unian.net", "nv.ua", "liga.net", "epravda.com.ua", "eurointegration.com.ua",
                "censor.net", "focus.ua", "glavcom.ua", "telegraf.com.ua", "obozrevatel.com", "24tv.ua", "ukranews.com", "forbes.ua",
                "fakty.ua", "ictv.ua", "korrespondent.net", "gazeta.ua", "dsnews.ua", "unn.ua", "strana.today", "strana.ua",
                "minfin.com.ua", "kyivindependent.com", "kyivpost.com", "bihus.info", "slidstvo.info", "newsroom.kh.ua", "sud.ua")
RU_DOM = (".ru", "tass.com", "ria.ru", "meduza.io", "rbc.ru", "novayagazeta.eu", "istories.media", "theins.ru", "tvrain.tv")
NOT_SOURCE_DOM = ("send.monobank.ua", "monobank.ua", "rozetka.com.ua", "privat24.ua", "prom.ua", "olx.ua", "bit.ly", "cutt.ly",
                  "telegra.ph", "mi.ua", "allo.ua", "epicentrk.ua", "favbet", "cosmolot", "pari", "1xbet", "aliexpress", "inzhur",
                  "docs.google.com", "forms.gle", "tinyurl.com")

# Власні назви каналів (самопосилання не рахуються джерелом)
SELF = {
    "truexanewsua": r"труха", "kievinfo_kyiv": r"киев\s*info|київ\s*інф|kievinfo|novosty_kiev", "UaOnlii": r"україна\s*online|украина\s*online|uaonlii",
    "vanek_nikolaev": r"ван[еє]к", "lachentyt": r"лачен", "times_ukraina": r"times\s*of\s*ukraine|радар\s*times|підписники\s*times",
    "batalionmonako": r"монако|оперативн\w*\s+монітор", "suspilnenews": r"суспільн\w*", "ukrpravda_news": r"українськ\w*\s+правд\w*|\bуп\b",
    "TCH_channel": r"\bтсн\b", "uniannet": r"ун[іи]ан",
}
SELF_HANDLES = {"truexanewsua", "kievinfo_kyiv", "uaonlii", "vanek_nikolaev", "lachentyt", "times_ukraina", "batalionmonako",
                "suspilnenews", "ukrpravda_news", "tch_channel", "uniannet", "novosty_kiev_bot", "truexausend_bot"}

AD = re.compile(r"#\s?реклам|#\s?ad\b|промокод|розіграш|розыгрыш|казино|слот\w*|космолот|ставк\w*\s+на\s+спорт|бонус\w*|"
                r"трейдинг|криптовалют\w*|заробіт\w*\s+від|заработ\w*\s+от|зареєстру\w*|зарегистр\w*|знижк\w*\s+до|скидк\w*\s+до|"
                r"переходь\w*\s+за\s+посиланням|ціни?\s+нижч|цены?\s+ниже|доставк\w*\s+по\s+україн|купуй\w*|замовля\w*|"
                r"пропоную\w*|інвестиційн\w*\s+компан|оптов\w*\s+цін|мольфар|ворож\w*|таро\b", re.I)
ALERT = re.compile(r"шахед\w*|мопед\w*|балістик\w*|баллистик\w*|ракет\w*|бпла|безпілотник\w*|кинджал|кинжал|тривог\w*|тревог\w*|"
                   r"укритт\w*|укрыти\w*|відбій|отбой|курсом|курс\s+на|напрямк\w*|направлени\w*|летить|летят|летит|громк\w*|"
                   r"гучн\w*|зліт|взлет|загроза|угроза", re.I)


class Attribution:
    def __init__(self):
        self.v2 = Detector()  # «білий список» медіа (config/media_aliases.json)
        self.wl_domains = [(d, i) for d, i in self.v2.domains]
        self.cats = [(n, [re.compile(p, re.I) for p in pats]) for n, pats in G.ORDER]

    # ---------- текст ----------
    @staticmethod
    def body(raw: str, boiler: set):
        """Повертає (чистий текст тіла, URL-и тіла). Рядки-підписи каналу вилучаються разом із їхніми посиланнями."""
        lines, urls = [], []
        for ln in (raw or "").splitlines():
            clean_ln = MD_LINK.sub(lambda m: m.group(1), ln)
            clean_ln = BARE_URL.sub(" ", clean_ln)
            if clean_ln.strip() in boiler or FMT.sub("", clean_ln).strip() in boiler:
                continue
            urls += [m.group(2) for m in MD_LINK.finditer(ln)] + BARE_URL.findall(ln)
            lines.append(FMT.sub("", clean_ln))
        text = "\n".join(l.rstrip() for l in lines if l.strip())
        return text, urls

    def message_type(self, raw: str, text: str) -> str:
        if AD.search(raw or ""):
            return "ad"
        if len(text) < 300 and len(ALERT.findall(text)) >= 2:
            return "alert"
        if len(text) < 15:
            return "too_short"
        return "news_or_other"

    # ---------- класифікація назви ----------
    def classify(self, name: str):
        n = name.strip(" «»\"“”'.,:;!?()[]-–—*_")
        low = n.lower()
        wl = self.v2.mention_ids(" за даними " + n)[0]
        if wl:
            return "ua_media", True
        for cat, rxs in self.cats:
            if any(r.search(low) for r in rxs):
                return cat, False
        return "other", False

    @staticmethod
    def specificity(cat: str, name: str) -> str:
        low = name.lower()
        if cat == "anonymous":
            return "anonymous"
        if cat in ("unnamed_media", "eyewitness"):
            return "generic"
        if cat in ("telegram", "social") and not re.search(r"@\w|deepstate|рибар|рыбар|exilenova|радар", low):
            return "generic"
        if cat == "expert" and re.fullmatch(r"(військов\w*\s+)?(експерт\w*|аналітик\w*|эксперт\w*|аналитик\w*|політолог\w*|синоптик\w*)", low):
            return "generic"
        return "named"

    @staticmethod
    def person_like(x: str) -> bool:
        toks = x.split()
        if not (1 <= len(toks) <= 3 and all(re.fullmatch(r"[A-ZА-ЯІЇЄҐ][a-zа-яіїєґ'’ʼ\-]+", t) for t in toks)):
            return False
        if len(toks) == 1:
            return bool(re.search(r"(енко|ук|юк|чук|ов|ев|єв|ова|ева|ін|ин|іна|ина|ський|цький|ська|цька|ский|цкий|ич|як|ник|ар|ко)$", toks[0]))
        return True

    @staticmethod
    def tidy(x: str) -> str:
        x = x.strip()
        for _ in range(3):
            x = re.sub(rf"^(?:{SPEECH}|пише|ділиться|делится|про\s+це|об\s+этом|на\s+брифінгу|на\s+брифинге|у|в|во)\s+", "", x, flags=re.I)
        x = re.split(rf"\s+(?i:{SPEECH})\b", x)[0]
        x = CUT.sub("", x)
        x = re.sub(r"[\U0001F000-\U0001FFFF☀-➿️]+", " ", x)
        x = re.sub(r"\s+", " ", x).strip(" «»\"“”'.,:;!?()[]-–—*_")
        return " ".join(x.split()[:7])

    # ---------- посилання ----------
    def link_source(self, url: str, channel: str):
        u = url.rstrip(").,;»\"'")
        try:
            p = urlparse(u if "://" in u else "http://" + u)
        except ValueError:
            return None
        h = p.netloc.lower().split("@")[-1].split(":")[0]
        h = h[4:] if h.startswith("www.") else h
        if not h:
            return None
        hit = lambda doms: any(h == d or h.endswith("." + d) or (d.startswith(".") and h.endswith(d)) for d in doms)
        if hit(NOT_SOURCE_DOM) or any(d in h for d in ("favbet", "cosmolot", "1xbet", "aliexpress")):
            return None
        if h in ("t.me", "telegram.me"):
            path = p.path.strip("/").split("/")
            handle = (path[0] if path else "").lower()
            if not handle or handle.startswith("+") or handle in ("joinchat", "c", "boost", "addlist", "share") or handle in SELF_HANDLES:
                return None
            if handle.endswith("bot"):
                return None
            return {"name": "@" + handle, "type": "telegram", "whitelist": False}
        for d, i in self.wl_domains:
            if h == d or h.endswith("." + d):
                return {"name": self.v2.names[i], "type": "ua_media", "whitelist": True}
        if hit(UA_OTHER_DOM):
            return {"name": h, "type": "ua_media", "whitelist": False}
        if hit(FOREIGN_DOM):
            return {"name": h, "type": "foreign_media", "whitelist": False}
        if hit(RU_DOM):
            return {"name": h, "type": "russian_media", "whitelist": False}
        if hit(OFFICIAL_DOM):
            return {"name": h, "type": "ua_official", "whitelist": False}
        if hit(SOCIAL_DOM):
            return {"name": h, "type": "social", "whitelist": False}
        return {"name": h, "type": "other", "whitelist": False}

    # ---------- одне повідомлення ----------
    def analyze(self, msg: dict, channel: str, boiler=frozenset()):
        raw = msg.get("text") or ""
        text, urls = self.body(raw, boiler)
        mtype = self.message_type(raw, text)
        self_rx = re.compile(SELF.get(channel, r"(?!x)x"), re.I)
        found = []

        def add(x, how, pattern):
            x = self.tidy(x)
            if len(x) < 2 or self_rx.search(x):
                return
            cat, wl = self.classify(x)
            if cat == "noise":
                return
            if cat == "other":
                if self.person_like(x):
                    cat = "person_other"
                elif pattern in ("before", "after", "signature") and not re.search(
                        r"рад[аи]|служб|компані|компани|фонд|асоціац|ассоциац|організац|организац|центр|інститут|институт|"
                        r"університет|университет|банк|суд|агентств|комітет|комитет|об.єднанн|союз|\.\w{2,4}$", x, re.I):
                    return
            found.append({"name": x, "type": cat, "whitelist": wl, "method": how, "pattern": pattern,
                          "specificity": self.specificity(cat, x)})

        lines = text.splitlines()
        for ln in lines[:3] + lines[-2:]:
            for rx in (P_SIGN, P_SIGN_HY):
                m = rx.search(ln)
                if m and len(m.group("x").split()) <= 8:
                    add(m.group("x"), "text", "signature")
        for ln in lines:
            for m in P_SIGN_MID.finditer(ln):
                if len(m.group("x").split()) <= 6:
                    add(m.group("x"), "text", "signature")
        if P_IMPERSONAL.search(text):
            found.append({"name": "невизначене («повідомляють»)", "type": "anonymous", "whitelist": False,
                          "method": "text", "pattern": "impersonal", "specificity": "anonymous"})
        for rx, tag in ((P_PREP, "prep"), (P_IN, "in_org"), (P_AFTER, "after"), (P_BEFORE, "before"), (P_ROLE_BEFORE, "before")):
            for m in rx.finditer(text):
                add(m.group("x"), "text", tag)
        if P_EYE.search(text) or re.search(r"#\s?нам\s?пишут", raw, re.I):
            add("підписники", "text", "eyewitness")
        if P_SOCIAL.search(text):
            add("соцмережі", "text", "social")
        self_promo = re.search(r"підписуй|подписыва|подпишись|наш\w*\s+(?:інстаграм|инстаграм|instagram|youtube|ютуб|тікток|тикток|"
                               r"tiktok|фейсбук|facebook)|ми\s+в\s+(?:інстаграм|instagram)|мы\s+в\s+(?:инстаграм|instagram)", text, re.I)
        for u in dict.fromkeys(urls):
            s = self.link_source(u, channel)
            if s and s["type"] == "social" and self_promo:
                continue
            if s:
                found.append({**s, "method": "link", "pattern": "hyperlink",
                              "specificity": self.specificity(s["type"], s["name"])})

        # дедуплікація: та сама назва/тип; посилання + текст на той самий тип медіа → method=both
        uniq = {}
        for f in found:
            key = (f["type"], f["name"].lower())
            if key in uniq:
                continue
            uniq[key] = f
        srcs = list(uniq.values())
        text_types = {f["type"] for f in srcs if f["method"] == "text"}
        link_types = {f["type"] for f in srcs if f["method"] == "link"}
        for f in srcs:
            if f["method"] == "link" and f["type"] in text_types and f["type"] != "other":
                f["method"] = "both"
        has_link, has_text = bool(link_types), bool(text_types)
        method = "both" if has_link and has_text else "hyperlink" if has_link else "textual" if has_text else "none"
        return {
            "message_type": mtype,
            "has_explicit_source": bool(srcs),
            "attribution_method": method,
            "n_sources": len(srcs),
            "sources": srcs,
            "clean_text": text,
        }
