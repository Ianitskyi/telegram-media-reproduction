"""Регресійні тести конвеєра валідації (аудит ChatGPT 2026-10-26)."""
from collections import Counter

from src.v3.adjudication import strict_same_name, same_name
from src.v3.replacement import leak_excluded
from src.v3.validation_report import estimate, final_q1, is_complete, reference


def test_strict_matching_classes():
    ok = [("Зеленський", "президент Зеленський"), ("Зеленський", "Зеленського"), ("МИД", "МЗС"),
          ("apostrophe.ua", "Апостроф"), ("Кличко", "Віталій Кличко"), ("ДСНС", "ДСНС України")]
    for a, b in ok:
        assert strict_same_name(a, b), (a, b)
    # нечітке зіставлення їх вважає однаковими, суворе — ні (→ до перевірки людиною)
    for a, b in [("Українська правда", "Українська правда. Життя"), ("Генштаб", "Генштаб ЗСУ")]:
        assert same_name(a, b) and not strict_same_name(a, b), (a, b)


def test_leak_range():
    assert leak_excluded("V0001") and leak_excluded("V0100") and not leak_excluded("V0101") and not leak_excluded("R0001")


def test_unsure_is_incomplete_and_q1_final_wins():
    assert not is_complete({"q1_initial": "unsure", "choice": "A"})
    assert not is_complete({"q1_initial": "yes", "choice": "unsure"})
    assert is_complete({"q1_initial": "unsure", "q1_final": "no", "choice": "A"})
    assert final_q1({"q1_initial": "yes", "q1_final": "no"}) == "no"
    item = {"variants": [{"id": "A", "content_type": "informational", "promotional": "no", "has_explicit_source": True,
                          "attribution_method": "textual", "direct_sources": [{"name": "X", "type": "other"}],
                          "other_sources": [], "destinations": []}]}
    ref = reference(item, {"q1_initial": "yes", "q1_final": "no", "choice": "A"})
    assert ref["has_explicit_source"] is False and ref["direct_sources"] == []


def test_two_stage_estimate():
    # клітинка c1 (w1=2): 2 повідомлення D (обидва перевірені), 4 U (перевірено 1); c2 (w1=1): 2 U (перевірено 1)
    units = [("c1", "D", "d1"), ("c1", "D", "d2"), ("c1", "U", "u1"), ("c1", "U", "u2"), ("c1", "U", "u3"), ("c1", "U", "u4"),
             ("c2", "U", "u5"), ("c2", "U", "u6")]
    m = {"d1": Counter(x=1), "d2": Counter(x=0), "u1": Counter(x=1), "u5": Counter(x=0)}
    S = estimate(units, m, {"c1": 2.0, "c2": 1.0})
    # D: точно 2·(1+0)=2; U: середнє в страті 0.5 → c1: 2·4·0.5=4, c2: 1·2·0.5=1
    assert abs(S["x"] - 7.0) < 1e-9
