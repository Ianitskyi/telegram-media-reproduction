"""Заміна переглянутих повідомлень (витік, аудит ChatGPT 2026-10-26).

Під час розробки інтерфейсу Claude бачив 12 повідомлень із V0001–V0100. Консервативно виключаємо з фінальних
метрик увесь пакет V0001–V0100 (leak_excluded=True). 67 A-повідомлень цього пакета замінено на R0001–R0067:
нова випадкова вибірка (seed 20261027) з тих самих страт канал×період, що й виключені A-повідомлення.
33 B-повідомлення не замінюються (B — збагачена частина, лише для точності механізму).

  python -m src.v3.replacement   → дописує R-рядки у v3_validation_key.csv і v3_validation_blind.csv (ідемпотентно)
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
VAL = ROOT / "validation"
LEAK_RANGE = ("V0001", "V0100")


def leak_excluded(item_id: str) -> bool:
    return LEAK_RANGE[0] <= item_id <= LEAK_RANGE[1]


def main() -> None:
    rep = pd.read_csv(VAL / "blind" / "replacement_items.csv", dtype=str).fillna("")
    key = pd.read_csv(VAL / "v3_validation_key.csv", dtype=str).fillna("")
    blind = pd.read_csv(VAL / "v3_validation_blind.csv", dtype=str).fillna("")
    new = rep[~rep.item_id.isin(key.item_id)]
    if len(new):
        k = pd.DataFrame({c: "" for c in key.columns}, index=range(len(new)))
        for c in ("item_id", "channel", "period", "date", "msg_id"):
            k[c] = new[c].values
        k["subsample"], k["double_coded"] = "A_random", "False"
        key = pd.concat([key, k], ignore_index=True)
        b = pd.DataFrame({c: "" for c in blind.columns}, index=range(len(new)))
        for c in ("item_id", "channel", "date", "msg_id", "text"):
            b[c] = new[c].values
        b["double_coded"] = "False"
        blind = pd.concat([blind, b], ignore_index=True)
    key["leak_excluded"] = key.item_id.map(leak_excluded)
    key.to_csv(VAL / "v3_validation_key.csv", index=False, encoding="utf-8-sig")
    blind.to_csv(VAL / "v3_validation_blind.csv", index=False, encoding="utf-8-sig")
    print(f"додано {len(new)} R-рядків; виключено {int(key.leak_excluded.sum())}; активних A: "
          f"{int(((key.subsample == 'A_random') & ~key.leak_excluded).sum())}")


if __name__ == "__main__":
    main()
