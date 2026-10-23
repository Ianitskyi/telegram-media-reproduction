"""Семантичні збіги з матеріалами САЙТІВ медіа — лише там, де корпус статей має дати.

Корпус статей (media_all_articles.json) — RSS-знімок: 2 509 статей, 1 236 з датою, майже всі
квітень 2026. Тому аналіз обмежено ВСІМА повідомленнями 7 немедійних каналів з 19.03 по 21.04.2026
і лише датованими статтями. Статті без дати не використовуються (у v1 вони збігались із будь-яким роком).

before  — max подібність до статті, опублікованої в [t-48 год, t)
after   — max подібність до статті, опублікованої в (t, t+48 год]  (контроль напрямку)

Запуск: python -m src.v2.semantic_articles [MODEL_DIR]
Вихід: results/v2/semantic_articles_apr2026.csv
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.v2.aggregate import NON_MEDIA
from src.v2.detect import ROOT
from src.v2.semantic_match import H48, best
from src.v2.detect import Detector
from src.v2.embed import prepare

MODEL = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "models" / "minilm"
START = np.datetime64("2026-03-19T00:00:00")  # статті з датою щільно йдуть з 17.03; +48 год


def main() -> None:
    from sentence_transformers import SentenceTransformer
    arts = json.loads((ROOT / "data" / "raw" / "media_all_articles.json").read_text(encoding="utf-8"))
    rows = [(src, a) for src, lst in arts.items() for a in lst if a.get("publish_date")]
    dates = pd.to_datetime(pd.Series([a["publish_date"] for _, a in rows]), utc=True, errors="coerce", format="ISO8601")
    keep = dates.notna().values
    rows = [r for r, k in zip(rows, keep) if k]
    a_dates = dates[keep].dt.tz_convert(None).values.astype("datetime64[s]")
    texts = [" ".join(f"{a.get('title', '')}. {a.get('text', '')}".split())[:400] for _, a in rows]
    model = SentenceTransformer(str(MODEL), device="cpu")
    a_emb = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)
    o = np.argsort(a_dates)
    a_dates, a_emb = a_dates[o], a_emb[o]
    a_src = np.array([s for s, _ in rows])[o]
    a_title = np.array([a.get("title", "") for _, a in rows])[o]
    a_url = np.array([a.get("url", "") for _, a in rows])[o]
    print("dated articles", len(a_dates), "range", a_dates.min(), a_dates.max(),
          "April 2026:", int(((a_dates >= START) & (a_dates < np.datetime64("2026-05-01"))).sum()))
    frames = []
    for ch in NON_MEDIA:
        msgs = json.loads((ROOT / "data" / "raw" / f"telegram_{ch}.json").read_text(encoding="utf-8"))
        ids, dd, tx = prepare(Detector(), msgs)  # усі пости, без вибірки
        d = pd.to_datetime(pd.Series(dd), utc=True).dt.tz_convert(None).values.astype("datetime64[s]")
        sel = d >= START
        ids, d = np.array(ids)[sel], d[sel]
        e = model.encode([t for t, k in zip(tx, sel) if k], batch_size=64, normalize_embeddings=True,
                         show_progress_bar=False).astype(np.float32)
        b_s, b_i = best(e, d, a_emb, a_dates, -H48, np.timedelta64(0, "s"))
        f_s, _ = best(e, d, a_emb, a_dates, np.timedelta64(1, "s"), H48 + np.timedelta64(1, "s"))
        frames.append(pd.DataFrame({
            "channel": ch, "msg_id": ids, "date": d.astype(str), "sim_before": b_s.round(4), "sim_after": f_s.round(4),
            "article_source": np.where(b_i >= 0, a_src[np.maximum(b_i, 0)], ""),
            "article_title": np.where(b_i >= 0, a_title[np.maximum(b_i, 0)], ""),
            "article_url": np.where(b_i >= 0, a_url[np.maximum(b_i, 0)], ""),
        }))
    df = pd.concat(frames)
    df.to_csv(ROOT / "results" / "v2" / "semantic_articles_apr2026.csv", index=False)
    print("messages", len(df))
    for th in (0.75, 0.80, 0.85, 0.90):
        print(th, "before", round(100 * (df.sim_before >= th).mean(), 2), "after", round(100 * (df.sim_after >= th).mean(), 2))


if __name__ == "__main__":
    main()
