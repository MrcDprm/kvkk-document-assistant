"""Detect and pseudonymize Turkish personal data."""

from kvkk_mask.known import find_known
from kvkk_mask.names import find_names
from kvkk_mask.recognizers import Entity, EntityType, find_entities


def detect(text: str, known: list[Entity] | None = None) -> list[Entity]:
    """All personal data in `text` (numbers, e-mails, plates and names), without overlaps.

    `known`: entities already found in a document; their mentions in `text` are found too,
    however they are typed (used for questions about that document).
    """
    names = find_names(text)
    if not known:
        return find_entities(text, extra=names)
    found = find_known(text, known)
    # A known value keeps the document's token, so it wins over a name the rules found at the
    # same place ("Ayşe Kayayla" would otherwise become a new person called "Ayşe Kayayla").
    names = [n for n in names if not any(n.start < k.end and k.start < n.end for k in found)]
    return find_entities(text, extra=names + found)


__all__ = ["Entity", "EntityType", "detect"]
