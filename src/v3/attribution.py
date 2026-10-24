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
BARE_URL = re.compile(r"(?<![(\w/])(?:(?<=_)|(?<!\w))https?://[^\s)\]_]+(?:_[^\s)\]_]+)*", re.I)
FMT = re.compile(r"\*\*|__|~~|`")

SPEECH_UA = (r"заяви\w*|повідоми\w*|повідомля\w*|сказа\w*|пише|пишуть|написа\w*|зазнач\w*|наголоси\w*|розпові\w*|"
             r"підтверди\w*|інформу\w*|передає|передають|додав|додала|додали|уточни\w*|попереди\w*|звітує|звітують|"
             r"анонсува\w*|оголоси\w*|прокоментува\w*|відповів|відповіла|вважає|переконаний|переконана|стверджу\w*|"
             r"пояснив|пояснила|пояснили|каже|кажуть|говорять|обіця\w*|пообіця\w*|закликав|закликала|закликали|припуска\w*|погрож\w*|назвав|назвала|назвали|"
             r"запевни\w*|визнав|визнала|визнали|спростува\w*|прогнозу\w*|звинуват\w*|відредагува\w*|розкритикува\w*|висловив\w*|"
             r"показав|показала|показали|наполяга\w*|вимага\w*|відреагува\w*|опублікува\w*|поскаржи\w*|попереджа\w*")
SPEECH_RU = (r"заявил\w*|сообщ\w*|сказал\w*|пишет|пишут|написал\w*|отметил\w*|подчеркнул\w*|рассказал\w*|подтвердил\w*|"
             r"передает|передают|добавил\w*|уточнил\w*|предупредил\w*|объявил\w*|прокомментировал\w*|ответил\w*|считает|утвержда\w*|"
             r"объяснил\w*|говорит|говорят|обеща\w*|пообеща\w*|призвал\w*|призыва\w*|предполож\w*|предполага\w*|угрожа\w*|назвал\w*|заверил\w*|"
             r"признал\w*|опроверг\w*|требу\w*|прогнозир\w*|обвинил\w*|обвиня\w*|раскритиковал\w*|высказал\w*|показал\w*|настаива\w*|отреагировал\w*|опубликовал\w*|пожаловал\w*|предупрежда\w*")
SPEECH = f"(?:{SPEECH_UA}|{SPEECH_RU})"
ROLE_START = (r"спикер\w*|руководител\w*|член\w*|генеральн\w*|госсекретар\w*|державн\w*\s+секретар\w*|государственн\w*\s+секретар\w*|секретар\w*|генерал\w*|"
              r"блогер\w*|волонтер\w*|боєць|боец|офіцер\w*|офицер\w*|в\.о|т\.в\.о|первый|перший|голова|глава|очільник\w*|керівник\w*|мер|мэр|міністр\w*|министр\w*|речни\w*|спікер\w*|прес\w*|пресс\w*|"
              r"заступни\w*|командир\w*|командувач\w*|представни\w*|радни\w*|советни\w*|посол\w*|депутат\w*|нардеп\w*|"
              r"експерт\w*|эксперт\w*|аналіти\w*|аналити\w*|прем.?єр\w*|премьер\w*|президент\w*|начальни\w*|директор\w*|"
              r"генпрокурор\w*|прокурор\w*|військов\w*|военн\w*|монітор\w*|монитор\w*|місцев\w*|местн\w*|очевид\w*|"
              r"джерел\w*|источник\w*|журналіст\w*|журналист\w*|видання|издание|змі|сми|росзмі|соцмереж\w*|користувач\w*|"
              r"підписник\w*|подписчик\w*|синоптик\w*|лікар\w*|врач\w*|адвокат\w*|омбудсман\w*|губернатор\w*|канцлер\w*")
CAP = r"[A-ZА-ЯІЇЄҐ«\"“@]"
_CYR, _LAT = "АВЕКМНОРСТХаеорсухіІ", "ABEKMHOPCTXaeopcyxiI"
CYR2LAT, LAT2CYR = str.maketrans(_CYR, _LAT), str.maketrans(_LAT, _CYR)
PLATFORM = (r"(?:facebook|фейсбук\w*|twitter|твіттер\w*|твиттер\w*|telegram|телеграм\w*|instagram|інстаграм\w*|инстаграм\w*|"
            r"youtube|ютуб\w*|tiktok|тікток\w*|тикток\w*|threads|x)")
P_PLATFORM_OWNER = re.compile(rf"^(?:у|в)?\s*{PLATFORM}(?:[\s-]+(?:канал\w*|акаунт\w*|аккаунт\w*|сторінк\w*|страниц\w*|блог\w*))?\s+(?P<o>[^\s].*)$", re.I)
BARE_PLATFORM = re.compile(rf"^{PLATFORM}$", re.I)
MEDIUM = re.compile(r"\s+(?:в|у)\s+(?:коментарі|комментарии|коментарях|комментариях|інтерв.ю|интервью|розмові|разговоре|ефірі|эфире|"
                    r"колонці|колонке|статті|статье)\s+(?=[A-ZА-ЯІЇЄҐ«\"])", re.I)
ANON_MARK = re.compile(r"анонімн|анонимн|побажав\w*\s+залишитис\w*\s+неназван|пожелавш\w*\s+остаться\s+неназванн|не\s+назвавш|"
                       r"на\s+умовах\s+анонім|на\s+условиях\s+аноним", re.I)
P_PRODUCER = re.compile(r"(?:відео|видео|фото|кадри|кадры|ролик\w*|запис\w*)\s+(?:[\w'’ʼ-]+\s+){0,3}?"
                        r"(?:зробил\w*|зробив|зняв\w*|зняли|зняте|знято|знятий|знята|снято|снятое|снятые|записал\w*|записав|змонтува\w*|сделал\w*|снял\w*|записали|смонтировал\w*)\s+"
                        r"(?P<x>[^,.;:!?\n]{2,60})", re.I)
P_CREDIT = re.compile(r"(?:^|\n)[^\w\n]{0,4}(?:Відео|Видео|Фото|Автор\s+відео|Автор\s+видео|Автор\s+фото|Джерело\s+відео|Источник\s+видео)\s*:\s*(?P<x>[^\n]{2,60})")
DOC_WORD = re.compile(r"^(?:проєкт\w*|проект\w*|законопроєкт\w*|законопроект\w*|документ\w*|постанов\w*|указ\w*|звіт\w*|отчет\w*|доповід\w*|доклад\w*|"
                      r"дослідженн\w*|исследовани\w*|опитуванн\w*|опрос\w*|рейтинг\w*|прогноз\w*|декларац\w*|статистик\w*|дані|данные)\b", re.I)
NAME_TAIL = re.compile(r"[A-ZА-ЯІЇЄҐ][a-zа-яіїєґ'’ʼ\-]+\s+[A-ZА-ЯІЇЄҐ][a-zа-яіїєґ'’ʼ\-]+$")
ROLE_ANY = re.compile(r"журналіст|журналист|кореспондент|корреспондент|секретар|міністр|министр|посол|президент|прем|канцлер|генерал|командувач|командующ|речни|представни|представител|"
                      r"спікер|спикер|голов|глав|мер|мэр|директор|керівни|руководител|начальни|депутат|сенатор|конгресмен", re.I)
NEST = re.compile(r"\s+(?:(?:із|зі|з)\s+посиланням\s+на|со\s+ссылкой\s+на|посилаючись\s+на|ссылаясь\s+на)\s+", re.I)
REL = re.compile(r",\s*(?:який|яка|яке|які|якого|якої|яку|котр\w+|который|которая|которое|которые|которого|которой|которую)\s[^,\n]{1,70},")
KIN = re.compile(r"^(?:зят\w*|зять|син|сын|доч\w*|дружин\w*|жена|чолов\w*|муж|брат\w*|сестр\w*|тещ\w*|теща|кум\w*|онук\w*|внук\w*|родич\w*|родственни\w*|коханк\w*|любовни\w*)\s", re.I)
COUNTRY = re.compile(r"\b(великобритан|британ|англі|англи|сша\b|америк|німеч|герман|франц|польщ|польш|чехі|чехи|чеськ|чешск|словач|угорщ|венгр|"
                     r"румун|молдов|литв|латв|естон|эстон|італ|итал|іспан|испан|канад|япон|китай|туреччин|турц|ізраїл|израил|нідерланд|"
                     r"нидерланд|бельг|швец|норвег|фінлянд|финлянд|данії|данія|дании|дания|австрі|австри|швейцар|грузі|грузи|білорус|беларус|"
                     r"казахстан|індії|индии|іран|иран|євросоюз|евросоюз)", re.I)
RUSSIA = re.compile(r"\b(росі|росси|рф\b|кремл|москв)", re.I)
GOV_GENERIC = re.compile(r"представни\w*\s+(уряд|правительств)|представител\w*\s+(уряд|правительств)|^уряд\w*$|^правительств\w*$|"
                         r"^(міністр|министр|мзс|мид|прем.?єр|премьер|посол|речни|пресс-секретар|прес-секретар|минобороны|міноборони|"
                         r"канцеляри|уряд|правительств)\w*(?:-міністр\w*|-министр\w*)?(?:\s+\S+)?$", re.I)
ROLE_WORD = re.compile(r"^(?:сам\s+|сама\s+|бывш\w*\s+|колишн\w*\s+|экс-?|екс-?)?(?:голова|глава|очільник\w*|керівник\w*|мер\w*|мэр\w*|міністр\w*|министр\w*|"
                       r"речни\w*|спікер\w*|спикер\w*|прес\w*|пресс\w*|заступни\w*|командир\w*|командувач\w*|представни\w*|"
                       r"представител\w*|радни\w*|советни\w*|посол\w*|депутат\w*|нардеп\w*|прем.?єр\w*|премьер\w*|президент\w*|"
                       r"експрезидент\w*|экспрезидент\w*|начальни\w*|директор\w*|гендиректор\w*|банкір\w*|банкир\w*|"
                       r"видання|издание|агентство|політсил\w*|политсил\w*|парті\w*|парти\w*|відомств\w*|ведомств\w*|канцлер\w*|губернатор\w*)\b", re.I)
ORG_NOUN = re.compile(r"^(?:дом\w*|дім\w*|безпек\w*|безопасност\w*|прес\w*-?служб\w*|пресс\w*-?служб\w*|горсовет\w*|міськрад\w*|рад[аиі]|совет\w*|адміністрац\w*|администрац\w*|служб\w*|управлін\w*|управлен\w*|"
                      r"міністерств\w*|министерств\w*|інститут\w*|институт\w*|університет\w*|университет\w*|центр\w*|комітет\w*|"
                      r"комитет\w*|прокуратур\w*|поліці\w*|полици\w*|уряд\w*|правительств\w*|парті\w*|парти\w*|банк\w*|компані\w*|"
                      r"компани\w*|фонд\w*|військ\w*|войск\w*|командуванн\w*|штаб\w*|академі\w*|академи\w*|агентств\w*)$", re.I)
ADJ_END = re.compile(r"(ський|ский|цький|цкий|ська|ская|цька|цкая|ське|ское|ий|ый|ой|ая|ій|ня|ое|е|а|ого|ої|ою)$")
P_OUTLET = re.compile(rf"(?:^|[\s,(])(?i:видання|издание|агентство|агентства|телеканал|газета|журнал|медіа|медиа)\s+(?P<x>{CAP}[^\s,.;:!?]{{1,30}}(?:\s+{CAP}[^\s,.;:!?]{{1,20}}){{0,2}})\s+"
                      rf"(?i:{SPEECH}|показал\w*|показав\w*|оприлюдни\w*|з.ясува\w*|выяснил\w*|дізнал\w*|узнал\w*|публікує|публикует)")

P_SIGN = re.compile(r"(?:[,\.!?»\"”…\)]\s*|\s|(?<=\w))[—–]{1,2}\s*(?P<x>[^\n—–]{2,90}?)\s*[\.!]?\s*$")
P_SIGN_MID = re.compile(r"[,!?»\"”…]\s*[—–]{1,2}\s*(?P<x>[^\n—–.]{2,60}?)\.(?=\s+[A-ZА-ЯІЇЄҐ«\"])")
P_ROLE_BEFORE = re.compile(rf"(?:^|[\.!?…—–]\s*|\n|(?<=\s))[^\w\n«\"“]{{0,6}}(?P<x>(?i:{ROLE_START})[\w\-\.]*(?:[ \t\u00a0]+[\w'’ʼ\-«»\"“”№]+){{0,7}}?)(?:[ \t ]+(?:сьогодні|сегодня|вчора|вчера|також|также|уже|вже|раніше|ранее|теж|тоже|ще|еще|в\s+свою\s+очередь|своєю\s+чергою|у\s+свою\s+чергу))?[ \t\u00a0]+(?i:{SPEECH})\b")
P_IMPERSONAL = re.compile(r"(?:^|[\.!?…]\s+|\n)[^\w\n]{0,6}(?:(?:повідомляють|кажуть|пишуть|говорять|сообщают|говорят|пишут|передают)\s*,?\s+(?:що|что)\b|"
                          r"(?:повідомляють|сообщают)\s+(?:про|о|об)\b)", re.I)
P_SIGN_HY2 = re.compile(r"\s-\s(?P<x>[A-ZА-ЯІЇЄҐ«\"][^\n\-]{1,45}?)\s*[\.!]?\s*$")
P_SIGN_HY = re.compile(r"[,»\"”]\s*-\s*(?P<x>[^\n—–\-]{2,90}?)\s*[\.!]?\s*$")
P_AFTER = re.compile(rf"(?<!\w)(?i:{SPEECH})\s+(?i:(?:на\s+брифінгу|на\s+брифинге|в\s+ефірі|у\s+ефірі|в\s+эфире|в\s+коментарі|у\s+коментарі|в\s+комментарии)\s+)?(?:(?:у|в|во)\s+)?(?P<x>(?:{CAP}|(?i:{ROLE_START})\b)[^,.;:!?\n«»\"“”]{{1,80}})")
P_BEFORE = re.compile(rf"(?:^|[\.!?…]\s+|[—–]\s*|\n|(?<![\w,])(?i:так|вот\s+так|ось\s+так)\s+)[^\w\n«\"“]{{0,6}}(?P<x>[A-ZА-ЯІЇЄҐ@][\w'’ʼ\-]*(?:[ \t\u00a0]+[\w'’ʼ\-№]+){{0,5}}?)(?:[ \t ]+(?:сьогодні|сегодня|вчора|вчера|також|также|уже|вже|раніше|ранее|теж|тоже|ще|еще|в\s+свою\s+очередь|своєю\s+чергою|у\s+свою\s+чергу))?[ \t\u00a0]+{SPEECH}\b")
P_COLON = re.compile(r"(?:^|\n)\W{0,4}(?P<x>[A-ZА-ЯІЇЄҐ«\"][^\n:]{1,45}?):\s+\S")
P_IN = re.compile(rf"(?:^|[\s,])[УВуВ]\s+(?P<x>{CAP}[^,.;:!?\n]{{1,60}}?)\s+"
                  rf"(?:повідомили|заявили|кажуть|розповіли|підтвердили|зазначили|наголосили|уточнили|відповіли|"
                  rf"сообщили|заявили|рассказали|назвали|подтвердили|отметили|уточнили|ответили)\b")
P_PREP = re.compile(r"(?P<t>зі\s+слів|із\s+слів|со\s+слов|за\s+даними|за\s+інформацією|за\s+словами|(?<!\w)(?:із|зі|з)\s+посиланням\s+на|посилаючись\s+на|як\s+повідомля\w*|"
                    r"як\s+пише|як\s+пишуть|як\s+заяви\w*|як\s+розпові\w*|джерело\s*:|джерела\s*:|"
                    r"по\s+данным|по\s+информации|по\s+словам|со\s+ссылкой\s+на|ссылаясь\s+на|как\s+сообща\w*|как\s+пишет|"
                    r"как\s+пишут|как\s+заявил\w*|источник\s*:|"
                    rf"про\s+це\s+{SPEECH}|об\s+этом\s+{SPEECH})\s+(?P<x>[^,.;:!?\n]{{2,80}})", re.I)
P_EYE = re.compile(r"#\s?нам\s?пишуть|#\s?нам\s?пишут|нам\s+пишуть|нам\s+пишут|пишуть\s+підписники|пишут\s+подписчики|"
                   r"підписники\s+(?:повідомляють|надіслали|пишуть)|подписчики\s+(?:сообщают|прислали|пишут)|"
                   r"очевидці\s+(?:повідомляють|розповідають|кажуть)|очевидцы\s+(?:сообщают|рассказывают)", re.I)
P_SOCIAL = re.compile(r"(?:з.яви\w*|опубліков\w*|появил\w*|попал\w*|потрапил\w*|слил\w*|злил\w*)\s+(?:у|в)\s+(?:мережі|мережу|сети|сеть|соцмереж\w*|соцсет\w*)|"
                      r"(?:у|в)\s+(?:мережі|сети)\s+(?:з.яви\w*|поширю\w*|поширил\w*|появил\w*|распространя\w*|опублікува\w*|публику\w*)|користувачі\s+соцмереж|пользователи\s+соцсетей|відео\s+(?:з\s+)?соцмереж",
                      re.I)
CUT = re.compile(r"\s+(?:що|чтобы|что|про|о|об|після|после|в\s+свою\s+очередь|своєю\s+чергою|у\s+свою\s+чергу|під\s+час|во\s+время|у\s+своєму|в\s+своем|в\s+ефірі|в\s+эфире|в\s+інтерв.ю|"
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
SELF_HANDLE_RX = re.compile(r"^(?:truexa|truekha|trukha|kiev_?info|kiev_operativ|novosty_kiev|ukrainaonl|uaonli|vanek|lachen|times_?ukr|kyiv_?times|"
                            r"batalion_?monako|monako)", re.I)
SELF_HANDLES = {"truexanewsua", "kievinfo_kyiv", "uaonlii", "vanek_nikolaev", "lachentyt", "times_ukraina", "batalionmonako",
                "suspilnenews", "ukrpravda_news", "tch_channel", "uniannet", "novosty_kiev_bot", "truexausend_bot"}

AD_STRONG = re.compile(r"#\s?реклам|#\s?ad\b|#\s?партнер|на\s+правах\s+реклами|партнерськ\w*\s+матеріал", re.I)
PHATIC = re.compile(r"^\W*(?:доброго\s+ранку|добрий\s+ранок|доброе\s+утро|бадьорого\s+ранку|гарного\s+дня|хорошего\s+дня|доброї\s+ночі|"
                    r"спокійної\s+ночі|спокойной\s+ночи|без\s+слів|без\s+слов|дякую\s+всім|спасибо\s+всем|всім\s+привіт|всем\s+привет)", re.I)
AD_MARK = re.compile(r"на\s+каналі\s+від|на\s+канале\s+от|у\s+своєму\s+блозі|в\s+своем\s+блоге|це\s+блог|это\s+блог|переходим\s+на\s+канал|"
                     r"набір\s+на\s+(?:навчанн|курс)|набор\s+на\s+(?:обучени|курс)|оплата:\s*\d+|"
                     r"отриму\w*\s+\d+\s*грн|получаем\s+\d+\s*грн|промокод|розіграш\w*|розыгрыш\w*|казино|онлайн-казино|слоти\b|слоты\b|космолот|ставк\w*\s+на\s+спорт|"
                     r"фрібет|фрибет|депозит\w*|трейдинг|заробіт\w*\s+від|заработ\w*\s+от|знижк\w*\s+до|скидк\w*\s+до|"
                     r"переходь\w*\s+за\s+посиланням|переходи\s+по\s+ссылке|ціни?\s+нижч|цены?\s+ниже|доставк\w*\s+по\s+україн|"
                     r"купуйте|замовляйте|оформлюй\w*|зареєструйся\s+(на|за)|зарегистрируйся\s+(на|по)|безкоштовн\w*\s+навчанн|"
                     r"інвестиційн\w*\s+компан|оптов\w*\s+цін|мольфар\w*|ворожк\w*|гадалк\w*|таро\b|пророцтв\w*|"
                     r"акці\w*\s+діє|акция\s+действует|кешбек|кэшбэк|ліміт\w*\s+місць|встигни|успей", re.I)
SELF_PROMO = re.compile(r"підпис(уйтесь|уйся|атись|атися)|подпис(ывайтесь|ывайся|аться|ывайтесь)|наш\w*\s+(?:канал|інстаграм|"
                        r"инстаграм|instagram|youtube|ютуб|тікток|тикток|tiktok)|голос\w*\s+за\s+(?:наш\s+)?канал|boost|"
                        r"підтримайте\s+канал|поддержите\s+канал|переходь\w*\s+(?:в|у|до)\s+(?:наш\s+)?канал|приєднуйтесь|присоединяйтесь|"
                        r"ми\s+в\s+(?:інстаграм|instagram)|мы\s+в\s+(?:инстаграм|instagram)|канал\s+про\s+\w+\s*👉", re.I)
ALERT_STRONG = re.compile(r"повітрян\w*\s+тривог|воздушн\w*\s+тревог|в\s+укритт|в\s+укрыти|покин\w*\s+помещени|"
                          r"загроза\s+(?:балістик|ракетн|застосуванн)|угроза\s+(?:баллистик|ракетн|применени)|пуск\w*\s+(?:кинджал|кинжал|кінджал|кінжал|ракет|балістик|баллистик)", re.I)
ALERT = re.compile(r"пуск\w*|шахед\w*|мопед\w*|балістик\w*|баллистик\w*|ракет\w*|бпла|безпілотник\w*|кинджал|кинжал|тривог\w*|тревог\w*|"
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

    @staticmethod
    def fix_homoglyphs(text: str) -> str:
        """«Аutoconsulting», «Новини.LIVЕ»: латинські й кириличні двійники в одному слові → однією абеткою."""
        def f(m):
            w = m.group(0)
            lat = len(re.findall(r"[A-Za-z]", w)); cyr = len(re.findall(r"[А-Яа-яІіЇїЄєҐґ]", w))
            if not lat or not cyr:
                return w
            return w.translate(CYR2LAT) if lat >= cyr else w.translate(LAT2CYR)
        return re.sub(r"[A-Za-zА-Яа-яІіЇїЄєҐґ]+", f, text)

    def content_type(self, text: str) -> str:
        """informational / alert / technical — що за зміст (незалежно від промо)."""
        letters = len(re.sub(r"[\W\d_]+", "", text))
        words = len(re.findall(r"[^\W\d_]{2,}", text))
        if letters < 6 or words < 2:
            return "technical"
        if len(text) < 140 and PHATIC.search(text) and not ALERT.search(text):
            return "technical"
        if (len(text) < 500 and ALERT_STRONG.search(text)) or (len(text) < 300 and len(ALERT.findall(text)) >= 2):
            return "alert"
        return "informational"

    def promotional(self, raw: str, text: str) -> str:
        """no / ad / self_promo — окрема ознака (аудит v3.1: промо не перекриває змістовне повідомлення)."""
        marks = {m.group(0).lower()[:6] for m in AD_MARK.finditer(text)}
        if re.search(r"t\.me/(?:\+|joinchat/)", raw or "") and not SELF_PROMO.search(text):
            marks.add("invite")   # запрошення в інший канал
        if AD_STRONG.search(raw or "") or len(marks) >= 2:
            return "ad"
        if SELF_PROMO.search(text):
            return "self_promo"
        return "no"

    @staticmethod
    def substantive_besides_promo(text: str) -> bool:
        rest = "\n".join(l for l in text.splitlines() if not SELF_PROMO.search(l))
        if len(re.sub(r"[\W\d_]+", "", rest)) < 40:
            return bool(ALERT_STRONG.search(rest)) or len(ALERT.findall(rest)) >= 2
        return not re.search(r"канал\w*", rest, re.I) or bool(re.search(rf"\b{SPEECH}\b", rest, re.I)) or len(ALERT.findall(rest)) >= 2

    def message_type(self, raw: str, text: str) -> str:
        """Зведений тип (для знаменника): ad / self_promo (лише якщо поза промо змісту немає) / technical / alert / informational."""
        promo, content = self.promotional(raw, text), self.content_type(text)
        if promo == "ad":
            return "ad"
        if promo == "self_promo" and not self.substantive_besides_promo(text):
            return "self_promo"
        return content

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
            return bool(re.search(r"(енко|ук|юк|чук|ов|ев|єв|ова|ева|ін|ин|іна|ина|ський|цький|ська|цька|ский|цкий|ич|як|ник|ар|ко|енка|ука|юка|чука|ича|ського|цького|ского|цкого|ета|ата|ята|ова|ева)$", toks[0]))
        return True

    @staticmethod
    def tidy(x: str) -> str:
        x = x.strip()
        for _ in range(4):
            x = re.sub(rf"^(?:{SPEECH}|тем\s+временем|тим\s+часом|между\s+тем|при\s+этом|при\s+цьому|однак|однако|проте|водночас|"
                       rf"сам|сама|самі|сами|пише|ділиться|делится|про\s+це|об\s+этом|на\s+брифінгу|на\s+брифинге|"
                       rf"(?:йдеться|говориться|говорится|зазначається|отмечается|сказано|йдеться)\s+(?:у|в)\s+\w+|"
                       rf"(?:у|в)\s+(?:матеріалі|материале|заяві|заявлении|повідомленні|сообщении|звіті|отчете|публікації|публикации)|"
                       rf"брифінг\w*|брифинг\w*|пресреліз\w*|пресс-релиз\w*|прес-реліз\w*|у|в|во)\s+", "", x, flags=re.I)
        x = re.split(rf"\s+(?i:{SPEECH})\b", x)[0]
        x = CUT.sub("", x)
        toks, out, seen_cap = x.split(), [], False
        for t in toks:
            bare = t.strip("«»\"“”'(),.:;")
            if seen_cap and bare and bare[0].islower() and bare.lower() not in ("з", "у", "в", "і", "та", "й", "и", "of", "de", "del", "der", "von", "the", "and", "при", "по",
                                                                                 "фон", "ван", "де", "ла", "бен", "ібн", "ибн", "ді", "да", "дер", "аль", "эль"):
                prev = out[-1].strip("«»\"“”'(),.:;") if out else ""
                org_head = any(ORG_NOUN.match(o.strip("«»\"“”'(),.:;")) for o in out)
                if not (ORG_NOUN.match(bare) and ADJ_END.search(prev.lower())) and not (org_head and len(out) < 7):
                    break
            if (bare[:1].isupper() or bare.startswith("@")) and not (not out and (ROLE_WORD.match(bare) or ROLE_ANY.match(bare))):
                seen_cap = True
            out.append(t)
        x = " ".join(out)
        x = re.sub(r"[\U0001F000-\U0001FFFF☀-➿️]+", " ", x)
        x = re.sub(r"\s+", " ", x).strip(" «»\"“”'.,:;!?()[]-–—*_")
        if x.count('"') == 1:
            x = x + '"' if not x.startswith('"') else x[1:]
        toks = x.split()[:8]
        while toks and toks[-1].lower() in ("з", "із", "у", "в", "і", "та", "й", "и", "and", "of", "при", "по", "на", "со", "с"):
            toks.pop()
        return " ".join(toks)

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
        if h.startswith("petition.") or ".petition." in h or "petition" in h.split(".")[0]:
            return {"domain": h, "entity": h, "platform_type": "other_site", "whitelist": False}  # ⚑6: петиції
        if h in ("t.me", "telegram.me"):
            path = p.path.strip("/").split("/")
            handle = (path[0] if path else "").lower()
            if not handle or handle.startswith("+") or handle in ("joinchat", "c", "boost", "addlist", "share") \
                    or handle in SELF_HANDLES or SELF_HANDLE_RX.match(handle) or handle.endswith("bot"):
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
                      (len(al.split()) == 1 and len(b["name"].split()) == 1 and al[:6] == b["name"].lower()[:6]) or
                      (role_only.match(al) and b["specificity"] == "named")) for b in out)
            if not dup:
                out.append(a)
        return Attribution._corefer(out)

    @staticmethod
    def _has_name(name: str) -> bool:
        """Чи є в назві власне ім'я/назва (Title-case слово, що не є роллю чи країною)."""
        for i, t in enumerate(name.split()):
            b = t.strip("«»\"“”'(),.:;")
            if i == 0 and ROLE_WORD.match(b):
                continue
            if re.fullmatch(r"[A-ZА-ЯІЇЄҐ][a-zа-яіїєґ'’ʼ\-]+", b) and not COUNTRY.match(b) and not RUSSIA.match(b) and not ROLE_WORD.match(b):
                return True
            if i > 0 and re.fullmatch(r"[A-ZА-ЯІЇЄҐ\"«][A-ZА-ЯІЇЄҐ\"»]{3,}", b) and not ROLE_WORD.match(b):
                return "org"
        return False

    @staticmethod
    def _corefer(actors: list) -> list:
        """Аудит v3.1 (3): роль без імені + одна названа особа того самого типу → одна сутність
        («Прем'єр Великобританії» + «Джонсон»; «Спикер» + «Петр Андрющенко»; «министра» + «Чернохова»)."""
        roles = [a for a in actors if a.get("source_level", "direct") == "direct" and ROLE_WORD.match(a["name"])
                 and Attribution._has_name(a["name"]) is not True]
        drop = set()
        for r in roles:
            cands = [p for p in actors if p is not r and id(p) not in drop and Attribution._has_name(p["name"]) is True
                     and (p["type"] == r["type"] or p["type"] == "person_other" or
                          (re.match(r"(видання|издание|агентство)$", r["name"], re.I) and p["type"].endswith("_media")))]
            if len(cands) == 1:
                p = cands[0]
                if p["type"] == "person_other" and r["specificity"] != "generic" and r["type"] not in ("other", "person_other"):
                    p["type"] = r["type"]
                p.setdefault("merged_with", []).append(r["name"])
                drop.add(id(r))
        return [a for a in actors if id(a) not in drop]

    # ---------- одне повідомлення ----------
    def analyze(self, msg: dict, channel: str, boiler=frozenset()):
        raw = msg.get("text") or ""
        text, urls = self.body(raw, boiler)
        text = self.fix_homoglyphs(text)
        mtype = self.message_type(raw, text)
        self_rx = re.compile(SELF.get(channel, r"(?!x)x"), re.I)
        found = []

        def ctx_of(pos):
            a = text.rfind("\n", 0, pos) + 1
            b = text.find("\n", pos)
            return text[a:b if b >= 0 else len(text)]

        def add(x, pattern, level="direct", ctx="", force_cat=None):
            x = re.sub(r"\b(т\.\s?)?в\.\s?о\.\s?", lambda m: ("т.в.о " if m.group(1) else "в.о "), x)
            if re.search(r"[.!?]\s|»\.|\.»", x):          # аудит (1): назва не може містити кінець речення
                return
            ms = re.match(r"^(?:[\w'’ʼ]+\s+)?(?:джерел\w*|источник\w*|співрозмовник\w*|собеседник\w*)\s+(?P<m>[A-ZА-ЯІЇЄҐ«\"][^\s].*)$", x.strip(), re.I)
            if ms and level == "direct":
                add(ms.group("m"), pattern, "direct", ctx)
                add("джерела", "prep", "embedded", ctx, force_cat="anonymous")
                return
            mm = MEDIUM.search(" " + x + " ")
            if mm:  # «український чиновник в коментарі The Economist на правах анонімності»: актор + видання-посередник
                xs = " " + x + " "
                head, tail = xs[:mm.start()].strip(), xs[mm.end():].strip()
                anon = "anonymous" if ANON_MARK.search(x) else None
                if head:
                    add(head, pattern, level, ctx, force_cat=anon)
                    add(tail, "medium", "intermediary", ctx)
                    return
            po = P_PLATFORM_OWNER.match(x.strip())
            if po and not re.match(r"(?:що|что|про|о|об)\b", po.group("o"), re.I):
                x = po.group("o")  # «— Twitter сейму»: джерело — власник акаунта, платформа — лише місце
            m = NEST.search(" " + x + " ")
            if m:  # «Радіо Свобода із посиланням на супутникові знімки»: пряме джерело + вкладене
                xs = " " + x + " "
                head, tail = xs[:m.start()].strip(), xs[m.end():].strip()
                if head:
                    add(head, pattern, level, ctx)
                    add(tail, "prep", "embedded", ctx)
                else:
                    add(tail, "prep", level, ctx)
                return
            if re.search(r"\s(?:і|та|и|й|and)\s|,\s", x):
                parts = [q for q in re.split(r"\s+(?:і|та|и|й|and)\s+|,\s*", x) if q.strip()]
                if 2 <= len(parts) <= 3 and all(len(q.split()) <= 4 and self.classify(self.tidy(q))[0] not in ("other", "noise") for q in parts):
                    for q in parts:
                        add(q, pattern, level, ctx)
                    return
            if len(x.split()) > 6 and len(self.tidy(x).split()) > 5 or len(x.split()) > 14:
                return  # аудит (1): шматок речення, а не назва
            if force_cat is None and ANON_MARK.search(x) and pattern != "medium":
                force_cat = "anonymous"
            locative = bool(re.match(r"^(?:у|в|во|на)\s+\S", x.strip(), re.I))
            raw_x = x
            x = self.tidy(x)
            if len(x) < 2 or self_rx.search(x):
                return
            cat, wl = self.classify(x)
            if force_cat:
                cat, wl = force_cat, False
            if cat == "noise":
                return
            if pattern == "medium" and not cat.endswith("_media"):
                return
            if cat == "ua_official" and re.match(r"(колишн|бывш|екс-?|экс-?)", x, re.I):
                cat = "politician"   # колишні посадовці — політики (ATTRIBUTION_RULES §3)
            if cat in ("other", "ua_official", "company_organization") and RUSSIA.search(x) and \
                    re.search(r"рад[аиі]\b|совет|служб|міністерств|министерств|управлін|управлен|агентств|комітет|комитет|уряд|правительств|мзс|мид", x, re.I):
                cat = "russian_official"  # «Рада безпеки рФ»
            if re.search(r"депутат|нардеп|сенатор|конгресмен", x, re.I) and cat in ("foreign_official", "ua_official", "russian_official"):
                cat = "politician"            # «депутат Європарламенту», «депутат Госдуми» — політики
            if re.search(r"олен\w*\s+зеленськ|олен\w*\s+зеленск|^зеленськ(а|ої|ій|у)$|^зеленск(ая|ой|ую)$", x, re.I):
                cat = "person_other"          # дружина президента — не посадовиця
            jm = re.match(r"^(?:журналіст\w*|журналист\w*|кореспондент\w*|корреспондент\w*)\s+(?P<o>.+)$", x, re.I)
            if jm and cat in ("unnamed_media", "other", "person_other"):
                oc = self.classify(jm.group("o"))[0]
                if oc.endswith("_media"):
                    cat = oc                  # «журналіст «Голосу Америки» Яриш» → тип видання
            if len(x.split()) == 1 and re.search(r"(ський|ский|цький|цкий|ний|ный)$", x.lower()) and cat in ("other", "foreign_official", "person_other"):
                return                        # прикметник без іменника («Американский …»)
            if pattern == "producer" and locative:
                return                        # «зняли в районі Вишгорода» — місце, а не автор
            if KIN.match(x):
                cat = "person_other"  # «Зять Шойгу» — родич, а не посадовець
            if cat in ("other", "ua_official") and GOV_GENERIC.search(x) and not re.search(r"україн|украин", x, re.I):
                if COUNTRY.search(x):
                    cat = "foreign_official"
                elif RUSSIA.search(x):
                    cat = "russian_official"
                elif cat == "other" and COUNTRY.search(ctx) and not RUSSIA.search(ctx):
                    cat = "foreign_official"   # «Великобритания не планирует…, по словам представителя правительства»
                elif cat == "other" and RUSSIA.search(ctx) and not COUNTRY.search(ctx):
                    cat = "russian_official"
            quoted_name = bool(re.match(r"^[«\"“]", raw_x.strip())) and len(x.split()) <= 4
            if cat == "other" and ROLE_ANY.search(x) and not re.search(r"україн|украин", x, re.I):
                if COUNTRY.search(x):
                    cat = "foreign_official"   # «Государственный секретарь США Майк Помпео», «Президент Польщі Дуда»
                elif RUSSIA.search(x):
                    cat = "russian_official"
            if cat == "other" and ROLE_ANY.search(x) and re.search(r"україн|украин", x, re.I):
                cat = "ua_official"
            keep_other = False
            if cat == "other":
                if self.person_like(x) or (NAME_TAIL.search(x) and (ROLE_ANY.search(x.split()[0]) or ROLE_WORD.match(x) or len(x.split()) <= 3)):
                    cat = "person_other"       # «директор медустанови Борис Тодуров», «журналист Андрей Цаплиенко»
                elif pattern in ("signature", "prep") and DOC_WORD.match(x):
                    keep_other = True          # документ як джерело: «— проєкт бюджету»
                elif pattern in ("signature", "producer") and (quoted_name or re.fullmatch(r"[A-ZА-ЯІЇЄҐ][\w'’ʼ.\-]*(?:\s+[A-ZА-ЯІЇЄҐ0-9][\w'’ʼ.\-]*){0,2}", x)):
                    keep_other = True          # власна назва в підписі: «— «VD»», «— Meteoagent»
            if cat == "other" and not keep_other:
                if self.person_like(x):
                    cat = "person_other"
                elif re.search(r"\bрад[аи]\b|служб|компані|компани|фонд|асоціац|ассоциац|організац|организац|\bцентр|інститут|"
                               r"институт|університет|университет|\bбанк|агентств|комітет|комитет|\bсоюз|\bго\b", x, re.I):
                    cat = "company_organization"
                elif pattern in ("before", "after", "signature", "colon", "producer"):
                    return
            if pattern == "colon" and (cat not in ("ua_official", "foreign_official", "russian_official", "ua_media", "foreign_media",
                                                   "russian_media", "politician", "expert", "telegram") or len(x.split()) > 4):
                return  # двокрапка — лише для впізнаних акторів (рішення ⚑1), не для заголовків-тем
            if pattern == "before" and locative and cat in ("other", "person_other"):
                return  # «В Волновахе ... сообщают» — місце, а не джерело
            if pattern in ("nest_direct", "medium") and cat == "other":
                return
            found.append({"name": x, "type": cat, "whitelist": wl, "pattern": pattern, "source_level": level,
                          "specificity": self.specificity(cat, x), "linked_destination": ""})

        lines = text.splitlines()
        for k, ln in enumerate(lines[:3] + lines[-2:]):
            for rx in ((P_SIGN, P_SIGN_HY, P_SIGN_HY2) if k < 3 else (P_SIGN, P_SIGN_HY)):
                m = rx.search(ln)
                if m and (len(self.tidy(m.group("x")).split()) <= 8 or NEST.search(" " + m.group("x") + " ") or MEDIUM.search(" " + m.group("x") + " ")):
                    add(m.group("x"), "signature", ctx=ln)
        for ln in lines:
            for m in P_SIGN_MID.finditer(ln):
                if len(m.group("x").split()) <= 6:
                    add(m.group("x"), "signature", ctx=ln)
        for m in P_COLON.finditer(text):
            if len(m.group("x").split()) <= 5:
                add(m.group("x"), "colon", ctx=ctx_of(m.start()))
        if P_IMPERSONAL.search(text):
            found.append({"name": "невизначене («повідомляють»)", "type": "anonymous", "whitelist": False,
                          "pattern": "impersonal", "specificity": "anonymous", "linked_destination": "", "source_level": "direct"})
        for m in P_PREP.finditer(text):
            level = "direct"
            if NEST.search(" " + m.group("t") + " "):
                ln = ctx_of(m.start())
                pre = text[text.rfind("\n", 0, m.start()) + 1:m.start()]
                head = re.split(r"[—–:.!?]\s*|,\s+(?=[—–])", pre)[-1].strip(" ,")
                if head and len(head.split()) <= 6:
                    n0 = len(found)
                    add(head, "nest_direct", "direct", ln)
                    if len(found) > n0:
                        level = "embedded"
            add(m.group("x"), "prep", level, ctx_of(m.start()))
        for m in P_CREDIT.finditer(text):  # «Відео: Стас Юрченко, Ґрати»
            add(m.group("x"), "producer", ctx=ctx_of(m.start()))
        for m in P_PRODUCER.finditer(text):  # ⚑7: виробник поширюваного контенту — джерело
            add(m.group("x"), "producer", ctx=ctx_of(m.start()))
        for m in P_OUTLET.finditer(text):
            add(m.group("x"), "signature", ctx=ctx_of(m.start()))
        text_nr = REL.sub("", text)  # без підрядних «…, которую возглавляет Порошенко, …»
        for rx, tag, src in ((P_IN, "in_org", text), (P_AFTER, "after", text), (P_BEFORE, "before", text_nr), (P_ROLE_BEFORE, "before", text_nr)):
            for m in rx.finditer(src):
                if tag == "after" and re.match(r"(?i)(?:заклика|призва|призыва|назва|звинуват|обвин|показа|вимага|требу|погрож|угрожа|обіця|обеща|запевни|завери)", m.group(0)):
                    continue  # після цих дієслів стоїть адресат, а не мовець («закликав військових …»)
                add(m.group("x"), tag, ctx=src[src.rfind("\n", 0, m.start()) + 1:])
        if P_EYE.search(text) or re.search(r"#\s?нам\s?пишут", raw, re.I):
            add("підписники", "eyewitness")
        if P_SOCIAL.search(text):
            add("соцмережі", "social")
        if self.promotional(raw, text) != "no":  # хендли каналів у промо-повідомленні — реклама, не джерело
            found = [f for f in found if not re.match(r"^(?:t\.me/|@)", f["name"])]
        # платформа («написав у Facebook») — не актор, якщо в повідомленні є справжній актор (аудит v3.2)
        if any(not (f["type"] == "social" and BARE_PLATFORM.match(f["name"])) for f in found):
            found = [f for f in found if not (f["type"] == "social" and BARE_PLATFORM.match(f["name"]))]
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
                inferred.append({"name": d["entity"], "type": t, "whitelist": d["whitelist"], "pattern": "link_only", "source_level": "direct",
                                 "specificity": "generic" if t in ("social", "other") else "named",
                                 "linked_destination": d["domain"], "actor_inferred_from_link": True})
        has_text = bool(actors)
        has_link = bool(src_dests) or any(x.get("linked_destination") for x in actors)
        method = "both" if has_text and has_link else "textual" if has_text else "hyperlink" if has_link else "none"
        return {
            "message_type": mtype,
            "content_type": self.content_type(text),
            "promotional": self.promotional(raw, text),
            "has_textual_source": has_text,
            "has_embedded_source": any(a.get("source_level") == "embedded" for a in actors),
            "n_direct_sources": sum(a.get("source_level", "direct") == "direct" for a in actors + inferred),
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
