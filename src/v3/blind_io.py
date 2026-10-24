"""Сліпі вхідні пакети для двох LLM-кодерів і перевірка їхніх відповідей (план валідації, docs/VALIDATION_PLAN.md).

  python -m src.v3.blind_io make                       → validation/blind/batch_01.jsonl … batch_15.jsonl
  python -m src.v3.blind_io check <coder> <файл.jsonl>  → перевірка формату пакета відповідей
  python -m src.v3.blind_io merge <coder>              → validation/llm/<coder>_blind_raw.jsonl (усі пакети)

У пакетах — лише item_id, channel (потрібен для правила самопосилань) і текст. Жодних полів від алгоритму.
Зміст відповідей LLM не виправляється; дозволена лише синтаксична нормалізація (регістр, пробіли, true/false).
"""
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BLIND = ROOT / "validation" / "blind"
LLM = ROOT / "validation" / "llm"
BATCH = 100

CONTENT = {"informational", "alert", "technical"}
PROMO = {"no", "ad", "self_promo"}
METHOD = {"textual", "hyperlink", "both", "none"}
TYPES = {"ua_media", "foreign_media", "russian_media", "ua_official", "foreign_official", "russian_official", "politician",
         "expert", "company_organization", "telegram", "social", "unnamed_media", "eyewitness", "anonymous", "person_other", "other"}
SPEC = {"named", "generic", "anonymous"}
LEVEL = {"direct", "embedded", "intermediary"}
SMETHOD = {"text", "link"}
PLATFORM = {"ua_media_site", "foreign_media_site", "russian_media_site", "official_site", "foreign_official_site",
            "social_platform", "telegram_channel", "other_site"}
RELATION = {"same_actor", "intermediary", "platform_hosting_actor", "unrelated", "unclear"}


def items() -> pd.DataFrame:
    b = pd.read_csv(ROOT / "validation" / "v3_validation_blind.csv", dtype=str).fillna("")
    return b[["item_id", "channel", "msg_id", "text"]]


def make() -> None:
    BLIND.mkdir(parents=True, exist_ok=True)
    df = items()
    manifest = []
    for k in range(0, len(df), BATCH):
        part = df.iloc[k:k + BATCH]
        name = f"batch_{k // BATCH + 1:02d}.jsonl"
        with open(BLIND / name, "w", encoding="utf-8") as f:
            for r in part.itertuples():
                f.write(json.dumps({"item_id": r.item_id, "channel": r.channel, "text": r.text}, ensure_ascii=False) + "\n")
        manifest.append({"batch": name, "first": part.item_id.iloc[0], "last": part.item_id.iloc[-1], "n": len(part),
                         "sha256": hashlib.sha256((BLIND / name).read_bytes()).hexdigest()})
    pd.DataFrame(manifest).to_csv(BLIND / "MANIFEST.csv", index=False)
    print(f"{len(manifest)} пакетів, {len(df)} повідомлень → {BLIND}")


def _norm(o: dict) -> dict:
    """Лише синтаксис: регістр/пробіли, 'true'/'false' → bool, число → int."""
    low = lambda v: str(v).strip().lower() if v is not None else ""
    b = lambda v: v if isinstance(v, bool) else low(v) in ("true", "yes", "1", "так")
    out = {"item_id": str(o.get("item_id", "")).strip(), "content_type": low(o.get("content_type")),
           "promotional": low(o.get("promotional")), "has_explicit_source": b(o.get("has_explicit_source")),
           "attribution_method": low(o.get("attribution_method")), "has_nested_source": b(o.get("has_nested_source")),
           "comment": str(o.get("comment", "") or "")}
    try:
        out["n_direct_sources"] = int(o.get("n_direct_sources", 0))
    except (TypeError, ValueError):
        out["n_direct_sources"] = -1
    out["sources"] = [{"name": str(s.get("name", "")).strip(), "type": low(s.get("type")), "specificity": low(s.get("specificity")),
                       "level": low(s.get("level")) or "direct", "method": low(s.get("method")) or "text"}
                      for s in (o.get("sources") or []) if isinstance(s, dict)]
    out["destinations"] = [{"domain": low(d.get("domain")), "platform_type": low(d.get("platform_type")), "relation": low(d.get("relation"))}
                           for d in (o.get("destinations") or []) if isinstance(d, dict)]
    return out


def check(path: Path, expected_ids=None):
    """Повертає (нормалізовані записи, список проблем)."""
    recs, problems = [], []
    for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip().strip(",")
        if not line or line.startswith("```"):
            continue
        try:
            recs.append(_norm(json.loads(line)))
        except json.JSONDecodeError as e:
            problems.append(f"рядок {i}: зіпсований JSON ({e.msg})")
    ids = [r["item_id"] for r in recs]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        problems.append(f"дублікати item_id: {sorted(dup)[:10]}")
    if expected_ids is not None:
        miss, extra = set(expected_ids) - set(ids), set(ids) - set(expected_ids)
        if miss:
            problems.append(f"бракує {len(miss)}: {sorted(miss)[:10]}")
        if extra:
            problems.append(f"зайві {len(extra)}: {sorted(extra)[:10]}")
    for r in recs:
        bad = []
        if r["content_type"] not in CONTENT: bad.append(f"content_type={r['content_type']}")
        if r["promotional"] not in PROMO: bad.append(f"promotional={r['promotional']}")
        if r["attribution_method"] not in METHOD: bad.append(f"attribution_method={r['attribution_method']}")
        if r["n_direct_sources"] < 0: bad.append("n_direct_sources")
        if r["has_explicit_source"] != (r["attribution_method"] != "none"): bad.append("has_explicit_source ≠ attribution_method")
        for s in r["sources"]:
            if not s["name"]: bad.append("порожня назва джерела")
            if s["type"] not in TYPES: bad.append(f"type={s['type']}")
            if s["specificity"] not in SPEC: bad.append(f"specificity={s['specificity']}")
            if s["level"] not in LEVEL: bad.append(f"level={s['level']}")
            if s["method"] not in SMETHOD: bad.append(f"method={s['method']}")
        for d in r["destinations"]:
            if d["platform_type"] not in PLATFORM: bad.append(f"platform_type={d['platform_type']}")
            if d["relation"] not in RELATION: bad.append(f"relation={d['relation']}")
        if bad:
            problems.append(f"{r['item_id']}: {'; '.join(sorted(set(bad)))}")
    return recs, problems


def batch_ids(name: str) -> list:
    return [json.loads(l)["item_id"] for l in (BLIND / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def merge(coder: str) -> None:
    LLM.mkdir(parents=True, exist_ok=True)
    allrecs, allprob = [], []
    for b in sorted(BLIND.glob("batch_*.jsonl")):
        out = LLM / coder / b.name
        if not out.exists():
            allprob.append(f"{b.name}: немає відповіді")
            continue
        recs, prob = check(out, batch_ids(b.name))
        allrecs += recs
        allprob += [f"{b.name}: {p}" for p in prob]
    with open(LLM / f"{coder}_blind_raw.jsonl", "w", encoding="utf-8") as f:
        for r in allrecs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{coder}: {len(allrecs)} записів; проблем: {len(allprob)}")
    for p in allprob[:40]:
        print("  -", p)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "make":
        make()
    elif cmd == "check":
        p = Path(sys.argv[3])
        recs, prob = check(p, batch_ids(p.name) if (BLIND / p.name).exists() else None)
        print(f"{len(recs)} записів; проблем: {len(prob)}")
        for x in prob:
            print("  -", x)
    elif cmd == "merge":
        merge(sys.argv[2])
