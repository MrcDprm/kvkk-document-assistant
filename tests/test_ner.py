import os

import pytest

from kvkk_mask import detect
from kvkk_mask.ner import NerModel, Span, split_words
from kvkk_mask.recognizers import EntityType

MODEL_DIR = os.environ.get("NER_MODEL_DIR", "models/ner")
needs_model = pytest.mark.skipif(not NerModel.available(MODEL_DIR), reason="trained model not downloaded")


class FakeNer:
    """Marks the given phrases as PER/ORG/LOC, like the model would."""

    def __init__(self, **labels: list[str]) -> None:
        self.labels = labels

    def spans(self, text: str) -> list[Span]:
        found = []
        for label, phrases in self.labels.items():
            for phrase in phrases:
                start = text.find(phrase)
                if start >= 0:
                    found.append(Span(label, start, start + len(phrase)))
        return found


def test_split_words_keeps_positions():
    text = "Ayşe Yılmaz'ın A.Ş. hissesi"
    for word, start, end in split_words(text):
        assert text[start:end] == word


# --- Hybrid rules (with a fake model) ---

def names(text, ner):
    return [e.text for e in detect(text, ner=ner) if e.type is EntityType.KISI]


def test_model_finds_names_the_rules_miss():
    assert names("Tayyar Gündoğdu imzaladı.", FakeNer(PER=["Tayyar Gündoğdu"])) == ["Tayyar Gündoğdu"]


def test_dictionary_only_rule_match_is_dropped_when_model_is_used():
    # The rules would call "Umut Verici" a person; the model does not.
    assert names("Umut Verici Gelişmeler raporu", FakeNer()) == []


def test_context_backed_rule_name_is_kept():
    assert names("Sn. Zümrüt Karaosmanoğlu geldi.", FakeNer()) == ["Zümrüt Karaosmanoğlu"]


def test_model_organisation_vetoes_rule_name():
    text = "Sayın Deniz Yatırım yetkilisi,"
    assert names(text, FakeNer(ORG=["Deniz Yatırım"])) == []


def test_numbers_still_come_from_rules():
    found = detect("TCKN 10000000146", ner=FakeNer())
    assert [(e.type, e.text) for e in found] == [(EntityType.TCKN, "10000000146")]


# --- The real model (skipped when models/ner is missing) ---

@pytest.fixture(scope="module")
def model():
    return NerModel(MODEL_DIR)


@needs_model
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Tayyar Gündoğdu sözleşmeyi imzaladı.", ["Tayyar Gündoğdu"]),
        ("gülfem kurtun telefonu ne", ["gülfem kurtun"]),
        ("Toplantıya Elif Kaya Demir katıldı.", ["Elif Kaya Demir"]),
        ("Bana Ayşe Kaya Hanım yazdı.", ["Ayşe Kaya"]),  # edge words are trimmed
        ("Kişi: Kezban Çetin\nT.C. Kimlik No: 1", ["Kezban Çetin"]),  # a name stops at a line break
        ("Umut Verici Gelişmeler başlıklı rapor ektedir.", []),
    ],
)
def test_real_model_people(model, text, expected):
    assert [text[s.start:s.end] for s in model.spans(text) if s.label == "PER"] == expected


@needs_model
def test_real_model_organisations_and_places(model):
    text = "Deniz Yatırım A.Ş. ile Umut Mahallesi'nde görüşüldü."
    labels = {text[s.start:s.end]: s.label for s in model.spans(text)}
    assert labels.get("Deniz Yatırım A.Ş.") == "ORG"
    assert labels.get("Umut Mahallesi") == "LOC"


@needs_model
def test_real_model_long_text_and_empty_text(model):
    assert model.spans("") == []
    long_text = "Kiracı Ayşe Yılmaz ödeme yaptı.\n" * 300
    found = [s for s in model.spans(long_text) if s.label == "PER"]
    assert len(found) == 300
