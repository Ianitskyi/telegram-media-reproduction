"""Звіт валідації за зваженою людською перевіркою (human-verified reference set; docs/VALIDATION_PLAN.md).

Вхід:
  validation/llm/{algorithm,claude,chatgpt}_blind_raw.jsonl (algorithm — algorithm_raw.jsonl)
  validation/human/strata.csv, review_queue.json, provenance.csv     ← python -m src.v3.adjudication queue
  validation/human/andrii_reviews.jsonl                               ← рішення Андрія з інтерфейсу
Запуск:  python -m src.v3.validation_report
Вихід:   results/v3/VALIDATION.md

Еталон для перевіреного повідомлення = варіант, обраний Андрієм (або його власне виправлення).
Ваги: weight = N_страти / n_перевірених_у_страті, окремо в частині A (випадкова) і B (збагачена позитивами).
Recall, поширеність і загальна precision — на A; B — precision за механізмами (textual / hyperlink / both-multi).
95% CI — стратифікований бутстреп (1 000 повторів). Будь-яка обов'язкова метрика без даних → NO-GO;
неповна перевірка (не всі відібрані повідомлення мають рішення) → помилка.
"""
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from src.v3.adjudication import CODERS, HUMAN, fields, in_denominator, load, same_name

ROOT = Path(__file__).resolve().parents[2]
B_REPS, SEED = 1000, 20261025
THRESHOLDS = [  # (назва, поріг, поріг нижньої межі CI або None)
    ("has_explicit_source precision (A)", 0.95, 0.90),
    ("has_explicit_source recall (A)", 0.90, 0.85),
    ("actor precision (A)", 0.90, None),
    ("actor recall (A)", 0.90, None),
    ("source_type macro-F1 end-to-end (A)", 0.85, None),
    ("denominator accuracy (A)", 0.95, None),
    ("substantive recall (A)", 0.98, None),
    ("destination type accuracy", 0.95, None),
]
SOFT_CI = {"actor precision (A)": 0.85, "actor recall (A)": 0.85}  # бажано, не блокує
MAX_UNANIMOUS_ERR = 0.05
MIN_N_TYPE = 10


class ReviewIncomplete(Exception):
    pass


def reference(item: dict, review: dict) -> dict:
    """Еталонні поля з рішення Андрія."""
    if review.get("choice") in ("A", "B", "C"):
        v = next(v for v in item["variants"] if v["id"] == review["choice"])
        ref = {k: v[k] for k in ("content_type", "promotional", "has_explicit_source", "attribution_method",
                                 "direct_sources", "other_sources", "destinations")}
    else:
        ref = dict(review.get("edited") or {})
        base = item["variants"][0]
        for k in ("content_type", "promotional", "has_explicit_source", "attribution_method", "direct_sources",
                  "other_sources", "destinations"):
            ref.setdefault(k, base[k])
    if review.get("q1") in ("yes", "no"):  # незалежна відповідь на «Є джерело?» має пріоритет
        ref["has_explicit_source"] = review["q1"] == "yes"
        if not ref["has_explicit_source"]:
            ref["direct_sources"], ref["attribution_method"] = [], "none"
    return ref


def match(gold, pred):
    used, pairs = set(), []
    for g in gold:
        j = next((j for j, p in enumerate(pred) if j not in used and same_name(g["name"], p["name"])), None)
        if j is not None:
            used.add(j)
            pairs.append((g, pred[j]))
    return pairs


def item_metrics(pred: dict, ref: dict) -> dict:
    """Лічильники для одного повідомлення (зважуються пізніше)."""
    m = Counter()
    ps, rs = bool(pred["has_explicit_source"]), bool(ref["has_explicit_source"])
    m["src_tp"], m["src_fp"], m["src_fn"], m["src_tn"] = ps and rs, ps and not rs, rs and not ps, not ps and not rs
    pd_, rd = in_denominator(pred), in_denominator(ref)
    m["den_ok"], m["den_n"] = pd_ == rd, 1
    m["subst_hit"], m["subst_n"] = pd_ and rd, rd
    m["method_ok"] = pred["attribution_method"] == ref["attribution_method"]
    m["content_ok"] = pred["content_type"] == ref["content_type"]
    m["nested_ok"] = bool(pred["other_sources"]) == bool(ref["other_sources"])
    pairs = match(ref["direct_sources"], pred["direct_sources"])
    m["act_tp"], m["act_fp"], m["act_fn"] = len(pairs), len(pred["direct_sources"]) - len(pairs), len(ref["direct_sources"]) - len(pairs)
    m["type_ok"], m["type_n"] = sum(g["type"] == p["type"] for g, p in pairs), len(pairs)
    mg, mp = {id(g) for g, _ in pairs}, {id(p) for _, p in pairs}
    for g, p in pairs:
        if g["type"] == p["type"]:
            m[f"t_tp|{g['type']}"] += 1
        else:
            m[f"t_fp|{p['type']}"] += 1; m[f"t_fn|{g['type']}"] += 1
    for g in ref["direct_sources"]:
        if id(g) not in mg:
            m[f"t_fn|{g['type']}"] += 1
        m[f"t_n|{g['type']}"] += 1
    for p in pred["direct_sources"]:
        if id(p) not in mp:
            m[f"t_fp|{p['type']}"] += 1
    rdom = {d["domain"]: d["platform_type"] for d in ref["destinations"]}
    pdom = {d["domain"]: d["platform_type"] for d in pred["destinations"]}
    m["dest_ok"] = sum(1 for d, t in rdom.items() if d in pdom and pdom[d] == t)
    m["dest_n"] = sum(1 for d in rdom if d in pdom)
    m["dest_tp"], m["dest_fp"], m["dest_fn"] = len(set(rdom) & set(pdom)), len(set(pdom) - set(rdom)), len(set(rdom) - set(pdom))
    return m


def ratio(a, b):
    return a / b if b else float("nan")


def summarize(rows) -> dict:
    """rows: [(weight, Counter, subsample)] → метрики."""
    S = defaultdict(float)
    for w, m, _ in rows:
        for k, v in m.items():
            S[k] += w * float(v)
    out = {
        "has_explicit_source precision (A)": ratio(S["src_tp"], S["src_tp"] + S["src_fp"]),
        "has_explicit_source recall (A)": ratio(S["src_tp"], S["src_tp"] + S["src_fn"]),
        "actor precision (A)": ratio(S["act_tp"], S["act_tp"] + S["act_fp"]),
        "actor recall (A)": ratio(S["act_tp"], S["act_tp"] + S["act_fn"]),
        "denominator accuracy (A)": ratio(S["den_ok"], S["den_n"]),
        "substantive recall (A)": ratio(S["subst_hit"], S["subst_n"]),
        "prevalence: reference (A)": ratio(S["src_tp"] + S["src_fn"], S["src_tp"] + S["src_fn"] + S["src_fp"] + S["src_tn"]),
        "prevalence: algorithm (A)": ratio(S["src_tp"] + S["src_fp"], S["src_tp"] + S["src_fn"] + S["src_fp"] + S["src_tn"]),
        "attribution method accuracy (A)": ratio(S["method_ok"], S["den_n"]),
        "content type accuracy (A)": ratio(S["content_ok"], S["den_n"]),
        "nested source accuracy (A)": ratio(S["nested_ok"], S["den_n"]),
        "source_type conditional accuracy (A)": ratio(S["type_ok"], S["type_n"]),
    }
    types = {k.split("|")[1] for k in S if k.startswith("t_")}
    per = {}
    for t in types:
        tp, fp, fn = S[f"t_tp|{t}"], S[f"t_fp|{t}"], S[f"t_fn|{t}"]
        p, r = ratio(tp, tp + fp), ratio(tp, tp + fn)
        per[t] = (2 * p * r / (p + r) if p == p and r == r and p + r else 0.0, S[f"t_n|{t}"])
    main = [f for f, n in per.values() if n >= MIN_N_TYPE]
    out["source_type macro-F1 end-to-end (A)"] = sum(main) / len(main) if main else float("nan")
    out["_per_type"] = per
    out["_dest"] = (ratio(S["dest_ok"], S["dest_n"]), ratio(S["dest_tp"], S["dest_tp"] + S["dest_fp"]),
                    ratio(S["dest_tp"], S["dest_tp"] + S["dest_fn"]))
    return out


def kappa(a: list, b: list) -> float:
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 20:
        return float("nan")
    po = sum(x == y for x, y in pairs) / len(pairs)
    ca, cb = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / len(pairs) ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def main() -> None:
    strata = pd.read_csv(HUMAN / "strata.csv", dtype={"item_id": str})
    queue = {q["item_id"]: q for q in json.loads((HUMAN / "review_queue.json").read_text(encoding="utf-8"))}
    reviews = {}
    for line in (HUMAN / "andrii_reviews.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            reviews[r["item_id"]] = r  # останнє рішення перекриває попереднє
    todo = [i for i in queue if i not in reviews or reviews[i].get("choice") in (None, "", "skip")]
    if todo:
        raise ReviewIncomplete(f"перевірку не завершено: {len(todo)} із {len(queue)} без рішення (напр. {', '.join(todo[:8])})")
    unsure = [i for i, r in reviews.items() if r.get("choice") == "unsure" or r.get("q1") == "unsure"]
    ans = {c: load(c) for c in CODERS}

    # ваги окремо в частинах A і B
    strata["part"] = strata.subsample.str[0]
    sel = strata[strata.selected.astype(str).str.lower() == "true"].copy()
    N = strata.groupby(["part", "stratum"]).size()
    n = sel[~sel.item_id.isin(unsure)].groupby(["part", "stratum"]).size()
    sel["w"] = sel.apply(lambda r: N[(r.part, r.stratum)] / n.get((r.part, r.stratum), float("nan")), axis=1)

    per_item = []
    for r in sel.itertuples():
        if r.item_id in unsure:
            continue
        ref = reference(queue[r.item_id], reviews[r.item_id])
        pred = fields(ans["algorithm"][r.item_id])
        per_item.append((r.w, item_metrics(pred, ref), r.subsample, r.stratum, r.item_id, ref))

    A = [(w, m, s) for w, m, s, *_ in per_item if s == "A_random"]
    res = summarize(A)
    # дестинації — на всій вибірці (класифікація типу на збігах доменів), зважено
    res["destination type accuracy"] = summarize([(w, m, s) for w, m, s, *_ in per_item])["_dest"][0]

    # бутстреп CI: перевибірка всередині кожної (частина × страта)
    rnd = random.Random(SEED)
    groups = defaultdict(list)
    for w, m, s, st, *_ in per_item:
        if s == "A_random":
            groups[st].append((w, m, s))
    boot = defaultdict(list)
    for _ in range(B_REPS):
        sample = [rnd.choice(g) for g in groups.values() for _ in g]
        b = summarize(sample)
        for k, v in b.items():
            if not k.startswith("_") and v == v:
                boot[k].append(v)
    ci = {k: (sorted(v)[int(0.025 * len(v))], sorted(v)[int(0.975 * len(v)) - 1]) for k, v in boot.items() if v}

    # precision за механізмами (B)
    mech = {}
    for s in ("B_textual", "B_hyperlink", "B_both_multi"):
        rows = [(w, m, ss) for w, m, ss, *_ in per_item if ss == s]
        b = summarize(rows)
        mech[s] = (b["has_explicit_source precision (A)"], b["actor precision (A)"])

    # частка суттєвих помилок серед перевірених одностайних (одностайність = алгоритм = обидва LLM)
    uni = [(it, ref) for _, m, s, st, it, ref in per_item if st.startswith("U_")]
    def substantial(it, ref):
        p = fields(ans["algorithm"][it])
        return (p["has_explicit_source"] != ref["has_explicit_source"] or in_denominator(p) != in_denominator(ref)
                or len(match(ref["direct_sources"], p["direct_sources"])) != max(len(ref["direct_sources"]), len(p["direct_sources"])))
    uni_err = ratio(sum(substantial(it, ref) for it, ref in uni), len(uni))

    # κ
    ids = sorted(set.intersection(*[set(a) for a in ans.values()]))
    kap = {}
    for f, get in (("M1 content_type", lambda o: o["content_type"]), ("M3 has_explicit_source", lambda o: bool(o["has_explicit_source"])),
                   ("M4 attribution_method", lambda o: o["attribution_method"])):
        kap[f"Claude ↔ ChatGPT, {f} (усі)"] = kappa([get(ans["claude"][i]) for i in ids], [get(ans["chatgpt"][i]) for i in ids])
        rev = [it for _, _, _, _, it, _ in per_item]
        refs = {it: ref for *_, it, ref in per_item}
        for c in ("claude", "chatgpt"):
            kap[f"Андрій ↔ {c}, {f} (перевірені)"] = kappa([get(refs[i]) for i in rev], [get(ans[c][i]) for i in rev])

    # звіт
    f = lambda x: "—" if x != x else f"{x:.3f}"
    lines = ["# Валідація класифікатора атрибуції v3.2 (AI-assisted coding з людською перевіркою)", "",
             f"Вибірка: {len(strata)} повідомлень; страти: {strata.stratum.value_counts().to_dict()}.",
             f"Перевірено Андрієм: {len(per_item)} (розбіжності — усі; одностайні — вибірка); «не впевнений»: {len(unsure)}.", "",
             "| Обов'язковий показник | Значення | 95% CI | Поріг | Результат |", "|---|---|---|---|---|"]
    go = True
    for name, thr, lo in THRESHOLDS:
        v = res.get(name, float("nan")); c = ci.get(name)
        ok = v == v and v >= thr and (lo is None or (c is not None and c[0] >= lo))
        go &= ok
        lines.append(f"| {name} | {f(v)} | {f(c[0]) + '–' + f(c[1]) if c else '—'} | ≥ {thr}{' (CI ≥ ' + str(lo) + ')' if lo else ''} | "
                     f"{'✅' if ok else ('❌ немає даних' if v != v else '❌')} |")
    ok_u = uni_err == uni_err and uni_err <= MAX_UNANIMOUS_ERR
    go &= ok_u
    lines.append(f"| суттєві помилки серед перевірених одностайних | {f(uni_err)} | — | ≤ {MAX_UNANIMOUS_ERR} | {'✅' if ok_u else '❌'} |")
    lines += ["", "## Додатково (A, зважено)", ""] + [f"- {k}: {f(v)}{' (CI ' + f(ci[k][0]) + '–' + f(ci[k][1]) + ')' if k in ci else ''}"
                                                      for k, v in res.items() if not k.startswith("_") and k not in dict((t[0], 1) for t in THRESHOLDS)]
    d = summarize([(w, m, s) for w, m, s, *_ in per_item])["_dest"]
    lines += [f"- destination extraction precision / recall (уся вибірка): {f(d[1])} / {f(d[2])}"]
    lines += [f"- {k}: бажано CI ≥ {v} — {'так' if k in ci and ci[k][0] >= v else 'ні'}" for k, v in SOFT_CI.items()]
    lines += ["", "## Precision за механізмами (частина B)", "", "| Механізм | has_source precision | actor precision |", "|---|---|---|"]
    lines += [f"| {k} | {f(a)} | {f(b)} |" for k, (a, b) in mech.items()]
    lines += ["", f"## Тип джерела end-to-end, F1 за типами (A; у macro-F1 — типи з N ≥ {MIN_N_TYPE})", "", "| Тип | F1 | N (еталон, зважено) |", "|---|---|---|"]
    lines += [f"| {t} | {f(v)} | {n:.0f}{'' if n >= MIN_N_TYPE else ' (пошуковий)'} |" for t, (v, n) in sorted(res["_per_type"].items(), key=lambda x: -x[1][1])]
    lines += ["", "## Узгодженість (κ) — показник узгодженості, не точності", ""] + [f"- {k}: {f(v)}" for k, v in kap.items()]
    lines += ["", f"**Рішення:** {'GO — можна пропонувати Андрію запуск на повному корпусі' if go else 'NO-GO — потрібні виправлення або бракує даних'}"]
    out = ROOT / "results" / "v3"
    out.mkdir(parents=True, exist_ok=True)
    (out / "VALIDATION.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except ReviewIncomplete as e:
        sys.exit(f"ПОМИЛКА: {e}")
