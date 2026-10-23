"""Будує config/media_aliases.json — ручний словник назв медіа для детектора згадок v2.

Режими:
  safe — назва характерна, шукається без урахування регістру;
  cs   — з урахуванням регістру (назва збігається зі звичайним словом лише в нижньому регістрі);
  ctx  — з урахуванням регістру І лише за наявності ознаки медіа поруч
         (лапки, «пише», «за даними», «видання», підпис через тире тощо).

Шаблони — регулярні вирази; `\\w*` після основи дає відмінки
(«Українська правда» → «Української правди», «Українській правді»...).
Запуск: python config/build_media_aliases.py
"""
import json
from pathlib import Path

A = "['’ʼ]"  # апостроф у будь-якому написанні

# id -> список (режим, шаблон). id = індекс у media_sources.json
ALIASES = {
    0: [("cs", r"Суспільн(е|ого|ому|им)\b"), ("safe", r"Suspilne"), ("safe", r"Суспільне\s+(Новини|Мовлення)"),
        ("ctx", r"Общественн(ое|ого|ому|ым)\b")],
    1: [("cs", r"Еспресо\b"), ("cs", r"Эспрессо\b"), ("safe", r"Espreso"), ("cs", r"Еспресо\.?\s?TV")],
    2: [("ctx", r"Бабел(ь|я|ю|ем)\b"), ("safe", r"\bBabel\.ua"), ("ctx", r"Babel\b")],
    3: [("safe", r"Українськ\w*\s+правд\w*"), ("safe", r"Украинск\w*\s+правд\w*"), ("safe", r"Ukrainska\s+Pravda"),
        ("ctx", r"\bУП\b")],
    4: [("safe", r"Раді[оo]\s+Свобод\w*"), ("safe", r"Радио\s+Свобод\w*"), ("safe", r"Radio\s+Svoboda"),
        ("safe", r"Радіо\s+Свобод\w*")],
    5: [("safe", r"\bhromadske\b(?!\.radio)"), ("safe", r"\bХромадске\b"), ("ctx", r"Громадськ(е|ого|ому)\b(?!\s+радіо)"),
        ("ctx", r"Громадское\b(?!\s+радио)")],
    6: [("safe", r"\bZN\.UA\b"), ("safe", r"Дзеркал\w*\s+тижня"), ("safe", r"Зеркал\w*\s+недели")],
    7: [("safe", r"Тексти\.org\.ua"), ("safe", r"Texty\.org\.ua"), ("ctx", r"Текст(и|ів)\b"), ("ctx", r"Texty\b")],
    8: [("safe", r"\bLB\.ua\b"), ("ctx", r"Лів(ий|ого|ому)\s+берег\w*"), ("ctx", r"Лев(ый|ого|ому)\s+берег\w*")],
    9: [("safe", r"Укрінформ\w*"), ("safe", r"Укринформ\w*"), ("safe", r"Ukrinform")],
    10: [("ctx", r"Ґрат(и|ам|ах)\b"), ("ctx", r"Грати\b"), ("safe", r"\bGraty\b")],
    11: [("safe", r"Громадськ\w*\s+раді[оо]"), ("safe", r"Громадское\s+радио"), ("safe", r"Hromadske\s+Radio")],
    12: [("safe", r"Український\s+тиждень"), ("safe", r"Українського\s+тижня"), ("safe", r"Украинская?\s+неделя"),
         ("ctx", r"Тижн(ь|я|ю)\b")],
    13: [("ctx", r"Рубрик(а|и|у|ою)\b"), ("safe", r"\bRubryka\b")],
    14: [("cs", r"Слово\s+і\s+[Дд]іло"), ("cs", r"Слово\s+и\s+[Дд]ело")],
    15: [("safe", r"Новинарн\w*"), ("safe", r"\bNovynarnia\b")],
    16: [("safe", r"\bFrontliner\b"), ("safe", r"Фронтлайнер\w*")],
    17: [("safe", r"МикВіст\w*"), ("safe", r"НикВест\w*"), ("safe", r"\bNikVesti\b")],
    18: [("safe", r"\bHUBZ\b")],
    19: [("ctx", r"Інтент\w*"), ("ctx", r"\bIntent\b")],
    20: [("safe", r"Бахмут\.?\s?IN\.?UA"), ("safe", r"Бахмут\.in\.ua")],
    21: [("safe", r"Новин\w*\s+здорово\w*\s+людин\w*"), ("safe", r"\bНЗЛ\b")],
    22: [("ctx", r"Відбудов(а|и)\b")],
    23: [("safe", r"Східн\w*\s+Варіант\w*"), ("safe", r"Восточн\w*\s+Вариант\w*")],
    24: [("safe", r"Доступ\s+Меді[ая]")],
    25: [("ctx", r"\bЛЮК\b"), ("ctx", r"Lyuk\b")],
    26: [("ctx", r"\bМОСТ\b")],
    27: [("safe", r"18000\.com\.ua"), ("ctx", r"\b18000\b")],
    28: [("ctx", r"Махал(а|и|у|ою)\b")],
    29: [("safe", r"Полтавськ\w*\s+хвил\w*")],
    30: [("safe", r"Gwara\s+Media"), ("safe", r"Гвар[аи]\s+Меді[ая]"), ("ctx", r"Гвар(а|и)\b")],
    31: [("ctx", r"\bКУРС\b"), ("safe", r"kurs\.if\.ua")],
    32: [("safe", r"Медіаплатформ\w*\s+[«\"]?Вгору"), ("ctx", r"Вгор(у)\b")],
    33: [("ctx", r"(?<![\w-])Є(?![\w-])"), ("safe", r"\bye\.ua\b")],
    34: [("safe", r"The\s+Bucha\s+City")],
    35: [("ctx", r"Гречк(а|и)\b"), ("safe", r"gre4ka")],
    36: [("safe", r"Полтавськ\w*\s+Думк\w*")],
    37: [("safe", r"Городок\.City")],
    38: [("ctx", r"Інформер\w*")],
    39: [("safe", r"Дивись\.info"), ("safe", r"\bDyvys\.info")],
    40: [("safe", r"Чернівці\s+С4"), ("ctx", r"\bС4\b"), ("ctx", r"\bC4\b")],
    41: [("safe", r"Крим[\.\s]*Реал\w*"), ("safe", r"Крым[\.\s]*Реал\w*"), ("safe", r"Krym[\.\s]*Realii")],
    42: [("safe", r"Гард\.City"), ("safe", r"\bThe\s?Gard\b")],
    43: [("ctx", r"Наки[пп][іе]ло\b"), ("ctx", r"Накіпело\b"), ("safe", r"\bNakypilo\b")],
    44: [("safe", r"\bGalka\.if\.ua"), ("ctx", r"Галк(а|и)\b")],
    45: [("safe", r"Трибун\w*\s+Суми")],
    46: [("safe", r"Район\.in\.ua")],
    47: [("safe", r"INFORM\.ZP\.UA")],
    48: [("safe", r"Odesa\s+Online"), ("ctx", r"Одеса\s+[Оо]нлайн")],
    49: [("safe", r"Об{A}єктив[\s-]+новин\w*".format(A=A)), ("ctx", r"Об{A}єктив\w*".format(A=A)), ("ctx", r"Объектив\w*")],
    50: [("safe", r"Вільн\w*\s+раді[оо]")],
    51: [("ctx", r"Зміст\b")],
    52: [("ctx", r"Трибун\b")],
    53: [("safe", r"6262\.com\.ua"), ("ctx", r"\bО?6262\b")],
    54: [("safe", r"Локатор[\s-]+Меді[ая]")],
    55: [("ctx", r"\bCBN\b")],
    56: [("safe", r"Харків\s+Times"), ("safe", r"Харьков\s+Times")],
    57: [("ctx", r"Менщин\w*")],
    58: [("safe", r"Біляївка\.City")],
    59: [("safe", r"Житомир[\.\s]+[Іі]нфо"), ("safe", r"Zhitomir\.info")],
    60: [("safe", r"Преступност\w*\.?\s?НЕТ"), ("safe", r"Злочинност\w*\.?\s?НЕТ"), ("safe", r"\bnews\.pn\b")],
    61: [("safe", r"\b0462\.ua\b")],
    62: [("safe", r"Бердянськ\s?24"), ("safe", r"Бердянск\s?24")],
    63: [("safe", r"Харків\s+2дей"), ("safe", r"\b2day\.kh\.ua")],
    64: [("ctx", r"Слобідськ\w*\s+[Кк]ра\w*"), ("safe", r"СЛОБІДСЬКИЙ\s+КРАЙ")],
    65: [("safe", r"Молод\w*\s+буковинц\w*"), ("safe", r"Молодий\s+буковинець")],
    66: [("safe", r"Жовті\s+Води\.City")],
    67: [("safe", r"Перш\w*\s+Криворізьк\w*"), ("safe", r"Перв\w*\s+Криворожск\w*")],
    68: [("safe", r"\b061\.ua\b")],
    69: [("safe", r"\bMyNizhyn\b")],
    70: [("safe", r"Час\s+Чернігівськ\w*")],
    71: [("safe", r"Фарватер\.?\s?Схід"), ("ctx", r"Фарватер\w*")],
    72: [("ctx", r"На\s+межі\b")],
    73: [("ctx", r"Нов\w*\s+українськ\w*\s+школ\w*")],
    74: [("safe", r"Реальн\w*\s+газет\w*")],
    75: [("ctx", r"Тво[єє]\s+[Мм]істо\b")],
    76: [("ctx", r"Цукр\b"), ("safe", r"cukr\.city")],
    77: [("safe", r"Куп{A}янськ\.City".format(A=A))],
    78: [("ctx", r"Думк(а|и)\b"), ("safe", r"dumka\.media")],
    79: [("safe", r"Сєвєродонецьк\s+[Оо]нлайн")],
    80: [("safe", r"0512\.com\.ua"), ("ctx", r"\bО?0512\b")],
    81: [("safe", r"\bVarosh\b")],
    82: [("safe", r"Глухів\.City")],
    83: [("safe", r"\bFinance\.ua\b")],
    84: [("safe", r"Горинь\s+[Іі]нфо")],
    85: [("ctx", r"Новин\w*\s+Донбас\w*"), ("ctx", r"Новост\w*\s+Донбасс\w*")],
    86: [("safe", r"Інформ\s+Агенці\w*\s+Вчасно"), ("ctx", r"Вчасно\b")],
    87: [("safe", r"\b0629\.com\.ua")],
    88: [("ctx", r"Карачун\w*")],
    89: [("safe", r"Кременчуцьк\w*\s+Телеграф\w*")],
    90: [("safe", r"\bGrivnaUA\b")],
    91: [("safe", r"Медіа\s+агентств\w*\s+АСС")],
    92: [("safe", r"Еспресо[:\.\s]+Біла\s+Церква")],
    93: [("safe", r"\bMind\.ua\b"), ("ctx", r"\bMind\b")],
    94: [("safe", r"20\s?хвилин\s+Вінниц\w*"), ("ctx", r"20\s?хвилин\b"), ("safe", r"20minut")],
    95: [("ctx", r"Слово\s+правди")],
    96: [("safe", r"\bmisto\.media\b")],
    97: [("safe", r"Перш\w*\s+Запорізьк\w*")],
    98: [("ctx", r"\bSODA\b")],
    99: [("ctx", r"Букв(и|ам)\b"), ("safe", r"\bBukvy\b")],
    100: [("cs", r"The\s+Page\b")],
    101: [("ctx", r"\bSpeka\b"), ("ctx", r"Спек(а|и)\b")],
    102: [("cs", r"Мілітарн(ий|ого|ому)\b"), ("safe", r"\bMilitarnyi\b")],
    103: [("safe", r"Освіторі\w*")],
    104: [("cs", r"\bШОТАМ\b"), ("safe", r"\bShotam\b")],
    105: [("safe", r"Голос\w*\s+Криму"), ("safe", r"Голос\w*\s+Крыма")],
    106: [("safe", r"КРВ\.?\s?медіа")],
    107: [("cs", r"Вечірн\w*\s+Київ\w*"), ("cs", r"Вечерн\w*\s+Киев\w*")],
    108: [("safe", r"\bQirim\b")],
    109: [("safe", r"\bNeformat\b")],
    110: [("safe", r"Вчися\.?\s?Меді[ая]")],
    111: [("safe", r"Новини\.?\s?LIVE"), ("safe", r"Новости\.?\s?LIVE"), ("safe", r"Novyny\.?\s?LIVE")],
    112: [("safe", r"Вісник\w*\s+Кіровоградщин\w*")],
    113: [("safe", r"Знам{A}янка\.City".format(A=A))],
    114: [("safe", r"\bZAXID\.NET\b"), ("safe", r"Захід\.?\s?нет"), ("safe", r"Західнет\w*")],
    115: [("safe", r"Сихів\.?\s?Меді[ая]")],
    116: [("safe", r"Інтерфакс[\s-]+Україн\w*"), ("safe", r"Интерфакс[\s-]+Украин\w*"), ("safe", r"Interfax[\s-]+Ukraine")],
    117: [("safe", r"Одеськ\w*\s+житт\w*")],
    118: [("ctx", r"Море\s+Людей")],
    119: [("ctx", r"Точк\w*\s+Сходу")],
    120: [("safe", r"Хутір\.?\s?News")],
    121: [("safe", r"\bMISTOSUMY\b")],
    122: [("safe", r"\bKordon\.Media\b")],
    123: [("safe", r"Свеса\.?\s?Online")],
    124: [("safe", r"Обрі\w*\s+Ізюмщин\w*")],
    125: [("safe", r"Громада\.Груп")],
    126: [("safe", r"МедіаПорт\w*"), ("safe", r"МедиаПорт\w*")],
    127: [("safe", r"Раді[оo]\s+Наки[пп][іи]ло")],
    128: [("safe", r"\b057\.ua\b")],
    129: [("safe", r"Волинь\s+Online")],
    130: [("safe", r"Вільногірськ\s+IN\s+UA")],
    131: [("safe", r"\bDnipro\.media\b")],
    132: [("safe", r"Місто\s+і\s+річка")],
    133: [("ctx", r"Прихист\w*")],
    134: [("safe", r"Kramatorsk\s+Post")],
    135: [("safe", r"\bPMG\.ua\b")],
    136: [("safe", r"\bZaholovok\b")],
    137: [("safe", r"IPC[\s-]+Південь"), ("safe", r"ІПЦ[\s-]+Південь")],
    138: [("safe", r"\b0372\.ua\b")],
    139: [("ctx", r"Шпальт(а|и)\b")],
    140: [("safe", r"PECHERA\.info"), ("ctx", r"Печер(а|и)\b")],
    141: [("ctx", r"Віст(ь|і)\b")],
}


def main() -> None:
    root = Path(__file__).resolve().parent
    sources = json.loads((root / "media_sources.json").read_text(encoding="utf-8"))
    assert len(sources) == len(ALIASES) == 142, (len(sources), len(ALIASES))
    out = []
    for i, src in enumerate(sources):
        out.append({
            "id": i,
            "name": src["name"],
            "domains": src["domains"],
            "type": src["type"],
            "aliases": [{"mode": m, "pattern": p} for m, p in ALIASES[i]],
        })
    (root / "media_aliases.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    modes = {}
    for v in ALIASES.values():
        for m, _ in v:
            modes[m] = modes.get(m, 0) + 1
    print("written", len(out), "media;", modes)


if __name__ == "__main__":
    main()
