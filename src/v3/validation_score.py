"""Оцінка класифікатора атрибуції v3.2 за ручним кодуванням (виправлено за аудитом ChatGPT, 2026-10-24).

Три файли (жоден не перезаписується іншим):
  gold    — узгоджений «золотий стандарт» (усі 1 495 рядків; після обговорення розбіжностей);
  coder1  — СИРЕ кодування кодера 1 (до узгодження);
  coder2  — СИРЕ кодування кодера 2 (лише рядки double_coded).
Алгоритм порівнюється з gold; міжкодерна надійність (Cohen's κ) — coder1_raw ↔ coder2_raw.

Запуск:  python -m src.v3.validation_score gold.xlsx coder1_raw.xlsx coder2_raw.xlsx
Вихід:   results/v3/VALIDATION.md

Принципи:
- поширеність, recall і загальна precision — ЛИШЕ на випадковій частині A (вона не збагачена позитивами);
- частина B (150 textual / 150 hyperlink / 150 both-multi) — лише precision за механізмами;
- зіставлення назв джерел консервативне: основи всіх слів коротшої назви мають бути в довшій
  («Порошенко» = «Петро Порошенко», але «Петро Порошенко» ≠ «Олексій Порошенко»);
- тип джерела — end-to-end (пропущений актор = FN його типу, зайвий = FP) + окремо умовна точність на збігах;
- будь-яка обов'язкова метрика NaN → NO-GO; незаповнене кодування → помилка, а не тихе викидання рядків.
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
THRESHOLDS = {  # пороги go/no-go (CODEBOOK_v3 §8; запропонував ChatGPT, затверджує Андрій)
    "has_explicit_source precision (A)": 0.95,
    "has_explicit_source recall (A)": 0.90,
    "actor extraction precision (A)": 0.90,
    "actor extraction recall (A)": 0.90,
    "source_type macro-F1 end-to-end (A)": 0.85,
    "denominator accuracy (A)": 0.95,
    "substantive recall (A)": 0.98,
    "destination type accuracy": 0.95,
    "kappa min (M1, M3, M4)": 0.80,
}
REQUIRED_CODING = ["M1_content_type", "M2_promotional", "M3_has_explicit_source", "M4_attribution_method"]
STOP = {"в", "у", "з", "із", "на", "і", "та", "и", "й", "the", "of", "de", "по", "при", "со", "с", "від", "от"}
MIN_N_TYPE = 10  # типи з меншою кількістю в золоті — пошукові, не входять у macro-F1


class CodingIncomplete(Exception):
    pass


def load(path: str) -> pd.DataFrame:
    p = Path(path)
    df = pd.read_excel(p, sheet_name=0, dtype=str) if p.suffix == ".xlsx" else pd.read_csv(p, dtype=str)
    return df.fillna("")


def yes(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().isin(["yes", "так", "true", "1"])


def stems(name: str) -> list:
    n = re.sub(r"[«»\"“”'’ʼ().,:;!?\-—–]", " ", name.lower().replace("ё", "е"))
    return [t[:5] for t in n.split() if t not in STOP]


def same(a: str, b: str) -> bool:
    sa, sb = stems(a), stems(b)
    if not sa or not sb:
        return False
    short, long_ = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    return set(short) <= set(long_)


def parse_sources(cell: str, levels=("direct",)) -> list:
    out = []
    for line in str(cell or "").splitlines():
        f = [x.strip() for x in line.split(";")]
        if not f or not f[0]:
            continue
        f += [""] * (5 - len(f))
        lvl = (f[3] or "direct").lower()
        if levels and lvl not in levels:
            continue
        out.append({"name": f[0], "type": f[1].lower(), "spec": f[2].lower(), "level": lvl, "how": f[4].lower()})
    return out


def parse_dest(cell: str) -> dict:
    out = {}
    for line in str(cell or "").splitlines():
        f = [x.strip() for x in line.split(";")] + ["", ""]
        if f[0]:
            out[f[0].lower().removeprefix("www.")] = f[1].lower()
    return out


def match(gold: list, pred: list):
    used, pairs = set(), []
    for g in gold:
        for j, p in enumerate(pred):
            if j not in used and same(g["name"], p["name"]):
                used.add(j)
                pairs.append((g, p))
                break
    return pairs


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f = 2 * p * r / (p + r) if p == p and r == r and p + r else float("nan")
    return p, r, f


def kappa(a: pd.Series, b: pd.Series) -> float:
    a, b = a.astype(str).str.strip().str.lower(), b.astype(str).str.strip().str.lower()
    m = (a != "") & (b != "")
    a, b = a[m], b[m]
    if len(a) < 20:
        return float("nan")
    po = (a == b).mean()
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / len(a) ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def check_complete(df: pd.DataFrame, label: str, rows=None) -> None:
    d = df if rows is None else df[df.item_id.isin(rows)]
    missing = d[(d[REQUIRED_CODING].apply(lambda c: c.str.strip() == "")).any(axis=1)].item_id.tolist()
    if missing:
        raise CodingIncomplete(f"{label}: кодування не завершене — {len(missing)} рядків без обов'язкових полів "
                               f"({', '.join(REQUIRED_CODING)}), напр.: {', '.join(missing[:10])}")


def actor_eval(rows: pd.DataFrame):
    """Повертає (tp, fp, fn, пари, per-type end-to-end лічильники)."""
    tp = fp = fn = 0
    pairs_all = []
    e2e = defaultdict(lambda: [0, 0, 0])  # type → [tp, fp, fn]
    for _, r in rows.iterrows():
        g, p = parse_sources(r.SOURCES), parse_sources(r.pred_sources)
        pairs = match(g, p)
        tp += len(pairs); fp += len(p) - len(pairs); fn += len(g) - len(pairs)
        pairs_all += pairs
        mg, mp = {id(a) for a, _ in pairs}, {id(b) for _, b in pairs}
        for a, b in pairs:
            if a["type"] == b["type"]:
                e2e[a["type"]][0] += 1
            else:
                e2e[b["type"]][1] += 1; e2e[a["type"]][2] += 1
        for a in g:
            if id(a) not in mg:
                e2e[a["type"]][2] += 1
        for b in p:
            if id(b) not in mp:
                e2e[b["type"]][1] += 1
    return tp, fp, fn, pairs_all, e2e


def main(gold_path: str, coder1_path: str = None, coder2_path: str = None) -> None:
    key = pd.read_csv(ROOT / "validation" / "v3_validation_key.csv", dtype=str).fillna("")
    gold = load(gold_path)
    check_complete(gold, "gold")
    coder_cols = [c for c in gold.columns if c.startswith(("M", "SOURCES", "DESTINATIONS"))]
    df = key.merge(gold[["item_id"] + coder_cols], on="item_id", how="left", indicator=True)
    if (df._merge != "both").any():
        raise CodingIncomplete(f"gold: бракує {int((df._merge != 'both').sum())} рядків вибірки")
    df["g_src"], df["p_src"] = yes(df.M3_has_explicit_source), df.pred_has_explicit_source.str.lower().eq("true")
    df["g_den"] = df.M1_content_type.str.strip().isin(["informational", "alert"]) & (df.M2_promotional.str.strip() != "ad")
    df["p_den"] = df.pred_in_denominator.str.lower().eq("true")
    A = df[df.subsample == "A_random"]
    res, extra = {}, {}

    # 1) has_explicit_source — на A
    p, r, _ = prf((A.g_src & A.p_src).sum(), (~A.g_src & A.p_src).sum(), (A.g_src & ~A.p_src).sum())
    res["has_explicit_source precision (A)"], res["has_explicit_source recall (A)"] = p, r
    # precision за механізмами — на B
    for s in ("B_textual", "B_hyperlink", "B_both_multi"):
        B = df[df.subsample == s]
        extra[f"precision has_source, {s}"] = (B.g_src & B.p_src).sum() / B.p_src.sum() if B.p_src.sum() else float("nan")
        btp, bfp, _, _, _ = actor_eval(B)
        extra[f"precision actors, {s}"] = btp / (btp + bfp) if btp + bfp else float("nan")

    # 2) знаменник і зміст — на A
    res["denominator accuracy (A)"] = (A.g_den == A.p_den).mean()
    subst = A.g_den
    res["substantive recall (A)"] = (A.p_den & subst).sum() / subst.sum() if subst.sum() else float("nan")
    extra["content_type accuracy (A)"] = (A.M1_content_type.str.strip() == A.pred_content_type).mean()
    pp = A.pred_promotional != "no"; gp = A.M2_promotional.str.strip() != "no"
    extra["promo precision (A)"], extra["promo recall (A)"], _ = prf((gp & pp).sum(), (~gp & pp).sum(), (gp & ~pp).sum())
    extra["attribution_method accuracy (A)"] = (A.M4_attribution_method.str.strip() == A.pred_method).mean()
    if "M6_has_nested_source" in A:
        extra["nested source accuracy (A)"] = (yes(A.M6_has_nested_source) == A.pred_has_nested.str.lower().eq("true")).mean()

    # 3) джерела-актори — на A
    tp, fp, fn, pairs, e2e = actor_eval(A)
    res["actor extraction precision (A)"], res["actor extraction recall (A)"], extra["actor F1 (A)"] = prf(tp, fp, fn)
    gold_n = Counter(t for _, rr in A.iterrows() for t in [s["type"] for s in parse_sources(rr.SOURCES)])
    per_type = {t: (prf(*e2e[t])[2], gold_n.get(t, 0)) for t in set(e2e) | set(gold_n)}
    main_types = [t for t, (_, n) in per_type.items() if n >= MIN_N_TYPE]
    vals = [per_type[t][0] if per_type[t][0] == per_type[t][0] else 0.0 for t in main_types]
    res["source_type macro-F1 end-to-end (A)"] = sum(vals) / len(vals) if vals else float("nan")
    extra["source_type accuracy, лише на збігах (A)"] = (sum(a["type"] == b["type"] for a, b in pairs) / len(pairs)
                                                         if pairs else float("nan"))

    # 4) пункти призначення — уся вибірка (класифікація) + виділення на A
    dt = dn = 0
    dtp = dfp = dfn = 0
    for name, rows in (("all", df), ("A", A)):
        for _, rr in rows.iterrows():
            g, pr = parse_dest(rr.DESTINATIONS), parse_dest(rr.pred_destinations)
            hits = {gd: next((pd_ for pd_ in pr if gd and (gd in pd_ or pd_ in gd)), None) for gd in g}
            if name == "all":
                for gd, h in hits.items():
                    if h:
                        dn += 1; dt += g[gd] == pr[h]
            else:
                found = {h for h in hits.values() if h}
                dtp += len(found); dfn += sum(h is None for h in hits.values()); dfp += len(set(pr) - found)
    res["destination type accuracy"] = dt / dn if dn else float("nan")
    extra["destination extraction precision (A)"], extra["destination extraction recall (A)"], _ = prf(dtp, dfp, dfn)

    # 5) міжкодерна надійність — сирі кодування
    kap = {}
    if coder1_path and coder2_path:
        c1, c2 = load(coder1_path), load(coder2_path)
        dbl = key[key.double_coded.str.lower() == "true"].item_id.tolist()
        check_complete(c1, "coder1", dbl)
        check_complete(c2, "coder2", dbl)
        both = c1[c1.item_id.isin(dbl)].merge(c2[c2.item_id.isin(dbl)], on="item_id", suffixes=("_1", "_2"))
        if len(both) < len(dbl):
            raise CodingIncomplete(f"double-coded: у сирих файлах {len(both)} із {len(dbl)} рядків")
        for c in ("M1_content_type", "M2_promotional", "M3_has_explicit_source", "M4_attribution_method", "M6_has_nested_source"):
            if c + "_1" in both:
                kap[c] = kappa(both[c + "_1"], both[c + "_2"])
        t2 = f2 = n2 = 0
        for _, rr in both.iterrows():
            a, b = parse_sources(rr.SOURCES_1), parse_sources(rr.SOURCES_2)
            pr2 = match(a, b); t2 += len(pr2); f2 += len(b) - len(pr2); n2 += len(a) - len(pr2)
        kap["SOURCES F1 між кодерами"] = prf(t2, f2, n2)[2]
        ks = [kap.get(c, float("nan")) for c in ("M1_content_type", "M3_has_explicit_source", "M4_attribution_method")]
        res["kappa min (M1, M3, M4)"] = float("nan") if any(k != k for k in ks) else min(ks)
    else:
        res["kappa min (M1, M3, M4)"] = float("nan")

    # звіт
    f = lambda x: "—" if x != x else f"{x:.3f}"
    lines = ["# Валідація класифікатора атрибуції v3.2", "",
             f"Закодовано: {len(df)} повідомлень; випадкова частина A: {len(A)}; подвійно: {int(key.double_coded.str.lower().eq('true').sum())}.",
             "Поширеність, recall і загальна precision — лише на A; B — precision за механізмами.", "",
             "| Обов'язковий показник | Значення | Поріг | Результат |", "|---|---|---|---|"]
    go = True
    for k, thr in THRESHOLDS.items():
        v = res.get(k, float("nan"))
        ok = v == v and v >= thr
        go &= ok   # NaN → NO-GO
        lines.append(f"| {k} | {f(v)} | ≥ {thr} | {'✅' if ok else ('❌ немає даних' if v != v else '❌')} |")
    lines += ["", "## Додаткові показники", ""] + [f"- {k}: {f(v)}" for k, v in extra.items()]
    lines += ["", f"## Тип джерела end-to-end, F1 за типами (A; у macro-F1 — типи з N ≥ {MIN_N_TYPE})", "",
              "| Тип | F1 | N (золото) |", "|---|---|---|"]
    lines += [f"| {t} | {f(v)} | {n}{'' if n >= MIN_N_TYPE else ' (пошуковий)'} |"
              for t, (v, n) in sorted(per_type.items(), key=lambda x: -x[1][1])]
    if kap:
        lines += ["", "## Міжкодерна надійність (сирі coder1 ↔ coder2)", ""] + [f"- {k}: {f(v)}" for k, v in kap.items()]
    gA = A[A.g_den]
    lines += ["", "## Частка повідомлень з явним джерелом (A, основний знаменник)", "",
              f"- золото: {f(gA.g_src.mean())} (n={len(gA)}); алгоритм на тих самих: {f(gA.p_src.mean())}", "",
              f"**Рішення:** {'GO — можна пропонувати Андрію запуск на повному корпусі' if go else 'NO-GO — потрібні виправлення або бракує даних'}"]
    out = ROOT / "results" / "v3"
    out.mkdir(parents=True, exist_ok=True)
    (out / "VALIDATION.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main(*sys.argv[1:4])
    except CodingIncomplete as e:
        sys.exit(f"ПОМИЛКА: {e}")
