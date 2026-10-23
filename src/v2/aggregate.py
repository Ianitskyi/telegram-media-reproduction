"""Підсумкові таблиці v2 (посилання + згадки; семантика — окремо).

Запуск: python -m src.v2.aggregate
Вихід: results/v2/*.csv і results/v2/SUMMARY.md
"""
import json
from pathlib import Path

import pandas as pd

from src.v2.detect import ROOT

OUT = ROOT / "results" / "v2"
NON_MEDIA = ["truexanewsua", "kievinfo_kyiv", "UaOnlii", "vanek_nikolaev", "lachentyt", "times_ukraina", "batalionmonako"]
MEDIA_OWNED = ["TCH_channel", "suspilnenews", "uniannet", "ukrpravda_news"]
EXCLUDED = ["insider_zsy", "ukraina_novosti"]
INVASION = pd.Timestamp("2022-02-24", tz="UTC")


def load() -> pd.DataFrame:
    df = pd.read_csv(OUT / "messages_link_mention.csv.gz", dtype={"link_ids": str, "mention_ids": str})
    df["date"] = pd.to_datetime(df["date"], utc=True)
    df["year"] = df["date"].dt.year
    df["link"] = df["link_ids"].notna()
    df["mention"] = df["mention_ids"].notna()
    df["any"] = df["link"] | df["mention"]
    df["has_text"] = df["clean_len"] > 0
    df["group"] = df["channel"].map(lambda c: "non_media" if c in NON_MEDIA else "media_owned" if c in MEDIA_OWNED else "excluded")
    return df


def shares(g: pd.DataFrame) -> pd.Series:
    n, nt = len(g), int(g["has_text"].sum())
    return pd.Series({
        "messages": n, "with_text": nt,
        "any_pct": 100 * g["any"].mean(),
        "any_pct_of_text": 100 * g["any"].sum() / nt if nt else float("nan"),
        "link_pct": 100 * g["link"].mean(),
        "mention_pct": 100 * g["mention"].mean(),
        "link_only": int((g["link"] & ~g["mention"]).sum()),
        "mention_only": int((~g["link"] & g["mention"]).sum()),
        "link_and_mention": int((g["link"] & g["mention"]).sum()),
        "self_link_pct": 100 * g["self_link"].mean(),
        "self_mention_pct": 100 * g["self_mention"].mean(),
    })


def main() -> None:
    df = load()
    names = {m["id"]: m["name"] for m in json.loads((ROOT / "config" / "media_aliases.json").read_text(encoding="utf-8"))}
    sub = df[df.group != "excluded"]

    by_channel = sub.groupby(["group", "channel"]).apply(shares).round(2)
    by_channel.to_csv(OUT / "by_channel.csv")

    nm = df[df.group == "non_media"]
    pooled = shares(nm).round(2)
    unweighted = by_channel.loc["non_media", "any_pct"].mean()

    by_year = nm.groupby("year").apply(shares).round(2)
    by_year.to_csv(OUT / "non_media_by_year.csv")
    by_ch_year = nm.pivot_table(index="channel", columns="year", values="any", aggfunc="mean").mul(100).round(1)
    by_ch_year.to_csv(OUT / "non_media_channel_by_year.csv")
    counts_ch_year = nm.pivot_table(index="channel", columns="year", values="any", aggfunc="size")
    counts_ch_year.to_csv(OUT / "non_media_channel_by_year_counts.csv")

    # 365 днів до / після 24.02.2022 усередині кожного каналу
    rows = []
    for ch, g in nm.groupby("channel"):
        pre = g[(g.date >= INVASION - pd.Timedelta(days=365)) & (g.date < INVASION)]
        post = g[(g.date >= INVASION) & (g.date < INVASION + pd.Timedelta(days=365))]
        rows.append({"channel": ch, "pre_n": len(pre), "pre_pct": round(100 * pre["any"].mean(), 1) if len(pre) else None,
                     "post_n": len(post), "post_pct": round(100 * post["any"].mean(), 1) if len(post) else None})
    prepost = pd.DataFrame(rows)
    prepost.to_csv(OUT / "non_media_pre_post_invasion.csv", index=False)

    # Які медіа (повідомлення може посилатися/згадувати кілька)
    def explode(col):
        s = nm[col].dropna().str.split(";").explode().astype(int)
        return s.map(names).value_counts()
    top = pd.DataFrame({"link_msgs": explode("link_ids"), "mention_msgs": explode("mention_ids")}).fillna(0).astype(int)
    top["any_msgs"] = nm.assign(ids=(nm["link_ids"].fillna("") + ";" + nm["mention_ids"].fillna(""))) \
        .assign(ids=lambda x: x["ids"].str.split(";").apply(lambda l: sorted({int(i) for i in l if i}))) \
        .explode("ids").dropna(subset=["ids"])["ids"].astype(int).map(names).value_counts()
    top = top.fillna(0).astype(int).sort_values("any_msgs", ascending=False)
    top.to_csv(OUT / "non_media_top_media.csv")

    # Звіт
    lines = ["# Результати v2 — посилання і згадки (2026-10-23)", "",
             "Семантичну подібність ще не включено. Детектори — `src/v2/detect.py`, словник — `config/media_aliases.json`.",
             "Ручної валідації ще немає → усі цифри попередні.", "",
             "## 7 немедійних каналів разом", "",
             f"- повідомлень: {int(pooled.messages):,}; з текстом: {int(pooled.with_text):,}",
             f"- **посилання або згадка: {pooled.any_pct:.2f}%** усіх повідомлень ({pooled.any_pct_of_text:.2f}% повідомлень з текстом)",
             f"- незважене середнє по 7 каналах: {unweighted:.2f}%",
             f"- посилання: {pooled.link_pct:.2f}%, згадки: {pooled.mention_pct:.2f}%",
             f"- лише посилання: {int(pooled.link_only):,}; лише згадка: {int(pooled.mention_only):,}; обидва: {int(pooled.link_and_mention):,}",
             "", "Для порівняння: v1 давала 32,39% для тих самих каналів.", "",
             "## По каналах", "", by_channel.to_markdown(), "",
             "## Немедійні канали по роках (разом)", "", by_year[["messages", "any_pct", "link_pct", "mention_pct"]].to_markdown(), "",
             "## Немедійні канали: частка по роках усередині кожного каналу, %", "", by_ch_year.to_markdown(), "",
             "## 365 днів до / після 24.02.2022", "", prepost.to_markdown(index=False), "",
             "## Найчастіші медіа (немедійні канали, повідомлень)", "", top.head(25).to_markdown(), ""]
    (OUT / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
