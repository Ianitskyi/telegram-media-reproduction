"""Семантичні збіги: пости немедійних каналів ↔ пости Telegram-каналів професійних медіа.

Чому так: корпус статей із сайтів медіа покриває лише квітень 2026 (див. DATA.md), а
Telegram-канали Суспільного, УП, ТСН і УНІАН є за весь 2020–2026. Тож вони — єдиний
поздовжньо порівнянний «еталон» контенту професійних медіа (лише 4 редакції!).

Для кожного поста немедійного каналу (час t):
  before  — найбільша косинусна подібність до поста медіа в [t-48 год, t)   ← медіа раніше
  after   — найбільша подібність до поста медіа в (t, t+48 год]             ← медіа пізніше
  control — те саме, що before, але вікно зсунуте на 30 днів назад            ← випадкові збіги
Для найкращої пари «before» — частка спільних слівних триграм (Jaccard) як міра дослівності.

Запуск: python -m src.v2.semantic_match
Запуск: python -m src.v2.semantic_match suspilnenews,ukrpravda_news whitelist2
Вихід: results/v2/semantic_matches_<TAG>.csv.gz
Немедійні канали — стабільна 30% вибірка (див. embed.py).
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.v2.aggregate import NON_MEDIA
from src.v2.detect import ROOT, Detector

EMB = ROOT / "results" / "v2" / "emb"
OUT = ROOT / "results" / "v2"
import sys as _sys
MEDIA_TG = _sys.argv[1].split(",") if len(_sys.argv) > 1 else ["suspilnenews", "ukrpravda_news", "TCH_channel", "uniannet"]
TAG = _sys.argv[2] if len(_sys.argv) > 2 else "all4"
H48 = np.timedelta64(48, "h")
SHIFT = np.timedelta64(30, "D")
WORD = re.compile(r"\w+", re.U)


import os as _os
EMB_FULL = ROOT / "results" / "v2" / "emb_full"


def load(ch):
    # FULL=1 — немедійні канали з повних ембедингів (emb_full), канали медіа — завжди з emb
    f = EMB_FULL / f"{ch}.npz" if _os.environ.get("FULL") == "1" and (EMB_FULL / f"{ch}.npz").exists() else EMB / f"{ch}.npz"
    z = np.load(f)
    d = pd.to_datetime(pd.Series(z["dates"]), utc=True).dt.tz_convert(None).values.astype("datetime64[s]")
    return z["ids"], d, z["emb"].astype(np.float32)


def trigrams(t):
    w = WORD.findall(t.lower())
    return {tuple(w[i:i + 3]) for i in range(len(w) - 2)}


def best(q_emb, q_dates, m_emb, m_dates, lo_off, hi_off, chunk=2000):
    """Для кожного запиту — max подібність до медіа з датою в [q+lo_off, q+hi_off)."""
    n = len(q_dates)
    best_s = np.full(n, -1.0, dtype=np.float32)
    best_i = np.full(n, -1, dtype=np.int64)
    order = np.argsort(q_dates)
    for s in range(0, n, chunk):
        idx = order[s:s + chunk]
        lo, hi = q_dates[idx].min() + lo_off, q_dates[idx].max() + hi_off
        a, b = np.searchsorted(m_dates, lo, "left"), np.searchsorted(m_dates, hi, "right")
        if b <= a:
            continue
        sims = q_emb[idx] @ m_emb[a:b].T
        md = m_dates[a:b][None, :]
        qd = q_dates[idx][:, None]
        mask = (md >= qd + lo_off) & (md < qd + hi_off)
        sims = np.where(mask, sims, -1.0)
        j = sims.argmax(1)
        best_s[idx] = sims[np.arange(len(idx)), j]
        best_i[idx] = np.where(best_s[idx] > -1, j + a, -1)
    return best_s, best_i


def main() -> None:
    m_ids, m_dates, m_emb, m_ch = [], [], [], []
    for ch in MEDIA_TG:
        i, d, e = load(ch)
        m_ids.append(i); m_dates.append(d); m_emb.append(e); m_ch += [ch] * len(i)
    m_ids, m_dates, m_emb, m_ch = np.concatenate(m_ids), np.concatenate(m_dates), np.vstack(m_emb), np.array(m_ch)
    o = np.argsort(m_dates)
    m_ids, m_dates, m_emb, m_ch = m_ids[o], m_dates[o], m_emb[o], m_ch[o]

    det = Detector()
    text = {}
    for ch in NON_MEDIA + MEDIA_TG:
        for m in json.loads((ROOT / "data" / "raw" / f"telegram_{ch}.json").read_text(encoding="utf-8")):
            text[(ch, m["id"])] = det.clean(m.get("text") or "")[:600]

    frames = []
    for ch in NON_MEDIA:
        q_ids, q_dates, q_emb = load(ch)
        b_s, b_i = best(q_emb, q_dates, m_emb, m_dates, -H48, np.timedelta64(0, "s"))
        a_s, _ = best(q_emb, q_dates, m_emb, m_dates, np.timedelta64(1, "s"), H48 + np.timedelta64(1, "s"))
        c_s, _ = best(q_emb, q_dates, m_emb, m_dates, -SHIFT - H48, -SHIFT)
        jac, lag = [], []
        for k in range(len(q_ids)):
            if b_i[k] < 0:
                jac.append(np.nan); lag.append(np.nan); continue
            t1 = trigrams(text[(ch, int(q_ids[k]))])
            t2 = trigrams(text[(m_ch[b_i[k]], int(m_ids[b_i[k]]))])
            jac.append(len(t1 & t2) / len(t1 | t2) if t1 and t2 else 0.0)
            lag.append((q_dates[k] - m_dates[b_i[k]]).astype("timedelta64[m]").astype(int))
        frames.append(pd.DataFrame({
            "channel": ch, "msg_id": q_ids, "date": q_dates.astype(str),
            "sim_before": b_s.round(4), "sim_after": a_s.round(4), "sim_control": c_s.round(4),
            "match_channel": np.where(b_i >= 0, m_ch[np.maximum(b_i, 0)], ""),
            "match_msg_id": np.where(b_i >= 0, m_ids[np.maximum(b_i, 0)], -1),
            "lag_minutes": lag, "trigram_jaccard": np.round(jac, 4),
        }))
        print(ch, len(q_ids), flush=True)
    df = pd.concat(frames)
    df.to_csv(OUT / f"semantic_matches_{TAG}.csv.gz", index=False)
    for th in (0.75, 0.80, 0.85, 0.90):
        print(th, "before", round(100 * (df.sim_before >= th).mean(), 2), "control", round(100 * (df.sim_control >= th).mean(), 2),
              "after", round(100 * (df.sim_after >= th).mean(), 2))


if __name__ == "__main__":
    main()
