"""Optional cross-encoder reranker. Lazily loaded so the app still runs if the
sentence-transformers/torch dependency is unavailable or disabled."""
from app.config import settings

_model = None
_load_error: str | None = None


def is_enabled() -> bool:
    return settings.reranker_enabled


def _get_model():
    global _model, _load_error
    if _model is not None or _load_error is not None:
        return _model
    try:
        from sentence_transformers import CrossEncoder

        _model = CrossEncoder(settings.reranker_model)
    except Exception as exc:  # pragma: no cover - environment dependent
        _load_error = str(exc)
        _model = None
    return _model


def rerank(question: str, candidates: list[tuple[str, str]]) -> list[tuple[str, float]]:
    """candidates: list of (chunk_id, text). Returns (chunk_id, score) sorted desc.
    Falls back to input order with score 0.0 if the reranker cannot be loaded."""
    model = _get_model()
    if model is None or not candidates:
        return [(cid, 0.0) for cid, _ in candidates]
    pairs = [(question, text) for _, text in candidates]
    scores = model.predict(pairs)
    scored = list(zip([cid for cid, _ in candidates], (float(s) for s in scores)))
    return sorted(scored, key=lambda x: x[1], reverse=True)


def load_error() -> str | None:
    _get_model()
    return _load_error
