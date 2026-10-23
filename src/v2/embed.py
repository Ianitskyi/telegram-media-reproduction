"""Векторні представлення (ембединги) повідомлень для семантичного аналізу.

Модель: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (та сама, що у v1),
файли — локально в models/minilm (SHA256 model.safetensors =
eaa086f0ffee582aeb45b36e34cdd1fe2d6de2bef61f8a559a1bbc9bd955917b, як на Hugging Face).

Текст: очищений (без URL і markdown-посилань, без рядків-підписів каналу), перші 400 символів
(модель однаково обрізає вхід до 128 токенів). Повідомлення з очищеним текстом < 50 символів
не кодуються (як у v1), але лишаються в знаменнику.

Запуск: python -m src.v2.embed [MODEL_DIR]
Немедійні канали — стабільна вибірка 30% (in_sample), канали медіа — повністю.
Вихід: results/v2/emb/<channel>.npz (ids, dates, emb float16)
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

from src.v2.detect import Detector, ROOT

MODEL = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "models" / "minilm"
FULL = os.environ.get("FULL") == "1"  # FULL=1: немедійні канали повністю, у results/v2/emb_full/
OUT = ROOT / "results" / "v2" / ("emb_full" if FULL else "emb")
MIN_LEN, MAX_CHARS = 50, 400
SAMPLE_PCT = 30  # немедійні канали: стабільна вибірка 30% повідомлень (за md5 від channel:id)
NON_MEDIA = {"truexanewsua", "kievinfo_kyiv", "UaOnlii", "vanek_nikolaev", "lachentyt", "times_ukraina", "batalionmonako"}


def in_sample(ch, msg_id) -> bool:
    import hashlib
    return int(hashlib.md5(f"{ch}:{msg_id}".encode()).hexdigest(), 16) % 100 < SAMPLE_PCT


def prepare(det, msgs, sample_channel=None):
    boiler = det.boilerplate_lines(msgs)
    ids, dates, texts = [], [], []
    for m in msgs:
        if sample_channel and not in_sample(sample_channel, m["id"]):
            continue
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
    order = ["suspilnenews", "ukrpravda_news", "truexanewsua", "kievinfo_kyiv", "UaOnlii", "vanek_nikolaev", "lachentyt",
             "times_ukraina", "batalionmonako", "TCH_channel", "uniannet"]
    only = os.environ.get("ONLY")
    for ch in order:
        if only and ch != only:
            continue
        f = OUT / f"{ch}.npz"
        if f.exists():
            continue
        t0 = time.time()
        msgs = json.loads((ROOT / "data" / "raw" / f"telegram_{ch}.json").read_text(encoding="utf-8"))
        ids, dates, texts = prepare(det, msgs, ch if (ch in NON_MEDIA and not FULL) else None)
        n_all = len(msgs); del msgs
        parts = []
        tmp = OUT / f"_partial_{ch}"  # порції зберігаються — після перезапуску робота продовжується
        tmp.mkdir(exist_ok=True)
        for s in range(0, len(texts), 4000):
            pf = tmp / f"{s:07d}.npy"
            if pf.exists():
                parts.append(np.load(pf)); continue
            e = model.encode(texts[s:s + 4000], batch_size=64, normalize_embeddings=True,
                             show_progress_bar=False).astype(np.float16)
            np.save(pf, e); parts.append(e)
            print(f"  {ch}: {s + len(texts[s:s + 4000])}/{len(texts)} {time.time()-t0:.0f}s", flush=True)
        emb = np.vstack(parts)
        np.savez_compressed(f, ids=np.array(ids), dates=np.array(dates), emb=emb)
        import shutil; shutil.rmtree(tmp, ignore_errors=True)
        print(f"{ch}: {len(texts)} encoded of {n_all} in {time.time()-t0:.0f}s", flush=True)
    print("done")


if __name__ == "__main__":
    main()
