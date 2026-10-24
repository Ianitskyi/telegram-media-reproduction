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
            out.append({"item_id": r.item_id, "content_type": a["content_type"], "promotional": a["promotional"],
                        "has_explicit_source": a["has_explicit_source"], "attribution_method": a["attribution_method"],
                        "n_direct_sources": a["n_direct_sources"], "has_nested_source": a["has_embedded_source"],
                        "sources": [{"name": s["name"], "type": s["type"], "specificity": s["specificity"],
                                     "level": s.get("source_level", "direct"),
                                     "method": "link" if s.get("actor_inferred_from_link") else "text"} for s in a["attributed_sources"]],
                        "destinations": [{"domain": d["domain"] if d["domain"] != "t.me" else "t.me/" + d["entity"].lstrip("@"),
                                          "platform_type": d["platform_type"], "relation": ""} for d in a["linked_destinations"]],
                        "comment": "", "in_primary_denominator": a["in_primary_denominator"]})
    out.sort(key=lambda x: x["item_id"])
    with open(LLM / "algorithm_raw.jsonl", "w", encoding="utf-8") as f:
        for o in out:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print(f"algorithm: {len(out)} записів → {LLM / 'algorithm_raw.jsonl'}")


# ---------- канонічна форма відповіді ----------
def stems(name: str) -> list:
    n = re.sub(r"[«»\"“”'’ʼ().,:;!?\-—–@]", " ", name.lower().replace("ё", "е"))
    toks = [t for t in n.split() if t not in STOP]
    core = [t for t in toks if not ROLE.match(t)] or toks
    return [t[:5] for t in core]


def same_name(a: str, b: str) -> bool:
    sa, sb = stems(a), stems(b)
    if not sa or not sb:
        return False
    short, long_ = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    return set(short) <= set(long_)


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


def same_sources(a: list, b: list, with_type=True) -> bool:
    if len(a) != len(b):
        return False
    used = set()
    for s in a:
        j = next((j for j, t in enumerate(b) if j not in used and same_name(s["name"], t["name"])
                  and (not with_type or s["type"] == t["type"])), None)
        if j is None:
            return False
        used.add(j)
    return True


def same_dest(a: list, b: list) -> bool:
    key = lambda L: sorted((d["domain"].split("/")[0] if not d["domain"].startswith("t.me") else d["domain"], d["platform_type"]) for d in L)
    return key(a) == key(b)


def diff_fields(fa: dict, fb: dict) -> set:
    d = {k for k in ("content_type", "promotional", "has_explicit_source", "attribution_method") if fa[k] != fb[k]}
    if not same_sources(fa["direct_sources"], fb["direct_sources"]):
        d.add("direct_sources")
    if not same_sources(fa["other_sources"], fb["other_sources"], with_type=False):
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
    ids = sorted(set.intersection(*[set(a) for a in ans.values()]))
    rows = []
    for i in ids:
        F = {c: fields(ans[c][i]) for c in CODERS}
        diffs = set().union(*[diff_fields(F[a], F[b]) for a, b in (("algorithm", "claude"), ("algorithm", "chatgpt"), ("claude", "chatgpt"))])
        if diffs:
            stratum = "D_disagreement"
        elif F["algorithm"]["has_explicit_source"]:
            a = ans["algorithm"][i]
            special = (a["attribution_method"] in ("hyperlink", "both") or len(F["algorithm"]["direct_sources"]) >= 2
                       or F["algorithm"]["other_sources"] or any(s["type"] in RARE_TYPES for s in a["sources"]))
            stratum = "U_yes_special" if special else "U_yes_plain"
        else:
            stratum = "U_no"
        rows.append({"item_id": i, "stratum": stratum, "diff_fields": sorted(diffs), "subsample": key.loc[i, "subsample"]})
    df = pd.DataFrame(rows)
    rnd = random.Random(SEED)
    df["selected"] = df.stratum.eq("D_disagreement")
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
    for r in sel.itertuples():
        variants = []  # унікальні варіанти відповіді
        for c in CODERS:
            f = fields(ans[c][r.item_id])
            for v in variants:
                if not diff_fields(v["f"], f):
                    v["by"].append(c)
                    break
            else:
                variants.append({"f": f, "by": [c], "raw": ans[c][r.item_id]})
        rnd.shuffle(variants)
        letters = "ABC"
        shown = sorted(set(r.diff_fields) | ({"direct_sources"} if any(v["f"]["has_explicit_source"] for v in variants) else set()))
        text = texts.loc[r.item_id, "text"]
        queue_items.append({
            "item_id": r.item_id, "channel": key.loc[r.item_id, "channel"], "date": key.loc[r.item_id, "date"], "text": text,
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
