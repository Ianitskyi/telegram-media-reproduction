"""Детектори v2: посилання і згадки, незалежно один від одного.

Відмінності від v1 (див. docs/AUDIT_2026-10-21.md):
- згадки шукаються в тексті, з якого вилучено URL і markdown-посилання
  («[Сайт](https://...)» → «Сайт»), тож посилання саме по собі не стає «згадкою»;
- згадки — лише за ручним словником config/media_aliases.json (без автоматичних
  «перших слів» і фрагментів доменів); неоднозначні назви — лише з ознакою медіа поруч;
- посилання — лише з поля urls (воно містить і текстові, і приховані посилання);
- самопосилання/самозгадки каналу власного медіа рахуються окремо;
- шаблонні рядки-підписи каналу (повторюються в ≥1% повідомлень) вилучаються до пошуку.
"""
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]

# Канали, що належать медіа зі списку: username -> id медіа в media_aliases.json
SELF_MEDIA = {"suspilnenews": {0}, "ukrpravda_news": {3}}

MD_LINK = re.compile(r"\[([^\]]*)\]\((?:https?://|tg://|mailto:)[^)]*\)")
URL = re.compile(r"(?:https?://|www\.)\S+", re.I)

# Ознаки того, що поруч ідеться про медіа (для режиму ctx)
CUE_BEFORE = re.compile(
    r"(видання|медіа|сайт\w*|портал\w*|газет\w*|агенці\w*|журнал\w*|ресурс\w*|телеканал\w*|радіо|"
    r"за\s+даними|за\s+інформацією|з\s+посиланням\s+на|джерело|повідомля\w*|пише|пишуть|інформу\w*|"
    r"издани\w*|по\s+данным|по\s+информации|со\s+ссылкой\s+на|источник|сообща\w*|пишет|пишут)"
    r"[\s:,«\"“„]*$", re.I)
CUE_AFTER = re.compile(
    r"^[»\"”\s,]*(пише|пишуть|повідом(?:ля|и)\w*|інформу\w*|з{A}ясува\w*|дізна\w*|передає|передають|"
    r"сообща\w*|пишет|пишут|выяснил\w*|узнал\w*|передает)\b".replace("{A}", "['’ʼ]"), re.I)
DASH_BEFORE = re.compile(r"[—–-]\s*[«\"“]?$")
DASH_END = re.compile(r"^[»\"”]?\s*(?:[\.\n!]|$|\s*\n)")   # після назви — кінець речення/рядка
QUOTE_OPEN = re.compile(r"[«\"“„]$")
QUOTE_CLOSE = re.compile(r"^[»\"”]")


class Detector:
    def __init__(self, aliases_path: Path = ROOT / "config" / "media_aliases.json"):
        self.media = json.loads(Path(aliases_path).read_text(encoding="utf-8"))
        self.names = {m["id"]: m["name"] for m in self.media}
        self.domains = []  # (domain, id)
        self.patterns = []  # (id, mode, compiled)
        for m in self.media:
            for d in m["domains"]:
                self.domains.append((d.lower(), m["id"]))
            for a in m["aliases"]:
                flags = re.I if a["mode"] == "safe" else 0
                self.patterns.append((m["id"], a["mode"], re.compile(a["pattern"], flags)))

    # --- підготовка тексту -------------------------------------------------
    @staticmethod
    def clean(text: str) -> str:
        text = MD_LINK.sub(lambda m: m.group(1), text or "")
        return URL.sub(" ", text)

    @staticmethod
    def boilerplate_lines(messages, min_share=0.01, min_count=50):
        """Рядки, що повторюються у ≥1% повідомлень каналу (підписи, футери)."""
        c = Counter()
        for m in messages:
            lines = {ln.strip() for ln in Detector.clean(m.get("text") or "").splitlines() if ln.strip()}
            c.update(lines)
        n = max(len(messages), 1)
        return {ln for ln, k in c.items() if k >= min_count and k / n >= min_share}

    # --- посилання ----------------------------------------------------------
    def link_ids(self, urls):
        ids = set()
        for u in urls or []:
            u = u.strip().rstrip(").,;»\"'")
            try:
                host = urlparse(u if "://" in u else "http://" + u).netloc.lower()
            except ValueError:
                continue
            host = host.split("@")[-1].split(":")[0]
            if host.startswith("www."):
                host = host[4:]
            for d, i in self.domains:
                if host == d or host.endswith("." + d):
                    ids.add(i)
        return ids

    # --- згадки -------------------------------------------------------------
    def mention_ids(self, clean_text: str):
        ids, hits = set(), []
        for i, mode, rx in self.patterns:
            if i in ids:
                continue
            for m in rx.finditer(clean_text):
                if mode == "ctx" and not self._has_cue(clean_text, m.start(), m.end()):
                    continue
                ids.add(i)
                hits.append((i, m.group(0)))
                break
        return ids, hits

    @staticmethod
    def _has_cue(t, s, e):
        before, after = t[max(0, s - 40):s], t[e:e + 30]
        quoted = QUOTE_OPEN.search(before) and QUOTE_CLOSE.search(after)
        signed = DASH_BEFORE.search(before) and DASH_END.search(after)
        return bool(quoted or signed or CUE_BEFORE.search(before) or CUE_AFTER.search(after))

    # --- одне повідомлення -------------------------------------------------
    def analyze(self, msg, channel, boiler=frozenset()):
        own = SELF_MEDIA.get(channel, set())
        text = self.clean(msg.get("text") or "")
        if boiler:
            text = "\n".join(ln for ln in text.splitlines() if ln.strip() not in boiler)
        links = self.link_ids(msg.get("urls"))
        mentions, hits = self.mention_ids(text)
        return {
            "link_ids": sorted(links - own),
            "mention_ids": sorted(mentions - own),
            "self_link": bool(links & own),
            "self_mention": bool(mentions & own),
            "hits": [h for h in hits if h[0] not in own],
            "clean_len": len(text.strip()),
        }
