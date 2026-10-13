"""Realistic fake Turkish personal data and demo documents.

Every number passes the same checksum rules the recognizers use, so the documents
are useful both as demo content and as a labeled evaluation set: each document
comes with the exact position of every piece of personal data in it.
All values are random; they are not taken from real people.
"""

import random
import re
from dataclasses import dataclass

from kvkk_mask.names import first_names, tr_capitalize, tr_lower
from kvkk_mask.recognizers import Entity, EntityType
from kvkk_mask.validators import iban_check_digits, luhn_check_digit, tckn_check_digits, vkn_check_digit

SURNAMES = [
    "Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Yıldırım", "Öztürk", "Aydın", "Özdemir",
    "Arslan", "Doğan", "Kılıç", "Aslan", "Çetin", "Kara", "Koç", "Kurt", "Özkan", "Şimşek",
    "Polat", "Özer", "Korkmaz", "Erdoğan", "Güneş", "Aksoy", "Tekin", "Ünal", "Bulut", "Keskin",
    "Karabulut", "Altun", "Avcı", "Taş", "Güler", "Sarı", "Bozkurt", "Ateş", "Işık", "Karaca",
    "Uçar", "Tunç", "Akın", "Coşkun", "Erdem", "Turan", "Yavuz", "Gündoğdu", "Kocabaş", "Yücel",
]
# Names that are NOT in the recognizer's dictionary: they keep the evaluation honest.
RARE_FIRST_NAMES = ["Zümrüt", "Nurdan", "Gülfem", "Sevdiye", "Tayyar", "Rasim", "Feyyaz", "Ümmühan"]

_BANK_CODES = ["00010", "00012", "00015", "00046", "00062", "00064", "00067", "00111"]
_PLATE_LETTERS = "ABCDEFGHJKLMNPRSTUVYZ"
_ASCII = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


class FakeData:
    """Generates single values. Use a seed for reproducible output."""

    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)
        self._common_names = sorted(tr_capitalize(n) for n in first_names())

    def _digits(self, n: int) -> str:
        return "".join(self.rng.choice("0123456789") for _ in range(n))

    def tckn(self) -> str:
        first9 = self.rng.choice("123456789") + self._digits(8)
        return first9 + tckn_check_digits(first9)

    def vkn(self) -> str:
        first9 = self._digits(9)
        return first9 + vkn_check_digit(first9)

    def iban(self, spaced: bool = True) -> str:
        bban = self.rng.choice(_BANK_CODES) + "0" + self._digits(16)
        value = "TR" + iban_check_digits("TR", bban) + bban
        return " ".join(value[i:i + 4] for i in range(0, 26, 4)) if spaced else value

    def card(self) -> str:
        partial = self.rng.choice(["4", "5"]) + self._digits(14)
        number = partial + luhn_check_digit(partial)
        return " ".join(number[i:i + 4] for i in range(0, 16, 4))

    def phone(self) -> str:
        area = "5" + self.rng.choice("03456") + self._digits(1)
        a, b, c = self._digits(3), self._digits(2), self._digits(2)
        style = self.rng.choice(["spaced", "compact", "intl", "dashed"])
        if style == "spaced":
            return f"0{area} {a} {b} {c}"
        if style == "compact":
            return f"0{area}{a}{b}{c}"
        if style == "intl":
            return f"+90 {area} {a} {b} {c}"
        return f"0{area}-{a}-{b}-{c}"

    def plate(self) -> str:
        il = f"{self.rng.randint(1, 81):02d}"
        n_letters = self.rng.randint(1, 3)
        letters = "".join(self.rng.choice(_PLATE_LETTERS) for _ in range(n_letters))
        n_digits = {1: 4, 2: self.rng.choice([3, 4]), 3: self.rng.choice([2, 3])}[n_letters]
        digits = str(self.rng.randint(10 ** (n_digits - 1), 10 ** n_digits - 1))
        return f"{il} {letters} {digits}"

    def name(self, rare: bool = False) -> str:
        first = self.rng.choice(RARE_FIRST_NAMES if rare else self._common_names)
        return f"{first} {self.rng.choice(SURNAMES)}"

    def email(self, name: str) -> str:
        user = tr_lower(name).translate(_ASCII).replace(" ", self.rng.choice([".", "_", ""]))
        return f"{user}@{self.rng.choice(['ornek.com', 'posta.com.tr', 'mail.net'])}"


# --- Demo documents ---
# {TYPE:key} is replaced with a value; the same key gets the same value inside one document.
# {KISI:key:upper} writes the name in capitals, as many official forms do.

TEMPLATES = {
    "kira-sozlesmesi": """KİRA SÖZLEŞMESİ

Sözleşme Tarihi: 01.09.2026
Kiraya Veren: {KISI:k1} (T.C. Kimlik No: {TCKN:t1})
Kiracı: {KISI:k2:upper}, T.C. {TCKN:t2}, Tel: {TELEFON:p2}
Kefil: Sn. {KISI:k3:rare}, Tel: {TELEFON:p3}

Madde 4 - Kira bedeli aylık 25.000 TL olup her ayın 5'inde kiraya verenin {IBAN:i1} numaralı hesabına yatırılır.
Madde 7 - Kiracı, {PLAKA:a1} plakalı aracını otoparkın 12 numaralı yerine park edebilir.
Madde 9 - Bildirimler {EPOSTA:k2} adresine yapılır. {KISI:k1} ile {KISI:k2}, sözleşmenin bir nüshasını aldıklarını kabul eder.
""",
    "sikayet-eposta": """Konu: Sipariş 2026-118734 hakkında şikâyet

Merhaba,

Ben {KISI:k1}. 14.09.2026 tarihinde verdiğim siparişin bedeli {KART:c1} numaralı kartımdan iki kez çekildi.
Müşteri hizmetlerinizi {TELEFON:p1} numaralı telefonumdan üç kez aradım, temsilciniz {KISI:k2} Hanım dönüş yapılacağını söyledi ama dönüş olmadı.

Fazla çekilen 1.249,90 TL'nin {IBAN:i1} hesabıma iadesini talep ediyorum.
Bana {EPOSTA:k1} adresinden ya da {TELEFON:p1} numarasından ulaşabilirsiniz.

{KISI:k1}
T.C. {TCKN:t1}
""",
    "personel-bilgi": """PERSONEL BİLGİ FORMU

Adı Soyadı: {KISI:k1:rare}
T.C. Kimlik No: {TCKN:t1}
Cep Telefonu: {TELEFON:p1}
E-posta: {EPOSTA:k1}
Maaş Hesabı (IBAN): {IBAN:i1}
Acil Durumda Aranacak Kişi: {KISI:k2} ({TELEFON:p2})
Servis Aracı Plakası: {PLAKA:a1}

İşe Giriş Tarihi: 03.02.2025   Departman: Muhasebe   Sicil No: 4471
Onaylayan: İnsan Kaynakları Müdürü {KISI:k3}
""",
    "fatura-itiraz": """Sayın Yetkili,

Firmamız adına düzenlenen 2026/0915 numaralı faturaya itiraz ediyoruz.
Firma: Örnek Lojistik Ltd. Şti., Vergi No: {VKN:v1}, Kadıköy Vergi Dairesi.
Yetkili kişi {KISI:k1}, faturanın teslim edilen {PLAKA:a1} plakalı araç için kesildiğini ancak hizmetin 3 gün geç verildiğini belirtmiştir.

Fark tutarının {IBAN:i1} numaralı şirket hesabımıza iadesini rica ederiz.
İletişim: {KISI:k1}, {TELEFON:p1}, {EPOSTA:k1}

Saygılarımızla,
Av. {KISI:k2:rare}
""",
}

_PLACEHOLDER = re.compile(r"\{(\w+):(\w+)(?::(\w+))?\}")


@dataclass(frozen=True)
class FakeDocument:
    kind: str
    text: str
    entities: list[Entity]


def _value(fake: FakeData, t: EntityType, option: str | None, names: dict[str, str], key: str) -> str:
    if t is EntityType.KISI:
        return names.setdefault(key, fake.name(rare=option == "rare"))
    if t is EntityType.EPOSTA:
        # An e-mail key refers to a person: k1's e-mail is built from k1's name.
        return fake.email(names.setdefault(key, fake.name()))
    return {
        EntityType.TCKN: fake.tckn,
        EntityType.VKN: fake.vkn,
        EntityType.IBAN: fake.iban,
        EntityType.KART: fake.card,
        EntityType.TELEFON: fake.phone,
        EntityType.PLAKA: fake.plate,
    }[t]()


def make_document(kind: str, seed: int | None = None) -> FakeDocument:
    fake = FakeData(seed)
    names: dict[str, str] = {}
    values: dict[tuple[EntityType, str], str] = {}
    template = TEMPLATES[kind]
    parts: list[str] = []
    entities: list[Entity] = []
    pos = 0
    length = 0

    for m in _PLACEHOLDER.finditer(template):
        parts.append(template[pos:m.start()])
        length += m.start() - pos
        t, key, option = EntityType(m.group(1)), m.group(2), m.group(3)
        if (t, key) not in values:
            values[(t, key)] = _value(fake, t, option, names, key)
        value = values[(t, key)]
        if option == "upper":
            value = value.replace("i", "İ").replace("ı", "I").upper()
        entities.append(Entity(t, length, length + len(value), value))
        parts.append(value)
        length += len(value)
        pos = m.end()

    parts.append(template[pos:])
    return FakeDocument(kind, "".join(parts), entities)


def make_documents(count: int, seed: int = 0) -> list[FakeDocument]:
    """`count` documents cycling through all templates, each with its own seed."""
    kinds = list(TEMPLATES)
    return [make_document(kinds[i % len(kinds)], seed + i) for i in range(count)]
