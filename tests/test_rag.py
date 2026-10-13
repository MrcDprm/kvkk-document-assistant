import asyncio

import pytest

from app.rag import TOP_K, AskError, ask, build_prompt, chunk_text, masked_document, top_k
from app.store import Session
from kvkk_mask import detect
from kvkk_mask.fakegen import make_documents
from tests.fake_llm import FakeLLM

DOC = (
    "KİRA SÖZLEŞMESİ\n\n"
    "Kiraya Veren: Ayşe Yılmaz (T.C. 10000000146), Tel: 0532 123 45 67\n\n"
    "Kira bedeli TR33 0006 1005 1978 6457 8413 26 numaralı hesaba yatırılır."
)


def make_session(text: str = DOC) -> Session:
    session = Session(id="s", last_used=0.0, text=text, entities=detect(text))
    session.pseudonymizer.mask(text, session.entities)
    return session


def run(coro):
    return asyncio.run(coro)


# --- Chunking ---

def test_short_text_is_one_chunk():
    assert chunk_text("Bir paragraf.\n\nİkinci paragraf.") == ["Bir paragraf.\n\nİkinci paragraf."]


def test_chunks_respect_size():
    text = "\n\n".join(f"Paragraf {i} " + "kelime " * 40 for i in range(30))
    chunks = chunk_text(text, size=600, overlap=100)
    assert len(chunks) > 5
    assert all(len(c) <= 600 + 300 for c in chunks)
    assert "Paragraf 0" in chunks[0] and "Paragraf 29" in chunks[-1]


def test_long_paragraph_is_split_at_spaces_only():
    text = " ".join(f"[KISI_{i}]" for i in range(400))
    chunks = chunk_text(text, size=200)
    assert len(chunks) > 1
    tokens = " ".join(chunks).split()
    assert all(t.startswith("[KISI_") and t.endswith("]") for t in tokens)


def test_short_paragraph_is_repeated_as_overlap():
    text = "A" * 500 + "\n\nKısa başlık\n\n" + "B" * 500
    chunks = chunk_text(text, size=600, overlap=50)
    assert chunks[0].endswith("Kısa başlık")
    assert chunks[1].startswith("Kısa başlık")


def test_top_k_returns_best_in_document_order():
    vectors = [[1, 0], [0, 1], [0.9, 0.1], [0.1, 0.9]]
    assert top_k([1, 0], vectors, 2) == [0, 2]


# --- Prompt ---

def test_prompt_numbers_excerpts_and_keeps_question_last():
    system, prompt = build_prompt("[KISI_1] kim?", [(1, "parça bir"), (2, "parça iki")], "tr")
    assert "takma ad" in system
    assert prompt.index("[1]") < prompt.index("[2]") < prompt.index("[KISI_1] kim?")


def test_english_prompt():
    system, prompt = build_prompt("Who is [KISI_1]?", [(1, "x")], "en")
    assert "pseudonyms" in system
    assert "Excerpt [1]" in prompt


# --- Asking ---

def test_no_personal_data_leaves_the_server():
    session = make_session()
    llm = FakeLLM()
    run(ask(session, "Ayşe Yılmaz'ın telefonu 0532 123 45 67 mi?", llm, "tr"))
    sent = llm.sent_texts()
    for value in ["Ayşe", "Yılmaz", "10000000146", "0532 123 45 67", "TR33"]:
        assert value not in sent
    assert "[KISI_1]'ın telefonu [TELEFON_1] mi?" in sent  # question masked with the same tokens


def test_answer_is_unmasked_on_the_server():
    session = make_session()
    result = run(ask(session, "Kiraya veren kim?", FakeLLM("[KISI_1] kiraya verendir [1]."), "tr"))
    assert result["answer"] == "Ayşe Yılmaz kiraya verendir [1]."
    assert result["answer_masked"] == "[KISI_1] kiraya verendir [1]."
    assert result["sources"][0]["n"] == 1
    assert "Ayşe Yılmaz" in result["sources"][0]["text"]
    assert result["usage"] == {"input_tokens": 120, "output_tokens": 12, "latency_ms": 5, "model": ""}


def test_short_document_is_sent_whole_without_embeddings():
    session = make_session()
    llm = FakeLLM()
    run(ask(session, "Kira ne kadar?", llm, "tr"))
    assert llm.embedded == []
    assert [a.kind for a in session.audit] == ["answer"]


def test_long_document_uses_retrieval():
    text = "\n\n".join(d.text for d in make_documents(12, seed=5))
    session = make_session(text)
    llm = FakeLLM()
    result = run(ask(session, "IBAN hangi hesaba?", llm, "tr"))
    tasks = [task for task, _ in llm.embedded]
    assert tasks == ["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]
    assert len(result["sources"]) == TOP_K
    assert [a.kind for a in session.audit] == ["embed_document", "embed_query", "answer"]

    # The index is reused for the next question; only the question is embedded again.
    run(ask(session, "Araç plakası ne?", llm, "tr"))
    assert [task for task, _ in llm.embedded] == tasks + ["RETRIEVAL_QUERY"]


def test_index_is_rebuilt_after_exclusion_changes():
    text = "\n\n".join(d.text for d in make_documents(12, seed=5))
    session = make_session(text)
    llm = FakeLLM()
    run(ask(session, "Kira?", llm, "tr"))
    session.excluded.add("[KISI_1]")
    run(ask(session, "Kira?", llm, "tr"))
    assert [task for task, _ in llm.embedded].count("RETRIEVAL_DOCUMENT") == 2


def test_excluded_value_is_sent_unmasked_everywhere():
    session = make_session()
    session.excluded.add("[KISI_1]")
    llm = FakeLLM()
    run(ask(session, "Ayşe Yılmaz kim?", llm, "tr"))
    _, prompt = llm.prompts[0]
    assert "Ayşe Yılmaz" in prompt  # the user chose not to mask it, in the document and the question
    assert "[TCKN_1]" in prompt
    assert masked_document(session).count("Ayşe Yılmaz") == 1


@pytest.mark.parametrize("question, code", [("   ", "empty"), ("a" * 501, "too_long")])
def test_invalid_questions(question, code):
    with pytest.raises(AskError) as info:
        run(ask(make_session(), question, FakeLLM(), "tr"))
    assert info.value.code == code


def test_question_limit_per_session():
    session = make_session()
    session.questions = 30
    with pytest.raises(AskError) as info:
        run(ask(session, "Kira?", FakeLLM(), "tr"))
    assert info.value.code == "limit"


def test_rare_name_in_lowercase_question_is_masked():
    # "Ümmühan" is not in the name dictionary; the document found it only thanks to the
    # "Adı Soyadı:" label. The question has no label and is typed in lower case.
    session = make_session("Adı Soyadı: Ümmühan Çelik\nCep Telefonu: 0532 123 45 67")
    llm = FakeLLM()
    run(ask(session, "ümmühan çelik in telefon numarası ne", llm, "tr"))
    sent = llm.sent_texts().lower()
    assert "ümmühan" not in sent and "çelik" not in sent
    assert "[KISI_1] in telefon numarası ne" in llm.sent_texts()


def test_vectors_are_stored_compactly():
    from array import array
    text = "\n\n".join(d.text for d in make_documents(12, seed=5))
    session = make_session(text)
    run(ask(session, "Kira?", FakeLLM(), "tr"))
    _, vectors = session.index
    assert all(isinstance(v, array) and v.typecode == "f" for v in vectors)
