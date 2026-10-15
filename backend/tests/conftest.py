"""Test configuration.

Redirects all storage (SQLite DB, Chroma dir, uploads, eval reports) to a fresh
temp directory via environment variables BEFORE `app.config` (and anything that
imports it) is loaded, so tests never touch the real project `data/` directory.
"""
import hashlib
import os
import tempfile
from pathlib import Path

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="evidencedesk_test_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_DATA_DIR / 'test.db').as_posix()}"
os.environ["CHROMA_DIR"] = str(_TEST_DATA_DIR / "chroma")
os.environ["UPLOAD_DIR"] = str(_TEST_DATA_DIR / "uploads")
os.environ["EVAL_REPORTS_DIR"] = str(_TEST_DATA_DIR / "eval_reports")
os.environ["RERANKER_ENABLED"] = "false"  # keep unit tests fast and dependency-free by default

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures"

init_db()


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    return TestClient(app)


def fake_embed_dim() -> int:
    return 64


def fake_embedding_for_text(text: str) -> list[float]:
    """Deterministic bag-of-words feature-hashed embedding so similarity between
    texts sharing vocabulary is meaningfully higher than between unrelated texts,
    without requiring a live Ollama embedding model in unit tests."""
    dim = fake_embedding_for_text.__dict__.setdefault("_dim", 64)
    vec = [0.0] * dim
    for word in text.lower().split():
        word = "".join(ch for ch in word if ch.isalnum())
        if not word:
            continue
        h = int(hashlib.sha256(word.encode()).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h // dim) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


@pytest.fixture()
def fake_provider(monkeypatch):
    """Patches the module-level Ollama provider with deterministic fakes.
    `chat_response` can be set by a test to control what the "LLM" returns."""
    from app import llm_client

    state = {"chat_response": None, "chat_calls": []}

    def fake_embed(texts: list[str]) -> list[list[float]]:
        return [fake_embedding_for_text(t) for t in texts]

    def fake_chat(system: str, user: str, *, timeout=None, temperature=0.0, json_mode=False) -> str:
        state["chat_calls"].append({"system": system, "user": user})
        if state["chat_response"] is None:
            raise llm_client.LLMError("no fake chat_response configured for this test")
        resp = state["chat_response"]
        if callable(resp):
            return resp(system, user)
        return resp

    monkeypatch.setattr(llm_client.provider, "embed", fake_embed)
    monkeypatch.setattr(llm_client.provider, "chat", fake_chat)
    return state
