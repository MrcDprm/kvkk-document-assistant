"""A fake LLM for tests: records every request and answers with a fixed text."""

from app.llm import Generation, LLMError


class FakeLLM:
    def __init__(self, answer: str = "[KISI_1] kiracıdır [1].", error: str | None = None) -> None:
        self.answer = answer
        self.error = error
        self.embedded: list[tuple[str, list[str]]] = []
        self.prompts: list[tuple[str, str]] = []

    async def embed(self, texts: list[str], task: str) -> list[list[float]]:
        if self.error:
            raise LLMError(self.error)
        self.embedded.append((task, list(texts)))
        # A tiny "embedding": how often a few marker words appear. Enough to test ranking.
        words = ["kira", "iban", "telefon", "araç", "kefil"]
        return [[float(t.lower().count(w)) + 0.01 for w in words] for t in texts]

    async def generate(self, system: str, prompt: str) -> Generation:
        if self.error:
            raise LLMError(self.error)
        self.prompts.append((system, prompt))
        return Generation(self.answer, input_tokens=120, output_tokens=12, latency_ms=5)

    def sent_texts(self) -> str:
        """Everything that would have left the server."""
        parts = [t for _, texts in self.embedded for t in texts]
        parts += [s + p for s, p in self.prompts]
        return "\n".join(parts)
