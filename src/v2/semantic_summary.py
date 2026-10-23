"""Підсумкові таблиці семантичних збігів.

Запуск: python -m src.v2.semantic_summary <TAG>   (напр. all4_full)
Вихід: results/v2/semantic_summary_<TAG>.md
"""
import sys

import pandas as pd

from src.v2.detect import ROOT

TAG = sys.argv[1] if len(sys.argv) > 1 else "whitelist2"
TH = [0.80, 0.85, 0.90]


def rates(x, th):
    b, a, c = x.sim_before >= th, x.sim_after >= th, x.sim_control >= th
    return pd.Series({
        "n": len(x),
        "media_before_%": 100 * b.mean(),
        "control_%": 100 * c.mean(),
        "excess_%": 100 * (b.mean() - c.mean()),
        "media_after_%": 100 * a.mean(),
        "closer_media_first_%": 100 * (b & (x.sim_before >= x.sim_after)).mean(),
        "closer_channel_first_%": 100 * (a & (x.sim_after > x.sim_before)).mean(),
        "near_verbatim_media_first_%": 100 * (b & (x.trigram_jaccard >= 0.3)).mean(),
    })


def main() -> None:
    df = pd.read_csv(ROOT / "results" / "v2" / f"semantic_matches_{TAG}.csv.gz")
    df["year"] = df.date.str[:4]
    out = [f"# Семантичні збіги — {TAG}", "", f"Повідомлень: {len(df):,}", ""]
    out += ["## Усі разом", "", pd.DataFrame({th: rates(df, th) for th in TH}).T.round(2).to_markdown(), ""]
    out += ["## По каналах (поріг 0,85)", "", df.groupby("channel").apply(rates, 0.85).round(2).to_markdown(), ""]
    out += ["## По роках (поріг 0,85)", "", df.groupby("year").apply(rates, 0.85).round(2).to_markdown(), ""]
    h = df[df.sim_before >= 0.85]
    out += ["## Пари «медіа раніше» ≥0,85", "",
            f"- медіана затримки: {h.lag_minutes.median():.0f} хв; до 60 хв: {100*(h.lag_minutes <= 60).mean():.0f}%",
            f"- частка майже дослівних (Jaccard ≥0,3): {100*(h.trigram_jaccard >= 0.3).mean():.0f}%",
            f"- за каналом медіа: {h.match_channel.value_counts().to_dict()}", ""]
    (ROOT / "results" / "v2" / f"semantic_summary_{TAG}.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
