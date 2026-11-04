"""Keep form field labels out of names.

In official documents (military status, civil registry) labels such as "Baba Adı", "Ana Adı"
or "Sona Erme Tarihi" sit right next to names. "Baba", "Ana" and "Sona" are capitalized and can
be real given names, so the model marked them as people or glued them to the next name
("Kerem Yalçınkaya Baba", "Osman Ana").

The labels are located in the text; label words are cut out of any name that overlaps them,
and a name with nothing left is dropped.
"""

import re

from kvkk_mask.names import tr_lower
from kvkk_mask.recognizers import Entity, EntityType

# Matched on tr_lower(text): same length, so positions stay valid.
# "sona eren" is left out on purpose: "Sona Eren" can be a real full name, and when in doubt
# a name stays masked (privacy first).
_LABELS = re.compile(
    r"(?<!\w)(?:"
    r"(?:baba|ana|anne)[ \t]+ad[ıi]"
    r"|medeni[ \t]+hal[ıi]"
    r"|sona[ \t]+er(?:me(?:si)?|mek|di(?:ği)?|ecek(?:tir)?|er|miş(?:tir)?)"
    r")(?!\w)"
)
_TRIM = " \t\n:;,.-/"


def label_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) of every field label in `text`."""
    return [m.span() for m in _LABELS.finditer(tr_lower(text))]


def strip_labels(text: str, entities: list[Entity]) -> list[Entity]:
    """Cut label words out of person names; other entity types are left as they are."""
    spans = label_spans(text)
    if not spans:
        return entities

    result: list[Entity] = []
    for e in entities:
        if e.type is not EntityType.KISI or not any(s < e.end and e.start < t for s, t in spans):
            result.append(e)
            continue
        # Split the name around the labels; every piece left is a name of its own.
        start = e.start
        cuts = sorted((max(s, e.start), min(t, e.end)) for s, t in spans if s < e.end and e.start < t)
        pieces = []
        for s, t in cuts:
            pieces.append((start, s))
            start = t
        pieces.append((start, e.end))
        for s, t in pieces:
            while s < t and text[s] in _TRIM:
                s += 1
            while t > s and text[t - 1] in _TRIM:
                t -= 1
            if s < t:
                result.append(Entity(EntityType.KISI, s, t, text[s:t]))
    return result
