"""Вибірка для перевірки правил атрибуції (до запуску на повному корпусі).

1) Стратифікована випадкова вибірка: 7 немедійних каналів × 3 періоди × 40 = до 840 повідомлень (seed 20261024),
   на ній — описова статистика прототипу.
2) Із неї — 150 прикладів для ручного перегляду: 84 випадкових (по 4 на страту) + цільові приклади кожного
   типу джерела / способу атрибуції / типу повідомлення (щоб кожна категорія була представлена).

Запуск: python -m src.v3.sample_examples
Вихід: validation/attribution_sample_v1.csv (840, з результатами прототипу),
       validation/attribution_examples_v2.csv (150 для перегляду), docs/ATTRIBUTION_EXAMPLES.md
"""
import json
import random
from collections import Counter

import pandas as pd

from src.v2.detect import Detector, ROOT
from src.v3.attribution import Attribution

NON_MEDIA = ["truexanewsua", "kievinfo_kyiv", "UaOnlii", "vanek_nikolaev", "lachentyt", "times_ukraina", "batalionmonako"]
PERIODS = [("P1_pre", None, "2022-02-24"), ("P2_2022_23", "2022-02-24", "2024-01-01"), ("P3_2024_26", "2024-01-01", None)]
SEED = 20261024
TYPES = ["company_organization", "ua_media", "foreign_media", "russian_media", "ua_official", "foreign_official", "russian_official", "politician", "person_other",
         "expert", "telegram", "social", "unnamed_media", "eyewitness", "anonymous", "other"]


def main() -> None:
    rnd = random.Random(SEED)
    at, det = Attribution(), Detector()
    rows = []
    for ch in NON_MEDIA:
        msgs = json.loads((ROOT / "data" / "raw" / f"telegram_{ch}.json").read_text(encoding="utf-8"))
        boiler = det.boilerplate_lines(msgs)
        for pname, a, b in PERIODS:
            pool = [m for m in msgs if (not a or m["date"] >= a) and (not b or m["date"] < b) and (m.get("text") or "").strip()]
            for m in rnd.sample(pool, min(40, len(pool))):
                r = at.analyze(m, ch, boiler)
                rows.append({
                    "channel": ch, "period": pname, "date": m["date"][:10], "msg_id": m["id"],
                    "message_type": r["message_type"], "in_primary_denominator": r["in_primary_denominator"],
                    "has_explicit_source": r["has_explicit_source"],
                    "attribution_method": r["attribution_method"], "n_sources": r["n_sources"],
                    "attributed_sources": " | ".join(
                        f"{s['name']} [{s['type']}{', WL' if s['whitelist'] else ''}; {s['pattern']}; {s['specificity']}"
                        f"{'; →' + s['linked_destination'] if s.get('linked_destination') else ''}"
                        f"{'; АКТОР З ПОСИЛАННЯ' if s.get('actor_inferred_from_link') else ''}]" for s in r["attributed_sources"]),
                    "linked_destinations": " | ".join(f"{d['entity']} [{d['platform_type']}{', WL' if d['whitelist'] else ''}]"
                                                      for d in r["linked_destinations"]),
                    "source_types": ";".join(sorted({s["type"] for s in r["attributed_sources"]})),
                    "text": r["clean_text"][:700],
                })
    df = pd.DataFrame(rows)
    (ROOT / "validation").mkdir(exist_ok=True)
    df.to_csv(ROOT / "validation" / "attribution_sample_v2.csv", index=False, encoding="utf-8-sig")

    # --- 150 прикладів для перегляду
    pick = set()
    for (ch, p), g in df.groupby(["channel", "period"]):
        pick |= set(g.sample(min(4, len(g)), random_state=SEED).index)
    targets = [("source_types", t) for t in TYPES] + [("attribution_method", m) for m in ("hyperlink", "textual", "both")] + \
              [("message_type", m) for m in ("ad", "alert", "self_promo", "technical")]
    for col, val in targets:
        cand = df[df[col].astype(str).str.contains(rf"(^|;){val}(;|$)", regex=True)].drop(index=list(pick), errors="ignore")
        pick |= set(cand.sample(min(4, len(cand)), random_state=SEED).index)
    ex = df.loc[sorted(pick)].copy()
    if len(ex) > 150:
        extra = ex.index.difference(df.groupby(["channel", "period"]).head(0).index)
        ex = ex.sample(150, random_state=SEED)
    ex = ex.sample(frac=1, random_state=SEED).reset_index(drop=True)
    ex.insert(0, "item", range(1, len(ex) + 1))
    for c in ("ok_has_source", "ok_actors", "ok_types", "ok_message_type", "correct_value", "comment"):
        ex[c] = ""
    ex.to_csv(ROOT / "validation" / "attribution_examples_v2.csv", index=False, encoding="utf-8-sig")

    # --- статистика по вибірці 840
    news = df[df.in_primary_denominator]
    tc = Counter(t for s in df.source_types for t in s.split(";") if t)
    md = ["# Приклади атрибуції — прототип v3.1 (після аудиту ChatGPT, 2026-10-24)", "",
          "Схема v3.1: **джерело-актор** (хто є джерелом) окремо від **пункту призначення посилання** (куди веде лінк). "
          "«АКТОР З ПОСИЛАННЯ» — у тексті актора немає, тому джерелом вважається видавець за посиланням.", "",
          "Це **не результати**, а перевірка правил на стратифікованій вибірці (до запуску на повному корпусі).", "",
          f"Вибірка: {len(df)} повідомлень (7 каналів × 3 періоди × до 40).", "",
          "## Що показує прототип на вибірці", "",
          f"- тип повідомлення: {df.message_type.value_counts().to_dict()}",
          f"- з явним джерелом — усі: {100*df.has_explicit_source.mean():.1f}%; основний знаменник (без реклами/самопромо/технічних): {100*news.has_explicit_source.mean():.1f}% (n={len(news)})",
          f"- спосіб атрибуції: {df.attribution_method.value_counts().to_dict()}",
          f"- типи джерел (кількість повідомлень): {dict(tc.most_common())}", "",
          "## Приклади для перегляду", "",
          "Повна таблиця з колонками для ваших позначок — `validation/attribution_examples_v2.csv`.", ""]
    for _, r in ex.iterrows():
        md += [f"**#{r['item']}** · {r['channel']} · {r['date']} · тип повідомлення: `{r['message_type']}` · "
               f"джерело: **{'так' if r['has_explicit_source'] else 'ні'}** · спосіб: `{r['attribution_method']}`",
               f"> {r['text'][:400].replace(chr(10), ' ')}", "",
               f"Джерела-актори: {r['attributed_sources'] or '—'}",
               f"Посилання (пункт призначення): {r['linked_destinations'] or '—'}", ""]
    (ROOT / "docs" / "ATTRIBUTION_EXAMPLES.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md[:12]))
    print("examples:", len(ex))


if __name__ == "__main__":
    main()
