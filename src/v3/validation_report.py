"""Звіт валідації за зваженою людською перевіркою (human-verified reference set; docs/VALIDATION_PLAN.md).

Вхід:
  validation/llm/{algorithm,claude,chatgpt}_blind_raw.jsonl (algorithm — algorithm_raw.jsonl)
  validation/human/strata.csv, review_queue.json, provenance.csv     ← python -m src.v3.adjudication queue
  validation/human/andrii_reviews.jsonl                               ← рішення Андрія з інтерфейсу (колекція reviews)
Запуск:  python -m src.v3.validation_report
Вихід:   results/v3/VALIDATION.md

Еталон = варіант, обраний Андрієм, або його виправлення; «Є джерело?» — q1_final, інакше q1_initial.
Ваги двоетапні (аудит ChatGPT 2026-10-26):
  етап 1 — вибірка A по стратах канал×період: w1 = N_корпусу_клітинки / n_вибірки_клітинки («корпусні»)
           або w1 = 1 («макро»: кожна клітинка рівновага, як у дизайні вибірки);
  етап 2 — відбір на перевірку за стратами D / F / U_*: оцінка = Σ_клітинка w1 · Σ_страта N_клітинка,страта · середнє
           перевірених (у тій самій клітинці × страті, а якщо там перевірених немає — у страті загалом).
GO вимагає, щоб пороги виконувалися і за корпусними, і за макро-вагами (консервативно).
95% CI — дворівневий бутстреп: (1) перевибірка повідомлень A всередині кожної клітинки канал×період;
(2) перевибірка перевірених повідомлень усередині кожної страти перевірки.
«Не впевнений» = незавершене рішення (не відкидається): поки такі є, GO неможливий.
Частина A — основа GO; якщо B не завершено, звіт по A дійсний, B позначено як пошукову.
κ Андрій↔LLM — лише для полів, закодованих ДО показу варіантів (q1_initial, тип змісту, промо, знаменник);
для промо/знаменника виключено ⚑8-випадки (правило ухвалено після сліпого кодування LLM).
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
FIELDS = ("content_type", "promotional", "has_explicit_source", "attribution_method", "direct_sources", "other_sources", "destinations")


class ReviewIncomplete(Exception):
    pass


def final_q1(review: dict):
    q = review.get("q1_final") or review.get("q1_initial") or review.get("q1")
    return q if q in ("yes", "no") else None


def is_complete(review) -> bool:
    return bool(review) and review.get("choice") in ("A", "B", "C", "edit") and final_q1(review) is not None


def reference(item: dict, review: dict) -> dict:
    """Еталонні поля з остаточного рішення Андрія."""
    if review.get("choice") in ("A", "B", "C"):
        v = next(v for v in item["variants"] if v["id"] == review["choice"])
        ref = {k: v[k] for k in FIELDS}
    else:
        ref = dict(review.get("edited") or {})
        base = item["variants"][0]
        for k in FIELDS:
            ref.setdefault(k, base[k])
    ref["has_explicit_source"] = final_q1(review) == "yes"
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


def weighted_sum(rows) -> dict:
    """rows: [(weight, Counter)] → зважені суми лічильників."""
    S = defaultdict(float)
    for w, m in rows:
        for k, v in m.items():
            S[k] += w * float(v)
    return S


RAW_TYPE_N: Counter = Counter()  # незважена кількість еталонних джерел кожного типу в перевірених A (для порогу MIN_N_TYPE)


def summarize(S) -> dict:
    """S: зважені суми лічильників → метрики."""
    S = defaultdict(float, S)
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
    main = [f for t, (f, n) in per.items() if RAW_TYPE_N[t] >= MIN_N_TYPE]
    out["source_type macro-F1 end-to-end (A)"] = sum(main) / len(main) if main else float("nan")
    out["_per_type"] = per
    out["_dest"] = (ratio(S["dest_ok"], S["dest_n"]), ratio(S["dest_tp"], S["dest_tp"] + S["dest_fp"]),
                    ratio(S["dest_tp"], S["dest_tp"] + S["dest_fn"]))
    out["destination type accuracy"] = out["_dest"][0]
    return out


def kappa(a: list, b: list) -> float:
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if len(pairs) < 20:
        return float("nan")
    po = sum(x == y for x, y in pairs) / len(pairs)
    ca, cb = Counter(x for x, _ in pairs), Counter(y for _, y in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / len(pairs) ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0




# ---------- двоетапна оцінка ----------
def cell_population() -> dict:
    """N повідомлень із текстом у кожній клітинці канал×період (як у генеральній сукупності вибірки A)."""
    cache = HUMAN / "cell_population.csv"
    if cache.exists():
        df = pd.read_csv(cache)
    else:
        from src.v3.validation_sample import NON_MEDIA, PERIODS
        rows = []
        for ch in NON_MEDIA:
            msgs = json.loads((ROOT / "data" / "raw" / f"telegram_{ch}.json").read_text(encoding="utf-8"))
            for pname, a, b in PERIODS:
                n = sum(1 for m in msgs if (not a or m["date"] >= a) and (not b or m["date"] < b) and (m.get("text") or "").strip())
                if n:
                    rows.append({"channel": ch, "period": pname, "N": n})
        df = pd.DataFrame(rows)
        df.to_csv(cache, index=False)
    return {(r.channel, r.period): r.N for r in df.itertuples()}


def _accumulate(units: list, metrics: dict, pool_s: dict, w1: dict) -> dict:
    """Повністю перевірені страти (D, F): точна сума по повідомленнях з вагою w1 клітинки.
    Вибіркові страти (U_*): N_клітинка,страта · w1 · середнє перевірених у страті (пул pool_s)."""
    count = Counter()
    S = defaultdict(float)
    for c, st, i in units:
        if st in pool_s:
            count[(c, st)] += 1
        elif i in metrics:
            for key, v in metrics[i].items():
                S[key] += w1[c] * float(v)
    for (c, st), n in count.items():
        pool = pool_s[st]
        k = w1[c] * n / len(pool)
        for m in pool:
            for key, v in m.items():
                S[key] += k * float(v)
    return S


def _sampled_strata(units, metrics):
    by = defaultdict(list)
    for _, st, i in units:
        by[st].append(i)
    full = {st for st, ids in by.items() if all(i in metrics for i in ids)}
    return {st: [i for i in ids if i in metrics] for st, ids in by.items() if st not in full and any(i in metrics for i in ids)}


def estimate(units: list, metrics: dict, w1: dict) -> dict:
    """units: [(cell, stratum, item_id)] — усі повідомлення вибірки етапу 1; metrics: item_id → Counter перевірених."""
    samp = _sampled_strata(units, metrics)
    return _accumulate(units, metrics, {st: [metrics[i] for i in ids] for st, ids in samp.items()}, w1)


def _accumulate_boot(count: Counter, pools_cs: dict, pools_s: dict, w1: dict) -> dict:
    S = defaultdict(float)
    for (c, st), n in count.items():
        pool = pools_cs.get((c, st)) or pools_s.get(st)
        if not pool:
            continue
        k = w1[c] * n / len(pool)
        for m in pool:
            for key, v in m.items():
                S[key] += k * float(v)
    return S


def bootstrap(units: list, metrics: dict, w1: dict, reps=B_REPS) -> dict:
    """Дворівневий бутстреп.
    Рівень 1: перевибірка повідомлень A всередині кожної клітинки канал×період → нові N_cell,страта;
              для повністю перевірених страт (D, F) середнє береться з перевибраних повідомлень клітинки.
    Рівень 2: для вибірково перевірених страт (U_*) — перевибірка перевірених усередині страти."""
    rnd = random.Random(SEED)
    by_cell = defaultdict(list)
    for u in units:
        by_cell[u[0]].append(u)
    st_all = Counter(st for _, st, _ in units)
    st_rev = Counter(st for _, st, i in units if i in metrics)
    full = {st for st in st_all if st_rev[st] == st_all[st]}
    rev_by_st = defaultdict(list)
    for c, st, i in units:
        if i in metrics and st not in full:
            rev_by_st[st].append(metrics[i])
    boot = defaultdict(list)
    for _ in range(reps):
        res = [rnd.choice(g) for g in by_cell.values() for _ in g]
        count = Counter((c, st) for c, st, _ in res)
        pools_cs = defaultdict(list)
        for c, st, i in res:
            if st in full:
                pools_cs[(c, st)].append(metrics[i])
        pools_s = {st: [rnd.choice(ms) for _ in ms] for st, ms in rev_by_st.items()}
        for key, v in summarize(_accumulate_boot(count, pools_cs, pools_s, w1)).items():
            if not key.startswith("_") and v == v:
                boot[key].append(v)
    return {k: (sorted(v)[int(0.025 * len(v))], sorted(v)[int(0.975 * len(v)) - 1]) for k, v in boot.items() if v}


# ---------- головне ----------
def load_reviews() -> dict:
    reviews = {}
    p = HUMAN / "andrii_reviews.jsonl"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                reviews[r["item_id"]] = r  # останнє рішення перекриває попереднє
    return reviews


def main() -> None:
    strata = pd.read_csv(HUMAN / "strata.csv", dtype={"item_id": str})
    strata["selected"] = strata.selected.astype(str).str.lower() == "true"
    strata["flag8"] = strata.get("flag8", False).astype(str).str.lower() == "true"
    queue = {q["item_id"]: q for q in json.loads((HUMAN / "review_queue.json").read_text(encoding="utf-8"))}
    reviews = load_reviews()
    ans = {c: load(c) for c in CODERS}
    strata["part"] = strata.subsample.str[0]
    sel = strata[strata.selected]
    incomplete = {p: [i for i in sel[sel.part == p].item_id if not is_complete(reviews.get(i))] for p in ("A", "B")}
    unsure = [i for i in sel.item_id if reviews.get(i) and not is_complete(reviews[i]) and reviews[i].get("choice") == "unsure"
              or (reviews.get(i) and reviews[i].get("q1_initial") == "unsure" and not reviews[i].get("q1_final"))]
    if len(incomplete["A"]) == len(sel[sel.part == "A"]):
        raise ReviewIncomplete("у частині A ще немає жодного завершеного рішення")

    metrics, refs = {}, {}
    for i in sel.item_id:
        if is_complete(reviews.get(i)):
            refs[i] = reference(queue[i], reviews[i])
            metrics[i] = item_metrics(fields(ans["algorithm"][i]), refs[i])

    A = strata[strata.part == "A"]
    RAW_TYPE_N.clear()
    RAW_TYPE_N.update(s_["type"] for i in A.item_id if i in refs for s_ in refs[i]["direct_sources"])
    units = [((r.channel, r.period), r.stratum, r.item_id) for r in A.itertuples()]
    pop = cell_population()
    nA = Counter(u[0] for u in units)
    W = {"корпусні": {c: pop[c] / n for c, n in nA.items()}, "макро": {c: 1.0 for c in nA}}
    res, ci = {}, {}
    for wname, w1 in W.items():
        S = estimate(units, metrics, w1)
        res[wname] = summarize(S)
        ci[wname] = bootstrap(units, metrics, w1)

    # B: precision за механізмами (без ваг етапу 1; вага етапу 2 у межах субвибірки × страти)
    B = strata[strata.part == "B"]
    mech = {}
    for s_ in ("B_textual", "B_hyperlink", "B_both_multi"):
        u = [(("B", s_), r.stratum, r.item_id) for r in B[B.subsample == s_].itertuples()]
        b = summarize(estimate(u, metrics, {("B", s_): 1.0}))
        mech[s_] = (b["has_explicit_source precision (A)"], b["actor precision (A)"])

    # суттєві помилки серед перевірених одностайних (лише U-страти; ⚑8-страта F — окремо)
    def substantial(it, ref):
        p = fields(ans["algorithm"][it])
        return (p["has_explicit_source"] != ref["has_explicit_source"] or in_denominator(p) != in_denominator(ref)
                or len(match(ref["direct_sources"], p["direct_sources"])) != max(len(ref["direct_sources"]), len(p["direct_sources"])))
    uni = [i for i in sel[sel.stratum.str.startswith("U_")].item_id if i in refs]
    uni_err = ratio(sum(substantial(i, refs[i]) for i in uni), len(uni))

    # κ: LLM↔LLM на всіх; Андрій↔LLM лише для полів до показу варіантів
    flag8 = set(strata[strata.flag8].item_id)
    ids = sorted(set(strata.item_id))
    kap = {}
    for f_, get in (("content_type", lambda o: o["content_type"]), ("has_explicit_source", lambda o: bool(o["has_explicit_source"])),
                    ("promotional", lambda o: o["promotional"]), ("знаменник", in_denominator)):
        kap[f"Claude ↔ ChatGPT, {f_} (усі)"] = kappa([get(ans["claude"][i]) for i in ids], [get(ans["chatgpt"][i]) for i in ids])
    pre = {i: r for i, r in reviews.items() if r.get("q1_initial") in ("yes", "no") or r.get("pre")}
    def pre_get(r, f_):
        p = r.get("pre") or {}
        if f_ == "has_explicit_source":
            return {"yes": True, "no": False}.get(r.get("q1_initial"))
        if f_ in ("content_type", "promotional"):
            return p.get(f_) or None
        if f_ == "знаменник":
            return (p["content_type"] in ("informational", "alert") and p["promotional"] != "ad") if p.get("content_type") and p.get("promotional") else None
    for f_, get in (("content_type", lambda o: o["content_type"]), ("has_explicit_source", lambda o: bool(o["has_explicit_source"])),
                    ("promotional", lambda o: o["promotional"]), ("знаменник", in_denominator)):
        rv = [i for i in pre if i in ans["claude"] and not (f_ in ("promotional", "знаменник") and i in flag8)]
        for c in ("claude", "chatgpt"):
            kap[f"Андрій (до показу) ↔ {c}, {f_}"] = kappa([pre_get(reviews[i], f_) for i in rv], [get(ans[c][i]) for i in rv])

    # звіт
    f = lambda x: "—" if x != x else f"{x:.3f}"
    a_done = not incomplete["A"]
    lines = ["# Валідація класифікатора атрибуції v3.3 (AI-assisted coding з людською перевіркою)", "",
             f"Вибірка (без V0001–V0100, витік): {len(strata)} повідомлень; страти: {strata.stratum.value_counts().to_dict()}.",
             f"До перевірки: A {int((sel.part == 'A').sum())}, B {int((sel.part == 'B').sum())}. "
             f"Незавершено: A {len(incomplete['A'])}, B {len(incomplete['B'])}; з них «не впевнений»: {len(unsure)}.", ""]
    if not a_done:
        lines += [f"⚠️ **Частину A не завершено ({len(incomplete['A'])}) — метрики попередні, GO неможливий.**", ""]
    if incomplete["B"]:
        lines += ["ℹ️ Частину B не завершено — результати B пошукові.", ""]
    go = a_done
    for wname in W:
        lines += [f"## Обов'язкові показники — ваги «{wname}»", "",
                  "| Показник | Значення | 95% CI | Поріг | Результат |", "|---|---|---|---|---|"]
        for name, thr, lo in THRESHOLDS:
            v = res[wname].get(name, float("nan")); c = ci[wname].get(name)
            ok = v == v and v >= thr and (lo is None or (c is not None and c[0] >= lo))
            go &= ok
            lines.append(f"| {name} | {f(v)} | {f(c[0]) + '–' + f(c[1]) if c else '—'} | ≥ {thr}{' (CI ≥ ' + str(lo) + ')' if lo else ''} | "
                         f"{'✅' if ok else ('❌ немає даних' if v != v else '❌')} |")
        lines += [""] + [f"- {k}: {f(v)}{' (CI ' + f(ci[wname][k][0]) + '–' + f(ci[wname][k][1]) + ')' if k in ci[wname] else ''}"
                         for k, v in res[wname].items() if not k.startswith("_") and k not in dict((t[0], 1) for t in THRESHOLDS)]
        lines += [f"- {k}: бажано CI ≥ {v} — {'так' if k in ci[wname] and ci[wname][k][0] >= v else 'ні'}" for k, v in SOFT_CI.items()]
        lines += [""]
    ok_u = uni_err == uni_err and uni_err <= MAX_UNANIMOUS_ERR
    go &= ok_u
    lines += [f"**Суттєві помилки серед перевірених одностайних:** {f(uni_err)} (поріг ≤ {MAX_UNANIMOUS_ERR}) {'✅' if ok_u else '❌'}", ""]
    lines += ["## Precision за механізмами (частина B" + (", пошуково" if incomplete["B"] else "") + ")", "",
              "| Механізм | has_source precision | actor precision |", "|---|---|---|"]
    lines += [f"| {k} | {f(a)} | {f(b)} |" for k, (a, b) in mech.items()]
    lines += ["", f"## Тип джерела end-to-end, F1 за типами (A, корпусні ваги; у macro-F1 — типи з N ≥ {MIN_N_TYPE})", "",
              "| Тип | F1 | N перевірених (незважено) |", "|---|---|---|"]
    lines += [f"| {t} | {f(v)} | {RAW_TYPE_N[t]}{'' if RAW_TYPE_N[t] >= MIN_N_TYPE else ' (пошуковий)'} |"
              for t, (v, n) in sorted(res["корпусні"]["_per_type"].items(), key=lambda x: -x[1][1])]
    lines += ["", "## Узгодженість (κ) — показник узгодженості, не точності", ""] + [f"- {k}: {f(v)}" for k, v in kap.items()]
    lines += ["", f"**Рішення:** {'GO — можна пропонувати Андрію запуск на повному корпусі' if go else 'NO-GO — потрібні виправлення, перевірка не завершена або бракує даних'}"]
    out = ROOT / "results" / "v3"
    out.mkdir(parents=True, exist_ok=True)
    (out / "VALIDATION.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except ReviewIncomplete as e:
        sys.exit(f"ПОМИЛКА: {e}")
