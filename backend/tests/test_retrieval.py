import uuid

import pytest

from app import retrieval, vector_store
from app.models import Chunk, Collection
from tests.conftest import fake_embedding_for_text


@pytest.fixture()
def indexed_collection(db_session, fake_provider):
    c = Collection(name="Retrieval Test")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    texts = [
        (1, "Mitochondria produce ATP through cellular respiration in the cell."),
        (2, "Photosynthesis converts light energy into glucose using chlorophyll."),
        (3, "A deadlock occurs when processes circularly wait for resources."),
        (4, "Round Robin scheduling gives each process a fixed time quantum."),
    ]
    ids, embeddings, docs, metas = [], [], [], []
    for page, text in texts:
        chunk_id = str(uuid.uuid4())
        db_session.add(Chunk(id=chunk_id, document_id="doc-1", collection_id=c.id, page_number=page, chunk_index=0, text=text))
        ids.append(chunk_id)
        embeddings.append(fake_embedding_for_text(text))
        docs.append(text)
        metas.append({"document_id": "doc-1", "page_number": page})
    db_session.commit()
    vector_store.add_chunks(c.id, ids, embeddings, docs, metas)
    return c


def test_vector_search_ranks_relevant_chunk_first(indexed_collection, db_session):
    results = retrieval.retrieve(db_session, indexed_collection.id, "What produces ATP in a cell?", mode="vector", top_k=4)
    assert results[0].page_number == 1


def test_keyword_search_finds_exact_term_match(indexed_collection, db_session):
    results = retrieval.retrieve(db_session, indexed_collection.id, "deadlock circularly wait resources", mode="keyword", top_k=4)
    assert results
    assert results[0].page_number == 3


def test_hybrid_fuses_vector_and_keyword_without_duplicates(indexed_collection, db_session):
    results = retrieval.retrieve(db_session, indexed_collection.id, "scheduling quantum round robin process", mode="hybrid", top_k=4)
    chunk_ids = [r.chunk_id for r in results]
    assert len(chunk_ids) == len(set(chunk_ids))
    assert results[0].page_number == 4


def test_unknown_mode_raises():
    from sqlalchemy.orm import Session

    with pytest.raises(ValueError):
        retrieval.retrieve(Session, "whatever", "q", mode="not_a_real_mode")


def test_empty_collection_returns_no_results(db_session, fake_provider):
    c = Collection(name="Empty")
    db_session.add(c)
    db_session.commit()
    results = retrieval.retrieve(db_session, c.id, "anything", mode="hybrid", top_k=4)
    assert results == []
