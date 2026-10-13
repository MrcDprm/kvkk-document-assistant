English | [Türkçe](README.tr.md)

# KVKK Document Assistant

Ask an LLM about documents that contain Turkish personal data without sending that data to the model. Personal data is detected, validated and replaced with reversible pseudonyms; only the masked text leaves the server.

> Draft: work in progress.

## Features (MVP plan)
- Upload `.txt`, `.pdf` or `.docx` (max 2 MB) or paste text
- Turkish recognizers with validation: TCKN and VKN (checksum), IBAN (mod-97), card number (Luhn), phone, e-mail, licence plate, full name
- Before/after view with consistent pseudonyms (`[KISI_1]`); remove a false positive with one click
- Ask questions about the document: retrieval over masked chunks, answers with sources, pseudonyms restored locally
- Audit log: exactly what was sent to the LLM, token count and latency
- Realistic fake test data generator (valid-checksum TCKN/IBAN), also used for evaluation
- TR/EN, light/dark theme, rate limiting, strict CSP; nothing is stored (memory only, 30 min)

## Future Plans
- Turkish NER model for names, address detection
- Self-hosted LLM option (Ollama)
