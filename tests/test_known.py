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


@pytest.mark.parametrize(
    "question, expected",
    [
        ("ümmühan çelikin telefonu ne", "[KISI_1]in telefonu ne"),
        ("ummuhan celige ne gönderildi", "[KISI_1]e ne gönderildi"),  # k -> ğ before a vowel
        ("Ümmühan Çelikten haber var mı", "[KISI_1]ten haber var mı"),
        ("Ayşe Kayayla görüştüm", "[KISI_2]yla görüştüm"),
    ],
)
def test_suffix_attached_without_apostrophe(question, expected):
    assert masked_question(question) == expected


def test_suffix_limit_keeps_longer_words():
    assert masked_question("Ümmühan Çelikhanelerinden") == "Ümmühan Çelikhanelerinden".replace("Ümmühan", "[KISI_1]")


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


# --- Systematic check: no spelling of a document name reaches the model ---

from kvkk_mask.fakegen import make_documents  # noqa: E402
from kvkk_mask.names import tr_capitalize, tr_lower  # noqa: E402
from kvkk_mask.recognizers import EntityType  # noqa: E402

_SUFFIXES = ["", "'in", "'un", "in", "un", "ın", "nin", "e", "a", "ye", "ya", "yla", "le", "den", "dan", "ten", "tan", "de", "da"]
_SOFT = {"k": "ğ", "t": "d", "p": "b"}


def _spellings(name: str):
    first, *rest = name.split()
    last = rest[-1] if rest else first
    stems = [name]
    if last[-1].lower() in _SOFT:  # Çelik + e -> Çeliğe
        stems.append(name[:-1] + _SOFT[last[-1].lower()])
    for stem in stems:
        for suffix in _SUFFIXES:
            if stem != name and (not suffix or suffix[0] not in "aeıiouöü"):
                continue  # the softened stem only appears before a vowel
            base = stem + suffix
            yield base
            yield tr_lower(base)
            yield tr_lower(base).upper()
            yield fold(base)
            yield " ".join(tr_capitalize(w) for w in tr_lower(base).split())


def test_no_spelling_of_a_document_name_is_sent_unmasked():
    leaks = []
    for doc in make_documents(60, seed=11):
        known = detect(doc.text)
        people = {e.text for e in known if e.type is EntityType.KISI}
        p = Pseudonymizer()
        p.mask(doc.text, known)
        for person in people:
            first = fold(person.split()[0])
            for spelling in set(_spellings(person)):
                question = f"{spelling} telefon numarası nedir?"
                masked = p.mask(question, detect(question, known=known)).text
                if first in fold(masked):
                    leaks.append((person, question, masked))
    assert leaks == []
