"""Регресійні тести класифікатора атрибуції v3. Запуск: python -m pytest tests/ -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.v3.attribution import Attribution  # noqa: E402

AT = Attribution()


def run(text, channel="truexanewsua", urls=None):
    return AT.analyze({"text": text, "urls": urls or []}, channel)


def types(text, **kw):
    return {s["type"] for s in run(text, **kw)["sources"]}


NO_SOURCE = [
    "Зеленський прибув до Парижа",
    "Українська правда святкує 25-річчя",
    "У Києві зараз сонячно",
    "Вибухи в Харкові. В укриття!",
    "❗️Ще одна ціль на Харків",
    "Збили людину на вул. Героїв полку Азов, швидка прямує на місце.",
]

EXPECT = [
    ("❗️Суд арештував екс-директора департаменту, — УП.", "ua_media"),
    ("Росія готує масований удар, — монітори", "telegram"),
    ("Зеленський заявив, що війна закінчиться дипломатією", "ua_official"),
    ("Наслідки атаки: 3 загиблих, — ОВА.", "ua_official"),
    ("За даними Reuters, США готують нові санкції", "foreign_media"),
    ("Країни Заходу закликають Україну, — Wall Street Journal", "foreign_media"),
    ("Невпинне підвищення цін на енергію, – ЗМІ.", "unnamed_media"),
    ("Тарифи на тепло зростуть, – нардеп Железняк.", "politician"),
    ("В Генштабі повідомили про успіхи на фронті", "ua_official"),
    ("Про це пише Суспільне", "ua_media"),
    ("Стрілець народився в москві, — Пєсков", "russian_official"),
    ("Удар по нафтобазі, — росЗМІ", "unnamed_media"),
    ("#нампишуть Вибух на Борщагівці", "eyewitness"),
    ("Росіяни вийдуть з Херсона, — експерт Жданов", "expert"),
    ("В мережі з'явилося відео удару по мосту", "social"),
    ("США не надаватимуть Tomahawk, — Трамп", "foreign_official"),
    ("Як повідомляє ТСН, у Києві знеструмлення", "ua_media"),
    ("Обстріл Курська, — джерела", "anonymous"),
    ("Байден заявил, что народ Украины подвергся атаке", "foreign_official"),
    ("Горить будинок. Місцеві говорять, що було чутно вибух", "eyewitness"),
    ("Путін схвалив арешт журналіста, – Bloomberg. Ймовірно, кремль обміняє його", "foreign_media"),
    ("Зараз працює все, — військові пишуть про зміни на фронті", "eyewitness"),
    ("Сообщают, что в Херсоне сняли флаги", "anonymous"),
    ("Затримано підозрюваного, — президент Володимир Зеленський.", "ua_official"),
    ("У путіна є 10 годин, – речник німецького уряду Корнеліус.", "foreign_official"),
    ("Кінець 2024 року. За словами західного дипломата, переговори можливі", "anonymous"),
]


def test_no_source():
    bad = {t: run(t)["sources"] for t in NO_SOURCE if run(t)["has_explicit_source"]}
    assert not bad, bad


def test_types():
    bad = [(t, e, types(t)) for t, e in EXPECT if e not in types(t)]
    assert not bad, bad


def test_no_fragments():
    r = run("СБУ опублікувала відео навчань силовиків біля кордону")
    assert all("идео" not in s["name"] for s in r["sources"]), r["sources"]


def test_self_reference_ignored():
    r = run("Новина дня, — ТРУХА⚡️Україна", channel="truexanewsua")
    assert not r["has_explicit_source"]


def test_link_and_method():
    r = run("Тарифи зростуть, — [NV](https://nv.ua/ukr/x.html)", urls=["https://nv.ua/ukr/x.html"])
    assert r["attribution_method"] == "both", r
    r = run("Детальніше: [тут](https://www.pravda.com.ua/news/1/)", urls=["https://www.pravda.com.ua/news/1/"])
    assert r["attribution_method"] == "hyperlink" and r["sources"][0]["whitelist"], r
    r = run("Збір на дрони: [банка](https://send.monobank.ua/jar/x)")
    assert not r["has_explicit_source"]


def test_message_type():
    assert run("Космолот: зареєструйся і отримай бонус! #реклама")["message_type"] == "ad"
    assert run("2 шахеди курсом на Київ, в укриття")["message_type"] == "alert"
