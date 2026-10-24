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
             r"пояснив|пояснила|пояснили|каже|кажуть|говорять|відреагува\w*|опублікува\w*|поскаржи\w*|попереджа\w*")
SPEECH_RU = (r"заявил\w*|сообщ\w*|сказал\w*|пишет|пишут|написал\w*|отметил\w*|подчеркнул\w*|рассказал\w*|подтвердил\w*|"
             r"передает|передают|добавил\w*|уточнил\w*|предупредил\w*|объявил\w*|прокомментировал\w*|ответил\w*|считает|утвержда\w*|"
             r"объяснил\w*|говорит|говорят|отреагировал\w*|опубликовал\w*|пожаловал\w*|предупрежда\w*")
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
P_BEFORE = re.compile(rf"(?:^|[\.!?…]\s+|[—–]\s*|\n)(?P<x>[A-ZА-ЯІЇЄҐ@][\w'’ʼ\-]*(?:\s+[\w'’ʼ\-]+){{0,5}}?)\s+{SPEECH}\b")
P_COLON = re.compile(r"(?:^|\n)\W{0,4}(?P<x>[A-ZА-ЯІЇЄҐ«\"][^\n:]{1,45}?):\s+\S")
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
               "independent.co.uk", "understandingwar.org", "rmf24.pl", "onet.pl", "timesofisrael.com", "nypost.com", "nhk.or.jp",
               "voanews.com", "holosameryky.com", "rferl.org", "kyodonews.net", "yonhapnews.co.kr", "aljazeera.com", "cbc.ca",
               "abc.net.au", "lrt.lt", "delfi.lt", "err.ee", "pap.pl", "wyborcza.pl", "corriere.it", "repubblica.it", "elpais.com")
FOREIGN_OFFICIAL_DOM = (".gov", "defense.gov", "state.gov", "whitehouse.gov", "nato.int", "europa.eu", "un.org", "iaea.org",
                        "imf.org", "worldbank.org", "gov.uk", "bundesregierung.de", "elysee.fr", "gov.pl", "consilium.europa.eu")
UA_OTHER_DOM = ("rbc.ua", "tsn.ua", "unian.ua", "unian.net", "nv.ua", "liga.net", "epravda.com.ua", "eurointegration.com.ua",
                "censor.net", "focus.ua", "glavcom.ua", "telegraf.com.ua", "obozrevatel.com", "24tv.ua", "ukranews.com", "forbes.ua",
                "fakty.ua", "ictv.ua", "korrespondent.net", "gazeta.ua", "dsnews.ua", "unn.ua", "strana.today", "strana.ua",
                "minfin.com.ua", "kyivindependent.com", "kyivpost.com", "bihus.info", "slidstvo.info", "newsroom.kh.ua", "sud.ua",
                "apostrophe.ua", "versii.com", "fraza.ua", "fraza.com", "zn.ua", "lb.ua", "ua.interfax.com.ua", "radiosvoboda.org",
                "hromadske.ua", "babel.ua", "espreso.tv", "ukrinform.ua", "pravda.com.ua", "suspilne.media", "dumskaya.net",
                "vgorode.ua", "segodnya.ua", "znaj.ua", "politeka.net", "ukr.net", "novyny.live", "4studio.com.ua")
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

AD_STRONG = re.compile(r"#\s?реклам|#\s?ad\b|#\s?партнер|на\s+правах\s+реклами|партнерськ\w*\s+матеріал", re.I)
AD_MARK = re.compile(r"промокод|розіграш\w*|розыгрыш\w*|казино|онлайн-казино|слоти\b|слоты\b|космолот|ставк\w*\s+на\s+спорт|"
                     r"фрібет|фрибет|депозит\w*|трейдинг|заробіт\w*\s+від|заработ\w*\s+от|знижк\w*\s+до|скидк\w*\s+до|"
                     r"переходь\w*\s+за\s+посиланням|переходи\s+по\s+ссылке|ціни?\s+нижч|цены?\s+ниже|доставк\w*\s+по\s+україн|"
                     r"купуйте|замовляйте|оформлюй\w*|зареєструйся\s+(на|за)|зарегистрируйся\s+(на|по)|безкоштовн\w*\s+навчанн|"
                     r"інвестиційн\w*\s+компан|оптов\w*\s+цін|мольфар\w*|ворожк\w*|гадалк\w*|таро\b|пророцтв\w*|"
                     r"акці\w*\s+діє|акция\s+действует|кешбек|кэшбэк|ліміт\w*\s+місць|встигни|успей", re.I)
SELF_PROMO = re.compile(r"підпис(уйтесь|уйся|атись|атися)|подпис(ывайтесь|ывайся|аться|ывайтесь)|наш\w*\s+(?:канал|інстаграм|"
                        r"инстаграм|instagram|youtube|ютуб|тікток|тикток|tiktok)|голос\w*\s+за\s+(?:наш\s+)?канал|boost|"
                        r"підтримайте\s+канал|поддержите\s+канал|переходь\w*\s+(?:в|у|до)\s+(?:наш\s+)?канал|приєднуйтесь|присоединяйтесь|"
                        r"ми\s+в\s+(?:інстаграм|instagram)|мы\s+в\s+(?:инстаграм|instagram)|канал\s+про\s+\w+\s*👉", re.I)
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
        """ad / self_promo / technical / alert / informational (див. ATTRIBUTION_RULES §5)."""
        if AD_STRONG.search(raw or "") or len({m.group(0).lower()[:6] for m in AD_MARK.finditer(text)}) >= 2:
            return "ad"
        if len(re.sub(r"[\W_]+", "", text)) < 15:
            return "technical"
        if SELF_PROMO.search(text) and len(text) < 250 and len(ALERT.findall(text)) < 2:
            return "self_promo"
        if len(text) < 300 and len(ALERT.findall(text)) >= 2:
            return "alert"
        return "informational"

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
        if re.fullmatch(r"(міністр\w*|министр\w*|голова|глава|мер|мэр|спікер\w*|спикер\w*|речни\w*|посол\w*|"
                        r"депутат\w*|нардеп\w*|прем.?єр\w*|премьер\w*|бывш\w*\s+министр\w*|колишн\w*\s+міністр\w*)", low):
            return "generic"
        if cat in ("telegram", "social") and not re.search(r"@\w|t\.me/|deepstate|рибар|рыбар|exilenova|радар|гаюн", low):
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
            x = re.sub(rf"^(?:{SPEECH}|пише|ділиться|делится|про\s+це|об\s+этом|на\s+брифінгу|на\s+брифинге|"
                       rf"(?:йдеться|говориться|говорится|зазначається|отмечается|сказано|йдеться)\s+(?:у|в)\s+\w+|"
                       rf"(?:у|в)\s+(?:матеріалі|материале|заяві|заявлении|повідомленні|сообщении|звіті|отчете|публікації|публикации)|"
                       rf"брифінг\w*|брифинг\w*|пресреліз\w*|пресс-релиз\w*|прес-реліз\w*|у|в|во)\s+", "", x, flags=re.I)
        x = re.split(rf"\s+(?i:{SPEECH})\b", x)[0]
        x = CUT.sub("", x)
        toks, out, seen_cap = x.split(), [], False
        for t in toks:
            bare = t.strip("«»\"“”'(),.:;")
            if seen_cap and bare and bare[0].islower() and bare.lower() not in ("з", "у", "в", "і", "та", "й", "of", "de", "del", "der", "von", "the", "and", "при", "по"):
                break
            if bare[:1].isupper() or bare.startswith("@"):
                seen_cap = True
            out.append(t)
        x = " ".join(out)
        x = re.sub(r"[\U0001F000-\U0001FFFF☀-➿️]+", " ", x)
        x = re.sub(r"\s+", " ", x).strip(" «»\"“”'.,:;!?()[]-–—*_")
        return " ".join(x.split()[:7])

    # ---------- посилання: пункт призначення / платформа (НЕ джерело-актор) ----------
    def link_destination(self, url: str):
        """Куди веде посилання. Повертає {domain, entity, platform_type, whitelist} або None (донати, магазини, самопромо)."""
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
            if not handle or handle.startswith("+") or handle in ("joinchat", "c", "boost", "addlist", "share") \
                    or handle in SELF_HANDLES or handle.endswith("bot"):
                return None
            return {"domain": "t.me", "entity": "@" + handle, "platform_type": "telegram_channel", "whitelist": False}
        for d, i in self.wl_domains:
            if h == d or h.endswith("." + d):
                return {"domain": h, "entity": self.v2.names[i], "platform_type": "ua_media_site", "whitelist": True}
        for doms, pt in ((UA_OTHER_DOM, "ua_media_site"), (FOREIGN_DOM, "foreign_media_site"), (RU_DOM, "russian_media_site"),
                         (OFFICIAL_DOM, "official_site"), (FOREIGN_OFFICIAL_DOM, "foreign_official_site"),
                         (SOCIAL_DOM, "social_platform")):
            if hit(doms):
                return {"domain": h, "entity": h, "platform_type": pt, "whitelist": False}
        return {"domain": h, "entity": h, "platform_type": "other_site", "whitelist": False}

    # Тип джерела, що відповідає платформі (для «лише посилання», коли актора в тексті немає)
    NON_SOURCE_PLATFORMS = ("social_platform", "other_site")
    PLATFORM_TO_TYPE = {"ua_media_site": "ua_media", "foreign_media_site": "foreign_media", "russian_media_site": "russian_media",
                        "official_site": "ua_official", "foreign_official_site": "foreign_official",
                        "telegram_channel": "telegram", "social_platform": "social",
                        "other_site": "other"}

    @staticmethod
    def _same_entity(actor: dict, dest: dict) -> bool:
        a = re.sub(r"[^\wа-яіїєґ]", "", actor["name"].lower())
        d = re.sub(r"[^\wа-яіїєґ]", "", dest["entity"].lower().split(".")[0])
        return bool(a and d) and (a in d or d in a or (actor.get("whitelist") and dest.get("whitelist") and actor["name"] == dest["entity"]))

    @staticmethod
    def _dedup(actors: list) -> list:
        """Аудит (3): «СБУ» + «пресслужба СБУ», «міністр Степанов» + «міністр» → одна сутність (лишається конкретніша)."""
        role_only = re.compile(r"^(міністр\w*|министр\w*|голова|глава|мер|мэр|спікер\w*|спикер\w*|речни\w*|прем.?єр\w*|"
                               r"премьер\w*|президент\w*|посол\w*|депутат\w*|нардеп\w*|експерт\w*|эксперт\w*|пресслужб\w*|"
                               r"прес-служб\w*|пресс-служб\w*)$", re.I)
        out = []
        for a in sorted(actors, key=lambda x: -len(x["name"])):
            al = a["name"].lower()
            dup = any((b["type"] == a["type"] or a["type"] == "person_other") and (al in b["name"].lower() or
                      (role_only.match(al) and b["specificity"] == "named")) for b in out)
            if not dup:
                out.append(a)
        return out

    # ---------- одне повідомлення ----------
    def analyze(self, msg: dict, channel: str, boiler=frozenset()):
        raw = msg.get("text") or ""
        text, urls = self.body(raw, boiler)
        mtype = self.message_type(raw, text)
        self_rx = re.compile(SELF.get(channel, r"(?!x)x"), re.I)
        found = []

        def add(x, pattern):
            if re.search(r"[.!?]\s|»\.|\.»", x):          # аудит (1): назва не може містити кінець речення
                return
            if len(x.split()) > 6:
                return  # аудит (1): шматок речення, а не назва
            locative = bool(re.match(r"^(?:у|в|во|на)\s+\S", x.strip(), re.I))
            x = self.tidy(x)
            if len(x) < 2 or self_rx.search(x):
                return
            cat, wl = self.classify(x)
            if cat == "noise":
                return
            if cat == "other":
                if self.person_like(x):
                    cat = "person_other"
                elif re.search(r"\bрад[аи]\b|служб|компані|компани|фонд|асоціац|ассоциац|організац|организац|\bцентр|інститут|"
                               r"институт|університет|университет|\bбанк|агентств|комітет|комитет|\bсоюз|\bго\b", x, re.I):
                    cat = "company_organization"
                elif pattern in ("before", "after", "signature", "colon"):
                    return
            if pattern == "colon" and (cat not in ("ua_official", "foreign_official", "russian_official", "ua_media", "foreign_media",
                                                   "russian_media", "politician", "expert", "telegram") or len(x.split()) > 4):
                return  # двокрапка — лише для впізнаних акторів (рішення ⚑1), не для заголовків-тем
            if pattern == "before" and locative and cat in ("other", "person_other"):
                return  # «В Волновахе ... сообщают» — місце, а не джерело
            found.append({"name": x, "type": cat, "whitelist": wl, "pattern": pattern,
                          "specificity": self.specificity(cat, x), "linked_destination": ""})

        lines = text.splitlines()
        for ln in lines[:3] + lines[-2:]:
            for rx in (P_SIGN, P_SIGN_HY):
                m = rx.search(ln)
                if m and len(m.group("x").split()) <= 8:
                    add(m.group("x"), "signature")
        for ln in lines:
            for m in P_SIGN_MID.finditer(ln):
                if len(m.group("x").split()) <= 6:
                    add(m.group("x"), "signature")
        for m in P_COLON.finditer(text):
            if len(m.group("x").split()) <= 5:
                add(m.group("x"), "colon")
        if P_IMPERSONAL.search(text):
            found.append({"name": "невизначене («повідомляють»)", "type": "anonymous", "whitelist": False,
                          "pattern": "impersonal", "specificity": "anonymous", "linked_destination": ""})
        for rx, tag in ((P_PREP, "prep"), (P_IN, "in_org"), (P_AFTER, "after"), (P_BEFORE, "before"), (P_ROLE_BEFORE, "before")):
            for m in rx.finditer(text):
                add(m.group("x"), tag)
        if P_EYE.search(text) or re.search(r"#\s?нам\s?пишут", raw, re.I):
            add("підписники", "eyewitness")
        if P_SOCIAL.search(text):
            add("соцмережі", "social")
        actors = self._dedup(found)

        # пункти призначення посилань
        self_promo = bool(SELF_PROMO.search(text))
        dests = []
        for u in dict.fromkeys(urls):
            d = self.link_destination(u)
            if not d or (d["platform_type"] == "social_platform" and self_promo):
                continue
            if all(d["entity"] != x["entity"] for x in dests):
                dests.append(d)
        for a in actors:  # той самий суб'єкт і в тексті, і в посиланні → linked_destination
            for d in dests:
                if self._same_entity(a, d):
                    a["linked_destination"] = d["domain"]
        # «лише посилання»: актора в тексті немає → актор = видавець за посиланням (позначено)
        # Рішення ⚑6 (2026-10-24): посилання лише на соцмережу чи «інший сайт» — тільки пункт призначення, не атрибуція
        src_dests = [d for d in dests if d["platform_type"] not in self.NON_SOURCE_PLATFORMS]
        inferred = []
        if not actors and src_dests:
            for d in src_dests:
                t = self.PLATFORM_TO_TYPE[d["platform_type"]]
                inferred.append({"name": d["entity"], "type": t, "whitelist": d["whitelist"], "pattern": "link_only",
                                 "specificity": "generic" if t in ("social", "other") else "named",
                                 "linked_destination": d["domain"], "actor_inferred_from_link": True})
        has_text = bool(actors)
        has_link = bool(src_dests) or any(x.get("linked_destination") for x in actors)
        method = "both" if has_text and has_link else "textual" if has_text else "hyperlink" if has_link else "none"
        return {
            "message_type": mtype,
            "in_primary_denominator": mtype in ("informational", "alert"),
            "has_explicit_source": has_text or has_link,
            "attribution_method": method,
            "attributed_sources": actors + inferred,
            "linked_destinations": dests,
            "n_sources": len(actors) + len(inferred),
            "clean_text": text,
            # сумісність зі старими звітами/тестами
            "sources": actors + inferred,
        }
