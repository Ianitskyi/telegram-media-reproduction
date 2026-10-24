"""Вибірка для ручної валідації класифікатора атрибуції v3.2 (план ChatGPT, 2026-10-24).

1 500 повідомлень:
  A) 1 045 випадкових — 19 непорожніх страт (канал × період) × 55 (рахуємо recall, поширеність і реальну частку помилок);
  B)   450 позитивних за прогнозом прототипу — 150 textual, 150 hyperlink, 150 both / ≥2 джерела
       (стабільна оцінка precision за механізмами); беруться з окремого випадкового пулу, не з A.
300 повідомлень (20%: 209 з A — по 11 на страту, 90 з B — по 30 на механізм) кодують ДВОЄ незалежно.

Кодери бачать лише текст (сліпе кодування, без прогнозу алгоритму).
Запуск: python -m src.v3.validation_sample
Вихід: validation/v3_validation_coding.xlsx  — аркуш для кодування (випадаючі списки) + довідка;
       validation/v3_validation_blind.csv    — те саме без форматування;
       validation/v3_validation_key.csv      — прогнози алгоритму (НЕ давати кодерам).
Повний корпус НЕ обробляється: прототип запускається лише на ~10 тис. випадкових повідомлень.
"""
import json
import random
import re

import pandas as pd

from src.v2.detect import Detector, ROOT
from src.v3.attribution import Attribution, MD_LINK

NON_MEDIA = ["truexanewsua", "kievinfo_kyiv", "UaOnlii", "vanek_nikolaev", "lachentyt", "times_ukraina", "batalionmonako"]
PERIODS = [("P1_pre", None, "2022-02-24"), ("P2_2022_23", "2022-02-24", "2024-01-01"), ("P3_2024_26", "2024-01-01", None)]
SEED = 20261025
N_RANDOM, N_POOL, N_POS = 55, 400, 150  # 19 непорожніх страт × 55 ≈ 1 050 (двох каналів до 24.02.2022 не існувало)

CONTENT = ["informational", "alert", "technical"]
PROMO = ["no", "ad", "self_promo"]
YESNO = ["yes", "no"]
METHOD = ["textual", "hyperlink", "both", "none"]
TYPES = ["ua_media", "foreign_media", "russian_media", "ua_official", "foreign_official", "russian_official", "politician",
         "expert", "company_organization", "telegram", "social", "unnamed_media", "eyewitness", "anonymous", "person_other", "other"]
CODER_COLS = ["M1_content_type", "M2_promotional", "M3_has_explicit_source", "M4_attribution_method", "M5_n_direct_sources",
              "M6_has_nested_source", "SOURCES", "DESTINATIONS", "coder_comment"]


def display_text(raw: str, boiler: set) -> str:
    out = []
    for ln in (raw or "").splitlines():
        clean = MD_LINK.sub(lambda m: m.group(1), ln).strip()
        if clean in boiler:
            continue
        out.append(MD_LINK.sub(lambda m: f"{m.group(1)} [{m.group(2)}]", ln))
    return "\n".join(out).strip()[:3000]


def fmt_sources(r) -> str:
    return "\n".join(f"{s['name']}; {s['type']}; {s['specificity']}; {s.get('source_level', 'direct')}; "
                     f"{'link' if s.get('actor_inferred_from_link') else 'text'}" for s in r["attributed_sources"])


def main() -> None:
    rnd = random.Random(SEED)
    at, det = Attribution(), Detector()
    rand_rows, pool_rows = [], []
    for ch in NON_MEDIA:
        msgs = json.loads((ROOT / "data" / "raw" / f"telegram_{ch}.json").read_text(encoding="utf-8"))
        boiler = det.boilerplate_lines(msgs)
        for pname, a, b in PERIODS:
            pool = [m for m in msgs if (not a or m["date"] >= a) and (not b or m["date"] < b) and (m.get("text") or "").strip()]
            take = rnd.sample(pool, min(N_RANDOM + N_POOL, len(pool)))
            for k, m in enumerate(take):
                r = at.analyze(m, ch, boiler)
                row = {"channel": ch, "period": pname, "date": m["date"][:10], "msg_id": m["id"],
                       "text": display_text(m.get("text"), boiler),
                       "pred_content_type": r["content_type"], "pred_promotional": r["promotional"],
                       "pred_message_type": r["message_type"], "pred_in_denominator": r["in_primary_denominator"],
                       "pred_has_explicit_source": r["has_explicit_source"], "pred_has_textual_source": r["has_textual_source"],
                       "pred_method": r["attribution_method"], "pred_n_sources": r["n_sources"],
                       "pred_has_nested": r["has_embedded_source"], "pred_sources": fmt_sources(r),
                       "pred_destinations": "\n".join(f"{d['entity']}; {d['platform_type']}" for d in r["linked_destinations"])}
                (rand_rows if k < N_RANDOM else pool_rows).append(row)
    A = pd.DataFrame(rand_rows).assign(subsample="A_random")
    P = pd.DataFrame(pool_rows)
    picks = []
    for name, mask in (("B_textual", P.pred_method == "textual"),
                       ("B_hyperlink", P.pred_method == "hyperlink"),
                       ("B_both_multi", (P.pred_method == "both") | (P.pred_n_sources >= 2))):
        cand = P[mask & ~P.index.isin([i for p in picks for i in p.index])]
        picks.append(cand.sample(min(N_POS, len(cand)), random_state=SEED).assign(subsample=name))
    B = pd.concat(picks)
    df = pd.concat([A, B], ignore_index=True)

    # подвійне кодування: 10 на страту з A + 30 на механізм з B
    df["double_coded"] = False
    for _, g in df[df.subsample == "A_random"].groupby(["channel", "period"]):
        df.loc[g.sample(min(11, len(g)), random_state=SEED).index, "double_coded"] = True
    for s in ("B_textual", "B_hyperlink", "B_both_multi"):
        g = df[df.subsample == s]
        df.loc[g.sample(min(30, len(g)), random_state=SEED).index, "double_coded"] = True

    df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)  # кодер не бачить підвибірку
    df.insert(0, "item_id", [f"V{i:04d}" for i in range(1, len(df) + 1)])
    key = df.drop(columns=["text"])
    key.to_csv(ROOT / "validation" / "v3_validation_key.csv", index=False, encoding="utf-8-sig")
    blind = df[["item_id", "channel", "date", "msg_id", "double_coded", "text"]].copy()
    for c in CODER_COLS:
        blind[c] = ""
    blind.to_csv(ROOT / "validation" / "v3_validation_blind.csv", index=False, encoding="utf-8-sig")
    write_xlsx(blind)
    print(df.subsample.value_counts().to_dict(), "double:", int(df.double_coded.sum()), "total:", len(df))
    print("random A — прогноз з явним джерелом (знаменник):",
          round(100 * A[A.pred_in_denominator].pred_has_explicit_source.mean(), 1), "%")


def write_xlsx(blind: pd.DataFrame) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "Кодування"
    cols = list(blind.columns)
    ws.append(cols)
    for row in blind.itertuples(index=False):
        ws.append(["так" if v is True else "" if v is False else v for v in row])
    widths = {"item_id": 8, "channel": 14, "date": 11, "msg_id": 8, "double_coded": 7, "text": 70, "SOURCES": 45,
              "DESTINATIONS": 35, "coder_comment": 30}
    for i, c in enumerate(cols, 1):
        letter = ws.cell(1, i).column_letter
        ws.column_dimensions[letter].width = widths.get(c, 16)
        ws.cell(1, i).font = Font(bold=True)
        if c in CODER_COLS:
            ws.cell(1, i).fill = PatternFill("solid", fgColor="FFF2CC")
    for r in ws.iter_rows(min_row=2):
        for cell in r:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "G2"
    n = ws.max_row
    for col, opts in (("M1_content_type", CONTENT), ("M2_promotional", PROMO), ("M3_has_explicit_source", YESNO),
                      ("M4_attribution_method", METHOD), ("M6_has_nested_source", YESNO)):
        letter = ws.cell(1, cols.index(col) + 1).column_letter
        dv = DataValidation(type="list", formula1='"' + ",".join(opts) + '"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{letter}2:{letter}{n}")
    h = wb.create_sheet("Довідка")
    for line in HELP:
        h.append([line])
    h.column_dimensions["A"].width = 140
    wb.save(ROOT / "validation" / "v3_validation_coding.xlsx")


HELP = [
    "Коротка довідка для кодера (повна інструкція — validation/CODEBOOK_v3.md)",
    "",
    "Кодуйте лише те, що видно в тексті. Прогнозу алгоритму ви не бачите — так і має бути.",
    "Рядки з double_coded = так кодують дві людини незалежно (не радячись).",
    "",
    "M1_content_type: informational (змістовне) / alert (оперативне оповіщення про загрозу) / technical (порожнє, лише емодзі, службове)",
    "M2_promotional: no / ad (реклама) / self_promo (самопромо каналу). Промо НЕ скасовує змісту: повідомлення може бути і alert, і self_promo.",
    "M3_has_explicit_source: yes, якщо адміністратор явно вказує, ЗВІДКИ інформація (текстом або посиланням на медіа / офіційний сайт / Telegram-канал).",
    "M4_attribution_method: textual / hyperlink / both / none",
    "M5_n_direct_sources: скільки різних ПРЯМИХ джерел (число)",
    "M6_has_nested_source: yes, якщо є «джерело джерела» («CBS із посиланням на чиновників»)",
    "",
    "SOURCES — по одному джерелу в рядку (Alt+Enter у клітинці), поля через «;»:",
    "   назва; тип; конкретність; рівень; спосіб",
    "   тип: " + ", ".join(TYPES),
    "   конкретність: named / generic / anonymous;  рівень: direct / embedded;  спосіб: text / link",
    "   приклад:  CBS News; foreign_media; named; direct; text",
    "             американські чиновники; anonymous; anonymous; embedded; text",
    "DESTINATIONS — по одному посиланню в рядку:  домен; тип платформи; відношення до джерела",
    "   тип платформи: ua_media_site, foreign_media_site, russian_media_site, official_site, foreign_official_site, social_platform, telegram_channel, other_site",
    "   відношення: same_actor / intermediary / platform_hosting_actor / unrelated / unclear",
    "   приклад:  nv.ua; ua_media_site; intermediary   (у тексті «— The Washington Post», посилання на NV)",
]


if __name__ == "__main__":
    main()
