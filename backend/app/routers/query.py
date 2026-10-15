import json
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.generation import answer_question
from app.models import Collection, QueryLog
from app.schemas import AnswerOut, CitationOut, ClaimOut, QuestionIn

router = APIRouter(tags=["query"])


@router.post("/api/collections/{collection_id}/query", response_model=AnswerOut)
def ask_question(collection_id: str, payload: QuestionIn, db: Session = Depends(get_db)):
    if db.get(Collection, collection_id) is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    t0 = time.perf_counter()
    result = answer_question(db, collection_id, payload.question, retrieval_mode=payload.retrieval_mode, top_k=payload.top_k)
    total_ms = int((time.perf_counter() - t0) * 1000)

    claims_out = [
        ClaimOut(
            claim_text=c.claim_text,
            citation=(
                CitationOut(
                    document_id=c.document_id,
                    document_filename=c.document_filename or "unknown",
                    page_number=c.page_number or 0,
                    chunk_id=c.chunk_id or "",
                    quote=c.quote,
                )
                if c.document_id
                else None
            ),
            verification_status=c.verdict.status,
            explanation=c.verdict.explanation,
        )
        for c in result.claims
    ]
    passages_out = [
        CitationOut(
            document_id=c.document_id,
            document_filename="",
            page_number=c.page_number,
            chunk_id=c.chunk_id,
            quote=c.text[:300],
        )
        for c in result.retrieved
    ]

    log = QueryLog(
        collection_id=collection_id,
        question=payload.question,
        retrieval_mode=result.retrieval_mode,
        answer_json=json.dumps({"answer_text": result.answer_text, "refused": result.refused}),
        refused=result.refused,
        retry_count=result.retry_count,
        latency_ms=total_ms,
        retrieval_ms=result.timings_ms.get("retrieval_ms", 0),
        generation_ms=result.timings_ms.get("generation_ms", 0),
        verification_ms=result.timings_ms.get("verification_ms", 0),
    )
    db.add(log)
    db.commit()

    return AnswerOut(
        refused=result.refused,
        refusal_reason=result.refusal_reason,
        answer_text=result.answer_text,
        claims=claims_out,
        retrieved_passages=passages_out,
        retrieval_mode=result.retrieval_mode,
        retry_count=result.retry_count,
        timings_ms={**result.timings_ms, "total_ms": total_ms},
    )
