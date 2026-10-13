import pytest

from kvkk_mask import detect
from kvkk_mask.names import find_names, tr_lower
from kvkk_mask.recognizers import EntityType


def names(text):
    return [e.text for e in find_names(text)]


def test_tr_lower():
    assert tr_lower("IŞIK") == "ışık"
    assert tr_lower("İSMAİL") == "ismail"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Ayşe Yılmaz bugün aradı.", ["Ayşe Yılmaz"]),
        ("Müşterimiz Ali Rıza Kaya ile görüşüldü.", ["Ali Rıza Kaya"]),
        ("AYŞE YILMAZ", ["AYŞE YILMAZ"]),
        ("Ayşe YILMAZ imzaladı", ["Ayşe YILMAZ"]),
        ("İSMAİL ÖZTÜRK", ["İSMAİL ÖZTÜRK"]),
        ("Mehmet Ali geldi", ["Mehmet Ali"]),
    ],
)
def test_first_name_plus_surname(text, expected):
    assert names(text) == expected


def test_apostrophe_suffix_is_not_part_of_name():
    assert names("Belgeyi Ahmet Demir'e ilettik.") == ["Ahmet Demir"]


def test_city_after_name_is_not_part_of_name():
    assert names("Ahmet Yılmaz Ankara'ya taşındı.") == ["Ahmet Yılmaz"]


def test_title_allows_unknown_names():
    assert names("Av. Zümrüt Karaosmanoğlu dilekçeyi verdi.") == ["Zümrüt Karaosmanoğlu"]
    assert names("Sayın Tülay Bozkurt,") == ["Tülay Bozkurt"]
    assert names("Prof. Dr. Kerem Aksoy") == ["Kerem Aksoy"]


def test_label_allows_unknown_names():
    assert names("Adı Soyadı: Zümrüt Karaosmanoğlu") == ["Zümrüt Karaosmanoğlu"]


def test_first_name_with_honorific():
    assert names("Emre Bey toplantıya katılmadı.") == ["Emre"]
    assert names("Zeynep Hanım'a bilgi verildi.") == ["Zeynep"]


@pytest.mark.parametrize(
    "text",
    [
        "Ahmet aradı.",                        # lone first name, no context
        "Umut Mahallesi Deniz Sokak No: 5",     # names used as place names
        "Deniz Kuvvetleri Komutanlığı",
        "Türkiye Cumhuriyeti",
        "Sözleşme Tarihi: 12.03.2024",
        "Ayşe\nYılmaz",                         # line break ends a name
    ],
)
def test_not_a_name(text):
    assert names(text) == []


def test_two_names_in_one_sentence():
    assert names("Ayşe Yılmaz ve Mehmet Kaya imzaladı.") == ["Ayşe Yılmaz", "Mehmet Kaya"]


def test_detect_combines_names_and_numbers():
    text = "Ayşe Yılmaz (TCKN 10000000146) 0532 123 45 67 numarasından aradı."
    assert [(e.type, e.text) for e in detect(text)] == [
        (EntityType.KISI, "Ayşe Yılmaz"),
        (EntityType.TCKN, "10000000146"),
        (EntityType.TELEFON, "0532 123 45 67"),
    ]


def test_tr_capitalize():
    from kvkk_mask.names import tr_capitalize
    assert tr_capitalize("irem") == "İrem"
    assert tr_capitalize("ılgaz") == "Ilgaz"
    assert tr_capitalize("ÖMER") == "Ömer"


def test_addressee_words_are_not_names():
    assert names("Sayın Yetkili,") == []
    assert names("Sayın İlgili,") == []
