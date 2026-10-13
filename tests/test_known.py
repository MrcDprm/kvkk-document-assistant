import pytest

from kvkk_mask import detect
from kvkk_mask.known import find_known, fold
from kvkk_mask.pseudonymizer import Pseudonymizer

DOC = (
    "Adı Soyadı: Ümmühan Çelik\n"
    "Cep Telefonu: 0532 123 45 67\n"
    "Acil Durumda Aranacak Kişi: Ayşe Kaya (0533 111 22 33)\n"
    "Kefil: Sn. Mehmet Kaya\n"
    "Araç: 34 ABC 123, IBAN: TR33 0006 1005 1978 6457 8413 26"
)
KNOWN = detect(DOC)


def masked_question(question: str) -> str:
    p = Pseudonymizer()
    p.mask(DOC, KNOWN)
    return p.mask(question, detect(question, known=KNOWN)).text


def test_fold_keeps_length():
    assert fold("Ümmühan ÇELİK") == "ummuhan celik"
    assert len(fold("İIıiŞşĞğ")) == 8


@pytest.mark.parametrize(
    "question",
    [
        "ümmühan çelik in telefonu ne",
        "Ümmühan Çelik'in telefonu ne?",
        "ÜMMÜHAN ÇELİK telefonu ne",
        "ummuhan celik telefonu ne",
        "ummuhan   celik telefonu ne",
    ],
)
def test_full_name_in_any_spelling(question):
    assert masked_question(question).startswith("[KISI_1]")
    assert "mmuhan" not in masked_question(question).lower()


def test_unique_name_part_when_capitalized():
    assert masked_question("Çelik'in telefonu ne?") == "[KISI_1]'in telefonu ne?"
    assert masked_question("Ümmühan nerede?") == "[KISI_1] nerede?"


def test_lowercase_part_is_an_ordinary_word():
    assert masked_question("çelik kapı ne kadar?") == "çelik kapı ne kadar?"


def test_shared_surname_is_ambiguous():
    # Two people are called Kaya, so "Kaya" alone is not linked to either of them.
    assert masked_question("Kaya'nın telefonu ne?") == "Kaya'nın telefonu ne?"
    assert masked_question("ayşe kaya nerede?") == "[KISI_2] nerede?"


@pytest.mark.parametrize(
    "question, expected",
    [
        ("05321234567 kimin?", "[TELEFON_1] kimin?"),
        ("34abc123 kimin aracı?", "[PLAKA_1] kimin aracı?"),
        ("tr330006100519786457841326 kimin?", "[IBAN_1] kimin?"),
    ],
)
def test_numbers_typed_differently(question, expected):
    assert masked_question(question) == expected


def test_returns_document_spelling_for_the_token():
    [entity] = find_known("ummuhan celik", KNOWN)
    assert entity.text == "Ümmühan Çelik"
