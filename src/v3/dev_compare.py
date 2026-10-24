"""Навчальна вибірка (НЕ валідаційна): алгоритм vs сліпий Claude — для пошуку класів помилок.
python -m src.v3.dev_compare → validation/dev/algorithm.jsonl, validation/dev/disagreements.csv, зведення в консоль."""
import json, sys
from collections import Counter
from pathlib import Path
import pandas as pd
from src.v2.detect import Detector, ROOT
from src.v3.attribution import Attribution
from src.v3.blind_io import _norm
from src.v3.adjudication import fields, same_sources, in_denominator

DEV = ROOT / "validation" / "dev"

def run_algorithm():
    at, det = Attribution(), Detector()
    items = pd.read_csv(DEV / "dev_items.csv", dtype=str)
    out = {}
    for ch, g in items.groupby("channel"):
        msgs = json.loads((ROOT / "data" / "raw" / f"telegram_{ch}.json").read_text(encoding="utf-8"))
        b = det.boilerplate_lines(msgs); by = {str(m["id"]): m for m in msgs}
        for r in g.itertuples():
            a = at.analyze(by[r.msg_id], ch, b)
            out[r.item_id] = {"item_id": r.item_id, "content_type": a["content_type"], "promotional": a["promotional"],
                "has_explicit_source": a["has_explicit_source"], "attribution_method": a["attribution_method"],
                "sources": [{"name": s["name"], "type": s["type"], "specificity": s["specificity"], "level": s.get("source_level", "direct"),
                             "method": "link" if s.get("actor_inferred_from_link") else "text", "pattern": s["pattern"]} for s in a["attributed_sources"]],
                "destinations": [{"domain": d["domain"] if d["domain"] != "t.me" else "t.me/" + d["entity"].lstrip("@"), "platform_type": d["platform_type"]} for d in a["linked_destinations"]]}
    return out

def main():
    alg = run_algorithm()
    cl = {}
    for f in sorted((DEV / "claude").glob("dev_*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            if l.strip():
                o = _norm(json.loads(l)); cl[o["item_id"]] = o
    items = pd.read_csv(DEV / "dev_items.csv", dtype=str).set_index("item_id")
    rows, c = [], Counter()
    for i in sorted(cl):
        a, o = alg[i], cl[i]; fa, fo = fields(a), fields(o)
        cls = []
        if fa["has_explicit_source"] and not fo["has_explicit_source"]: cls.append("FP_source")
        if fo["has_explicit_source"] and not fa["has_explicit_source"]: cls.append("FN_source")
        if in_denominator(a) != in_denominator(o): cls.append("denominator")
        if fa["has_explicit_source"] and fo["has_explicit_source"]:
            if not same_sources(fa["direct_sources"], fo["direct_sources"], with_type=False): cls.append("source_set")
            elif not same_sources(fa["direct_sources"], fo["direct_sources"]): cls.append("type")
        c.update(cls)
        if cls:
            rows.append({"item_id": i, "classes": ";".join(cls), "channel": items.loc[i, "channel"],
                         "alg": " | ".join(f"{s['name']} [{s['type']},{s['pattern']},{s['level']}]" for s in a["sources"]),
                         "claude": " | ".join(f"{s['name']} [{s['type']},{s['level']}]" for s in o["sources"]),
                         "alg_ct": f"{a['content_type']}/{a['promotional']}", "cl_ct": f"{o['content_type']}/{o['promotional']}",
                         "text": items.loc[i, "text"][:500].replace("\n", " / ")})
    pd.DataFrame(rows).to_csv(DEV / "disagreements.csv", index=False, encoding="utf-8-sig")
    with open(DEV / "algorithm.jsonl", "w", encoding="utf-8") as f:
        for v in alg.values(): f.write(json.dumps(v, ensure_ascii=False) + "\n")
    n = len(cl)
    print(f"n={n}; будь-яка ключова розбіжність: {len(rows)} ({100*len(rows)/n:.0f}%)", dict(c))
    print("алгоритм джерело:", sum(alg[i]["has_explicit_source"] for i in cl), "Claude:", sum(cl[i]["has_explicit_source"] for i in cl))

if __name__ == "__main__":
    main()
