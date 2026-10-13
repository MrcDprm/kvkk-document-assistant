"""Find values that were already detected in a document inside another text (e.g. a question).

The recognizers alone are not enough for questions: users type names in lower case or
without Turkish letters ("ummuhan celik"), and a rare first name that was found in the
document thanks to a label ("Adı Soyadı: ...") has no label in the question. Without this
step such a name would be sent to the model unmasked.
"""

import re

from kvkk_mask.names import tr_lower
from kvkk_mask.recognizers import Entity, EntityType

_ASCII = str.maketrans("çğıöşüâîû", "cgiosuaiu")
_MIN_PART = 3  # shorter name parts ("Su", "Ay") are too likely to be ordinary words


def fold(text: str) -> str:
    """Lower case without Turkish letters: "Ümmühan ÇELİK" -> "ummuhan celik".

    Every character maps to exactly one character, so positions in the folded text are
    positions in the original text.
    """
    return tr_lower(text).translate(_ASCII)


def _pattern(value: str, entity_type: EntityType) -> str:
    folded = fold(value)
    if entity_type is EntityType.KISI:
        body = r"\s+".join(re.escape(w) for w in folded.split())
    else:
        # Numbers, IBANs and plates may be typed with or without spaces/dashes.
        body = r"[\s-]*".join(re.escape(c) for c in folded if not c.isspace() and c != "-")
    return rf"(?<!\w){body}(?!\w)"


def find_known(text: str, known: list[Entity]) -> list[Entity]:
    """Mentions of `known` values in `text`.

    The returned entities carry the value as it was written in the document (not as typed),
    so the pseudonymizer gives them the document's token.
    """
    folded = fold(text)
    if len(folded) != len(text):
        return []  # an unusual character changed length; positions would not line up

    found: list[Entity] = []
    for value, entity_type in {(e.text, e.type) for e in known}:
        for m in re.finditer(_pattern(value, entity_type), folded):
            found.append(Entity(entity_type, m.start(), m.end(), value))

    # A single name part ("Çelik'in") counts only if it is capitalized in the text and
    # belongs to exactly one person in the document; otherwise it is ambiguous.
    owners: dict[str, set[str]] = {}
    for e in known:
        if e.type is EntityType.KISI:
            for part in fold(e.text).split():
                if len(part) >= _MIN_PART:
                    owners.setdefault(part, set()).add(fold(e.text))
    full_names = {fold(e.text): e.text for e in known if e.type is EntityType.KISI}
    for part, people in owners.items():
        if len(people) != 1:
            continue
        value = full_names[next(iter(people))]
        for m in re.finditer(rf"(?<!\w){re.escape(part)}(?!\w)", folded):
            if text[m.start()].isupper():
                found.append(Entity(EntityType.KISI, m.start(), m.end(), value))
    return found
