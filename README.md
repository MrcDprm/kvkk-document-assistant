# KVKK Document Assistant

**English** | [Türkçe](README.tr.md)

Ask an AI model about documents that contain Turkish personal data, without sending that data to the model. Names, Turkish ID numbers (TCKN), tax numbers, IBANs, card numbers, phone numbers, e-mails and licence plates are found, validated and replaced with pseudonyms such as `[KISI_1]`. Only the masked text leaves the server; in the answer, the pseudonyms are turned back into the real values on the server.

**Live demo:** [kvkk.miracdeprem.com](https://kvkk.miracdeprem.com). The site runs on a free server, so the first page can take about half a minute after a quiet period.

![Masking result: the original document with highlighted personal data next to the masked text that goes to the model](docs/screenshot-masking.png)

**Why:** Companies want to use large language models, but documents full of personal data cannot simply be sent to a model abroad (KVKK, the Turkish data protection law, restricts transfers abroad). Ready-made tools such as Microsoft Presidio have no Turkish recognizers. This project puts a Turkish masking layer between the documents and the model; a company would run it on its own server.

## Features

**Finding personal data**
- Numbers are validated, not just matched: TCKN and VKN check digits, IBAN mod-97, card numbers with Luhn
- Phone numbers in every common format, e-mails, licence plates (province code and letter/digit rules)
- Names are found by **a model I trained**: a small Turkish BERT fine-tuned for names, organisations and places, combined with rules for titles ("Av.", "Sn.") and labels ("Adı Soyadı:")
- A demo document generator with fake but valid data (check digits pass, nothing belongs to a real person)

**Masking**
- The same value always gets the same pseudonym, however it is written: `0532 123 45 67` and `+90 532 123 45 67` are both `[TELEFON_1]`, `AYŞE YILMAZ` and `Ayşe Yılmaz` are both `[KISI_1]`
- Before/after view; a wrong match can be removed from masking with one click
- Upload `.txt`, `.pdf` or `.docx` (max 10 MB, about 40 pages of text) or paste text

**Asking questions**
- The question is masked too, with the same pseudonyms; "gülfem kurtun telefonu" (lower case, suffix attached) still becomes `[KISI_1]un telefonu`
- Long documents: the masked chunks are embedded and the closest ones are sent (retrieval-augmented generation); short documents are sent whole
- Answers cite their source excerpts; Turkish case endings are fixed when names are put back ("Bulut'nin" → "Bulut'un")
- Audit log: every request that left the server, exactly as it was sent, with token counts, time and the model that answered

**Everywhere**
- Nothing is stored: no database, no files on disk; a document lives only in memory and is deleted after 30 minutes without use
- Turkish and English interface, light and dark theme, works on phones

## Screenshots

| | |
|---|---|
| ![Home page with the three steps and the upload form](docs/screenshot-home.png) | ![Findings table with types, values and pseudonyms](docs/screenshot-findings.png) |
| ![A question, the answer with real values, and what the model actually saw](docs/screenshot-ask.png) | ![Audit log showing the exact masked text sent to the model](docs/screenshot-audit.png) |

![Masking result in the dark theme](docs/screenshot-dark.png)

<p align="center"><img src="docs/screenshot-mobile.png" width="300" alt="Masking result on a phone"></p>

## How it works

```
document ──► text extraction ──► detection ──────────────► pseudonyms ──► masked text
             (txt, pdf, docx)    rules: numbers + checksums   [KISI_1]        │
                                 model: names, orgs, places   [TCKN_1]        │
                                                                              ▼
question ──► detection + document values ──► masked question ──► retrieval ──► LLM
                                                                              │
answer  ◄── pseudonyms replaced, case endings fixed ◄── masked answer ◄────────┘
```

1. **Extract.** The file type is checked from its content, not only its name. PDF text goes through Unicode NFC so that "ş" stored as "s + cedilla" becomes one letter again. A `.docx` is a zip file, so its unpacked size is checked first (zip bombs).
2. **Detect.** Rules find numbers and validate their check digits. The name model reads the text in windows that end at line breaks. Names the rules find only through the dictionary are dropped when the model is used (the model decides); names after a title or label are kept.
3. **Mask.** Each value gets a pseudonym that stays the same for every mention. The table from pseudonyms to real values never leaves the server.
4. **Ask.** The question is masked with the same table. Values already found in the document are also searched in the question regardless of case, Turkish letters, attached suffixes and consonant changes ("Çeliğe").
5. **Answer.** Groq models answer first (under a second); if one is out of free quota or busy, the next one is tried, then Gemini models. Embeddings come from Gemini.

## The name model

The first version found names with a dictionary and rules. In hand-written hard cases it missed names that were not in the dictionary, names typed in lower case, and treated "Umut Verici" (a headline) as a person. So I trained a model.

- **Data:** WikiANN Turkish (20,000 sentences) plus 20,000 synthetic sentences from [`training/synth.py`](training/synth.py): contracts, forms, e-mails and questions, with names in lower case or without Turkish letters, suffixes with and without apostrophes, and organisations or places that contain a first name ("Deniz Yatırım A.Ş.", "Umut Mahallesi"). Names used in the evaluation sets are excluded from training.
- **Training:** [`training/train_ner.py`](training/train_ner.py) on a free Google Colab GPU ([notebook](training/train_ner.ipynb)), a plain PyTorch loop with mixed precision, exported to ONNX.
- **Choosing the size:** the free server has 0.1 CPU, so speed mattered as much as accuracy. I trained three base models and measured them; the 11.5M-parameter model in full precision was as accurate as the 66M one and 7x faster. int8 quantization hurt the small model, so it runs in fp32. Details: [eval/model_comparison.md](eval/model_comparison.md).
- **Runtime:** only `onnxruntime` and `tokenizers`, no PyTorch on the server. The model file is attached to a [GitHub Release](https://github.com/MrcDprm/kvkk-document-assistant/releases/tag/ner-model-v1) and checked with SHA-256 when the image is built.

## Evaluation

`python -m eval.run_eval` compares the rules alone, the model alone and both together. A match counts only if type, start and end are exact. "Leaked" means a labelled value still has a visible character after masking. Full output: [eval/results.md](eval/results.md).

| Data | Detector | Name precision | Name recall | Leaked values |
|---|---|---|---|---|
| Synthetic documents (400) | Rules + model | 1.00 | 1.00 | 0 / 3800 |
| Hard cases (used while tuning) | Rules | 0.81 | 0.77 | 5 / 35 |
| Hard cases (used while tuning) | Rules + model | 1.00 | 1.00 | 0 / 35 |
| **Hard cases 2 (held out)** | Rules | 0.75 | **0.14** | 18 / 29 |
| **Hard cases 2 (held out)** | Rules + model | **1.00** | **1.00** | **0 / 29** |

The second set of hard cases was written after the tuning and never used for it. It is small (29 values), so it shows the direction rather than a precise accuracy.

## Tech Stack

- **Python**, **FastAPI**, Jinja templates and plain JavaScript (no framework, no build step)
- **Hugging Face Transformers** and **PyTorch** for training (Colab only); **ONNX Runtime** for inference
- **Groq** (gpt-oss-120b, Qwen3) and **Google Gemini** (answers and embeddings)
- **pypdf**, **python-docx** for text extraction
- **pytest** (600+ tests), **Docker** on **Render**

## Installation

Open [kvkk.miracdeprem.com](https://kvkk.miracdeprem.com), or run it locally with Python 3.12:

```bash
git clone https://github.com/MrcDprm/kvkk-document-assistant.git
cd kvkk-document-assistant
python -m venv .venv
.venv/Scripts/activate          # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
```

Optional pieces:

```bash
# the name model (without it, names are found by the rules alone)
python scripts/fetch_model.py https://github.com/MrcDprm/kvkk-document-assistant/releases/download/ner-model-v1/kvkk-ner-model-v1.zip 463ea7aa9dc903b0338a2d168a8751e0f80f9c0db96926ab501474f4536eb50d models/ner

# API keys for asking questions: copy .env.example to .env and fill in GROQ_API_KEY and/or GEMINI_API_KEY
```

Run the app (`COOKIE_SECURE=0` is needed only over plain http on your own machine):

```bash
COOKIE_SECURE=0 uvicorn app.main:app --reload --env-file .env
```

Then open `http://127.0.0.1:8000`. Tests and evaluation:

```bash
pytest
python -m eval.run_eval
```

### Project structure

```
kvkk_mask/        The masking library (no web code)
  validators.py   TCKN, VKN, IBAN and Luhn check digits
  recognizers.py  Number, phone, e-mail and plate patterns; overlap resolution
  names.py        Rule-based names: dictionary, titles, labels, Bey/Hanım
  ner.py          The trained name model (ONNX Runtime)
  known.py        Finding a document's values again in a question
  pseudonymizer.py, suffix.py   Pseudonyms, putting values back, Turkish case endings
  fakegen.py      Fake but valid data and demo documents
app/              FastAPI app: pages, upload, question answering, LLM providers, security
training/         Synthetic training data, training script, Colab notebook
eval/             Hard cases, evaluation script, results and model comparison
scripts/          Model download with SHA-256 check (used in the Dockerfile)
tests/            pytest suites
```

### Security and privacy

- Personal data never reaches the model: documents and questions are masked; the audit log shows exactly what was sent
- Nothing is written to disk or a database; uploads stay in memory (Starlette's spill-to-disk is turned off), sessions expire after 30 minutes
- Session cookie is HttpOnly, Secure and SameSite=Lax with a 256-bit random id; POSTs from other sites are refused (Origin check)
- Strict Content Security Policy (only the site's own scripts and styles, no inline code, no third-party requests), HSTS, `nosniff`, `Cache-Control: no-store`, no CORS
- Upload checks: type from content, size limits before parsing, zip-bomb check, XML entities disabled
- Rate limiting per IP, a host name allow-list, no stack traces or provider errors shown to users
- Instructions inside a document are treated as data; even if a model followed them, it has no real personal data to reveal
- API keys are server-side environment variables; `.env` is ignored by git

### Limitations

- A name that is neither in the document nor recognisable by the model, typed in lower case in a question, can reach the model unmasked
- Addresses are not detected yet; scanned (image-only) PDFs have no text to read
- The free server analyses about 2,500 characters per second with the model, so a 40-page document takes around 40 seconds
- WikiANN's license is listed as unknown; it was used only to train the model and is not redistributed. The base model's card does not state a license

## What I Learned

- **A privacy tool is only as good as its weakest input.** My tests passed, but when I asked "gülfem kurtun telefonu ne" on the live site, the name went to the model unmasked: the question had no "Adı Soyadı:" label, it was lower case and the suffix was attached. I fixed it by searching the document's values in the question, then wrote a systematic test with 12,000 spellings of every name. Before the fix 67% of them leaked; after, none.
- **Measuring before and after.** I wrote an evaluation script before training anything, so I could see that the rules found only 14% of names in a held-out set and the model found all of them. Keeping a second set that I never tuned on made the numbers honest.
- **Training and shipping a model.** I prepared token-level labels (IOB2), aligned them to sub-words, fine-tuned BERT models on a Colab GPU and exported them to ONNX so the server needs no PyTorch.
- **Model size is a product decision.** On 0.1 CPU, the most accurate model was too slow. I compared three sizes and two precisions; int8 cost the big model almost nothing but hurt the small one, so I shipped the small model in fp32.
- **Turkish text has its own traps.** Python's `lower()` turns "I" into "i" instead of "ı", `capitalize()` gives "Irem" instead of "İrem", PDFs can store "ş" as two characters, and suffixes follow vowel harmony. Each of these caused a real bug.
- **Free tiers are not a production plan.** Gemini 2.5 Flash allows 20 requests a day; another model took 10–35 seconds or returned "busy". I put the providers behind one interface and built a fallback chain, so the demo keeps answering.

## Credits

- Base model: [ytu-ce-cosmos/turkish-mini-bert-uncased](https://huggingface.co/ytu-ce-cosmos/turkish-mini-bert-uncased) (Kesgin et al., 2023)
- Training data: [WikiANN](https://huggingface.co/datasets/unimelb-nlp/wikiann) (Pan et al., 2017; Rahimi et al., 2019)

## License

[MIT](LICENSE)
