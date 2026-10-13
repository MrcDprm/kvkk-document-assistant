import asyncio
import json

import httpx
import pytest

from app.llm import ChainLLM, Generation, GroqLLM, LLMError
from app.main import build_llm
from tests.test_app import make_settings


def run(coro):
    return asyncio.run(coro)


class Fixed:
    def __init__(self, name: str, error: str | None = None) -> None:
        self.name, self.error, self.calls = name, error, 0

    async def generate(self, system: str, prompt: str) -> Generation:
        self.calls += 1
        if self.error:
            raise LLMError(self.error)
        return Generation(f"answer from {self.name}", 10, 2, 5, self.name)


# --- Chain ---

def test_chain_uses_the_first_working_model():
    first, second = Fixed("groq"), Fixed("gemini")
    assert run(ChainLLM([first, second], None).generate("s", "p")).model == "groq"
    assert second.calls == 0


@pytest.mark.parametrize("code", ["quota", "unavailable"])
def test_chain_falls_back_on_quota_or_outage(code):
    first, second = Fixed("groq", error=code), Fixed("gemini")
    assert run(ChainLLM([first, second], None).generate("s", "p")).model == "gemini"


def test_chain_raises_the_last_error_when_all_fail():
    chain = ChainLLM([Fixed("a", "unavailable"), Fixed("b", "quota")], None)
    with pytest.raises(LLMError) as info:
        run(chain.generate("s", "p"))
    assert info.value.code == "quota"


def test_blocked_answer_is_not_retried():
    first, second = Fixed("groq", error="blocked"), Fixed("gemini")
    with pytest.raises(LLMError):
        run(ChainLLM([first, second], None).generate("s", "p"))
    assert second.calls == 0


def test_chain_without_gemini_cannot_embed():
    with pytest.raises(LLMError):
        run(ChainLLM([Fixed("groq")], None).embed(["x"], "RETRIEVAL_QUERY"))


# --- Groq over HTTP (mocked transport, no network) ---

def groq_with(handler) -> GroqLLM:
    return GroqLLM("test-key", "llama-test", transport=httpx.MockTransport(handler))


def test_groq_request_and_answer():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": " [KISI_1] kiracıdır [1]. "}}],
            "usage": {"prompt_tokens": 321, "completion_tokens": 9},
        })

    result = run(groq_with(handler).generate("system text", "prompt text"))
    assert result == Generation("[KISI_1] kiracıdır [1].", 321, 9, result.latency_ms, "llama-test")
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["messages"] == [
        {"role": "system", "content": "system text"},
        {"role": "user", "content": "prompt text"},
    ]


@pytest.mark.parametrize("status, code", [(429, "quota"), (500, "unavailable"), (401, "unavailable")])
def test_groq_errors(status, code):
    with pytest.raises(LLMError) as info:
        run(groq_with(lambda r: httpx.Response(status, json={"error": "x"})).generate("s", "p"))
    assert info.value.code == code


def test_groq_unexpected_body():
    with pytest.raises(LLMError):
        run(groq_with(lambda r: httpx.Response(200, json={"nope": 1})).generate("s", "p"))


def test_groq_network_error():
    def handler(request):
        raise httpx.ConnectError("down")

    with pytest.raises(LLMError) as info:
        run(groq_with(handler).generate("s", "p"))
    assert info.value.code == "unavailable"


# --- Building the chain from settings ---

def test_no_keys_no_llm():
    assert build_llm(make_settings()) is None


def test_groq_only():
    llm = build_llm(make_settings(groq_api_key="g"))
    assert [type(g).__name__ for g in llm._generators] == ["GroqLLM"]


def test_groq_then_gemini_models():
    settings = make_settings(groq_api_key="g", groq_models=["x", "y"], gemini_api_key="k", gemini_models=["a", "b"])
    llm = build_llm(settings)
    assert [type(g).__name__ for g in llm._generators] == ["GroqLLM", "GroqLLM", "GeminiLLM", "GeminiLLM"]
    assert llm._embedder is not None


@pytest.mark.parametrize(
    "model, expected",
    [("openai/gpt-oss-120b", "low"), ("qwen/qwen3.8-27b", "none"), ("some/other-model", None)],
)
def test_reasoning_is_kept_short(model, expected):
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}], "usage": {}})

    run(GroqLLM("k", model, transport=httpx.MockTransport(handler)).generate("s", "p"))
    assert seen.get("reasoning_effort") == expected
