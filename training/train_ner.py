"""Fine-tune a Turkish BERT for NER (PER, ORG, LOC) and export it as an int8 ONNX model.

Runs on Google Colab with a GPU (see train_ner.ipynb); a few minutes on a T4.
    python -m training.train_ner --model mini --out /content/kvkk-ner-mini

Three base models are supported, from large to small: the free server has 0.1 CPU, so the
speed / accuracy trade-off is measured instead of assumed.

Data: WikiANN Turkish (Wikipedia sentences) + synthetic document/question sentences
(training/synth.py). The output folder holds everything the app needs at runtime:
model.onnx (full precision), model-int8.onnx, tokenizer.json, labels.json, preprocess.json
and metrics.json for the README.
"""

import argparse
import json
import random
import shutil
import time
from pathlib import Path

from kvkk_mask.names import tr_lower
from training.synth import LABELS, SynthGenerator

# name: (Hugging Face id, lower-case input?, learning rate)
# The YTU Cosmos models are uncased: they expect text lower-cased with Turkish rules.
BASE_MODELS = {
    "distil": ("dbmdz/distilbert-base-turkish-cased", False, 5e-5),  # 6 layers, 768 hidden
    "small": ("ytu-ce-cosmos/turkish-small-bert-uncased", True, 1e-4),  # 4 layers, 512 hidden
    "mini": ("ytu-ce-cosmos/turkish-mini-bert-uncased", True, 2e-4),  # 4 layers, 256 hidden
}
MAX_LENGTH = 128
SYNTH_TRAIN = 20_000
SYNTH_DEV = 2_000


# --- Data ---

def load_wikiann():
    from datasets import load_dataset

    data = load_dataset("unimelb-nlp/wikiann", "tr")
    # WikiANN uses the same label order as LABELS (O, B-PER, I-PER, B-ORG, I-ORG, B-LOC, I-LOC).
    names = data["train"].features["ner_tags"].feature.names
    assert names == LABELS, names

    def rows(split):
        return [(r["tokens"], [LABELS[t] for t in r["ner_tags"]]) for r in data[split]]

    return rows("train"), rows("validation")


def build_datasets(seed: int = 42):
    wiki_train, wiki_dev = load_wikiann()
    synth = SynthGenerator(seed=seed)
    synth_train, synth_dev = synth.sentences(SYNTH_TRAIN), synth.sentences(SYNTH_DEV)
    train = wiki_train + synth_train
    random.Random(seed).shuffle(train)
    return train, {"wikiann": wiki_dev, "synthetic": synth_dev}


def prepare(tokens: list[str], lowercase: bool) -> list[str]:
    return [tr_lower(t) for t in tokens] if lowercase else tokens


def encode(tokenizer, tokens: list[str], tags: list[str], lowercase: bool = False) -> dict:
    """Tokenize pre-split words; only the first sub-word of each word carries the label.

    Other sub-words get -100, which the loss ignores. ("Karaosmanoğlu" -> "Kara", "##osman", ...)
    """
    enc = tokenizer(prepare(tokens, lowercase), is_split_into_words=True, truncation=True, max_length=MAX_LENGTH)
    labels, previous = [], None
    for word_id in enc.word_ids():
        if word_id is None or word_id == previous:
            labels.append(-100)
        else:
            labels.append(LABELS.index(tags[word_id]))
        previous = word_id
    return {"input_ids": enc["input_ids"], "attention_mask": enc["attention_mask"], "labels": labels}


# --- Metrics (entity level, like seqeval) ---

def spans(tags: list[str]) -> set[tuple[str, int, int]]:
    found, start, kind = set(), None, None
    for i, tag in enumerate(tags + ["O"]):
        if start is not None and not (tag.startswith("I-") and tag[2:] == kind):
            found.add((kind, start, i))
            start = None
        if tag.startswith("B-") or (tag.startswith("I-") and start is None):
            start, kind = i, tag[2:]
    return found


def f1_report(gold: list[list[str]], predicted: list[list[str]]) -> dict:
    report = {}
    for kind in ("PER", "ORG", "LOC", "ALL"):
        tp = fp = fn = 0
        for g, p in zip(gold, predicted):
            gs = {s for s in spans(g) if kind == "ALL" or s[0] == kind}
            ps = {s for s in spans(p) if kind == "ALL" or s[0] == kind}
            tp, fp, fn = tp + len(gs & ps), fp + len(ps - gs), fn + len(gs - ps)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        report[kind] = {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}
    return report


def word_predictions(word_ids: list, logits_row) -> list[int]:
    """Label of each word = prediction on its first sub-word."""
    out, previous = [], None
    for position, word_id in enumerate(word_ids):
        if word_id is not None and word_id != previous:
            out.append(int(logits_row[position].argmax()))
        previous = word_id
    return out


# --- Training ---

def train(out: Path, base: str, epochs: int, batch_size: int, seed: int) -> None:
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForTokenClassification, AutoTokenizer, DataCollatorForTokenClassification
    from transformers import get_linear_schedule_with_warmup

    base_model, lowercase, lr = BASE_MODELS[base]
    torch.manual_seed(seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"device: {device}")

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForTokenClassification.from_pretrained(
        base_model,
        num_labels=len(LABELS),
        id2label=dict(enumerate(LABELS)),
        label2id={label: i for i, label in enumerate(LABELS)},
    ).to(device)

    train_rows, dev_sets = build_datasets(seed)
    print(f"train sentences: {len(train_rows)}; dev: " + ", ".join(f"{k} {len(v)}" for k, v in dev_sets.items()))
    collate = DataCollatorForTokenClassification(tokenizer)
    loader = DataLoader([encode(tokenizer, t, g, lowercase) for t, g in train_rows], batch_size=batch_size, shuffle=True, collate_fn=collate)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
    steps = epochs * len(loader)
    scheduler = get_linear_schedule_with_warmup(optimizer, int(0.1 * steps), steps)
    scaler = torch.amp.GradScaler(enabled=device == "cuda")

    started = time.time()
    for epoch in range(epochs):
        model.train()
        total = 0.0
        for step, batch in enumerate(loader, start=1):
            batch = {k: v.to(device) for k, v in batch.items()}
            with torch.autocast(device_type=device, dtype=torch.float16, enabled=device == "cuda"):
                loss = model(**batch).loss
            optimizer.zero_grad()
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            total += loss.item()
            if step % 200 == 0:
                print(f"epoch {epoch + 1} step {step}/{len(loader)} loss {total / step:.4f}")
        scores = {name: evaluate_torch(model, tokenizer, rows, device, lowercase) for name, rows in dev_sets.items()}
        print(f"epoch {epoch + 1} done in {time.time() - started:.0f}s: " + json.dumps({k: v['ALL'] for k, v in scores.items()}))

    out.mkdir(parents=True, exist_ok=True)
    hf_dir = out / "hf"
    model.save_pretrained(hf_dir)
    tokenizer.save_pretrained(hf_dir)
    export_onnx(model.cpu().eval(), tokenizer, out, lowercase)

    metrics = {
        "base_model": base_model,
        "parameters": sum(p.numel() for p in model.parameters()),
        "epochs": epochs,
        "train_sentences": len(train_rows),
        "training_seconds": round(time.time() - started),
        "pytorch": scores,
        "onnx_fp32": {name: evaluate_onnx(out / "model.onnx", tokenizer, rows, lowercase) for name, rows in dev_sets.items()},
        "onnx_int8": {name: evaluate_onnx(out / "model-int8.onnx", tokenizer, rows, lowercase) for name, rows in dev_sets.items()},
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


def evaluate_torch(model, tokenizer, rows, device, lowercase: bool) -> dict:
    import torch

    model.eval()
    gold, predicted = [], []
    with torch.no_grad():
        for tokens, tags in rows:
            enc = tokenizer(prepare(tokens, lowercase), is_split_into_words=True, truncation=True, max_length=MAX_LENGTH, return_tensors="pt")
            logits = model(input_ids=enc["input_ids"].to(device), attention_mask=enc["attention_mask"].to(device)).logits[0].cpu()
            labels = word_predictions(enc.word_ids(), logits)
            gold.append(tags[:len(labels)])
            predicted.append([LABELS[i] for i in labels])
    return f1_report(gold, predicted)


# --- Export ---

def export_onnx(model, tokenizer, out: Path, lowercase: bool) -> None:
    import torch
    from onnxruntime.quantization import QuantType, quantize_dynamic

    sample = tokenizer(prepare(["Ayşe", "Yılmaz", "aradı"], lowercase), is_split_into_words=True, return_tensors="pt")
    fp32 = out / "model.onnx"
    torch.onnx.export(
        model,
        (sample["input_ids"], sample["attention_mask"]),
        str(fp32),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={"input_ids": {0: "batch", 1: "seq"}, "attention_mask": {0: "batch", 1: "seq"}, "logits": {0: "batch", 1: "seq"}},
        opset_version=17,
        dynamo=False,
    )
    # int8 weights: about 4x smaller and faster on CPU. Small models lose more accuracy than large
    # ones, so both files are kept and measured; per-channel scales lose less than one scale per tensor.
    quantize_dynamic(str(fp32), str(out / "model-int8.onnx"), weight_type=QuantType.QInt8, per_channel=True)

    tokenizer.backend_tokenizer.save(str(out / "tokenizer.json"))
    (out / "labels.json").write_text(json.dumps(LABELS), encoding="utf-8")
    (out / "preprocess.json").write_text(json.dumps({"lowercase": lowercase}), encoding="utf-8")


def evaluate_onnx(model_file: Path, tokenizer, rows, lowercase: bool) -> dict:
    import numpy as np
    import onnxruntime as ort

    session = ort.InferenceSession(str(model_file), providers=["CPUExecutionProvider"])
    gold, predicted = [], []
    for tokens, tags in rows:
        enc = tokenizer(prepare(tokens, lowercase), is_split_into_words=True, truncation=True, max_length=MAX_LENGTH, return_tensors="np")
        logits = session.run(["logits"], {
            "input_ids": enc["input_ids"].astype(np.int64),
            "attention_mask": enc["attention_mask"].astype(np.int64),
        })[0][0]
        labels = word_predictions(enc.word_ids(), logits)
        gold.append(tags[:len(labels)])
        predicted.append([LABELS[i] for i in labels])
    return f1_report(gold, predicted)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=BASE_MODELS, default="mini")
    parser.add_argument("--out", type=Path, default=Path("kvkk-ner"))
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    train(args.out, args.model, args.epochs, args.batch_size, args.seed)
    shutil.rmtree(args.out / "hf", ignore_errors=True)  # only the ONNX files are shipped
    archive = shutil.make_archive(str(args.out), "zip", args.out)
    print(f"done: {archive}")


if __name__ == "__main__":
    main()
