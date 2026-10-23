#!/bin/bash
# Черга семантичних розрахунків; відновлювана (вже пораховане пропускається).
cd "$(dirname "$0")/.." || exit 1
export HF_HUB_OFFLINE=1 PYTHONUNBUFFERED=1
M=/home/claude/models/minilm
ONLY=uniannet python3 -m src.v2.embed $M
for ch in UaOnlii kievinfo_kyiv lachentyt times_ukraina batalionmonako vanek_nikolaev; do
  FULL=1 ONLY=$ch python3 -m src.v2.embed $M
done
echo QUEUE_EMBED_DONE
