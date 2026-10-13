"""Fix Turkish case endings after a pseudonym is replaced with the real name.

The model writes "[KISI_1]'in" without knowing who [KISI_1] is; once the name is put back the
ending may not match it ("Bulut'nin"). Endings follow vowel harmony and consonant rules,
so the right form can be computed from the name: "Bulut'un", "Kaya'nın", "Kurt'ta".
Only the common single case endings are changed; anything else is left as it was.
"""

import re

from kvkk_mask.names import tr_lower

_VOWELS = "aeıioöuü"
_BACK = "aıou"
_FOUR_WAY = {"a": "ı", "ı": "ı", "e": "i", "i": "i", "o": "u", "u": "u", "ö": "ü", "ü": "ü"}
_HARD_CONSONANTS = "fstkçşhp"  # after these, d becomes t: Kurt'ta, Öztürk'ten

_ENDINGS = [
    ("genitive", re.compile(r"n?[ıiuü]n")),       # 'ın 'in 'un 'ün 'nın 'nin ...
    ("accusative", re.compile(r"y?[ıiuü]")),      # 'ı 'i 'yı 'yi ...
    ("dative", re.compile(r"y?[ae]")),            # 'a 'e 'ya 'ye
    ("locative", re.compile(r"[dt][ae]")),        # 'da 'de 'ta 'te
    ("ablative", re.compile(r"[dt][ae]n")),       # 'dan 'den 'tan 'ten
    ("instrumental", re.compile(r"y?l[ae]")),     # 'la 'le 'yla 'yle
    ("copula", re.compile(r"[dt][ıiuü]r")),       # 'dır 'dir 'tır ...
]


def harmonize(name: str, suffix: str) -> str:
    """The form of `suffix` (written after an apostrophe) that fits `name`."""
    word = tr_lower(name.split()[-1]) if name.split() else ""
    vowels = [c for c in word if c in _VOWELS]
    if not vowels:
        return suffix
    last = vowels[-1]
    two = "a" if last in _BACK else "e"
    four = _FOUR_WAY[last]
    ends_with_vowel = word[-1] in _VOWELS
    d = "t" if word[-1] in _HARD_CONSONANTS else "d"

    kind = next((k for k, pattern in _ENDINGS if pattern.fullmatch(tr_lower(suffix))), None)
    if kind == "genitive":
        return ("n" if ends_with_vowel else "") + four + "n"
    if kind == "accusative":
        return ("y" if ends_with_vowel else "") + four
    if kind == "dative":
        return ("y" if ends_with_vowel else "") + two
    if kind == "locative":
        return d + two
    if kind == "ablative":
        return d + two + "n"
    if kind == "instrumental":
        return ("y" if ends_with_vowel else "") + "l" + two
    if kind == "copula":
        return d + four + "r"
    return suffix
