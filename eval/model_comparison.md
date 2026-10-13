# Choosing the name model

The app runs on a free server with **0.1 CPU**, so the name recognizer had to be fast as well
as accurate. Five candidates were fine-tuned on the same data (WikiANN Turkish + synthetic
sentences, `training/train_ner.py`) and measured on the same machine.

| Model | Parameters | ONNX file | Speed (1 CPU thread) | WikiANN PER F1 | Hard cases 2 (held out): leaked names |
|---|---|---|---|---|---|
| DistilBERTurk, int8 | 66 M | 68 MB | 3,500 chars/s | 0.913 | 0 / 29 |
| YTU small, int8 (per-tensor) | 29 M | 29 MB | 10,700 chars/s | 0.883 | 0 / 29 (44 / 3800 on synthetic documents) |
| YTU mini, int8 (per-tensor) | 11.5 M | 12 MB | 35,000 chars/s | 0.824 | 1 / 29 |
| YTU mini, int8 (per-channel) | 11.5 M | 12 MB | 29,900 chars/s | 0.901 | 1 / 29 |
| **YTU mini, fp32 (chosen)** | 11.5 M | 46 MB | 24,600 chars/s | 0.912 | **0 / 29** |

Findings:

- The small uncased models matched the larger cased model on our documents. Lower-casing the
  input also makes "gülfem kurt" and "Gülfem Kurt" look the same to the model.
- int8 quantization cost the large model almost nothing (0.920 → 0.913) but hurt the small ones
  a lot with one scale per tensor (mini 0.912 → 0.824). One scale per output channel recovered
  most of it (0.901), but it still missed a name in the held-out set.
- fp32 mini is 7x faster than DistilBERTurk with the same accuracy here. On the 0.1 CPU server
  that is roughly 2,500 characters per second (a 10-page document in about 10 seconds).

Base models: [dbmdz/distilbert-base-turkish-cased](https://huggingface.co/dbmdz/distilbert-base-turkish-cased),
[ytu-ce-cosmos/turkish-small-bert-uncased](https://huggingface.co/ytu-ce-cosmos/turkish-small-bert-uncased),
[ytu-ce-cosmos/turkish-mini-bert-uncased](https://huggingface.co/ytu-ce-cosmos/turkish-mini-bert-uncased)
(Kesgin et al., 2023, [arXiv:2307.14134](https://arxiv.org/abs/2307.14134)).
