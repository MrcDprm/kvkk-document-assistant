from eval.run_eval import evaluate, load_hard_cases, parse_markup
from kvkk_mask.recognizers import EntityType


def test_parse_markup():
    case = parse_markup("[[KISI:Ayşe Yılmaz]] aradı: [[TELEFON:0532 123 45 67]]")
    assert case.text == "Ayşe Yılmaz aradı: 0532 123 45 67"
    assert [(e.type, e.text) for e in case.gold] == [
        (EntityType.KISI, "Ayşe Yılmaz"),
        (EntityType.TELEFON, "0532 123 45 67"),
    ]
    for e in case.gold:
        assert case.text[e.start:e.end] == e.text


def test_hard_cases_load():
    cases = load_hard_cases()
    assert len(cases) > 20
    assert all("[[" not in c.text and "#" not in c.text[:1] for c in cases)


def test_evaluate_counts_errors():
    score = evaluate([parse_markup("[[KISI:Ayşe Yılmaz]] ve Umut Verici")])
    assert score.tp[EntityType.KISI] == 1
    assert score.fp[EntityType.KISI] == 1
    assert score.leaked == 0
