"""LLM providers behind a small interface, so tests (and other providers) can replace them.

Only masked text is ever passed to this module.

Free tiers are small and sometimes busy (Gemini 2.5 Flash: 20 requests a day), so answers go
through a chain: Groq first (fast, ~1,000 requests a day), then Gemini models. A provider that
is out of quota or unavailable is skipped. Embeddings always come from Gemini (Groq has none).
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Protocol

import httpx
from google import genai
from google.genai import errors, types

TIMEOUT_SECONDS = 45
EMBED_BATCH = 100  # the API accepts up to 100 texts per embedding request


@dataclass(frozen=True)
class Generation:
    text: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    model: str = ""


class LLMError(Exception):
    """`code` is shown to the user as a translated message: quota, unavailable, blocked."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class LLM(Protocol):
    async def embed(self, texts: list[str], task: str) -> list[list[float]]: ...

    async def generate(self, system: str, prompt: str) -> Generation: ...


class Generator(Protocol):
    async def generate(self, system: str, prompt: str) -> Generation: ...


def _status_error(status: int) -> LLMError:
    return LLMError("quota" if status == 429 else "unavailable")


class GeminiLLM:
    def __init__(self, api_key: str, model: str, embed_model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._embed_model = embed_model

    async def embed(self, texts: list[str], task: str) -> list[list[float]]:
        """`task` is RETRIEVAL_DOCUMENT for chunks and RETRIEVAL_QUERY for the question."""
        vectors: list[list[float]] = []
        try:
            for i in range(0, len(texts), EMBED_BATCH):
                batch = texts[i:i + EMBED_BATCH]
                response = await asyncio.wait_for(
                    self._client.aio.models.embed_content(
                        model=self._embed_model,
                        contents=batch,
                        config=types.EmbedContentConfig(task_type=task, output_dimensionality=768),
                    ),
                    TIMEOUT_SECONDS,
                )
                vectors.extend(e.values for e in response.embeddings)
        except errors.APIError as exc:
            raise _status_error(exc.code) from exc
        except Exception as exc:
            raise LLMError("unavailable") from exc
        if len(vectors) != len(texts):
            raise LLMError("unavailable")  # some models merge a list into one vector
        return vectors

    async def generate(self, system: str, prompt: str) -> Generation:
        started = time.perf_counter()
        try:
            response = await asyncio.wait_for(
                self._client.aio.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=0.2,
                        max_output_tokens=1024,
                        # Answers come from the given excerpts; "thinking" only adds latency here.
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                ),
                TIMEOUT_SECONDS,
            )
        except errors.APIError as exc:
            raise _status_error(exc.code) from exc
        except Exception as exc:
            raise LLMError("unavailable") from exc

        text = (response.text or "").strip()
        if not text:
            raise LLMError("blocked")  # empty answer, e.g. stopped by a safety filter
        usage = response.usage_metadata
        return Generation(
            text=text,
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
            latency_ms=round((time.perf_counter() - started) * 1000),
            model=self._model,
        )


class GroqLLM:
    """Groq's OpenAI-compatible chat API, called with plain HTTP (no extra SDK)."""

    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._model = model
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"}, timeout=TIMEOUT_SECONDS, transport=transport
        )

    async def generate(self, system: str, prompt: str) -> Generation:
        started = time.perf_counter()
        body = {
            "model": self._model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 1024,
        }
        try:
            response = await self._client.post(self.URL, json=body)
        except httpx.HTTPError as exc:
            raise LLMError("unavailable") from exc
        if response.status_code != 200:
            raise _status_error(response.status_code)
        try:
            data = response.json()
            text = (data["choices"][0]["message"]["content"] or "").strip()
            usage = data.get("usage") or {}
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("unavailable") from exc
        if not text:
            raise LLMError("blocked")
        return Generation(
            text=text,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=round((time.perf_counter() - started) * 1000),
            model=self._model,
        )


class ChainLLM:
    """Try each generator in order; skip the ones that are out of quota or unavailable."""

    def __init__(self, generators: list[Generator], embedder: GeminiLLM | None) -> None:
        if not generators:
            raise ValueError("at least one generator is needed")
        self._generators = generators
        self._embedder = embedder

    async def embed(self, texts: list[str], task: str) -> list[list[float]]:
        if self._embedder is None:
            raise LLMError("unavailable")  # long documents need embeddings (Gemini key)
        return await self._embedder.embed(texts, task)

    async def generate(self, system: str, prompt: str) -> Generation:
        last = LLMError("unavailable")
        for generator in self._generators:
            try:
                return await generator.generate(system, prompt)
            except LLMError as exc:
                if exc.code == "blocked":
                    raise  # another model would most likely refuse too
                last = exc
        raise last
