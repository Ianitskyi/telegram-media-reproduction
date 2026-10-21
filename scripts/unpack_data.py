"""Розпаковує сирі дані з data/raw_xz/ у data/raw/ і перевіряє контрольні суми.

Також збирає telegram_all_messages.json у форматі, який очікує main.py
({username: [повідомлення, ...]}).

Запуск:  python scripts/unpack_data.py
"""
import hashlib
import json
import lzma
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "raw_xz"
DST = ROOT / "data" / "raw"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    expected = {}
    for line in (SRC / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        expected[name.lstrip("*")] = digest

    for xz_file in sorted(SRC.glob("*.json.xz")):
        out = DST / xz_file.name[:-3]
        if not out.exists():
            with lzma.open(xz_file, "rb") as src, open(out, "wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
        ok = sha256(out) == expected.get(out.name)
        print(f"{'OK ' if ok else 'BAD'} {out.name}")
        if not ok:
            raise SystemExit(f"Контрольна сума не збігається: {out.name}")

    combined = {}
    for f in sorted(DST.glob("telegram_*.json")):
        if f.name == "telegram_all_messages.json":
            continue
        combined[f.stem.removeprefix("telegram_")] = json.loads(f.read_text(encoding="utf-8"))
    with open(DST / "telegram_all_messages.json", "w", encoding="utf-8") as fh:
        json.dump(combined, fh, ensure_ascii=False)
    total = sum(len(v) for v in combined.values())
    print(f"telegram_all_messages.json: {len(combined)} каналів, {total:,} повідомлень")


if __name__ == "__main__":
    main()
