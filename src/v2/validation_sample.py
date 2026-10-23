"""Стратифікована вибірка для ручної перевірки детекторів (план ChatGPT, затверджено Андрієм 2026-10-23).

7 немедійних каналів × 3 періоди × (40 випадкових + 20 позитивних за детектором v2) ≈ 1 260.
Якщо позитивних у страті менше 20 — беруться всі. Випадкові й позитивні не перетинаються.

Запуск: python -m src.v2.validation_sample
Вихід: validation/sample_v1.csv (кодувальні колонки порожні), validation/CODEBOOK.md
"""
import json

import pandas as pd

from src.v2.aggregate import NON_MEDIA, load
from src.v2.detect import ROOT, Detector

SEED = 20261023
OUT = ROOT / "validation"
PERIODS = [("P1_pre_invasion", None, "2022-02-24"), ("P2_2022_2023", "2022-02-24", "2024-01-01"), ("P3_2024_2026", "2024-01-01", None)]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    df = load()
    df = df[df.channel.isin(NON_MEDIA)].copy()
    raw = json.loads((ROOT / "data" / "raw" / "telegram_all_messages.json").read_text(encoding="utf-8"))
    text = {(ch, m["id"]): m.get("text") or "" for ch in NON_MEDIA for m in raw[ch]}
    names = {m["id"]: m["name"] for m in Detector().media}

    parts = []
    for ch in NON_MEDIA:
        for pname, a, b in PERIODS:
            g = df[df.channel == ch]
            if a:
                g = g[g.date >= pd.Timestamp(a, tz="UTC")]
            if b:
                g = g[g.date < pd.Timestamp(b, tz="UTC")]
            g = g[g.has_text]
            if g.empty:
                continue
            rnd = g.sample(min(40, len(g)), random_state=SEED).assign(stratum_type="random")
            pos = g[g["any"] & ~g.index.isin(rnd.index)]
            pos = pos.sample(min(20, len(pos)), random_state=SEED).assign(stratum_type="detector_positive")
            parts.append(pd.concat([rnd, pos]).assign(period=pname))
    s = pd.concat(parts)
    ids2names = lambda v: "; ".join(names[int(i)] for i in str(v).split(";")) if isinstance(v, str) else ""
    s = s.assign(
        text=[text[(c, i)] for c, i in zip(s.channel, s.msg_id)],
        detector_links=s.link_ids.map(ids2names),
        detector_mentions=s.mention_ids.map(ids2names),
    )
    s = s.sample(frac=1, random_state=SEED)  # перемішати, щоб кодувальник не бачив страт підряд
    s.insert(0, "item", range(1, len(s) + 1))
    cols = ["item", "channel", "period", "stratum_type", "date", "msg_id", "text", "detector_links", "detector_mentions"]
    code = ["Q1_names_prof_media", "Q1_which_media", "Q2_attribution_type", "Q3_reproduces_content", "fp_reason", "coder", "notes"]
    out = s[cols].copy()
    for c in code:
        out[c] = ""
    out.to_csv(OUT / "sample_v1.csv", index=False, encoding="utf-8-sig")
    # «сліпа» версія — без відповідей детектора, для незалежного кодування
    out.drop(columns=["stratum_type", "detector_links", "detector_mentions"]).to_csv(OUT / "sample_v1_blind.csv", index=False, encoding="utf-8-sig")
    print(len(out), out.groupby(["stratum_type"]).size().to_dict())
    print(out.groupby(["channel", "period"]).size().unstack())


if __name__ == "__main__":
    main()
