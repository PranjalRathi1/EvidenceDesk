"""BM25 keyword retrieval, built on-demand from the chunk rows of a collection.

Rebuilding per query is acceptable at the scale of a personal study-document
collection (hundreds to a few thousand chunks); if this needs to scale further,
the index should be cached and incrementally updated instead.
"""
import re

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Result:
    def __init__(self, chunk_id: str, score: float):
        self.chunk_id = chunk_id
        self.score = score


def search(chunk_ids: list[str], chunk_texts: list[str], question: str, top_k: int) -> list[BM25Result]:
    if not chunk_ids:
        return []
    corpus = [tokenize(t) for t in chunk_texts]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(tokenize(question))
    ranked = sorted(zip(chunk_ids, scores), key=lambda x: x[1], reverse=True)
    return [BM25Result(chunk_id=cid, score=float(score)) for cid, score in ranked[:top_k] if score > 0]
