"""Detect and pseudonymize Turkish personal data."""

from kvkk_mask.names import find_names
from kvkk_mask.recognizers import Entity, EntityType, find_entities


def detect(text: str) -> list[Entity]:
    """All personal data in `text` (numbers, e-mails, plates and names), without overlaps."""
    return find_entities(text, extra=find_names(text))


__all__ = ["Entity", "EntityType", "detect"]
