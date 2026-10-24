"""Оцінка класифікатора атрибуції v3.2 за ручним кодуванням (після того, як кодери заповнять аркуш).

Запуск:
  python -m src.v3.validation_score validation/coded_coder1.xlsx [validation/coded_coder2.xlsx]
Перший файл — «золотий стандарт» (після узгодження розбіжностей), другий — незалежний другий кодер
(лише рядки double_coded) для міжкодерної надійності (Cohen's κ, F1 між кодерами для списків джерел).
Порогові значення go/no-go — з плану ChatGPT (docs/ATTRIBUTION_RULES.md §9, validation/CODEBOOK_v3.md §6).
Вихід: results/v3/VALIDATION.md
"""
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
THRESHOLDS = {
    "has_explicit_source precision": 0.95, "has_explicit_source recall": 0.90,
    "actor extraction precision": 0.90, "actor extraction recall": 0.90,
    "source_type macro-F1": 0.85, "denominator accuracy": 0.95, "substantive recall": 0.98,
    "destination type accuracy": 0.95, "kappa (key variables)": 0.80,
}


def load(path: str) -> pd.DataFrame:
    p = Path(path)
    df = pd.read_excel(p, sheet_name=0, dtype=str) if p.suffix == ".xlsx" else pd.read_csv(p, dtype=str)
    return df.fillna("")


def norm(name: str) -> str:
    n = re.sub(r"[«»\"“”'’ʼ().,:;!?\-—–]", " ", name.lower())
    return " ".join(n.split())


def parse_sources(cell: str, level: str = "direct") -> list:
    out = []
    for line in str(cell or "").splitlines():
        f = [x.strip() for x in line.split(";")]
        if not f or not f[0]:
            continue
        f += [""] * (5 - len(f))
        if level and f[3] and f[3] != level:
            continue
        out.append({"name": norm(f[0]), "type": f[1], "spec": f[2], "level": f[3] or "direct", "how": f[4]})
    return out


def same(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) / max(1, len(ta | tb)) >= 0.5 or any(len(t) > 4 and t[:5] in b for t in ta)


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
    if not len(a):
        return float("nan")
    po = (a == b).mean()
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / len(a) ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def macro_f1(pairs) -> tuple:
    labels = sorted({g["type"] for g, _ in pairs} | {p["type"] for _, p in pairs})
    f1s, acc = {}, (sum(g["type"] == p["type"] for g, p in pairs) / len(pairs) if pairs else float("nan"))
    for L in labels:
        tp = sum(g["type"] == L and p["type"] == L for g, p in pairs)
        fp = sum(g["type"] != L and p["type"] == L for g, p in pairs)
        fn = sum(g["type"] == L and p["type"] != L for g, p in pairs)
        f1s[L] = (prf(tp, fp, fn)[2], sum(g["type"] == L for g, _ in pairs))
    valid = [f for f, n in f1s.values() if f == f]
    return acc, (sum(valid) / len(valid) if valid else float("nan")), f1s


def main(gold_path: str, second_path: str = None) -> None:
    key = pd.read_csv(ROOT / "validation" / "v3_validation_key.csv", dtype=str).fillna("")
    gold = load(gold_path)
    df = key.merge(gold[["item_id"] + [c for c in gold.columns if c.startswith(("M", "SOURCES", "DESTINATIONS"))]],
                   on="item_id", how="inner")
    df = df[df.M3_has_explicit_source.str.strip() != ""]
    yes = lambda s: s.str.strip().str.lower().isin(["yes", "так", "true", "1"])
    df["g_src"], df["p_src"] = yes(df.M3_has_explicit_source), df.pred_has_explicit_source.str.lower().eq("true")
    df["g_den"] = df.M1_content_type.isin(["informational", "alert"]) & (df.M2_promotional != "ad")
    df["p_den"] = df.pred_in_denominator.str.lower().eq("true")
    R = df[df.subsample == "A_random"]
    res, lines = {}, []

    # 1) has_explicit_source: precision — уся вибірка (з позитивами), recall — лише випадкова частина
    tp = (df.g_src & df.p_src).sum(); fp = (~df.g_src & df.p_src).sum()
    res["has_explicit_source precision"] = tp / (tp + fp) if tp + fp else float("nan")
    tpr = (R.g_src & R.p_src).sum(); fnr = (R.g_src & ~R.p_src).sum()
    res["has_explicit_source recall"] = tpr / (tpr + fnr) if tpr + fnr else float("nan")

    # 2) знаменник і тип змісту (випадкова частина)
    res["denominator accuracy"] = (R.g_den == R.p_den).mean()
    subst = R.M1_content_type.isin(["informational", "alert"])
    res["substantive recall"] = (R.p_den & subst).sum() / subst.sum() if subst.sum() else float("nan")
    content_acc = (R.M1_content_type == R.pred_content_type).mean()
    promo_tp = ((R.M2_promotional != "no") & (R.pred_promotional != "no")).sum()
    promo = prf(promo_tp, ((R.M2_promotional == "no") & (R.pred_promotional != "no")).sum(),
                ((R.M2_promotional != "no") & (R.pred_promotional == "no")).sum())

    # 3) джерела-актори (прямі) і типи
    tp = fp = fn = 0
    all_pairs, nest_hits = [], []
    for _, r in df.iterrows():
        g, p = parse_sources(r.SOURCES), parse_sources(r.pred_sources)
        pairs = match(g, p)
        tp += len(pairs); fp += len(p) - len(pairs); fn += len(g) - len(pairs)
        all_pairs += pairs
        nest_hits.append((yes(pd.Series([r.M6_has_nested_source])).iloc[0], r.pred_has_nested.lower() == "true"))
    ap, ar, af = prf(tp, fp, fn)
    res["actor extraction precision"], res["actor extraction recall"] = ap, ar
    type_acc, mf1, per_type = macro_f1(all_pairs)
    res["source_type macro-F1"] = mf1
    method_acc = (df.M4_attribution_method == df.pred_method).mean()
    nest_acc = sum(a == b for a, b in nest_hits) / len(nest_hits) if nest_hits else float("nan")

    # 4) пункти призначення
    dt = dn = 0
    for _, r in df.iterrows():
        gd = {l.split(";")[0].strip().lower(): (l.split(";") + [""])[1].strip() for l in str(r.DESTINATIONS).splitlines() if l.strip()}
        pd_ = {l.split(";")[0].strip().lower(): (l.split(";") + [""])[1].strip() for l in str(r.pred_destinations).splitlines() if l.strip()}
        for dom, t in gd.items():
            hit = next((pt for pdm, pt in pd_.items() if dom and (dom in pdm or pdm in dom)), None)
            dn += 1; dt += hit == t
    res["destination type accuracy"] = dt / dn if dn else float("nan")

    # 5) міжкодерна надійність
    kap = {}
    if second_path:
        s = load(second_path)
        both = gold.merge(s, on="item_id", suffixes=("_1", "_2"))
        both = both[both.get("double_coded_1", pd.Series(dtype=str)).astype(str).str.lower().isin(["так", "true", "yes"])] \
            if "double_coded_1" in both else both
        for c in ("M1_content_type", "M2_promotional", "M3_has_explicit_source", "M4_attribution_method", "M6_has_nested_source"):
            kap[c] = kappa(both[c + "_1"], both[c + "_2"])
        t2 = f2 = n2 = 0
        for _, r in both.iterrows():
            a, b = parse_sources(r.SOURCES_1), parse_sources(r.SOURCES_2)
            pr = match(a, b); t2 += len(pr); f2 += len(b) - len(pr); n2 += len(a) - len(pr)
        kap["SOURCES F1 (між кодерами)"] = prf(t2, f2, n2)[2]
        key_k = [kap[c] for c in ("M1_content_type", "M3_has_explicit_source", "M4_attribution_method") if kap[c] == kap[c]]
        res["kappa (key variables)"] = min(key_k) if key_k else float("nan")

    # звіт
    f = lambda x: "—" if x != x else f"{x:.3f}"
    lines += ["# Валідація класифікатора атрибуції v3.2", "",
              f"Закодовано: {len(df)} повідомлень (випадкова частина: {len(R)}).", "",
              "| Показник | Значення | Поріг | Результат |", "|---|---|---|---|"]
    ok_all = True
    for k, thr in THRESHOLDS.items():
        v = res.get(k, float("nan"))
        ok = v == v and v >= thr
        ok_all &= ok or v != v
        lines.append(f"| {k} | {f(v)} | ≥ {thr} | {'✅' if ok else ('—' if v != v else '❌')} |")
    lines += ["", f"Додатково: точність типу змісту {f(content_acc)}; промо P/R {f(promo[0])}/{f(promo[1])}; "
              f"спосіб атрибуції {f(method_acc)}; вкладене джерело {f(nest_acc)}; точність типу на збігах {f(type_acc)}; "
              f"F1 акторів {f(af)}.", "",
              "## F1 за типами джерел (на збігах)", "", "| Тип | F1 | N (золото) |", "|---|---|---|"]
    lines += [f"| {t} | {f(v)} | {n} |" for t, (v, n) in sorted(per_type.items(), key=lambda x: -x[1][1])]
    if kap:
        lines += ["", "## Міжкодерна надійність", ""] + [f"- {k}: {f(v)}" for k, v in kap.items()]
    gR = R[R.g_den]
    lines += ["", "## Оцінка частки з явним джерелом (золото, випадкова частина, основний знаменник)", "",
              f"- кодери: {f(gR.g_src.mean())}; алгоритм на тих самих повідомленнях: {f(gR.p_src.mean())}", "",
              f"**Рішення go/no-go:** {'GO — можна пропонувати Андрію запуск на повному корпусі' if ok_all else 'NO-GO — потрібні виправлення'}"]
    out = ROOT / "results" / "v3"
    out.mkdir(parents=True, exist_ok=True)
    (out / "VALIDATION.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main(*sys.argv[1:3])
