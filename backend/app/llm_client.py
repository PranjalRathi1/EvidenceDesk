"""Thin provider abstraction over local Ollama (default) and an optional hosted LLM.

Only Ollama is wired up and enabled by default — no paid API is required to run
EvidenceDesk. A hosted provider can be added later behind the same interface if
`settings.hosted_provider_enabled` is turned on; it is not implemented here because
no credential/provider was specified, and the spec requires us not to invent provider
capabilities that haven't been verified.
"""
import httpx

from app.config import settings


class LLMError(Exception):
    pass


class EmbeddingError(Exception):
    pass


class OllamaProvider:
    def __init__(self, base_url: str | None = None, chat_model: str | None = None, embed_model: str | None = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.chat_model = chat_model or settings.llm_model
        self.embed_model = embed_model or settings.embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        with httpx.Client(timeout=60.0) as client:
            for text in texts:
                resp = client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.embed_model, "prompt": text},
                )
                if resp.status_code != 200:
                    raise EmbeddingError(f"Ollama embeddings call failed: {resp.status_code} {resp.text[:200]}")
                data = resp.json()
                vec = data.get("embedding")
                if not vec:
                    raise EmbeddingError("Ollama returned an empty embedding")
                vectors.append(vec)
        return vectors

    def chat(self, system: str, user: str, *, timeout: float | None = None, temperature: float = 0.0, json_mode: bool = False) -> str:
        payload = {
            "model": self.chat_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"
        with httpx.Client(timeout=timeout or settings.generation_timeout_s) as client:
            resp = client.post(f"{self.base_url}/api/chat", json=payload)
            if resp.status_code != 200:
                raise LLMError(f"Ollama chat call failed: {resp.status_code} {resp.text[:200]}")
            data = resp.json()
            message = data.get("message", {})
            content = message.get("content", "")
            if not content:
                raise LLMError("Ollama returned an empty chat response")
            return content

    def is_available(self) -> tuple[bool, str]:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    return False, f"Ollama responded with {resp.status_code}"
                return True, ""
        except Exception as exc:
            return False, str(exc)


provider = OllamaProvider()
