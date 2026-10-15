"""Idempotently creates (or reuses) a demo collection containing the three
synthetic sample documents, so there's always something to evaluate/demo against.

Usage (from backend/, with the venv activated):
    python scripts/seed_demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import document_service
from app.database import SessionLocal, init_db
from app.evaluation.sample_docs import DOCUMENT_DEFS, generate_all
from app.models import Collection

DEMO_COLLECTION_NAME = "Demo Study Collection"
SAMPLE_DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sample_documents"


def ensure_sample_pdfs() -> list[Path]:
    if not SAMPLE_DOCS_DIR.exists() or not any(SAMPLE_DOCS_DIR.glob("*.pdf")):
        generate_all(SAMPLE_DOCS_DIR)
    return [SAMPLE_DOCS_DIR / name for name in DOCUMENT_DEFS]


def seed() -> str:
    init_db()
    db = SessionLocal()
    try:
        collection = db.query(Collection).filter(Collection.name == DEMO_COLLECTION_NAME).first()
        if collection is None:
            collection = Collection(name=DEMO_COLLECTION_NAME)
            db.add(collection)
            db.commit()
            db.refresh(collection)
            print(f"Created collection '{DEMO_COLLECTION_NAME}' ({collection.id})")
        else:
            print(f"Reusing existing collection '{DEMO_COLLECTION_NAME}' ({collection.id})")

        for pdf_path in ensure_sample_pdfs():
            file_bytes = pdf_path.read_bytes()
            try:
                doc = document_service.create_document(db, collection.id, pdf_path.name, file_bytes)
            except document_service.UploadValidationError:
                print(f"  {pdf_path.name}: already indexed, skipping")
                continue
            document_service.process_document(db, doc)
            db.refresh(doc)
            print(f"  {pdf_path.name}: {doc.status} ({doc.page_count} pages, {doc.chunk_count} chunks)")

        return collection.id
    finally:
        db.close()


if __name__ == "__main__":
    collection_id = seed()
    print(f"\nDemo collection ready: {collection_id}")
