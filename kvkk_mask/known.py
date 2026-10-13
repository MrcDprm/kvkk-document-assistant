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
# Turkish case endings are often typed without an apostrophe ("gülfem kurtun", "çelike").
# After a name, up to 5 more letters are allowed; they stay in the text after the token.
_NAME_END = r"(?=[a-z]{0,5}(?![\w]))"
# Before a vowel ending the last consonant softens: Çelik -> Çeliğe, Kurt -> Kurda, Kalp -> Kalbi.
_SOFTENING = {"k": "[kg]", "t": "[td]", "p": "[pb]"}


def _name_word(word: str, last: bool) -> str:
    if last and len(word) > 2 and word[-1] in _SOFTENING:
        return re.escape(word[:-1]) + _SOFTENING[word[-1]]
    return re.escape(word)


def fold(text: str) -> str:
    """Lower case without Turkish letters: "Ümmühan ÇELİK" -> "ummuhan celik".

    Every character maps to exactly one character, so positions in the folded text are
    positions in the original text.
    """
    return tr_lower(text).translate(_ASCII)


def _pattern(value: str, entity_type: EntityType) -> str:
    folded = fold(value)
    if entity_type is EntityType.KISI:
        words = folded.split()
        body = r"\s+".join(_name_word(w, i == len(words) - 1) for i, w in enumerate(words))
        return r"(?<!\w)" + body + _NAME_END
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

    # A single name part ("gülfem'in", "Çelik'e") is masked too, in any case: for a privacy
    # tool masking an ordinary word ("çelik kapı") is a much smaller mistake than leaking a name.
    # A part that belongs to one person gets that person's token; a part shared by several
    # people ("Kaya") gets a token of its own, because it is not clear who is meant.
    owners: dict[str, set[str]] = {}
    for e in known:
        if e.type is EntityType.KISI:
            for part in fold(e.text).split():
                if len(part) >= _MIN_PART:
                    owners.setdefault(part, set()).add(fold(e.text))
    full_names = {fold(e.text): e.text for e in known if e.type is EntityType.KISI}
    for part, people in owners.items():
        value = full_names[next(iter(people))] if len(people) == 1 else part
        for m in re.finditer(rf"(?<!\w){_name_word(part, True)}{_NAME_END}", folded):
            found.append(Entity(EntityType.KISI, m.start(), m.end(), value))
    return found
