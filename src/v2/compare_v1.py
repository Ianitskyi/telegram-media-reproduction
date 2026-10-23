"""Порівняння зі старим (v1) детектором для 7 немедійних каналів.

Проганяє оригінальні LinkDetector і MentionDetector (src/analyzers/, код Олега) і
зіставляє з v2 по кожному повідомленню. Семантику v1 тут не відтворено (див. WORKLOG).

Запуск: python -m src.v2.compare_v1
Вихід: results/v2/v1_vs_v2.csv.gz, results/v2/v1_vs_v2_summary.json,
       validation/v1_only_sample.csv — випадкова вибірка повідомлень, які v1 вважає згадкою, а v2 — ні.
"""
import gzip
import csv
import json
import random
from collections import Counter

import pandas as pd

from src.analyzers.link_detector import LinkDetector
from src.analyzers.mention_detector import MentionDetector
from src.v2.aggregate import NON_MEDIA
from src.v2.detect import ROOT

OUT = ROOT / "results" / "v2"


def main() -> None:
    L, M = LinkDetector(), MentionDetector()
    data = json.loads((ROOT / "data" / "raw" / "telegram_all_messages.json").read_text(encoding="utf-8"))
    v2 = pd.read_csv(OUT / "messages_link_mention.csv.gz", dtype={"link_ids": str, "mention_ids": str})
    v2 = v2[v2.channel.isin(NON_MEDIA)].set_index(["channel", "msg_id"])
    rows, pool = [], []
    for ch in NON_MEDIA:
        for m in data[ch]:
            mm = dict(m); mm["urls"] = list(m.get("urls") or [])
            l1 = L.detect_media_links(mm)["has_media_link"]
            md = M.detect_mentions(mm)
            r2 = v2.loc[(ch, m["id"])]
            l2, m2 = isinstance(r2.link_ids, str), isinstance(r2.mention_ids, str)
            rows.append((ch, m["id"], m["date"][:10], int(l1), int(md["has_media_mention"]), int(l2), int(m2),
                         "; ".join(md["mentioned_media"])))
            if md["has_media_mention"] and not l1 and not (l2 or m2):
                pool.append((ch, m["id"], m["date"][:10], "; ".join(md["mentioned_media"]), m.get("text") or ""))
    df = pd.DataFrame(rows, columns=["channel", "msg_id", "date", "v1_link", "v1_mention", "v2_link", "v2_mention", "v1_mentioned"])
    df.to_csv(OUT / "v1_vs_v2.csv.gz", index=False)
    n = len(df)
    v1_any = (df.v1_link | df.v1_mention)
    v2_any = (df.v2_link | df.v2_mention)
    cnt = Counter(name.strip() for s in df.loc[df.v1_mention.astype(bool) & ~v2_any.astype(bool), "v1_mentioned"] for name in s.split(";") if name.strip())
    summary = {
        "messages": n,
        "v1_link_pct": round(100 * df.v1_link.mean(), 2),
        "v1_mention_pct": round(100 * df.v1_mention.mean(), 2),
        "v1_link_or_mention_pct": round(100 * v1_any.mean(), 2),
        "v2_link_or_mention_pct": round(100 * v2_any.mean(), 2),
        "v1_positive_v2_negative": int((v1_any.astype(bool) & ~v2_any.astype(bool)).sum()),
        "v2_positive_v1_negative": int((~v1_any.astype(bool) & v2_any.astype(bool)).sum()),
        "v1_old_reported_total_pct": 32.39,
        "implied_v1_semantic_only_pct": round(32.39 - 100 * v1_any.mean(), 2),
        "top_v1_only_media": cnt.most_common(30),
    }
    (OUT / "v1_vs_v2_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    random.seed(20261023)
    smp = random.sample(pool, min(200, len(pool)))
    (ROOT / "validation").mkdir(exist_ok=True)
    with open(ROOT / "validation" / "v1_only_sample.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "channel", "msg_id", "date", "v1_says_mentioned", "text", "claude_verdict", "claude_note"])
        for i, r in enumerate(smp, 1):
            w.writerow([i, *r, "", ""])
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
