"""Chroma-backed vector store, running embedded/persistent (no server, no Docker)."""
import chromadb

from app.config import settings

_client = None


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_dir)
    return _client


def get_collection(collection_id: str):
    client = get_client()
    return client.get_or_create_collection(name=f"col_{collection_id}")


def add_chunks(collection_id: str, ids: list[str], embeddings: list[list[float]], documents: list[str], metadatas: list[dict]) -> None:
    if not ids:
        return
    coll = get_collection(collection_id)
    coll.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)


def delete_document_chunks(collection_id: str, document_id: str) -> None:
    coll = get_collection(collection_id)
    coll.delete(where={"document_id": document_id})


def delete_collection(collection_id: str) -> None:
    client = get_client()
    try:
        client.delete_collection(name=f"col_{collection_id}")
    except Exception:
        pass


def query(collection_id: str, query_embedding: list[float], n_results: int) -> dict:
    coll = get_collection(collection_id)
    count = coll.count()
    if count == 0:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    n = min(n_results, count)
    return coll.query(query_embeddings=[query_embedding], n_results=n)
