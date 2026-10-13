"""Detect and pseudonymize Turkish personal data."""

from kvkk_mask.known import find_known
from kvkk_mask.names import find_names
from kvkk_mask.recognizers import Entity, EntityType, find_entities


def detect(text: str, known: list[Entity] | None = None) -> list[Entity]:
    """All personal data in `text` (numbers, e-mails, plates and names), without overlaps.

    `known`: entities already found in a document; their mentions in `text` are found too,
    however they are typed (used for questions about that document).
    """
    extra = find_names(text)
    if known:
        extra += find_known(text, known)
    return find_entities(text, extra=extra)


__all__ = ["Entity", "EntityType", "detect"]
