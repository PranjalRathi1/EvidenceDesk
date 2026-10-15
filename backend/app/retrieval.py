"""Retrieval pipeline: vector-only, keyword-only, hybrid (RRF fusion), hybrid+rerank."""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app import bm25_index, reranker, vector_store
from app.config import settings
from app.llm_client import provider
from app.models import Chunk


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    page_number: int
    text: str
    score: float
    vector_rank: int | None = None
    keyword_rank: int | None = None
    rerank_score: float | None = None


def _vector_search(collection_id: str, question: str, top_k: int) -> list[RetrievedChunk]:
    [embedding] = provider.embed([question])
    res = vector_store.query(collection_id, embedding, top_k)
    ids = res["ids"][0] if res["ids"] else []
    docs = res["documents"][0] if res["documents"] else []
    metas = res["metadatas"][0] if res["metadatas"] else []
    distances = res["distances"][0] if res["distances"] else []
    out = []
    for rank, (cid, text, meta, dist) in enumerate(zip(ids, docs, metas, distances), start=1):
        out.append(
            RetrievedChunk(
                chunk_id=cid,
                document_id=meta.get("document_id", ""),
                page_number=int(meta.get("page_number", 0)),
                text=text,
                score=1.0 / (1.0 + dist),
                vector_rank=rank,
            )
        )
    return out


def _keyword_search(db: Session, collection_id: str, question: str, top_k: int) -> list[RetrievedChunk]:
    chunks = db.query(Chunk).filter(Chunk.collection_id == collection_id).all()
    if not chunks:
        return []
    chunk_ids = [c.id for c in chunks]
    chunk_texts = [c.text for c in chunks]
    by_id = {c.id: c for c in chunks}
    results = bm25_index.search(chunk_ids, chunk_texts, question, top_k)
    out = []
    for rank, r in enumerate(results, start=1):
        c = by_id[r.chunk_id]
        out.append(
            RetrievedChunk(
                chunk_id=c.id,
                document_id=c.document_id,
                page_number=c.page_number,
                text=c.text,
                score=r.score,
                keyword_rank=rank,
            )
        )
    return out


def _rrf_fuse(vector_results: list[RetrievedChunk], keyword_results: list[RetrievedChunk], k: int) -> list[RetrievedChunk]:
    merged: dict[str, RetrievedChunk] = {}
    for r in vector_results:
        merged[r.chunk_id] = r
    for r in keyword_results:
        if r.chunk_id in merged:
            merged[r.chunk_id].keyword_rank = r.keyword_rank
        else:
            merged[r.chunk_id] = r

    def rrf_score(c: RetrievedChunk) -> float:
        score = 0.0
        if c.vector_rank is not None:
            score += 1.0 / (k + c.vector_rank)
        if c.keyword_rank is not None:
            score += 1.0 / (k + c.keyword_rank)
        return score

    fused = list(merged.values())
    for c in fused:
        c.score = rrf_score(c)
    fused.sort(key=lambda c: c.score, reverse=True)
    return fused


def retrieve(db: Session, collection_id: str, question: str, mode: str | None = None, top_k: int | None = None) -> list[RetrievedChunk]:
    mode = mode or settings.retrieval_mode
    top_k = top_k or settings.retrieval_top_k
    candidate_k = max(settings.retrieval_candidate_k, top_k)

    if mode == "vector":
        results = _vector_search(collection_id, question, top_k)
    elif mode == "keyword":
        results = _keyword_search(db, collection_id, question, top_k)
    elif mode in ("hybrid", "hybrid_rerank"):
        vec = _vector_search(collection_id, question, candidate_k)
        kw = _keyword_search(db, collection_id, question, candidate_k)
        fused = _rrf_fuse(vec, kw, settings.rrf_k)
        if mode == "hybrid_rerank" and reranker.is_enabled():
            candidates = [(c.chunk_id, c.text) for c in fused[:candidate_k]]
            scored = dict(reranker.rerank(question, candidates))
            for c in fused:
                if c.chunk_id in scored:
                    c.rerank_score = scored[c.chunk_id]
            fused.sort(key=lambda c: (c.rerank_score if c.rerank_score is not None else -1e9), reverse=True)
        results = fused[:top_k]
    else:
        raise ValueError(f"Unknown retrieval mode: {mode}")

    return results
