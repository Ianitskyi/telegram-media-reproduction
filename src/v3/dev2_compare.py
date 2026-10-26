"""Свіжа навчальна вибірка dev2 (НЕ валідаційна): алгоритм vs консенсус двох сліпих LLM (Claude + ChatGPT).
Консенсус = обидва LLM збігаються за ключовими полями; на ньому шукаємо класи помилок алгоритму.
python -m src.v3.dev2_compare → validation/dev2/disagreements.csv + зведення."""
import json
from collections import Counter
from pathlib import Path
import pandas as pd
from src.v2.detect import Detector, ROOT
from src.v3.attribution import Attribution
from src.v3.blind_io import _norm
from src.v3.adjudication import fields, same_sources, in_denominator

import os
D = ROOT / "validation" / os.environ.get("DEV2", "dev2a")

def key_diff(a, b):
    fa, fb = fields(a), fields(b)
    out = []
    if fa["has_explicit_source"] != fb["has_explicit_source"]:
        out.append("FP_source" if fa["has_explicit_source"] else "FN_source")
    if in_denominator(a) != in_denominator(b): out.append("denominator")
    if fa["has_explicit_source"] and fb["has_explicit_source"]:
        if not same_sources(fa["direct_sources"], fb["direct_sources"], with_type=False): out.append("source_set")
        elif not same_sources(fa["direct_sources"], fb["direct_sources"]): out.append("type")
    return out

def load_coder(sub):
    out = {}
    for f in sorted((D / sub).glob("*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            if l.strip().startswith("{"):
                o = _norm(json.loads(l)); out[o["item_id"]] = o
    return out

def main():
    at, det = Attribution(), Detector()
    items = pd.read_csv(D / "dev2_items.csv", dtype=str)
    alg = {}
    for ch, g in items.groupby("channel"):
        msgs = json.loads((ROOT / "data" / "raw" / f"telegram_{ch}.json").read_text(encoding="utf-8"))
        b = det.boilerplate_lines(msgs); by = {str(m["id"]): m for m in msgs}
        for r in g.itertuples():
            a = at.analyze(by[r.msg_id], ch, b)
            alg[r.item_id] = {"item_id": r.item_id, "content_type": a["content_type"], "promotional": a["promotional"],
                "has_explicit_source": a["has_explicit_source"], "attribution_method": a["attribution_method"],
                "sources": [{"name": s["name"], "type": s["type"], "specificity": s["specificity"], "level": s.get("source_level", "direct"),
                             "method": "link" if s.get("actor_inferred_from_link") else "text", "pattern": s["pattern"]} for s in a["attributed_sources"]],
                "destinations": [{"domain": d["domain"], "platform_type": d["platform_type"]} for d in a["linked_destinations"]]}
    cl, gp = load_coder("claude"), load_coder("chatgpt")
    txt = items.set_index("item_id")
    ids = sorted(set(cl) & set(gp))
    cons = [i for i in ids if not key_diff(cl[i], gp[i])]
    c, rows = Counter(), []
    for i in cons:
        d = key_diff(alg[i], cl[i]); c.update(d)
        if d:
            rows.append({"item_id": i, "classes": ";".join(d),
                         "alg": " | ".join(f"{s['name']} [{s['type']},{s['pattern']},{s['level']}]" for s in alg[i]["sources"]),
                         "llm": " | ".join(f"{s['name']} [{s['type']},{s['level']}]" for s in cl[i]["sources"]),
                         "alg_ct": f"{alg[i]['content_type']}/{alg[i]['promotional']}", "llm_ct": f"{cl[i]['content_type']}/{cl[i]['promotional']}",
                         "text": txt.loc[i, "text"][:450].replace("\n", " / ")})
    pd.DataFrame(rows).to_csv(D / "disagreements.csv", index=False, encoding="utf-8-sig")
    llm_dis = len(ids) - len(cons)
    a_cl = sum(bool(key_diff(alg[i], cl[i])) for i in ids); a_gp = sum(bool(key_diff(alg[i], gp[i])) for i in ids)
    print(f"n={len(ids)}; Claude↔ChatGPT розбіжні: {llm_dis} ({100*llm_dis/len(ids):.0f}%); алгоритм↔Claude {a_cl} ({100*a_cl/len(ids):.0f}%), алгоритм↔ChatGPT {a_gp} ({100*a_gp/len(ids):.0f}%)")
    print(f"на консенсусі LLM ({len(cons)}): алгоритм помиляється в {len(rows)} ({100*len(rows)/len(cons):.0f}%)", dict(c))

if __name__ == "__main__":
    main()
