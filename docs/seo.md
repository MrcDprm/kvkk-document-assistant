# SEO: KVKK Document Assistant

Site: https://kvkk.miracdeprem.com (Turkish by default, English with `?lang=en`)

Only the home page is for search. The document page holds a private, temporary session: it carries `noindex` and is closed in `robots.txt`.

## Keywords

| Type | Turkish | English |
|---|---|---|
| General | KVKK, kişisel veri maskeleme, kişisel veri anonimleştirme | personal data masking, data anonymization, PII redaction |
| Specific | KVKK uyumlu yapay zekâ, belgedeki kişisel verileri gizleme, T.C. kimlik no maskeleme, IBAN maskeleme, ChatGPT'ye kişisel veri göndermeden belge sorma | Turkish PII detection, mask personal data before sending to an LLM, KVKK compliant AI, Turkish named entity recognition |
| Technical | Türkçe NER modeli, RAG ile belge soru cevap, takma adlandırma (pseudonymization) | Turkish NER model, RAG document question answering, pseudonymization |

## Where they are used

- `<title>` "KVKK Belge Asistanı: kişisel veriyi maskele, belgeye soru sor" / "KVKK Document Assistant: mask personal data, ask your documents"; meta description lists the data types (T.C. kimlik no, IBAN, telefon, e-posta)
- Canonical + `hreflang` (tr, en, x-default) on the home page; `?lang=en` wins over the cookie and the browser language
- Open Graph and Twitter card with `/static/og-image.png`
- JSON-LD `WebApplication` (free, source code link)
- `/sitemap.xml` and `/robots.txt` (GET and HEAD)

## Google Search Console

The `miracdeprem.com` domain property covers this subdomain. Under **Sitemaps**, submit `https://kvkk.miracdeprem.com/sitemap.xml`. The site runs on Render's free plan and sleeps when idle, so the first fetch may fail once; Google retries.
