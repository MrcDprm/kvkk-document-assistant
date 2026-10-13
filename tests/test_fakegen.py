import pytest

from kvkk_mask import detect
from kvkk_mask.fakegen import TEMPLATES, FakeData, make_document, make_documents
from kvkk_mask.recognizers import EntityType, find_entities
from kvkk_mask.validators import is_valid_card, is_valid_iban, is_valid_tckn, is_valid_vkn

fake = FakeData(seed=42)


@pytest.mark.parametrize("_", range(200))
def test_numbers_pass_checksums(_):
    assert is_valid_tckn(fake.tckn())
    assert is_valid_vkn(fake.vkn())
    assert is_valid_iban(fake.iban())
    assert is_valid_iban(fake.iban(spaced=False))
    assert is_valid_card(fake.card())


@pytest.mark.parametrize("_", range(100))
def test_phone_and_plate_are_recognized(_):
    phone, plate = fake.phone(), fake.plate()
    assert [(e.type, e.text) for e in find_entities(phone)] == [(EntityType.TELEFON, phone)]
    assert [(e.type, e.text) for e in find_entities(plate)] == [(EntityType.PLAKA, plate)]


def test_email_is_ascii():
    assert fake.email("Gülşen Öztürk").split("@")[0] in ("gulsen.ozturk", "gulsen_ozturk", "gulsenozturk")


def test_same_seed_same_document():
    assert make_document("kira-sozlesmesi", seed=7) == make_document("kira-sozlesmesi", seed=7)


@pytest.mark.parametrize("kind", list(TEMPLATES))
def test_entity_positions_match_text(kind):
    doc = make_document(kind, seed=1)
    assert doc.entities
    assert "{" not in doc.text
    for e in doc.entities:
        assert doc.text[e.start:e.end] == e.text


def test_same_key_gets_same_value():
    doc = make_document("kira-sozlesmesi", seed=3)
    names = [e.text for e in doc.entities if e.type is EntityType.KISI]
    # k1 appears twice, k2 once in capitals and once normally
    assert names.count(names[0]) == 2
    assert names[1].isupper()


def test_make_documents_cycles_templates():
    docs = make_documents(8, seed=0)
    assert [d.kind for d in docs[:4]] == list(TEMPLATES)
    assert docs[0].text != docs[4].text


def test_detector_finds_all_numeric_entities_in_demo_documents():
    # Numbers have checksums, so the rules should find every one of them.
    numeric = {EntityType.TCKN, EntityType.VKN, EntityType.IBAN, EntityType.KART,
               EntityType.TELEFON, EntityType.EPOSTA, EntityType.PLAKA}
    for doc in make_documents(40, seed=100):
        found = {(e.type, e.start, e.end) for e in detect(doc.text)}
        expected = {(e.type, e.start, e.end) for e in doc.entities if e.type in numeric}
        assert expected <= found, doc.text


def test_email_from_name_with_dotted_capital_i():
    assert fake.email("İrfan Işık").split("@")[0] in ("irfan.isik", "irfan_isik", "irfanisik")
