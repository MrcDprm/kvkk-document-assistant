"""Turkish NER model (fine-tuned DistilBERTurk, int8 ONNX) for finding names.

Only onnxruntime and tokenizers are needed at runtime (no PyTorch), so it fits a small server.
The model files come from training/train_ner.py: model.onnx, tokenizer.json, labels.json.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from kvkk_mask.names import non_name_words, tr_lower
from kvkk_mask.recognizers import Entity, EntityType

_WORD = re.compile(r"\w+(?:[.]\w+)*|[^\w\s]")
MAX_WORDS = 100  # per window; training sentences were short, so long texts are cut at sentence ends
BATCH = 16
# The model sometimes takes the word next to a name into the name ("Ayşe Kaya Hanım", "Ben Ayşe").
_EDGE_WORDS = {"ben", "bana", "beni", "benim", "biz", "bize", "sen", "sana", "siz", "size", "o", "ona", "onu", "bu", "şu"}


def split_words(text: str) -> list[tuple[str, int, int]]:
    """Words and punctuation with character positions; the same split used in training."""
    return [(m.group(), m.start(), m.end()) for m in _WORD.finditer(text)]


@dataclass(frozen=True)
class Span:
    label: str  # PER, ORG or LOC
    start: int
    end: int


class NerModel:
    def __init__(self, model_dir: str | Path, threads: int = 2, model_file: str = "model.onnx") -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        model_dir = Path(model_dir)
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        self._session = ort.InferenceSession(str(model_dir / model_file), options, providers=["CPUExecutionProvider"])
        self._tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self._tokenizer.no_padding()
        self._tokenizer.enable_truncation(512)
        self._labels = json.loads((model_dir / "labels.json").read_text(encoding="utf-8"))
        settings = model_dir / "preprocess.json"
        # Uncased models expect text lower-cased with Turkish rules (I -> ı, İ -> i).
        self._lowercase = settings.is_file() and json.loads(settings.read_text(encoding="utf-8")).get("lowercase", False)

    @staticmethod
    def available(model_dir: str | Path) -> bool:
        model_dir = Path(model_dir)
        return all((model_dir / f).is_file() for f in ("model.onnx", "tokenizer.json", "labels.json"))

    def _windows(self, text: str, words: list[tuple[str, int, int]]) -> list[list[int]]:
        """Indexes of words, grouped into windows that end at a line break or sentence end."""
        windows: list[list[int]] = [[]]
        for i, (word, _, end) in enumerate(words):
            windows[-1].append(i)
            next_start = words[i + 1][1] if i + 1 < len(words) else end
            boundary = "\n" in text[end:next_start] or word in (".", "?", "!")
            if (boundary and len(windows[-1]) >= 8) or len(windows[-1]) >= MAX_WORDS:
                windows.append([])
        return [w for w in windows if w]

    def _predict_batch(self, batch: list[list[str]]) -> list[list[str]]:
        import numpy as np

        if self._lowercase:
            batch = [[tr_lower(w) for w in words] for words in batch]
        encodings = [self._tokenizer.encode(words, is_pretokenized=True) for words in batch]
        length = max(len(e.ids) for e in encodings)
        ids = np.zeros((len(batch), length), dtype=np.int64)
        mask = np.zeros((len(batch), length), dtype=np.int64)
        for row, e in enumerate(encodings):
            ids[row, :len(e.ids)] = e.ids
            mask[row, :len(e.ids)] = 1
        logits = self._session.run(["logits"], {"input_ids": ids, "attention_mask": mask})[0]

        results = []
        for row, e in enumerate(encodings):
            labels = ["O"] * len(batch[row])
            previous = None
            for position, word_id in enumerate(e.word_ids):
                if word_id is not None and word_id != previous:  # first sub-word decides
                    labels[word_id] = self._labels[int(logits[row, position].argmax())]
                previous = word_id
            results.append(labels)
        return results

    def spans(self, text: str) -> list[Span]:
        words = split_words(text)
        if not words:
            return []
        tags = ["O"] * len(words)
        windows = self._windows(text, words)
        for b in range(0, len(windows), BATCH):
            group = windows[b:b + BATCH]
            for window, labels in zip(group, self._predict_batch([[words[i][0] for i in w] for w in group])):
                for i, label in zip(window, labels):
                    tags[i] = label

        found: list[Span] = []
        start = kind = None
        for i, tag in enumerate(tags + ["O"]):
            # A name never continues onto the next line ("Kezban Çetin", then "T.C. Kimlik No").
            if 0 < i < len(words) and "\n" in text[words[i - 1][2]:words[i][1]] and tag.startswith("I-"):
                tag = "B-" + tag[2:]
            if start is not None and not (tag.startswith("I-") and tag[2:] == kind):
                first, last = start, i - 1
                if kind == "PER":
                    first, last = self._trim(words, first, last)
                if first <= last:
                    found.append(Span(kind, words[first][1], words[last][2]))
                start = None
            if tag.startswith("B-") or (tag.startswith("I-") and start is None):
                start, kind = i, tag[2:]
        return found

    @staticmethod
    def _trim(words: list[tuple[str, int, int]], first: int, last: int) -> tuple[int, int]:
        drop = non_name_words() | _EDGE_WORDS
        while first <= last and (tr_lower(words[first][0]) in drop or not words[first][0][0].isalpha()):
            first += 1
        while last >= first and (tr_lower(words[last][0]) in drop or not words[last][0][0].isalpha()):
            last -= 1
        return first, last

    def find_names(self, text: str) -> list[Entity]:
        return [Entity(EntityType.KISI, s.start, s.end, text[s.start:s.end]) for s in self.spans(text) if s.label == "PER"]
