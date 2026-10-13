"""Full-name recognizer based on a first-name dictionary and context rules.

A Turkish NER model would not fit in the 512 MB free server, so names are found with rules:
- a known first name followed by more capitalized words ("Ayşe Yılmaz", "Ali Rıza KAYA"),
- any capitalized words after a title or label ("Av. Zümrüt Karaosmanoğlu", "Adı Soyadı: ..."),
- a single known first name before "Bey" / "Hanım" ("Emre Bey").
"""

import re
from functools import lru_cache
from pathlib import Path

from kvkk_mask.recognizers import Entity, EntityType

_DATA = Path(__file__).parent / "data"

# A capitalized word ("Yılmaz") or an all-caps word ("YILMAZ"); a following apostrophe suffix is not part of it.
_TOKEN = re.compile(r"(?<![\w])[A-ZÇĞİÖŞÜ](?:[a-zçğıöşüâîû]+|[A-ZÇĞİÖŞÜÂÎÛ]+)(?![\w])")
# Only spaces or tabs between the words of one name; a line break or punctuation ends it.
_NAME_GAP = re.compile(r"[ \t]{1,3}")
_TITLE_BEFORE = re.compile(
    r"(?:\b(?:Sayın|SAYIN|Bay|Bayan)|\b(?:Sn|Av|Dr|Prof|Doç|Uzm|Öğr\.\s?Gör)\.)\s+$"
    r"|(?:Ad[ıi]?\s*(?:ve\s+)?Soyad[ıi]?|İsim|Name)\s*:\s*$",
    re.IGNORECASE,
)
_HONORIFICS = {"bey", "hanım", "beyefendi", "hanımefendi"}
_MAX_NAME_WORDS = 4
_MAX_TITLED_WORDS = 3


def tr_lower(word: str) -> str:
    """Lowercase with Turkish rules: I -> ı, İ -> i (Python's str.lower gets these wrong)."""
    return word.replace("I", "ı").replace("İ", "i").lower()


def _load_words(filename: str) -> frozenset[str]:
    lines = (_DATA / filename).read_text(encoding="utf-8").splitlines()
    return frozenset(line.strip() for line in lines if line.strip() and not line.startswith("#"))


@lru_cache(maxsize=1)
def _first_names() -> frozenset[str]:
    return _load_words("first_names_tr.txt")


@lru_cache(maxsize=1)
def _non_name_words() -> frozenset[str]:
    return _load_words("non_name_words_tr.txt")


def _runs(text: str) -> list[list[re.Match]]:
    """Group capitalized words that follow each other with only spaces between them."""
    runs: list[list[re.Match]] = []
    for m in _TOKEN.finditer(text):
        if runs and _NAME_GAP.fullmatch(text[runs[-1][-1].end():m.start()]):
            runs[-1].append(m)
        else:
            runs.append([m])
    return runs


def find_names(text: str) -> list[Entity]:
    first_names = _first_names()
    stop = _non_name_words()
    entities: list[Entity] = []

    for run in _runs(text):
        words = [tr_lower(m.group()) for m in run]
        i = 0
        while i < len(run):
            if words[i] in stop:
                i += 1
                continue

            titled = bool(_TITLE_BEFORE.search(text[max(0, run[i].start() - 20):run[i].start()]))
            if words[i] not in first_names and not titled:
                i += 1
                continue

            # Extend the name: after a first name another word may follow (second given name or surname).
            # After a title, up to 3 words are taken even if they are not in the dictionary.
            j = i
            while j + 1 < len(run) and words[j + 1] not in stop and j - i + 1 < _MAX_NAME_WORDS:
                if text[run[j].end():run[j].end() + 1] in ("'", "’"):
                    break  # "Yılmaz'ın": the suffix closes the name
                if words[j] in first_names or (titled and j - i + 1 < _MAX_TITLED_WORDS):
                    j += 1
                else:
                    break

            honorific = j + 1 < len(run) and words[j + 1] in _HONORIFICS
            if j > i or titled or honorific:
                start, end = run[i].start(), run[j].end()
                entities.append(Entity(EntityType.KISI, start, end, text[start:end]))
            i = j + 1

    return entities
