"""Порівняння алгоритм / LLM-Claude / LLM-ChatGPT і черга для людської перевірки (docs/VALIDATION_PLAN.md).

  python -m src.v3.adjudication algorithm   → validation/llm/algorithm_raw.jsonl (прогнози алгоритму в схемі кодерів)
  python -m src.v3.adjudication queue       → validation/human/review_queue.json (для інтерфейсу Андрія)
                                              + validation/human/provenance.csv (хто дав який варіант; Андрію не показується)

Сирі відповіді кодерів не змінюються. Зіставлення назв для групування варіантів — за основами слів
(усі основи коротшої назви є в довшій), зі зняттям слів-ролей; рішення щодо назв ухвалює людина.
"""
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LLM = ROOT / "validation" / "llm"
HUMAN = ROOT / "validation" / "human"
SEED = 20261025
AUDIT = {"U_yes_plain": 100, "U_no": 100, "U_yes_special": 50}
RARE_TYPES = {"russian_media", "expert", "politician", "anonymous", "eyewitness", "social", "company_organization", "person_other", "other"}
CODERS = ("algorithm", "claude", "chatgpt")
STOP = {"в", "у", "з", "із", "на", "і", "та", "и", "й", "the", "of", "de", "по", "при", "со", "с"}
ROLE = re.compile(r"^(сам|сама|голов|глав|очіль|керів|мер|мэр|мера|мэра|мініс|минис|речни|спіке|спике|прес|пресс|засту|коман|предс|радни|совет|"
                  r"посол|депут|нардеп|прем|прези|експр|экспр|начал|дирек|гендир|банкі|банки|експе|экспе|анали|політ|полит|колиш|бывш|"
                  r"екс|экс|лідер|лидер)", re.I)


# ---------- прогнози алгоритму в схемі кодерів ----------
def algorithm() -> None:
    from src.v2.detect import Detector
    from src.v3.attribution import Attribution
    at, det = Attribution(), Detector()
    key = pd.read_csv(ROOT / "validation" / "v3_validation_key.csv", dtype=str).fillna("")
    LLM.mkdir(parents=True, exist_ok=True)
    out = []
    for ch, g in key.groupby("channel"):
        msgs = json.loads((ROOT / "data" / "raw" / f"telegram_{ch}.json").read_text(encoding="utf-8"))
        boiler = det.boilerplate_lines(msgs)
        by_id = {str(m["id"]): m for m in msgs}
        for r in g.itertuples():
            a = at.analyze(by_id[r.msg_id], ch, boiler)
            body, urls = at.body(by_id[r.msg_id].get("text") or "", boiler)
            hidden_invite = bool(re.search(r"t\.me/(?:\+|joinchat/)", body + "\n" + "\n".join(urls)))
            out.append({"item_id": r.item_id, "content_type": a["content_type"], "promotional": a["promotional"],
                        "has_explicit_source": a["has_explicit_source"], "attribution_method": a["attribution_method"],
                        "n_direct_sources": a["n_direct_sources"], "has_nested_source": a["has_embedded_source"],
                        "sources": [{"name": s["name"], "type": s["type"], "specificity": s["specificity"],
                                     "level": s.get("source_level", "direct"),
                                     "method": "link" if s.get("actor_inferred_from_link") else "text"} for s in a["attributed_sources"]],
                        "destinations": [{"domain": d["domain"] if d["domain"] != "t.me" else "t.me/" + d["entity"].lstrip("@"),
                                          "platform_type": d["platform_type"], "relation": ""} for d in a["linked_destinations"]],
                        "comment": "", "in_primary_denominator": a["in_primary_denominator"],
                        "flag8_hidden_invite": hidden_invite})
    out.sort(key=lambda x: x["item_id"])
    with open(LLM / "algorithm_raw.jsonl", "w", encoding="utf-8") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    # знімок прогнозів під конкретний коміт алгоритму (історичні цифри не перезаписуються)
    import shutil
    import subprocess
    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or "nogit"
    dirty = subprocess.run(["git", "status", "--porcelain", "src/v3/attribution.py", "src/v3/gazetteer.py"], cwd=ROOT,
                           capture_output=True, text=True).stdout.strip()
    snap = LLM / "snapshots" / f"algorithm_raw_{rev}{'-dirty' if dirty else ''}.jsonl"
    snap.parent.mkdir(exist_ok=True)
    shutil.copy(LLM / "algorithm_raw.jsonl", snap)
    print(f"algorithm: {len(out)} записів → {LLM / 'algorithm_raw.jsonl'} (знімок {snap.name})")


# ---------- канонічна форма відповіді ----------
TR = str.maketrans({"а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e", "є": "ye", "ж": "zh", "з": "z", "и": "y",
                    "і": "i", "ї": "yi", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
                    "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ь": "", "ю": "yu",
                    "я": "ya", "ы": "y", "э": "e", "ъ": "", "ё": "e"})


def stems(name: str, translit: bool = False) -> list:
    n = name.lower().replace("ё", "е")
    n = re.sub(r"https?://|t\.me/|\.(?:com|ua|net|org|info|ru|eu|gov)\b", " ", n)
    n = re.sub(r"[«»\"“”'’ʼ().,:;!?\-—–@_/]", " ", n)
    if translit:
        n = n.translate(TR).replace("ph", "f").replace("g", "h")
    toks = [t for t in n.split() if t not in STOP]
    core = [t for t in toks if not ROLE.match(t)] or toks
    return [t[:5] for t in core]


def same_name(a: str, b: str) -> bool:
    for tr in (False, True):  # також через транслітерацію: «apostrophe.ua» = «Апостроф», «@arma_gov» = «АРМА»
        sa, sb = stems(a, tr), stems(b, tr)
        if sa and sb:
            short, long_ = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
            if set(short) <= set(long_):
                return True
    return False


# Суворе зіставлення (аудит ChatGPT 2026-10-26): лише для визначення одностайності в U-стратах.
# Дозволено: точний збіг; псевдонім (транслітерація, таблиця ALIASES); розширення сутності лише словами-ролями
# («Зеленський» = «президент Зеленський»); граматична варіація (відмінки: слова відрізняються лише закінченням ≤3 літер).
# Нечітке same_name (підмножина 5-літерних основ) — лише для скорингу, не для визначення одностайності.
ALIASES = [{"мзс", "мид", "mfa"}, {"зсу", "всу", "збройні сили україни", "вооруженные силы украины"},
           {"сбу", "служба безпеки україни", "служба безопасности украины"}, {"дснс", "гсчс", "гснс"},
           {"кмда", "кгга"}, {"кмва", "кгва"}, {"оп", "офіс президента", "офис президента"},
           {"мвс", "мвд"}, {"моз", "минздрав", "мінздоров'я"}, {"вр", "верховна рада", "верховная рада", "рада"},
           {"ундс", "уп", "українська правда", "украинская правда"}]


def _core_tokens(name: str, translit: bool) -> list:
    n = name.lower().replace("ё", "е").replace("’", "'").replace("ʼ", "'")
    n = re.sub(r"https?://|t\.me/|\.(?:com|ua|net|org|info|ru|eu|gov)\b", " ", n)
    n = re.sub(r"[«»\"“”'().,:;!?\-—–@_/]", " ", n)
    if translit:
        n = n.translate(TR).replace("ph", "f").replace("g", "h")
    toks = [t for t in n.split() if t not in STOP]
    return [t for t in toks if not ROLE.match(t)] or toks


def _tok_eq(a: str, b: str) -> bool:
    """Та сама лексема з іншим закінченням: різниця довжин ≤3 і спільний початок ≥ (коротше слово − 2), мін. 4 літери."""
    if a == b:
        return True
    k = min(len(a), len(b))
    if k < 4 or abs(len(a) - len(b)) > 3:
        return False
    common = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), k)
    return common >= max(4, k - 2)


def _alias(a: str, b: str) -> bool:
    na, nb = " ".join(_core_tokens(a, False)), " ".join(_core_tokens(b, False))
    return any(na in g and nb in g for g in ALIASES)


QUALIFIERS = {"україни", "украины", "рф", "росії", "россии", "сша", "ukraine", "russia", "usa", "uk"}


def _first_name_tokens(name: str) -> set:
    """Слова з великої літери (ім'я / по батькові) — у нижньому регістрі."""
    return {w.lower() for w in re.findall(r"\b[A-ZА-ЯІЇЄҐ][a-zа-яіїєґ'’]+", name)}


def strict_same_name(a: str, b: str) -> bool:
    if a.strip().lower() == b.strip().lower() or _alias(a, b):
        return True
    for tr in (False, True):
        ta, tb = _core_tokens(a, tr), _core_tokens(b, tr)
        if not ta or not tb:
            continue
        short, long_, long_name = (ta, tb, b) if len(ta) <= len(tb) else (tb, ta, a)
        rest = list(long_)
        for x in short:  # кожне слово коротшої назви — та сама лексема в довшій
            j = next((j for j, y in enumerate(rest) if _tok_eq(x, y)), None)
            if j is None:
                break
            rest.pop(j)
        else:
            # розширення сутності: лишок — лише уточнення країни або одне ім'я з великої літери до прізвища
            caps = _first_name_tokens(long_name) if not tr else set()
            if all(t in QUALIFIERS for t in rest) or (len(short) == 1 and len(rest) == 1 and rest[0] in caps):
                return True
    return False


def in_denominator(o: dict) -> bool:
    return o["content_type"] in ("informational", "alert") and o["promotional"] != "ad"


def norm_domain(d: str) -> str:
    d = d.lower().strip().removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")
    return d


def fields(o: dict) -> dict:
    """Поля, за якими визначається розбіжність."""
    direct = [s for s in o["sources"] if s["level"] == "direct"]
    return {
        "content_type": o["content_type"],
        "promotional": o["promotional"],
        "has_explicit_source": bool(o["has_explicit_source"]),
        "attribution_method": o["attribution_method"],
        "direct_sources": direct,
        "other_sources": [s for s in o["sources"] if s["level"] != "direct"],
        "destinations": [{"domain": norm_domain(d["domain"]), "platform_type": d["platform_type"]} for d in o["destinations"]],
    }


def same_sources(a: list, b: list, with_type=True, strict=False) -> bool:
    if len(a) != len(b):
        return False
    used = set()
    if strict:  # суворо: назва за strict_same_name, однакові тип і specificity, без «узагальнених» збігів
        ok = lambda s, t: (strict_same_name(s["name"], t["name"]) and s.get("specificity") == t.get("specificity")
                           and (not with_type or s["type"] == t["type"]))
    else:
        ok = lambda s, t: ((same_name(s["name"], t["name"]) or (s["type"] == t["type"] and s.get("specificity") in ("generic", "anonymous")
                                                               and t.get("specificity") in ("generic", "anonymous")))
                           and (not with_type or s["type"] == t["type"]))
    for s in a:
        j = next((j for j, t in enumerate(b) if j not in used and ok(s, t)), None)
        if j is None:
            return False
        used.add(j)
    return True


def same_dest(a: list, b: list) -> bool:
    key = lambda L: sorted((d["domain"].split("/")[0] if not d["domain"].startswith("t.me") else d["domain"], d["platform_type"]) for d in L)
    return key(a) == key(b)


def diff_fields(fa: dict, fb: dict, strict=False) -> set:
    d = {k for k in ("content_type", "promotional", "has_explicit_source", "attribution_method") if fa[k] != fb[k]}
    if not same_sources(fa["direct_sources"], fb["direct_sources"], strict=strict):
        d.add("direct_sources")
    if not same_sources(fa["other_sources"], fb["other_sources"], with_type=False, strict=strict):
        d.add("other_sources")
    if not same_dest(fa["destinations"], fb["destinations"]):
        d.add("destinations")
    return d


def load(coder: str) -> dict:
    p = LLM / f"{coder}_blind_raw.jsonl" if coder != "algorithm" else LLM / "algorithm_raw.jsonl"
    return {json.loads(l)["item_id"]: json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()}


# ---------- черга для перевірки ----------
def queue() -> None:
    from src.v3.blind_io import items
    HUMAN.mkdir(parents=True, exist_ok=True)
    key = pd.read_csv(ROOT / "validation" / "v3_validation_key.csv", dtype=str).fillna("").set_index("item_id")
    texts = items().set_index("item_id")
    ans = {c: load(c) for c in CODERS}
    allids = set.intersection(*[set(a) for a in ans.values()])
    # витік: V0001–V0100 виключено з фінальних метрик (замінено R0001–R0067), src/v3/replacement.py
    leak = set(key.index[key.get("leak_excluded", pd.Series(False, index=key.index)).astype(str).eq("True")])
    ids = sorted(allids - leak)
    missing = set(key.index) - leak - allids
    if missing:
        print(f"УВАГА: немає відповідей усіх кодерів для {len(missing)}: {sorted(missing)[:8]}")
    rows = []
    for i in ids:
        F = {c: fields(ans[c][i]) for c in CODERS}
        # одностайність — лише за суворим зіставленням назв (strict_same_name)
        diffs = set().union(*[diff_fields(F[a], F[b], strict=True)
                              for a, b in (("algorithm", "claude"), ("algorithm", "chatgpt"), ("claude", "chatgpt"))])
        flag8 = bool(ans["algorithm"][i].get("flag8_hidden_invite"))
        if diffs:
            stratum = "D_disagreement"
        elif flag8:  # ⚑8 ухвалено після сліпого кодування LLM → усі такі випадки до перевірки (100%)
            stratum = "F_flag8"
        elif F["algorithm"]["has_explicit_source"]:
            a = ans["algorithm"][i]
            special = (a["attribution_method"] in ("hyperlink", "both") or len(F["algorithm"]["direct_sources"]) >= 2
                       or F["algorithm"]["other_sources"] or any(s["type"] in RARE_TYPES for s in a["sources"]))
            stratum = "U_yes_special" if special else "U_yes_plain"
        else:
            stratum = "U_no"
        rows.append({"item_id": i, "stratum": stratum, "diff_fields": sorted(diffs), "subsample": key.loc[i, "subsample"],
                     "period": key.loc[i, "period"], "channel": key.loc[i, "channel"], "flag8": flag8})
    df = pd.DataFrame(rows)
    rnd = random.Random(SEED)
    df["selected"] = df.stratum.isin(["D_disagreement", "F_flag8"])
    for st, n in AUDIT.items():
        pool = df[df.stratum == st].item_id.tolist()
        pick = set(rnd.sample(pool, min(n, len(pool))))
        df.loc[df.item_id.isin(pick), "selected"] = True
    sizes = df.stratum.value_counts().to_dict()
    nsel = df[df.selected].stratum.value_counts().to_dict()
    df["sampling_prob"] = df.stratum.map(lambda s: nsel.get(s, 0) / sizes[s])
    df["weight"] = df.apply(lambda r: (1 / r.sampling_prob) if r.selected and r.sampling_prob else 0.0, axis=1)

    queue_items, prov = [], []
    sel = df[df.selected].sample(frac=1, random_state=SEED)  # змішати розбіжності й перевірку збігів
    sel = pd.concat([sel[sel.subsample == "A_random"], sel[sel.subsample != "A_random"]])  # спершу випадкова частина A
    for r in sel.itertuples():
        variants = []  # унікальні варіанти відповіді
        for c in CODERS:
            f = fields(ans[c][r.item_id])
            for v in variants:
                if not diff_fields(v["f"], f, strict=True):
                    v["by"].append(c)
                    break
            else:
                variants.append({"f": f, "by": [c], "raw": ans[c][r.item_id]})
        rnd.shuffle(variants)
        letters = "ABC"
        shown = sorted(set(r.diff_fields) | ({"direct_sources"} if any(v["f"]["has_explicit_source"] for v in variants) else set()))
        text = texts.loc[r.item_id, "text"]
        queue_items.append({
            "item_id": r.item_id, "part": r.subsample[0], "channel": key.loc[r.item_id, "channel"], "date": key.loc[r.item_id, "date"], "text": text,
            "fields": shown,
            "variants": [{"id": letters[k], **{fk: v["f"][fk] for fk in ("content_type", "promotional", "has_explicit_source",
                                                                      "attribution_method", "direct_sources", "other_sources", "destinations")}}
                         for k, v in enumerate(variants)],
        })
        for k, v in enumerate(variants):
            prov.append({"item_id": r.item_id, "variant": letters[k], "coders": "+".join(v["by"])})
    (HUMAN / "review_queue.json").write_text(json.dumps(queue_items, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame(prov).to_csv(HUMAN / "provenance.csv", index=False)
    df["text_sha1"] = df.item_id.map(lambda i: hashlib.sha1(texts.loc[i, "text"].encode()).hexdigest())
    df.to_csv(HUMAN / "strata.csv", index=False)
    print("страти:", sizes)
    print("до перевірки:", nsel, "усього", int(df.selected.sum()))
    print("поля розбіжностей:", Counter(f for d in df.diff_fields for f in d).most_common())


if __name__ == "__main__":
    {"algorithm": algorithm, "queue": queue}[sys.argv[1]]()
