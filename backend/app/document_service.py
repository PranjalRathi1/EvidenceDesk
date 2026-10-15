"""Document ingestion: validate -> extract -> chunk -> embed -> index -> persist."""
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app import vector_store
from app.chunking import chunk_pages
from app.config import settings
from app.llm_client import EmbeddingError, provider
from app.models import Chunk, Document
from app.pdf_processing import PageText, UnsupportedPDFError, compute_content_hash, extract_pages


class UploadValidationError(Exception):
    pass


def validate_upload(filename: str, file_bytes: bytes) -> None:
    if not filename.lower().endswith(".pdf"):
        raise UploadValidationError("Only PDF files are supported.")
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(file_bytes) == 0:
        raise UploadValidationError("The uploaded file is empty.")
    if len(file_bytes) > max_bytes:
        raise UploadValidationError(f"File exceeds the {settings.max_upload_mb}MB upload limit.")


def _safe_stored_name(document_id: str, original_filename: str) -> str:
    suffix = Path(original_filename).suffix.lower() or ".pdf"
    return f"{document_id}{suffix}"


def create_document(db: Session, collection_id: str, filename: str, file_bytes: bytes) -> Document:
    validate_upload(filename, file_bytes)
    content_hash = compute_content_hash(file_bytes)

    existing = (
        db.query(Document)
        .filter(Document.collection_id == collection_id, Document.content_hash == content_hash)
        .first()
    )
    if existing is not None:
        raise UploadValidationError(f"This file was already uploaded as '{existing.filename}' (duplicate content).")

    document_id = str(uuid.uuid4())
    stored_name = _safe_stored_name(document_id, filename)
    file_path = Path(settings.upload_dir) / stored_name
    file_path.write_bytes(file_bytes)

    doc = Document(
        id=document_id,
        collection_id=collection_id,
        filename=filename,
        content_hash=content_hash,
        file_path=str(file_path),
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def process_document(db: Session, document: Document) -> None:
    """Runs synchronously: extract, chunk, embed, index. Updates status in place."""
    document.status = "processing"
    document.status_message = ""
    db.commit()

    try:
        file_bytes = Path(document.file_path).read_bytes()
        extraction = extract_pages(file_bytes)
    except UnsupportedPDFError as exc:
        document.status = "unsupported"
        document.status_message = str(exc)
        db.commit()
        return
    except Exception as exc:
        document.status = "failed"
        document.status_message = f"Extraction failed: {exc}"
        db.commit()
        return

    if extraction.page_count > settings.max_pages_per_doc:
        document.status = "failed"
        document.status_message = (
            f"Document has {extraction.page_count} pages, exceeding the {settings.max_pages_per_doc}-page limit."
        )
        db.commit()
        return

    pages: list[PageText] = extraction.pages
    chunks = chunk_pages(pages, settings.chunk_size_chars, settings.chunk_overlap_chars)

    if not chunks:
        document.status = "unsupported"
        document.status_message = "No usable text chunks could be produced from this document."
        db.commit()
        return

    try:
        embeddings = provider.embed([c.text for c in chunks])
    except EmbeddingError as exc:
        document.status = "failed"
        document.status_message = f"Embedding generation failed: {exc}. Is Ollama running with the embedding model pulled?"
        db.commit()
        return

    chunk_rows: list[Chunk] = []
    ids, metadatas, docs_text = [], [], []
    for chunk, embedding in zip(chunks, embeddings):
        chunk_id = str(uuid.uuid4())
        chunk_rows.append(
            Chunk(
                id=chunk_id,
                document_id=document.id,
                collection_id=document.collection_id,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                text=chunk.text,
            )
        )
        ids.append(chunk_id)
        metadatas.append({"document_id": document.id, "page_number": chunk.page_number})
        docs_text.append(chunk.text)

    try:
        vector_store.add_chunks(document.collection_id, ids, embeddings, docs_text, metadatas)
    except Exception as exc:
        document.status = "failed"
        document.status_message = f"Vector indexing failed: {exc}"
        db.commit()
        return

    db.add_all(chunk_rows)
    document.status = "indexed"
    document.page_count = extraction.page_count
    document.chunk_count = len(chunk_rows)
    document.embedding_model = settings.embedding_model
    if extraction.empty_pages:
        document.status_message = (
            f"Indexed. Note: {len(extraction.empty_pages)} page(s) had little/no extractable text "
            f"(possibly scanned images): {extraction.empty_pages[:10]}"
        )
    db.commit()


def delete_document(db: Session, document: Document) -> None:
    vector_store.delete_document_chunks(document.collection_id, document.id)
    file_path = Path(document.file_path)
    if file_path.exists():
        file_path.unlink()
    db.delete(document)
    db.commit()
