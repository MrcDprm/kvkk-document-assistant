"""Rule-based recognizers for Turkish personal data.

Each recognizer finds candidates with a regex and keeps only the ones that pass
validation (checksum, area code, plate format). Overlapping matches are then
resolved so that every character belongs to at most one entity.
"""

import re
from dataclasses import dataclass
from enum import Enum

from kvkk_mask.validators import is_valid_card, is_valid_iban, is_valid_tckn, is_valid_vkn


class EntityType(str, Enum):
    TCKN = "TCKN"
    VKN = "VKN"
    IBAN = "IBAN"
    KART = "KART"
    TELEFON = "TELEFON"
    EPOSTA = "EPOSTA"
    PLAKA = "PLAKA"
    KISI = "KISI"


@dataclass(frozen=True)
class Entity:
    type: EntityType
    start: int
    end: int
    text: str


_TCKN = re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")
_VKN = re.compile(r"(?<!\d)\d{10}(?!\d)")
_IBAN = re.compile(r"\bTR\d{2}(?:\s?\d{4}){5}\s?\d{2}(?!\d)", re.IGNORECASE)
# 4-digit groups (optionally separated) followed by the rest: 13-19 digits in total.
_CARD = re.compile(r"(?<![\d-])(?:\d{4}[ -]?){3}\d{1,7}(?!\d)")
_PHONE = re.compile(
    r"(?<![\d+])"
    r"(?:\(0(?P<area_p>[2-5]\d{2})\)"  # (0212) 555 12 34
    # 0532..., 0 (532)..., +90 532...; a "(" is only taken when ")" closes the area code
    r"|(?P<prefix>(?:\+90|0090|0)[\s-]?)?(?P<open>\()?(?P<area>[2-5]\d{2})(?(open)\)))"
    r"[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)"
)
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b")
# Province code (01-81), 1-3 letters, 2-5 digits. Uppercase only, so "34 km 120" is not a plate.
_PLATE = re.compile(r"(?<![\w])(?P<il>0[1-9]|[1-7]\d|8[01]) ?(?P<letters>[A-Z]{1,3}) ?(?P<digits>\d{2,5})(?![\w])")
# A 10-digit number is only a VKN when a tax keyword appears shortly before it.
_VKN_CONTEXT = re.compile(r"verg[iıİI]|v\.?\s?k\.?\s?n|tax", re.IGNORECASE)
_VKN_CONTEXT_WINDOW = 40

# When two matches start at the same place and have the same length, the lower number wins.
_PRIORITY = {
    EntityType.EPOSTA: 0,
    EntityType.IBAN: 1,
    EntityType.KART: 2,
    EntityType.TCKN: 3,
    EntityType.VKN: 4,
    EntityType.TELEFON: 5,
    EntityType.PLAKA: 6,
    EntityType.KISI: 7,
}


def _valid_plate(letters: str, digits: str) -> bool:
    # Official combinations: 1 letter + 4-5 digits, 2 letters + 3-4 digits, 3 letters + 2-3 digits.
    allowed = {1: (4, 5), 2: (3, 4), 3: (2, 3)}
    low, high = allowed[len(letters)]
    return low <= len(digits) <= high


def _candidates(text: str):
    for m in _EMAIL.finditer(text):
        yield EntityType.EPOSTA, m

    for m in _IBAN.finditer(text):
        if is_valid_iban(m.group()):
            yield EntityType.IBAN, m

    for m in _CARD.finditer(text):
        if is_valid_card(m.group()):
            yield EntityType.KART, m

    for m in _TCKN.finditer(text):
        if is_valid_tckn(m.group()):
            yield EntityType.TCKN, m

    for m in _VKN.finditer(text):
        before = text[max(0, m.start() - _VKN_CONTEXT_WINDOW):m.start()]
        if is_valid_vkn(m.group()) and _VKN_CONTEXT.search(before):
            yield EntityType.VKN, m

    for m in _PHONE.finditer(text):
        # Without a 0 / +90 prefix only mobile numbers (5xx) are accepted;
        # a bare 10-digit number starting with 2-4 is too often something else.
        if m.group("prefix") or m.group("area_p") or m.group("area").startswith("5"):
            yield EntityType.TELEFON, m

    for m in _PLATE.finditer(text):
        if _valid_plate(m.group("letters"), m.group("digits")):
            yield EntityType.PLAKA, m


def _resolve_overlaps(entities: list[Entity]) -> list[Entity]:
    """Keep the earliest match; on a tie keep the longer one, then the higher priority."""
    ordered = sorted(entities, key=lambda e: (e.start, -(e.end - e.start), _PRIORITY[e.type]))
    result: list[Entity] = []
    last_end = -1
    for e in ordered:
        if e.start >= last_end:
            result.append(e)
            last_end = e.end
    return result


def find_entities(text: str, extra: list[Entity] | None = None) -> list[Entity]:
    """Return non-overlapping personal data entities in `text`, sorted by position.

    `extra` lets other recognizers (e.g. the name recognizer) join the same overlap resolution.
    """
    found = [Entity(t, m.start(), m.end(), m.group()) for t, m in _candidates(text)]
    if extra:
        found.extend(extra)
    return _resolve_overlaps(found)
