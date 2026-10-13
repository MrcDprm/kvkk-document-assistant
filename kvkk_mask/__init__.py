"""Detect and pseudonymize Turkish personal data."""

from typing import TYPE_CHECKING

from kvkk_mask.known import find_known
from kvkk_mask.names import find_names
from kvkk_mask.recognizers import Entity, EntityType, find_entities

if TYPE_CHECKING:
    from kvkk_mask.ner import NerModel


def _overlaps(a: Entity, b) -> bool:
    return a.start < b.end and b.start < a.end


def detect(text: str, known: list[Entity] | None = None, ner: "NerModel | None" = None) -> list[Entity]:
    """All personal data in `text` (numbers, e-mails, plates and names), without overlaps.

    `known`: entities already found in a document; their mentions in `text` are found too,
    however they are typed (used for questions about that document).
    `ner`: the trained model. It decides on names; the rules only add names backed by context
    (a title or label before them, Bey/Hanım after them), unless the model marks the same words
    as an organisation or place. Dictionary-only rule matches ("Umut Verici") are left out.
    """
    if ner is None:
        names = find_names(text)
    else:
        spans = ner.spans(text)
        people = [Entity(EntityType.KISI, s.start, s.end, text[s.start:s.end]) for s in spans if s.label == "PER"]
        not_people = [s for s in spans if s.label != "PER"]
        names = [n for n in find_names(text, strong_only=True) if not any(_overlaps(n, s) for s in not_people)]
        names += people
    if not known:
        return find_entities(text, extra=names)
    found = find_known(text, known)
    # A known value keeps the document's token, so it wins over a name found at the same place
    # ("Ayşe Kayayla" would otherwise become a new person called "Ayşe Kayayla").
    names = [n for n in names if not any(_overlaps(n, k) for k in found)]
    return find_entities(text, extra=names + found)


__all__ = ["Entity", "EntityType", "detect"]
