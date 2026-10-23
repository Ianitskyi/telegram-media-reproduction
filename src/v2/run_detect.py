"""Запускає детектори посилань і згадок v2 на всьому корпусі.

Вихід: results/v2/messages_link_mention.csv.gz — одне повідомлення на рядок.
Запуск: python -m src.v2.run_detect
"""
import csv
import gzip
import json
import time
from collections import Counter
from pathlib import Path

from src.v2.detect import Detector, ROOT

RAW = ROOT / "data" / "raw" / "telegram_all_messages.json"
OUT = ROOT / "results" / "v2"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    det = Detector()
    data = json.loads(RAW.read_text(encoding="utf-8"))
    boiler_report = {}
    alias_hits = Counter()
    t0 = time.time()
    with gzip.open(OUT / "messages_link_mention.csv.gz", "wt", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["channel", "msg_id", "date", "clean_len", "link_ids", "mention_ids",
                    "self_link", "self_mention", "mention_hits"])
        for ch, msgs in data.items():
            boiler = det.boilerplate_lines(msgs)
            boiler_report[ch] = sorted(boiler)
            for m in msgs:
                r = det.analyze(m, ch, boiler)
                for i, s in r["hits"]:
                    alias_hits[(i, s)] += 1
                w.writerow([ch, m.get("id"), m.get("date"), r["clean_len"],
                            ";".join(map(str, r["link_ids"])), ";".join(map(str, r["mention_ids"])),
                            int(r["self_link"]), int(r["self_mention"]),
                            " | ".join(s for _, s in r["hits"])])
            print(f"{ch}: {len(msgs)} msgs, boilerplate lines {len(boiler)}, {time.time()-t0:.0f}s", flush=True)
    (OUT / "boilerplate_lines.json").write_text(json.dumps(boiler_report, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(OUT / "mention_alias_hits.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["media_id", "media", "matched_text", "count"])
        for (i, s), k in alias_hits.most_common():
            w.writerow([i, det.names[i], s, k])
    print("done", time.time() - t0)


if __name__ == "__main__":
    main()
