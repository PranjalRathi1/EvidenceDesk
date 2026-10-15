from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import vector_store
from app.database import get_db
from app.models import Collection, Document
from app.schemas import CollectionCreate, CollectionOut

router = APIRouter(prefix="/api/collections", tags=["collections"])


@router.post("", response_model=CollectionOut, status_code=201)
def create_collection(payload: CollectionCreate, db: Session = Depends(get_db)):
    collection = Collection(name=payload.name)
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return CollectionOut(id=collection.id, name=collection.name, created_at=collection.created_at, document_count=0)


@router.get("", response_model=list[CollectionOut])
def list_collections(db: Session = Depends(get_db)):
    collections = db.query(Collection).order_by(Collection.created_at.desc()).all()
    out = []
    for c in collections:
        count = db.query(Document).filter(Document.collection_id == c.id).count()
        out.append(CollectionOut(id=c.id, name=c.name, created_at=c.created_at, document_count=count))
    return out


@router.get("/{collection_id}", response_model=CollectionOut)
def get_collection(collection_id: str, db: Session = Depends(get_db)):
    c = db.get(Collection, collection_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    count = db.query(Document).filter(Document.collection_id == c.id).count()
    return CollectionOut(id=c.id, name=c.name, created_at=c.created_at, document_count=count)


@router.delete("/{collection_id}", status_code=204)
def delete_collection(collection_id: str, db: Session = Depends(get_db)):
    c = db.get(Collection, collection_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    file_paths = [doc.file_path for doc in c.documents]

    db.delete(c)  # cascades to documents/chunks in SQL
    db.commit()
    vector_store.delete_collection(collection_id)

    for file_path in file_paths:
        path = Path(file_path)
        if path.exists():
            path.unlink()

    return None
