import pytest

from kvkk_mask.recognizers import Entity, EntityType, find_entities


def found(text):
    return [(e.type, e.text) for e in find_entities(text)]


# --- TCKN ---

def test_tckn_in_sentence():
    assert found("Kimlik no: 10000000146.") == [(EntityType.TCKN, "10000000146")]


def test_tckn_with_bad_checksum_is_ignored():
    assert found("Sipariş no 10000000145") == []


def test_tckn_inside_longer_number_is_ignored():
    assert found("Ref 9910000000146") == []


# --- VKN ---

def test_vkn_needs_tax_context():
    assert found("Vergi No: 4540536920") == [(EntityType.VKN, "4540536920")]
    assert found("VERGİ KİMLİK NO 4540536920") == [(EntityType.VKN, "4540536920")]
    assert found("V.K.N. 4540536920") == [(EntityType.VKN, "4540536920")]


def test_vkn_without_context_is_ignored():
    assert found("Dosya numarası 4540536920") == []


# --- IBAN ---

@pytest.mark.parametrize(
    "iban",
    ["TR330006100519786457841326", "TR33 0006 1005 1978 6457 8413 26"],
)
def test_iban(iban):
    assert found(f"IBAN: {iban} hesabına") == [(EntityType.IBAN, iban)]


def test_iban_with_bad_checksum_is_ignored():
    assert found("TR330006100519786457841327") == []


# --- Card ---

@pytest.mark.parametrize("card", ["4111111111111111", "4111 1111 1111 1111", "4111-1111-1111-1111"])
def test_card(card):
    assert found(f"Kart: {card}") == [(EntityType.KART, card)]


def test_card_failing_luhn_is_ignored():
    assert found("Kart: 4111 1111 1111 1112") == []


# --- Phone ---

@pytest.mark.parametrize(
    "phone",
    [
        "0532 123 45 67",
        "05321234567",
        "+90 532 123 45 67",
        "+905321234567",
        "0 (532) 123 45 67",
        "532 123 45 67",
        "0212 555 12 34",
        "0212-555-12-34",
        "(0212) 555 12 34",
        "(532) 123 45 67",
    ],
)
def test_phone(phone):
    assert found(f"Tel: {phone}") == [(EntityType.TELEFON, phone)]


def test_landline_with_parentheses():
    result = find_entities("Tel: 0 (212) 555 12 34")
    assert [(e.type, e.text) for e in result] == [(EntityType.TELEFON, "0 (212) 555 12 34")]


def test_parentheses_around_whole_number_are_not_included():
    assert found("Ayşe (05321234567)") == [(EntityType.TELEFON, "05321234567")]
    assert found("Ayşe (532 123 45 67)") == [(EntityType.TELEFON, "532 123 45 67")]


def test_bare_landline_without_prefix_is_ignored():
    assert found("Kod 2125551234") == []


# --- E-mail ---

def test_email():
    assert found("Bana ayse.yilmaz@ornek.com.tr adresinden yazın.") == [
        (EntityType.EPOSTA, "ayse.yilmaz@ornek.com.tr")
    ]


# --- Plate ---

@pytest.mark.parametrize("plate", ["34 ABC 123", "06 A 1234", "35AB123", "81 AB 1234"])
def test_plate(plate):
    assert found(f"Araç plakası {plate} olan") == [(EntityType.PLAKA, plate)]


@pytest.mark.parametrize("text", ["82 AB 123", "00 AB 123", "34 A 12", "34 ABC 1234", "34 km 120"])
def test_not_a_plate(text):
    assert found(text) == []


# --- Mixed text and overlaps ---

def test_mixed_document():
    text = (
        "Müşteri 10000000146 TC kimlik numaralı, 0532 123 45 67 telefonlu, "
        "ayse@ornek.com e-postalı kişi TR33 0006 1005 1978 6457 8413 26 IBAN'ına "
        "iade istedi. Araç: 34 ABC 123."
    )
    assert [e.type for e in find_entities(text)] == [
        EntityType.TCKN,
        EntityType.TELEFON,
        EntityType.EPOSTA,
        EntityType.IBAN,
        EntityType.PLAKA,
    ]


def test_iban_digits_are_not_reported_as_card():
    result = find_entities("TR330006100519786457841326")
    assert [e.type for e in result] == [EntityType.IBAN]


def test_positions_match_text():
    text = "Tel 05321234567 ve kimlik 10000000146"
    for e in find_entities(text):
        assert text[e.start:e.end] == e.text


def test_extra_entities_join_overlap_resolution():
    text = "Ayşe Yılmaz aradı"
    extra = [Entity(EntityType.KISI, 0, 11, "Ayşe Yılmaz")]
    assert [(e.type, e.text) for e in find_entities(text, extra)] == [(EntityType.KISI, "Ayşe Yılmaz")]
