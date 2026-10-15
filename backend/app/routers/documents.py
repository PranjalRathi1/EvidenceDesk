from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app import document_service
from app.database import get_db
from app.document_service import UploadValidationError
from app.models import Collection, Document
from app.schemas import DocumentOut, SourcePageOut

router = APIRouter(tags=["documents"])


@router.post("/api/collections/{collection_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(collection_id: str, file: UploadFile, db: Session = Depends(get_db)):
    collection = db.get(Collection, collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    file_bytes = await file.read()
    try:
        doc = document_service.create_document(db, collection_id, file.filename or "upload.pdf", file_bytes)
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    document_service.process_document(db, doc)
    db.refresh(doc)
    return doc


@router.get("/api/collections/{collection_id}/documents", response_model=list[DocumentOut])
def list_documents(collection_id: str, db: Session = Depends(get_db)):
    if db.get(Collection, collection_id) is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    return db.query(Document).filter(Document.collection_id == collection_id).order_by(Document.created_at.desc()).all()


@router.delete("/api/documents/{document_id}", status_code=204)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    document_service.delete_document(db, doc)
    return None


@router.get("/api/documents/{document_id}/pages/{page_number}", response_model=SourcePageOut)
def get_source_page(document_id: str, page_number: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    from pathlib import Path

    import fitz

    file_bytes = Path(doc.file_path).read_bytes()
    pdf = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        if page_number < 1 or page_number > pdf.page_count:
            raise HTTPException(status_code=404, detail=f"Page {page_number} out of range (1-{pdf.page_count})")
        page_text = pdf.load_page(page_number - 1).get_text("text")
    finally:
        pdf.close()

    return SourcePageOut(
        document_id=doc.id,
        filename=doc.filename,
        page_number=page_number,
        page_count=doc.page_count,
        page_text=page_text,
    )
