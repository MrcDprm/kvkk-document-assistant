from kvkk_mask import detect
from kvkk_mask.labels import label_spans, strip_labels
from kvkk_mask.names import find_names
from kvkk_mask.recognizers import Entity, EntityType


def _person(text: str, value: str) -> Entity:
    start = text.index(value)
    return Entity(EntityType.KISI, start, start + len(value), value)


def _names(entities: list[Entity]) -> list[str]:
    return [e.text for e in entities if e.type is EntityType.KISI]


def test_label_spans_find_form_labels_in_any_case():
    text = "Baba Adı: Osman\nANA ADI: HATİCE\nanne adı sevim\nMedeni Hali: Bekâr\nSONA ERME TARİHİ"
    found = [text[s:e] for s, e in label_spans(text)]
    assert found == ["Baba Adı", "ANA ADI", "anne adı", "Medeni Hali", "SONA ERME"]


def test_sona_as_a_name_is_not_a_label():
    for text in ("Adı: Sona", "Sona Gürbüz geldi", "Sona Erdem", "Sona Eren"):
        assert label_spans(text) == []


def test_sona_er_verb_forms_are_labels():
    for verb in ("erme", "ermesi", "erdi", "erdiği", "erecek", "erecektir", "erer", "ermiş", "ermiştir"):
        assert label_spans(f"Süre sona {verb}.") != [], verb


def test_label_glued_to_a_name_is_cut_off():
    text = "Adı Soyadı Kerem Yalçınkaya Baba Adı Osman Ana Adı Hatice"
    entities = [_person(text, "Kerem Yalçınkaya Baba"), _person(text, "Osman Ana"), _person(text, "Hatice")]
    assert _names(strip_labels(text, entities)) == ["Kerem Yalçınkaya", "Osman", "Hatice"]


def test_name_made_only_of_a_label_is_dropped():
    text = "Sona Erme Tarihi: 31.12.2027"
    assert strip_labels(text, [_person(text, "Sona Erme")]) == []


def test_other_entity_types_are_untouched():
    text = "Baba Adı 10000000146"
    tckn = Entity(EntityType.TCKN, 9, 20, "10000000146")
    assert strip_labels(text, [tckn]) == [tckn]


def test_name_after_a_form_label_is_found_by_the_rules():
    text = "Adı: Sona\nSoyadı: Gürbüz\nBaba Adı: Necati"
    assert [e.text for e in find_names(text, strong_only=True)] == ["Sona", "Gürbüz", "Necati"]


def test_adi_label_inside_a_line_is_not_a_person_label():
    assert find_names("Ürün Adı: Kahve Makinesi", strong_only=True) == []


def test_detect_cuts_a_label_the_rules_swallowed():
    # After "Adı Soyadı:" the rules take up to three capitalized words, "Baba" included.
    text = "Adı Soyadı: Kerem Yalçınkaya Baba Adı: Osman"
    assert _names(detect(text)) == ["Kerem Yalçınkaya", "Osman"]


def test_detect_with_model_cuts_labels_out():
    from kvkk_mask.ner import Span

    text = "Osman Ana Adı Hatice\nSona Erme Tarihi: 31.12.2027"

    class Ner:  # what the trained model returned for this kind of document
        def spans(self, t):
            return [Span("PER", 0, 9), Span("PER", 14, 20), Span("PER", 21, 30)]

    assert _names(detect(text, ner=Ner())) == ["Osman", "Hatice"]
