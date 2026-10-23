"""Векторні представлення (ембединги) повідомлень для семантичного аналізу.

Модель: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (та сама, що у v1),
файли — локально в models/minilm (SHA256 model.safetensors =
eaa086f0ffee582aeb45b36e34cdd1fe2d6de2bef61f8a559a1bbc9bd955917b, як на Hugging Face).

Текст: очищений (без URL і markdown-посилань, без рядків-підписів каналу), перші 400 символів
(модель однаково обрізає вхід до 128 токенів). Повідомлення з очищеним текстом < 50 символів
не кодуються (як у v1), але лишаються в знаменнику.

Запуск: python -m src.v2.embed [MODEL_DIR]
Вихід: results/v2/emb/<channel>.npz (ids, dates, emb float16)
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

from src.v2.detect import Detector, ROOT

MODEL = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "models" / "minilm"
OUT = ROOT / "results" / "v2" / "emb"
MIN_LEN, MAX_CHARS = 50, 400


def prepare(det, msgs):
    boiler = det.boilerplate_lines(msgs)
    ids, dates, texts = [], [], []
    for m in msgs:
        t = det.clean(m.get("text") or "")
        t = "\n".join(ln for ln in t.splitlines() if ln.strip() not in boiler)
        t = " ".join(t.replace("*", " ").replace("_", " ").split())
        if len(t) >= MIN_LEN:
            ids.append(m["id"]); dates.append(m["date"]); texts.append(t[:MAX_CHARS])
    return ids, dates, texts


def main() -> None:
    import torch
    from sentence_transformers import SentenceTransformer
    torch.set_num_threads(max(1, torch.get_num_threads()))
    OUT.mkdir(parents=True, exist_ok=True)
    model = SentenceTransformer(str(MODEL), device="cpu")
    det = Detector()
    order = ["truexanewsua", "kievinfo_kyiv", "UaOnlii", "vanek_nikolaev", "lachentyt", "times_ukraina",
             "batalionmonako", "suspilnenews", "ukrpravda_news", "TCH_channel", "uniannet"]
    for ch in order:
        f = OUT / f"{ch}.npz"
        if f.exists():
            continue
        t0 = time.time()
        msgs = json.loads((ROOT / "data" / "raw" / f"telegram_{ch}.json").read_text(encoding="utf-8"))
        ids, dates, texts = prepare(det, msgs)
        n_all = len(msgs); del msgs
        parts = []
        for s in range(0, len(texts), 4000):
            parts.append(model.encode(texts[s:s + 4000], batch_size=64, normalize_embeddings=True,
                                      show_progress_bar=False).astype(np.float16))
            print(f"  {ch}: {s + len(texts[s:s + 4000])}/{len(texts)} {time.time()-t0:.0f}s", flush=True)
        emb = np.vstack(parts)
        np.savez_compressed(f, ids=np.array(ids), dates=np.array(dates), emb=emb)
        print(f"{ch}: {len(texts)} encoded of {n_all} in {time.time()-t0:.0f}s", flush=True)
    print("done")


if __name__ == "__main__":
    main()
