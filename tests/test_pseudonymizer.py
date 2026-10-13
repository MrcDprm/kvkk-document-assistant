import pytest

from kvkk_mask import detect
from kvkk_mask.pseudonymizer import Pseudonymizer
from kvkk_mask.recognizers import Entity, EntityType

TEXT = (
    "Ayşe Yılmaz (10000000146) 0532 123 45 67 numarasından aradı. "
    "AYŞE YILMAZ daha sonra +90 532 123 45 67 numarasından tekrar aradı; "
    "Mehmet Kaya'ya bilgi verildi."
)


def test_mask_replaces_every_entity():
    result = Pseudonymizer().mask(TEXT, detect(TEXT))
    assert result.text == (
        "[KISI_1] ([TCKN_1]) [TELEFON_1] numarasından aradı. "
        "[KISI_1] daha sonra [TELEFON_1] numarasından tekrar aradı; "
        "[KISI_2]'ya bilgi verildi."
    )


def test_masked_text_contains_no_original_values():
    entities = detect(TEXT)
    masked = Pseudonymizer().mask(TEXT, entities).text
    for e in entities:
        assert e.text not in masked


def test_replacement_positions_point_to_tokens():
    result = Pseudonymizer().mask(TEXT, detect(TEXT))
    for r in result.replacements:
        assert result.text[r.masked_start:r.masked_end] == r.token


def test_unmask_restores_first_spelling():
    p = Pseudonymizer()
    p.mask(TEXT, detect(TEXT))
    answer = "[KISI_1] iki kez aradı, numarası [TELEFON_1]. [KISI_2]'ya bilgi verildi."
    assert p.unmask(answer) == (
        "Ayşe Yılmaz iki kez aradı, numarası 0532 123 45 67. Mehmet Kaya'ya bilgi verildi."
    )


def test_unmask_accepts_tokens_without_brackets():
    p = Pseudonymizer()
    p.mask(TEXT, detect(TEXT))
    assert p.unmask("KISI_1 aradı") == "Ayşe Yılmaz aradı"


def test_unmask_leaves_unknown_tokens():
    p = Pseudonymizer()
    p.mask(TEXT, detect(TEXT))
    assert p.unmask("[KISI_9] ve [IBAN_1]") == "[KISI_9] ve [IBAN_1]"


def test_tokens_stay_consistent_across_calls():
    p = Pseudonymizer()
    p.mask("Ayşe Yılmaz", detect("Ayşe Yılmaz"))
    second = p.mask("Mehmet Kaya ve Ayşe Yılmaz", detect("Mehmet Kaya ve Ayşe Yılmaz"))
    assert second.text == "[KISI_2] ve [KISI_1]"


def test_skipped_entity_stays_in_text():
    # The UI removes false positives by not passing them to mask().
    entities = [e for e in detect(TEXT) if e.type is not EntityType.TELEFON]
    masked = Pseudonymizer().mask(TEXT, entities).text
    assert "0532 123 45 67" in masked


def test_overlapping_entities_are_rejected():
    entities = [
        Entity(EntityType.KISI, 0, 11, "Ayşe Yılmaz"),
        Entity(EntityType.KISI, 5, 11, "Yılmaz"),
    ]
    with pytest.raises(ValueError):
        Pseudonymizer().mask("Ayşe Yılmaz", entities)


def test_mapping_for_audit():
    p = Pseudonymizer()
    p.mask(TEXT, detect(TEXT))
    assert p.mapping["[TCKN_1]"] == "10000000146"
