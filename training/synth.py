"""Synthetic Turkish NER sentences for training (labels in IOB2: PER, ORG, LOC).

WikiANN teaches the model names in Wikipedia sentences. These sentences teach it our domain:
contracts, forms, e-mails and questions; names typed in lower case or without Turkish
letters; suffixes with or without an apostrophe ("Kurt'un", "kurtun"); and organisations or
places that contain a first name ("Deniz Yatırım A.Ş.", "Umut Mahallesi"), which are not people.

Names used in the hand-written eval cases are excluded, so the evaluation stays honest.
"""

import random
import re

from kvkk_mask.fakegen import RARE_FIRST_NAMES, SURNAMES
from kvkk_mask.known import fold
from kvkk_mask.names import first_names, tr_capitalize, tr_lower

LABELS = ["O", "B-PER", "I-PER", "B-ORG", "I-ORG", "B-LOC", "I-LOC"]

# First names and surnames that appear in eval/hard_cases.txt must never be seen in training.
EVAL_ONLY = {
    "zümrüt", "tayyar", "necdet", "feyyaz", "rasim", "ümmühan",
    "karaosmanoğlu", "gündoğdu", "karabulut", "kocabaş",
    # eval/hard_cases_2.txt
    "cebrail", "nazlıcan", "ferdane", "ruhsar", "yekta", "sabahat", "yahya",
    "tuzcuoğlu", "ekşioğlu", "bilgiç", "hacıosmanoğlu", "sungur", "zorlu",
}

# Surnames are also built from common parts, so the model learns their shape
# instead of memorising a list ("Karahan", "Akdoğan", "Yıldızoğlu").
_SURNAME_HEADS = ["Kara", "Ak", "Er", "Öz", "Gün", "Yıl", "Tok", "Bay", "Kır", "Göl", "Ay", "Tan", "Sarı", "Demir", "Al", "Kurt", "Yıldız", "Taş", "Uz", "Ert"]
_SURNAME_TAILS = ["oğlu", "han", "er", "men", "türk", "can", "kaya", "taş", "demir", "doğan", "soy", "gül", "ay", "sel", "ekin", "dağ", "bulut", "yürek", "baş", "pınar"]
_EXTRA_FIRST = [
    "Nurdan", "Gülfem", "Sevdiye", "Hüsnüye", "Remzi", "Şaban", "Kâzım", "Lütfiye", "Fevziye", "Nusret",
    "Cahide", "Muzaffer", "Bedia", "Şükriye", "Rıdvan", "Nazmi", "Hayrünnisa", "Ziya", "Sacide", "Nezihe",
    "Behiye", "Rüçhan", "Selami", "Mürüvvet", "Kemalettin", "Saniye", "Turgay", "Behçet", "Nurettin", "Vasfiye",
]
_CITIES = ["İstanbul", "Ankara", "İzmir", "Bursa", "Antalya", "Konya", "Adana", "Trabzon", "Eskişehir", "Kayseri", "Samsun", "Mersin"]
_ORG_TAILS = ["Yatırım A.Ş.", "Holding", "Sigorta", "Lojistik Ltd. Şti.", "Gıda San. ve Tic. A.Ş.", "İnşaat", "Bankası", "Danışmanlık", "Vakfı", "Derneği"]
_LOC_TAILS = ["Mahallesi", "Caddesi", "Sokak", "Bulvarı", "Apartmanı", "Sitesi"]
_ORG_WORDS = ["Anadolu", "Marmara", "Ege", "Başkent", "Yıldız", "Güneş", "Deniz", "Umut", "Barış", "Can", "Doğa", "Akdeniz"]
_GENITIVE = {"a": "ın", "ı": "ın", "e": "in", "i": "in", "o": "un", "u": "un", "ö": "ün", "ü": "ün"}

# {PER}: full name, {FIRST}: first name only (used with Bey/Hanım), {ORG}, {LOC}, {CITY}.
# {PERS} / {FIRSTS}: the same with a genitive suffix ("Kurt'un", or glued: "kurtun").
# Lower-case words that are also names ("umut verici", "deniz kenarı") stay O.
TEMPLATES = [
    "Kiracı {PER} , T.C. kimlik numarası ile sözleşmeyi imzaladı .",
    "Kiraya veren {PER} ile kiracı {PER} arasında sözleşme yapılmıştır .",
    "Adı Soyadı : {PER}",
    "Ad Soyad : {PER} Departman : Muhasebe",
    "Acil durumda aranacak kişi : {PER}",
    "Sayın {PER} , başvurunuz alınmıştır .",
    "Merhaba {FIRST} Bey , dosyanız hazır .",
    "Merhaba {FIRST} Hanım , toplantı yarın saat 10'da .",
    "{FIRST} Hanım bugün aradı , dönüş bekliyor .",
    "Av. {PER} dilekçeyi mahkemeye sundu .",
    "Dr. {PER} hastayı muayene etti .",
    "Müşterimiz {PER} iade talebinde bulundu .",
    "Toplantıya {PER} ve {PER} katıldı .",
    "Belgeyi {PER} hazırladı , {PER} onayladı .",
    "{PER} , {ORG} adına imza attı .",
    "{ORG} yetkilisi {PER} ile görüşüldü .",
    "{PER} {CITY} şubesinde çalışıyor .",
    "{PER} {LOC} No : 12 adresinde oturuyor .",
    "Adres : {LOC} No : 5 , {CITY}",
    "{ORG} ile {ORG} arasında anlaşma imzalandı .",
    "Fatura {ORG} adına kesilmiştir .",
    "{PERS} telefon numarası nedir ?",
    "{PER} kimdir ?",
    "{PERS} maaş hesabı hangisi ?",
    "{PERS} adresi ne ?",
    "{FIRSTS} telefonu ne ?",
    "{PERS} imzası belgede var mı ?",
    "{PERS} kefili kim ?",
    "{PER} ne zaman işe başladı ?",
    "{PER} ile {PER} ne zaman görüştü ?",
    "{FIRST} hanımın telefonu ne ?",
    "{FIRST} beyin adresi nedir ?",
    "kefil {PER} mi ?",
    "Onaylayan : İnsan Kaynakları Müdürü {PER}",
    "Muhatap : {PER} , Keşideci : {PER}",
    "{PER} adına düzenlenen poliçe ektedir .",
    "Bu rapor umut verici sonuçlar içeriyor .",
    "Güneş enerjisi santrali için teklif istendi .",
    "Deniz kenarındaki daire kiralandı .",
    "Barış görüşmeleri sürüyor .",
    "Sözleşme tarihi 01.09.2026 , tutar 25.000 TL .",
    "Umut Verici Gelişmeler başlıklı rapor ektedir .",
    "{ORG} genel müdürü açıklama yaptı .",
    "Kargo {CITY} aktarma merkezine ulaştı .",
]


class SynthGenerator:
    def __init__(self, seed: int = 0) -> None:
        self.rng = random.Random(seed)
        names = {tr_capitalize(n) for n in first_names()} | set(RARE_FIRST_NAMES) | set(_EXTRA_FIRST)
        self.first = sorted(n for n in names if tr_lower(n) not in EVAL_ONLY)
        built = {h + tr_lower(t) for h in _SURNAME_HEADS for t in _SURNAME_TAILS}
        self.surnames = sorted(s for s in set(SURNAMES) | built if tr_lower(s) not in EVAL_ONLY)

    def _person(self) -> list[str]:
        words = [self.rng.choice(self.first)]
        if self.rng.random() < 0.12:
            words.append(self.rng.choice(self.first))  # second given name
        words.append(self.rng.choice(self.surnames))
        return words

    def _org(self) -> tuple[list[str], str]:
        head = self.rng.choice(_ORG_WORDS + self.surnames[:40])
        return [head, *self.rng.choice(_ORG_TAILS).split()], "ORG"

    def _loc(self) -> tuple[list[str], str]:
        head = self.rng.choice(_ORG_WORDS + self.first[:60])
        return [head, *self.rng.choice(_LOC_TAILS).split()], "LOC"

    def _genitive(self, words: list[str]) -> tuple[list[str], list[str]]:
        """Add "-in/-ın/-un/-ün" by vowel harmony: after an apostrophe (O-labelled tokens),
        or glued to the name as people often type it ("kurtun"), then the whole word is PER."""
        last = words[-1]
        vowels = [c for c in tr_lower(last) if c in _GENITIVE]
        suffix = _GENITIVE[vowels[-1]] if vowels else "in"
        if tr_lower(last)[-1] in _GENITIVE:
            suffix = "n" + suffix  # Kaya -> Kaya'nın
        if self.rng.random() < 0.35:
            return words[:-1] + [last + suffix], []
        return words, ["'", suffix]

    def sentence(self) -> tuple[list[str], list[str]]:
        tokens: list[str] = []
        tags: list[str] = []
        for piece in self.rng.choice(TEMPLATES).split():
            if piece in ("{PER}", "{FIRST}", "{PERS}", "{FIRSTS}"):
                words = self._person() if piece.startswith("{PER") else [self.rng.choice(self.first)]
                words, rest = self._genitive(words) if piece.endswith("S}") else (words, [])
                tokens += words + rest
                tags += ["B-PER"] + ["I-PER"] * (len(words) - 1) + ["O"] * len(rest)
            elif piece in ("{ORG}", "{LOC}"):
                words, label = self._org() if piece == "{ORG}" else self._loc()
                tokens += words
                tags += [f"B-{label}"] + [f"I-{label}"] * (len(words) - 1)
            elif piece == "{CITY}":
                tokens.append(self.rng.choice(_CITIES))
                tags.append("B-LOC")
            else:
                tokens.append(piece)
                tags.append("O")
        return self._casing(tokens), tags

    def _casing(self, tokens: list[str]) -> list[str]:
        """Users type questions carelessly: lower case, no Turkish letters, sometimes all caps."""
        r = self.rng.random()
        if r < 0.15:
            return [tr_lower(t) for t in tokens]
        if r < 0.25:
            return [fold(t) for t in tokens]
        if r < 0.30:
            return [t.replace("i", "İ").replace("ı", "I").upper() for t in tokens]
        return tokens

    def sentences(self, count: int) -> list[tuple[list[str], list[str]]]:
        return [self.sentence() for _ in range(count)]


def tokenize_with_spans(text: str) -> list[tuple[str, int, int]]:
    """Words and punctuation with character positions; the same split the model is trained on."""
    return [(m.group(), m.start(), m.end()) for m in re.finditer(r"\w+(?:[.]\w+)*|[^\w\s]", text)]
