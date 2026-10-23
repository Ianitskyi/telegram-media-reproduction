"""Перепис джерел: на кого посилаються немедійні канали (незалежно від «білого списку»).

Евристика, а не валідований класифікатор: витягує явні атрибуції з тексту
(«…, — Х.», «за даними Х», «пише Х», «джерело: Х», рос. відповідники) та домени посилань,
і відносить їх до типів за словниками нижче. Мета — описова картина + список
найчастіших джерел для ручного перегляду.

Запуск: python -m src.v2.source_census
Вихід: results/v2/sources_*.csv, results/v2/SOURCES.md
"""
import json
import re
from collections import Counter, defaultdict
from urllib.parse import urlparse

import pandas as pd

from src.v2.aggregate import NON_MEDIA
from src.v2.detect import ROOT, Detector

OUT = ROOT / "results" / "v2"

SIGN = re.compile(r"[,\.!»\"”\)]?\s*[—–-]{1,2}\s*([^\n—–]{2,70}?)\s*[\.!]?\s*$")
VERB = re.compile(
    r"(?:за\s+даними|за\s+інформацією|за\s+словами|з\s+посиланням\s+на|повідомля\w*|повідоми\w*|пише|пишуть|"
    r"джерело:|джерела\s+в|заяви\w*|по\s+данным|по\s+информации|по\s+словам|со\s+ссылкой\s+на|сообща\w*|пишет|"
    r"пишут|источник:|заяви\w*)\s+[«\"“]?([A-ZА-ЯІЇЄҐ0-9][^\s,\.:;!?»\"”]*(?:\s+[A-ZА-ЯІЇЄҐ0-9«\"][^\s,\.:;!?»\"”]*){0,3})")

CATS = [
    ("noise", r"громк|слышн|укритт|укрытие|відбій|отбой|тривог|тревог|небезпек|опасност|додав|заяви|сказав|сказал|^\d+$"),
    ("unnamed_media", r"^(?:місцев\w*|укр\w*|іноземн\w*|західн\w*|американськ\w*|британськ\w*|європейськ\w*|местн\w*|западн\w*|иностранн\w*)?\s*(змі|сми|медіа|видання|журналіст\w*|издани\w*|журналист\w*)\b"),
    ("telegram", r"монітор|монитор|канал|паблік|паблик|телеграм|telegram|deepstate|радар|підписник|подписчик|инсайдер|інсайдер|z-канал|военкор|рыбар"),
    ("official_ua", r"\bпс\b|міноборони|кмда|міненерго|мінекономік|мінсоцполітик|моз\b|мзс|мон\b|генштаб|генеральн\w* штаб|зсу\b|повітрян\w* сил|воздушн\w* сил|сили оборони|ова\b|ода\b|мва\b|"
     r"обласн\w* військов|міськ\w* військов|голова\s|глава\s|очільник|мер\b|мэр\b|міськ\w* голов|міністр|министр|мвс|мвд|дснс|гсчс|"
     r"поліці|полици|нацполіц|сбу\b|гур\b|гурмо|розвідк|разведк|зеленськ|зеленск|президент|офіс президента|оп\b|кабмін|кабмин|"
     r"уряд|правительств|верховн\w* рад|рнбо|снбо|прокурат|набу|дбр\b|гбр\b|укренерго|укрэнерго|нафтогаз|укрзалізниц|"
     r"нбу\b|нацбанк|омбудсман|лубінець|лубинец|сирськ|сырск|залужн|буданов|умєров|умеров|шмигал|свиридено|"
     r"кулеба|сибіга|сибига|клименко|кличко|терехов|синєгубов|синегубов|кім олег|ким виталий|федоров|прокопенко|ігнат|игнат|"
     r"держприкордон|дпсу|гпсу|кіберполіц|ювенальн"),
    ("russian", r"росзмі|россми|рос\.?\s?змі|тасс|риа\b|риа новост|интерфакс\b(?!-)|песков|минобороны рф|мо рф|кремл|путин|путін|лавров|захаров|"
     r"рос\w*\s+(?:сми|змі|пропаганд)|російськ\w* (?:змі|медіа|пропаганд)|z-канал|военкор|рыбар|медуза|meduza|"
     r"коммерсант|ведомост|рбк\b(?!-)|baza|shot|mash|astra|соловь|шойгу|белоусов|гладков"),
    ("foreign_official", r"трамп|байден|білий дім|белый дом|пентагон|держдеп|госдеп|нато|nato|єврокоміс|еврокомис|макрон|шольц|мерц|стармер|туск|орбан|венс|рубіо|рубио|уиткофф|віткофф|келлог|магате|оон|un\b"),
    ("ua_politicians_experts", r"нардеп|депутат|експерт|эксперт|аналітик|аналитик|арестович|гончаренко|железняк|порошенко|тимошенко|безугл|костенко|мосійчук|жданов|світан|лапін"),
    ("foreign_media", r"reuters|рейтер|bloomberg|блумберг|cnn|сі-ен-ен|nyt|new york times|нью-йорк таймс|wsj|wall street|"
     r"financial times|\bft\b|bbc|бі-бі-сі|би-би-си|politico|політико|axios|аксіос|guardian|ґардіан|гардиан|economist|економіст|"
     r"\bap\b|associated press|afp|dw\b|deutsche welle|spiegel|шпігель|bild|більд|le monde|washington post|вашингтон пост|"
     r"telegraph|times\b(?! of ukraine)|fox news|nbc|cbs|abc news|sky news|kyiv independent|kyiv post|isw|інститут вивчення війни|"
     r"институт изучения войны|forbes(?!\.ua)|business insider|the atlantic|newsweek|euronews|радіо свобода|радио свобода"),
    ("ua_media_other", r"тсн|tsn\b|уніан|униан|unian|нв\b|nv\b|новое время|новий час|ліга|лига|liga|рбк-україн|рбк-украин|rbc|"
     r"економічн\w* правд|экономическ\w* правд|європейськ\w* правд|европейск\w* правд|цензор|censor|фокус|focus|главком|glavcom|"
     r"телеграф|обозреват|24 канал|24tv|ictv|факти|фактах|1\+1|стб|новий канал|перший незалежний|5 канал|прямий|"
     r"кореспондент|корреспондент|страна|страны|gazeta|газета\.ua|ukranews|укрновини|унн\b|unn\b|dsnews|forbes\.ua|forbes україна|"
     r"суспільне|українськ\w* правд|украинск\w* правд|\bуп\b|укрінформ|укринформ|інтерфакс-україна|интерфакс-украина|"
     r"hromadske|громадське|бабел|еспресо|эспрессо|zn\.ua|дзеркал|зеркал|lb\.ua|мілітарн|милитарн|новини\.live|новости\.live|"
     r"слово і діло|слово и дело|крим\.?реал|крым\.?реал|zaxid|ділова столиця|деловая столица|минфин|мінфін|finance\.ua"),
    ("telegram", r"канал|паблік|паблик|телеграм|telegram|монітор\w* канал|инсайдер|інсайдер|кислород|хуевый|резидент|"
     r"легитимный|темный|картель|сплетниц|мєсні|местн\w* паблик|місцев\w* паблік"),
]
CATS = [(n, re.compile(p, re.I)) for n, p in CATS]

OFFICIAL_DOM = (".gov.ua", "gov.ua", "rada.gov.ua", "president.gov.ua", "mil.gov.ua", "npu.gov.ua", "ssu.gov.ua", "dsns.gov.ua")
SOCIAL_DOM = ("facebook.com", "instagram.com", "youtube.com", "youtu.be", "x.com", "twitter.com", "tiktok.com", "threads.net")
FOREIGN_DOM = ("reuters.com", "bloomberg.com", "nytimes.com", "ft.com", "cnn.com", "wsj.com", "washingtonpost.com", "bbc.com",
               "bbc.co.uk", "theguardian.com", "politico.com", "politico.eu", "economist.com", "apnews.com", "axios.com", "dw.com",
               "spiegel.de", "bild.de", "lemonde.fr", "foxnews.com", "nbcnews.com", "cbsnews.com", "news.sky.com", "kyivindependent.com",
               "kyivpost.com", "understandingwar.org", "forbes.com", "businessinsider.com", "newsweek.com", "euronews.com", "telegraph.co.uk")
UA_OTHER_DOM = ("rbc.ua", "tsn.ua", "unian.ua", "unian.net", "nv.ua", "liga.net", "epravda.com.ua", "eurointegration.com.ua",
                "censor.net", "focus.ua", "glavcom.ua", "telegraf.com.ua", "obozrevatel.com", "24tv.ua", "ukranews.com", "forbes.ua",
                "fakty.ua", "ictv.ua", "korrespondent.net", "gazeta.ua", "dsnews.ua", "unn.ua", "strana.today", "strana.ua", "minfin.com.ua")
RU_DOM = (".ru", "tass.com", "ria.ru", "meduza.io", "rbc.ru")


def dom_cat(h, det_domains):
    if h in ("t.me", "telegram.me"):
        return "telegram"
    if any(h == d or h.endswith("." + d) for d in det_domains):
        return "list_media"
    if h.endswith(OFFICIAL_DOM):
        return "official_ua"
    if any(h == d or h.endswith("." + d) for d in UA_OTHER_DOM):
        return "ua_media_other"
    if any(h == d or h.endswith("." + d) for d in FOREIGN_DOM):
        return "foreign_media"
    if h.endswith(RU_DOM) or h in RU_DOM:
        return "russian"
    if any(h == d or h.endswith("." + d) for d in SOCIAL_DOM):
        return "social"
    return "other_site"


def text_cat(x):
    for n, rx in CATS:
        if rx.search(x):
            return n
    return "unclassified"


def main() -> None:
    det = Detector()
    det_domains = {d for d, _ in det.domains}
    v2 = pd.read_csv(OUT / "messages_link_mention.csv.gz", dtype={"link_ids": str, "mention_ids": str})
    v2 = v2[v2.channel.isin(NON_MEDIA)].set_index(["channel", "msg_id"])
    attributed = Counter()
    per_cat_msgs = defaultdict(Counter)  # channel -> cat -> msgs
    year_cat = defaultdict(Counter)
    totals = Counter()
    for ch in NON_MEDIA:
        msgs = json.loads((ROOT / "data" / "raw" / f"telegram_{ch}.json").read_text(encoding="utf-8"))
        boiler = det.boilerplate_lines(msgs)
        for m in msgs:
            t = det.clean(m.get("text") or "")
            lines = [ln for ln in t.splitlines() if ln.strip() and ln.strip() not in boiler]
            if not lines:
                continue
            totals[ch] += 1
            y = m["date"][:4]
            year_cat[y]["_msgs"] += 1
            cats, names = set(), []
            # підпис «— Х» у кінці будь-якого рядка (переважно заголовок або останній рядок)
            for ln in lines[:3] + lines[-2:]:
                s = SIGN.search(ln.replace("*", "").replace("_", ""))
                if s:
                    names.append(s.group(1).strip(" «»\"“”"))
            for v in VERB.finditer(" ".join(lines).replace("*", "")):
                names.append(v.group(1).strip(" «»\"“”"))
            for x in names:
                if len(x) < 2 or len(x) > 70:
                    continue
                c = "list_media" if det.mention_ids(" за даними " + x)[0] else text_cat(x)
                if c == "noise":
                    continue
                cats.add(c)
                attributed[(c, x)] += 1
            r = v2.loc[(ch, m["id"])]
            if isinstance(r.mention_ids, str) or isinstance(r.link_ids, str):
                cats.add("list_media")
            for u in m.get("urls") or []:
                h = urlparse(u.rstrip(").,")).netloc.lower().split(":")[0]
                h = h[4:] if h.startswith("www.") else h
                if h and h not in ("t.me", "telegram.me"):
                    cats.add(dom_cat(h, det_domains))
            if not cats:
                cats.add("no_explicit_source")
            for c in cats:
                per_cat_msgs[ch][c] += 1
                year_cat[y][c] += 1
    order = ["no_explicit_source", "official_ua", "foreign_official", "ua_politicians_experts", "telegram", "list_media",
             "ua_media_other", "unnamed_media", "foreign_media", "russian", "social", "other_site", "unclassified"]
    tab = pd.DataFrame({ch: {c: 100 * per_cat_msgs[ch][c] / totals[ch] for c in order} for ch in NON_MEDIA}).T.round(1)
    allrow = {c: 100 * sum(per_cat_msgs[ch][c] for ch in NON_MEDIA) / sum(totals.values()) for c in order}
    tab.loc["ALL (pooled)"] = pd.Series(allrow).round(1)
    tab.insert(0, "msgs_with_text", [totals[ch] for ch in NON_MEDIA] + [sum(totals.values())])
    tab.to_csv(OUT / "sources_by_channel.csv")
    yt = pd.DataFrame({y: {c: 100 * year_cat[y][c] / year_cat[y]["_msgs"] for c in order} for y in sorted(year_cat)}).T.round(1)
    yt.to_csv(OUT / "sources_by_year.csv")
    top = pd.DataFrame([(c, x, k) for (c, x), k in attributed.most_common(400)], columns=["category", "attributed_to", "count"])
    top.to_csv(OUT / "sources_top_attributions.csv", index=False)
    md = ["# Перепис джерел у 7 немедійних каналах (евристика, 2026-10-23)", "",
          "Частка повідомлень з текстом, у яких є хоч одне джерело даного типу (повідомлення може мати кілька типів).",
          "`no_explicit_source` — не знайдено ні атрибуції в тексті, ні посилання. `list_media` — медіа з «білого списку» (детектор v2).",
          "Пересилання (forward) не враховано: збирач даних не зберігав, звідки переслано повідомлення.",
          "Посилання t.me не вважаються джерелом (це переважно реклама й «підпишись»); `telegram` — лише текстові атрибуції («— монітори», «місцеві канали»).", "",
          tab.to_markdown(), "", "## По роках (разом)", "", yt.to_markdown(), "",
          "## Найчастіші атрибуції (перші 80)", "", top.head(80).to_markdown(index=False), ""]
    (OUT / "SOURCES.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:12]))


if __name__ == "__main__":
    main()
