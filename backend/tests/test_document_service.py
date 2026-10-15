import fitz
import pytest

from app import document_service, vector_store
from app.config import settings
from app.document_service import UploadValidationError
from app.models import Chunk, Collection, Document
from tests.conftest import FIXTURES_DIR


@pytest.fixture()
def collection(db_session):
    c = Collection(name="Test Collection")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


def test_validate_upload_rejects_non_pdf():
    with pytest.raises(UploadValidationError):
        document_service.validate_upload("notes.txt", b"hello")


def test_validate_upload_rejects_empty_file():
    with pytest.raises(UploadValidationError):
        document_service.validate_upload("notes.pdf", b"")


def test_validate_upload_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    big = b"0" * (2 * 1024 * 1024)
    with pytest.raises(UploadValidationError):
        document_service.validate_upload("notes.pdf", big)


def test_create_and_process_document_indexes_chunks(db_session, collection, fake_provider):
    data = (FIXTURES_DIR / "operating_systems_notes.pdf").read_bytes()
    doc = document_service.create_document(db_session, collection.id, "operating_systems_notes.pdf", data)
    assert doc.status == "pending"

    document_service.process_document(db_session, doc)
    db_session.refresh(doc)

    assert doc.status == "indexed"
    assert doc.page_count == 6
    assert doc.chunk_count == 6

    chunks = db_session.query(Chunk).filter(Chunk.document_id == doc.id).all()
    assert len(chunks) == 6
    assert {c.page_number for c in chunks} == {1, 2, 3, 4, 5, 6}

    coll = vector_store.get_collection(collection.id)
    assert coll.count() == 6


def test_duplicate_upload_is_rejected(db_session, collection):
    data = (FIXTURES_DIR / "operating_systems_notes.pdf").read_bytes()
    document_service.create_document(db_session, collection.id, "operating_systems_notes.pdf", data)
    with pytest.raises(UploadValidationError):
        document_service.create_document(db_session, collection.id, "operating_systems_notes_copy.pdf", data)


def test_scanned_pdf_marked_unsupported(db_session, collection):
    blank = fitz.open()
    blank.new_page()
    blank_bytes = blank.tobytes()
    blank.close()

    doc = document_service.create_document(db_session, collection.id, "scanned.pdf", blank_bytes)
    document_service.process_document(db_session, doc)
    db_session.refresh(doc)

    assert doc.status == "unsupported"
    assert "scanned" in doc.status_message.lower() or "image" in doc.status_message.lower()


def test_embedding_failure_marks_document_failed(db_session, collection, fake_provider, monkeypatch):
    from app import llm_client

    def broken_embed(texts):
        raise llm_client.EmbeddingError("Ollama not running")

    monkeypatch.setattr(llm_client.provider, "embed", broken_embed)

    data = (FIXTURES_DIR / "operating_systems_notes.pdf").read_bytes()
    doc = document_service.create_document(db_session, collection.id, "operating_systems_notes.pdf", data)
    document_service.process_document(db_session, doc)
    db_session.refresh(doc)

    assert doc.status == "failed"
    assert "embedding" in doc.status_message.lower()


def test_delete_document_removes_sql_rows_and_vectors(db_session, collection, fake_provider):
    data = (FIXTURES_DIR / "operating_systems_notes.pdf").read_bytes()
    doc = document_service.create_document(db_session, collection.id, "operating_systems_notes.pdf", data)
    document_service.process_document(db_session, doc)

    document_service.delete_document(db_session, doc)

    assert db_session.get(Document, doc.id) is None
    assert db_session.query(Chunk).filter(Chunk.document_id == doc.id).count() == 0
    coll = vector_store.get_collection(collection.id)
    assert coll.count() == 0
