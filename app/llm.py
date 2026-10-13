"""Gemini client behind a small interface, so tests (and other providers) can replace it.

Only masked text is ever passed to this module.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Protocol

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


class LLMError(Exception):
    """`code` is shown to the user as a translated message: quota, unavailable, blocked."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class LLM(Protocol):
    async def embed(self, texts: list[str], task: str) -> list[list[float]]: ...

    async def generate(self, system: str, prompt: str) -> Generation: ...


def _map_error(exc: Exception) -> LLMError:
    if isinstance(exc, errors.APIError) and exc.code == 429:
        return LLMError("quota")  # free tier limit reached
    return LLMError("unavailable")


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
        except Exception as exc:
            raise _map_error(exc) from exc
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
        except Exception as exc:
            raise _map_error(exc) from exc

        text = (response.text or "").strip()
        if not text:
            raise LLMError("blocked")  # empty answer, e.g. stopped by a safety filter
        usage = response.usage_metadata
        return Generation(
            text=text,
            input_tokens=(usage.prompt_token_count or 0) if usage else 0,
            output_tokens=(usage.candidates_token_count or 0) if usage else 0,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
