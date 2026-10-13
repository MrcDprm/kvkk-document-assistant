"""Measure the detector on labeled data and write eval/results.md.

Two data sets:
- synthetic: demo documents from kvkk_mask.fakegen (labels come from the generator),
- hard cases: hand-written sentences in eval/hard_cases.txt.

A detection counts as correct only when type, start and end all match the label.
"Leak" counts labeled values that still have at least one visible character after masking.

Three detectors are compared: rules only, the trained model only (names from the model,
numbers still from the checksum rules), and both together (what the app uses).
The model is loaded from models/ner when it is there.

Run: python -m eval.run_eval
"""

import os
import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kvkk_mask import detect
from kvkk_mask.fakegen import make_documents
from kvkk_mask.ner import NerModel
from kvkk_mask.recognizers import Entity, EntityType, find_entities

_HERE = Path(__file__).parent
_MARKUP = re.compile(r"\[\[(\w+):(.+?)\]\]")
SYNTHETIC_COUNT = 400


@dataclass
class Case:
    text: str
    gold: list[Entity]


def parse_markup(marked: str) -> Case:
    """Turn "[[KISI:Ayşe Yılmaz]] aradı" into plain text plus labeled entities."""
    parts: list[str] = []
    gold: list[Entity] = []
    pos = 0
    length = 0
    for m in _MARKUP.finditer(marked):
        parts.append(marked[pos:m.start()])
        length += m.start() - pos
        value = m.group(2)
        gold.append(Entity(EntityType(m.group(1)), length, length + len(value), value))
        parts.append(value)
        length += len(value)
        pos = m.end()
    parts.append(marked[pos:])
    return Case("".join(parts), gold)


def load_hard_cases(filename: str = "hard_cases.txt") -> list[Case]:
    raw = (_HERE / filename).read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if not line.startswith("#")]
    blocks = "\n".join(lines).split("\n\n")
    return [parse_markup(b.strip()) for b in blocks if b.strip()]


def synthetic_cases() -> list[Case]:
    return [Case(d.text, d.entities) for d in make_documents(SYNTHETIC_COUNT, seed=2026)]


@dataclass
class Score:
    tp: Counter
    fp: Counter
    fn: Counter
    leaked: int
    total: int
    ms_per_doc: float
    errors: list[str]


Detector = Callable[[str], list[Entity]]


def evaluate(cases: list[Case], detector: Detector = detect) -> Score:
    tp, fp, fn = Counter(), Counter(), Counter()
    leaked = total = 0
    errors: list[str] = []
    started = time.perf_counter()
    predictions = [detector(c.text) for c in cases]
    ms_per_doc = (time.perf_counter() - started) * 1000 / len(cases)

    for case, predicted in zip(cases, predictions):
        gold = {(e.type, e.start, e.end) for e in case.gold}
        found = {(e.type, e.start, e.end) for e in predicted}
        for t, s, e in found & gold:
            tp[t] += 1
        for t, s, e in found - gold:
            fp[t] += 1
            errors.append(f"FP {t.value}: {case.text[s:e]!r}")
        for t, s, e in gold - found:
            fn[t] += 1
            errors.append(f"FN {t.value}: {case.text[s:e]!r}")

        covered = set()
        for e in predicted:
            covered.update(range(e.start, e.end))
        for e in case.gold:
            total += 1
            if not set(range(e.start, e.end)) <= covered:
                leaked += 1

    return Score(tp, fp, fn, leaked, total, ms_per_doc, errors)


def _ratio(a: int, b: int) -> str:
    return f"{a / b:.2f}" if b else "-"


def table(score: Score) -> str:
    rows = ["| Type | Precision | Recall | TP | FP | FN |", "|---|---|---|---|---|---|"]
    all_tp = all_fp = all_fn = 0
    for t in EntityType:
        tp, fp, fn = score.tp[t], score.fp[t], score.fn[t]
        if tp + fp + fn == 0:
            continue
        rows.append(f"| {t.value} | {_ratio(tp, tp + fp)} | {_ratio(tp, tp + fn)} | {tp} | {fp} | {fn} |")
        all_tp, all_fp, all_fn = all_tp + tp, all_fp + fp, all_fn + fn
    rows.append(
        f"| **All** | **{_ratio(all_tp, all_tp + all_fp)}** | **{_ratio(all_tp, all_tp + all_fn)}** "
        f"| {all_tp} | {all_fp} | {all_fn} |"
    )
    return "\n".join(rows)


def detectors() -> dict[str, Detector]:
    found: dict[str, Detector] = {"Rules": detect}
    model_dir = os.environ.get("KVKK_NER_MODEL", "models/ner")
    if NerModel.available(model_dir):
        model = NerModel(model_dir)
        found["Model"] = lambda text: find_entities(text, extra=model.find_names(text))
        found["Rules + model"] = lambda text: detect(text, ner=model)
    return found


def _person_scores(score: Score) -> tuple[str, str]:
    t = EntityType.KISI
    return _ratio(score.tp[t], score.tp[t] + score.fp[t]), _ratio(score.tp[t], score.tp[t] + score.fn[t])


def report() -> str:
    datasets = [
        (f"Synthetic documents ({SYNTHETIC_COUNT})", synthetic_cases()),
        ("Hard cases (tuning set)", load_hard_cases()),
        ("Hard cases 2 (held out)", load_hard_cases("hard_cases_2.txt")),
    ]
    modes = detectors()
    scores = {(d, m): evaluate(cases, fn) for d, cases in datasets for m, fn in modes.items()}

    summary = [
        "| Data | Detector | Name precision | Name recall | Leaked values | ms / document |",
        "|---|---|---|---|---|---|",
    ]
    for d, _ in datasets:
        for m in modes:
            score = scores[(d, m)]
            precision, recall = _person_scores(score)
            summary.append(
                f"| {d} | {m} | {precision} | {recall} | {score.leaked} / {score.total} | {score.ms_per_doc:.2f} |"
            )

    sections = [
        "# Evaluation results",
        "",
        "Generated by `python -m eval.run_eval`. Exact span match. "
        "Numbers (TCKN, IBAN, card...) always come from the checksum rules; the detectors differ in names.",
        "",
        "## Summary",
        "",
        *summary,
        "",
    ]
    best = list(modes)[-1]
    for d, _ in datasets:
        score = scores[(d, best)]
        sections += [f"## {d}: {best}", "", table(score), ""]
        if score.errors:
            sections += ["Errors:", "", *[f"- {e}" for e in sorted(score.errors)], ""]
    if len(modes) > 1:
        rules = scores[(datasets[1][0], "Rules")]
        sections += ["## Hard cases: errors of the rules alone", "", *[f"- {e}" for e in sorted(rules.errors)], ""]
    return "\n".join(sections)


if __name__ == "__main__":
    text = report()
    (_HERE / "results.md").write_text(text, encoding="utf-8", newline="\n")
    print(text)
