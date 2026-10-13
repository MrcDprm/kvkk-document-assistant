"""Reversible pseudonymization: replace personal data with tokens and put it back later.

The same value always gets the same token inside one Pseudonymizer, even when it is
written differently ("0532 123 45 67" and "05321234567", "AYŞE YILMAZ" and "Ayşe Yılmaz").
That keeps the masked text meaningful for the LLM: it can still tell that two mentions
are the same person. The token -> original table never leaves the server.
"""

import re
from collections import Counter
from dataclasses import dataclass

from kvkk_mask.names import tr_lower
from kvkk_mask.recognizers import Entity, EntityType
from kvkk_mask.validators import normalize_digits

# LLMs sometimes drop the brackets ("KISI_1"), so they are optional when restoring.
_TOKEN_IN_TEXT = re.compile(r"\[?\b(" + "|".join(t.value for t in EntityType) + r")_(\d+)\b\]?")


@dataclass(frozen=True)
class Replacement:
    entity: Entity
    token: str
    masked_start: int
    masked_end: int


@dataclass(frozen=True)
class MaskResult:
    text: str
    replacements: list[Replacement]


def _key(entity: Entity) -> tuple[EntityType, str]:
    """The value used to decide whether two mentions are the same."""
    t, value = entity.type, entity.text
    if t in (EntityType.TCKN, EntityType.VKN, EntityType.KART, EntityType.TELEFON):
        digits = normalize_digits(value).replace("(", "").replace(")", "").replace("+", "")
        if t is EntityType.TELEFON:
            digits = digits[-10:]  # 0532..., +90532... and 532... are the same number
        return t, digits
    if t in (EntityType.IBAN, EntityType.PLAKA):
        return t, re.sub(r"\s", "", value).upper()
    if t is EntityType.EPOSTA:
        return t, value.lower()
    return t, " ".join(tr_lower(value).split())


class Pseudonymizer:
    def __init__(self) -> None:
        self._token_by_key: dict[tuple[EntityType, str], str] = {}
        self._original_by_token: dict[str, str] = {}
        self._counters: Counter[EntityType] = Counter()

    def token_for(self, entity: Entity) -> str:
        key = _key(entity)
        token = self._token_by_key.get(key)
        if token is None:
            self._counters[entity.type] += 1
            token = f"[{entity.type.value}_{self._counters[entity.type]}]"
            self._token_by_key[key] = token
            # The first spelling seen is the one shown when the token is restored.
            self._original_by_token[token] = entity.text
        return token

    def mask(self, text: str, entities: list[Entity]) -> MaskResult:
        """Replace `entities` (sorted, non-overlapping, e.g. from detect()) with tokens."""
        parts: list[str] = []
        replacements: list[Replacement] = []
        pos = 0
        length = 0
        for e in sorted(entities, key=lambda e: e.start):
            if e.start < pos:
                raise ValueError(f"Overlapping entities at {e.start}")
            parts.append(text[pos:e.start])
            length += e.start - pos
            token = self.token_for(e)
            parts.append(token)
            replacements.append(Replacement(e, token, length, length + len(token)))
            length += len(token)
            pos = e.end
        parts.append(text[pos:])
        return MaskResult("".join(parts), replacements)

    def unmask(self, text: str) -> str:
        """Put the original values back. Unknown tokens are left as they are."""

        def restore(m: re.Match) -> str:
            return self._original_by_token.get(f"[{m.group(1)}_{m.group(2)}]", m.group())

        return _TOKEN_IN_TEXT.sub(restore, text)

    @property
    def mapping(self) -> dict[str, str]:
        """Token -> original value, for the audit view."""
        return dict(self._original_by_token)
