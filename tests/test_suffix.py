import pytest

from kvkk_mask.pseudonymizer import Pseudonymizer
from kvkk_mask.recognizers import Entity, EntityType
from kvkk_mask.suffix import harmonize


@pytest.mark.parametrize(
    "name, suffix, expected",
    [
        ("Gülfem Kurt", "in", "un"),
        ("Vedat Bulut", "nin", "un"),
        ("Ayşe Kaya", "ın", "nın"),
        ("Mehmet Öztürk", "ın", "ün"),
        ("Elif Demir", "un", "in"),
        ("Ayşe Kaya", "a", "ya"),
        ("Ali Rıza", "e", "ya"),
        ("Gülfem Kurt", "de", "ta"),
        ("Mehmet Öztürk", "dan", "ten"),
        ("Elif Demir", "ta", "de"),
        ("Ayşe Kaya", "le", "yla"),
        ("Elif Demir", "yla", "le"),
        ("Gülfem Kurt", "i", "u"),
        ("Ayşe Kaya", "ı", "yı"),
        ("Gülfem Kurt", "dir", "tur"),
        ("Gülfem Kurt", "ındaki", "ındaki"),  # unknown ending: left as it was
    ],
)
def test_harmonize(name, suffix, expected):
    assert harmonize(name, suffix) == expected


def test_unmask_fixes_endings_of_names_only():
    p = Pseudonymizer()
    text = "Vedat Bulut 0532 123 45 67"
    p.mask(text, [
        Entity(EntityType.KISI, 0, 11, "Vedat Bulut"),
        Entity(EntityType.TELEFON, 12, 26, "0532 123 45 67"),
    ])
    assert p.unmask("[KISI_1]'nin numarası [TELEFON_1]'dir.") == "Vedat Bulut'un numarası 0532 123 45 67'dir."
    assert p.unmask("[KISI_1] aradı") == "Vedat Bulut aradı"
