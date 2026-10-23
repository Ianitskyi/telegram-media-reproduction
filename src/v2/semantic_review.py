"""Вибірка пар для ручного перегляду семантичних збігів.

25 пар у кожному діапазоні подібності «before» (0.75–0.80, 0.80–0.85, 0.85–0.90, ≥0.90)
+ 25 пар із контрольного вікна (зсув −30 днів) з подібністю ≥0.80 — як виглядають «випадкові» збіги.

Запуск: python -m src.v2.semantic_review whitelist2
Вихід: validation/semantic_pairs_<TAG>.csv (колонки для вердикту порожні)
"""
import json
import sys

import numpy as np
import pandas as pd

from src.v2.detect import ROOT, Detector
from src.v2.semantic_match import best, load, H48, SHIFT

TAG = sys.argv[1] if len(sys.argv) > 1 else "whitelist2"
SEED = 20261023
BINS = [(0.75, 0.80), (0.80, 0.85), (0.85, 0.90), (0.90, 1.01)]


def main() -> None:
    df = pd.read_csv(ROOT / "results" / "v2" / f"semantic_matches_{TAG}.csv.gz")
    det = Detector()
    need = set(df.channel) | set(df.match_channel.dropna())
    text = {}
    for ch in need:
        if not isinstance(ch, str) or not ch:
            continue
        for m in json.loads((ROOT / "data" / "raw" / f"telegram_{ch}.json").read_text(encoding="utf-8")):
            text[(ch, m["id"])] = " ".join(det.clean(m.get("text") or "").split())[:500]
    rows = []
    for lo, hi in BINS:
        g = df[(df.sim_before >= lo) & (df.sim_before < hi)]
        for _, r in g.sample(min(25, len(g)), random_state=SEED).iterrows():
            rows.append({"bin": f"{lo:.2f}-{min(hi, 1):.2f}", "sim": r.sim_before, "lag_min": r.lag_minutes,
                         "trigram_jaccard": r.trigram_jaccard, "tg_channel": r.channel, "tg_date": r.date,
                         "tg_text": text.get((r.channel, r.msg_id), ""), "media_channel": r.match_channel,
                         "media_text": text.get((r.match_channel, r.match_msg_id), ""),
                         "verdict": "", "note": ""})
    # контроль: найкращий збіг у вікні, зсунутому на 30 днів назад
    ctrl = df[df.sim_control >= 0.80].sample(min(25, int((df.sim_control >= 0.80).sum())), random_state=SEED)
    media = [c for c in need if c not in set(df.channel) and isinstance(c, str) and c]
    m_ids, m_dates, m_emb, m_ch = [], [], [], []
    for ch in media:
        i, d, e = load(ch); m_ids.append(i); m_dates.append(d); m_emb.append(e); m_ch += [ch] * len(i)
    m_ids, m_dates, m_emb, m_ch = np.concatenate(m_ids), np.concatenate(m_dates), np.vstack(m_emb), np.array(m_ch)
    o = np.argsort(m_dates); m_ids, m_dates, m_emb, m_ch = m_ids[o], m_dates[o], m_emb[o], m_ch[o]
    for ch, g in ctrl.groupby("channel"):
        ids, d, e = load(ch)
        pos = {int(x): k for k, x in enumerate(ids)}
        k = np.array([pos[int(x)] for x in g.msg_id])
        s, j = best(e[k], d[k], m_emb, m_dates, -SHIFT - H48, -SHIFT)
        for (_, r), sj, jj in zip(g.iterrows(), s, j):
            rows.append({"bin": "control_-30d", "sim": round(float(sj), 4), "lag_min": None, "trigram_jaccard": None,
                         "tg_channel": ch, "tg_date": r.date, "tg_text": text.get((ch, r.msg_id), ""),
                         "media_channel": m_ch[jj], "media_text": text.get((m_ch[jj], int(m_ids[jj])), ""),
                         "verdict": "", "note": ""})
    out = pd.DataFrame(rows)
    out.insert(0, "item", range(1, len(out) + 1))
    out.to_csv(ROOT / "validation" / f"semantic_pairs_{TAG}.csv", index=False, encoding="utf-8-sig")
    print(out.groupby("bin").size())


if __name__ == "__main__":
    main()
