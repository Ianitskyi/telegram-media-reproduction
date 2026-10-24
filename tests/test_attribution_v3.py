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
    "СБУ затримала агента рф у Харкові",
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
    ("Генштаб: противник втратив 1200 осіб за добу", "ua_official"),
    ("Українці спустошили автосалони, — Autoconsulting", "company_organization"),
    ("Протест проти уряду, — Беларускі Гаюн", "telegram"),
    ("Росія готує наступ, — Резніков", "ua_official"),
    ("Переговоры невозможны, — МИД России", "russian_official"),
    ("Росія втрачає темп, — ISW", "expert"),
    ("Закон ухвалено, — Рада", "ua_official"),
    ("Війна триватиме, — радник керівника Офісу Президента Олексій Арестович", "ua_official"),
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


def test_actor_vs_destination():
    """Аудит: посилання — пункт призначення, а не джерело-актор."""
    r = run("США просять Японію передати ракети, — The Washington Post. [Детальніше](https://nv.ua/ukr/world/x.html)")
    names = {s["name"]: s for s in r["attributed_sources"]}
    assert "The Washington Post" in names and names["The Washington Post"]["type"] == "foreign_media", r["attributed_sources"]
    assert not any(s.get("actor_inferred_from_link") for s in r["attributed_sources"])
    assert r["linked_destinations"][0]["platform_type"] == "ua_media_site"
    r = run("Ворог готується до атак, – ОК «Південь».\n[Facebook](https://www.facebook.com/okpivden/posts/1)")
    assert {s["type"] for s in r["attributed_sources"]} == {"ua_official"}, r["attributed_sources"]
    assert r["linked_destinations"][0]["platform_type"] == "social_platform"
    r = run("Меланія передала листа, – [Reuters](https://www.reuters.com/world/x).")
    assert r["attributed_sources"][0]["linked_destination"] == "reuters.com", r


def test_dedup():
    r = run("Пресслужба СБУ повідомила про затримання. СБУ заявила, що агент діяв з 2022 року")
    assert sum(1 for s in r["attributed_sources"] if "СБУ" in s["name"]) == 1, r["attributed_sources"]
    r = run("Міністр Максим Степанов заявив про карантин. Міністр також повідомив про вакцини")
    assert len(r["attributed_sources"]) == 1, r["attributed_sources"]


def test_ad_false_positives():
    assert run("Окупанти поширюють знімки у ворожих каналах, — голова ЦПД Коваленко")["message_type"] == "informational"
    assert run('Telegram — загроза, — Буданов. "Хочеш вести новини - зареєструйся", — додав він')["message_type"] == "informational"


def test_audit_round2():
    names = lambda t: [s["name"] for s in run(t)["attributed_sources"]]
    assert names("Мир можливий, — йдеться у матеріалі New York Times") == ["New York Times"], names("Мир можливий, — йдеться у матеріалі New York Times")
    assert not any("Волновах" in n for n in names("В Волновахе Донецкой области сообщают о взрывах"))
    assert not run("Российский «Альфа-Банк Украина»: в чьих интересах действует банк")["has_explicit_source"]
    r = run("Пакет допомоги, — пресреліз Пентагону. [Детальніше](https://www.defense.gov/News/1)")
    assert r["linked_destinations"][0]["platform_type"] == "foreign_official_site", r["linked_destinations"]


def test_decision6_social_other_links_not_attribution():
    for t in ("Дивіться відео: [YouTube](https://youtu.be/abc)", "Підпишіть петицію: [тут](https://openpetition.eu/x)"):
        r = run(t)
        assert not r["has_explicit_source"] and r["attribution_method"] == "none", r
        assert r["linked_destinations"], r
    r = run("Детальніше: [тут](https://www.pravda.com.ua/news/1/)")
    assert r["has_explicit_source"] and r["attributed_sources"][0]["actor_inferred_from_link"]


def test_audit_v31_round():
    """Другий аудит ChatGPT (v3.1 → v3.2)."""
    names = lambda t: {s["name"]: s for s in run(t)["attributed_sources"]}
    n = names("Українці за 2 дні спустошили всі автосалони, — Аutoconsulting")   # кирилична «А»
    assert "Autoconsulting" in n, n
    assert "Новини.LIVE" in names("⚡ До 6 тис грн коштують квіти зараз у Києві, — «Новини.LIVЕ».")
    assert names("Видання Yle показали кадри 30-річної давнини")["Yle"]["type"] == "foreign_media"
    n = names("Прильоти в Павлограді, — місцеві ЗМІ і монітори.")
    assert set(n) == {"місцеві ЗМІ", "монітори"}, n
    assert "Мариупольский горсовет" in names("Мариупольский горсовет: «За 24 часа город бомбардировали 22 раза»")
    assert set(names("Повістки публікуватимуть онлайн, — ЗМІ з посиланням на законопроєкт")) >= {"ЗМІ"}
    n = names("Премьер-министр Великобритании заявил, что опасается атаки. «Это их сценарий», - сказал Джонсон в интервью")
    assert list(n) == ["Джонсон"] and n["Джонсон"]["type"] == "foreign_official", n
    n = names("Про це сам експрезидент США розповів в інтерв'ю. «Я вдарю», — заявив Трамп.")
    assert list(n) == ["Трамп"], n
    assert names("Зять Шойгу вважає війну безглуздою")["Зять Шойгу"]["type"] == "person_other"
    n = names("Великобритания не планирует отправлять корабли в Черное море, по словам представителя правительства.")
    assert n["представителя правительства"]["type"] == "foreign_official", n
    r = run("⚡️CBS News со ссылкой на американских чиновников сообщает, что подразделения выдвинулись")
    lv = {s["name"]: s["source_level"] for s in r["attributed_sources"]}
    assert lv.get("CBS News") == "direct" and lv.get("американских чиновников") == "embedded", lv
    r = run("Панцир не зміг збити дрон, — «Радіо Свобода» із посиланням на супутникові знімки та публікації в соцмережах.")
    lv = {s["name"]: s["source_level"] for s in r["attributed_sources"]}
    assert lv.get("Радіо Свобода") == "direct" and r["has_embedded_source"], lv
    n = names("Как сообщил советник мэра Мариуполя Петр Андрющенко, взрыв случился в отеле. Спикер опубликовал фото.")
    assert len(n) == 1 and n["советник мэра Мариуполя Петр Андрющенко"]["type"] == "ua_official", n


def test_content_vs_promo():
    r = run("Усик переміг")
    assert r["content_type"] == "informational" and r["in_primary_denominator"], r
    r = run("‼️ ВНИМАНИЕ БЕЛГОРОД ‼️\n❗️ВОЗДУШНАЯ ТРЕВОГА ❗️\n⚠️ВСЕМ НЕМЕДЛЕННО ПОКИНУТЬ ПОМЕЩЕНИЯ")
    assert r["content_type"] == "alert", r
    r = run("🔴Можливо буде пуск кінджала! Набрав швидкість та висоту\n➡️ ПІДПИСАТИСЬ ⤵️")
    assert r["promotional"] == "self_promo" and r["in_primary_denominator"], r
    r = run("‼️БУДАНОВ ДАВ ПОЯСНЕННЯ!\nКирило Олексійович пояснив, що відео зробили хлопці з каналу БАЗА.\nПідписуйтесь на авторів.")
    assert r["in_primary_denominator"], r
    r = run("Підписуйтесь на наш канал 👉 https://t.me/x")
    assert not r["in_primary_denominator"], r


def test_v32_review():
    names = lambda t: {s["name"]: s for s in run(t)["attributed_sources"]}
    assert set(names("Макрон відклав візит, — Challenges\nВидання зазначає, що дипломати «упали зі стільців».")) == {"Challenges"}
    assert set(names("Танки будуть восени, — глава Пентагона Ллойд Остин\nОстин объяснил, что ускорить сроки сложно")) == {"глава Пентагона Ллойд Остин"}
    n = names("Владимир Зеленский и Белый дом заявили о новых гарантиях")
    assert {"Владимир Зеленский", "Белый дом"} <= set(n), n
    assert names("Мобілізація неминуча, — Рада безпеки рФ")["Рада безпеки рФ"]["type"] == "russian_official"
