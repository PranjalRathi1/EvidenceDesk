from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VerificationStatus = Literal["supported", "weak", "not_found"]
DocStatus = Literal["pending", "processing", "indexed", "failed", "unsupported"]
RetrievalMode = Literal["vector", "keyword", "hybrid", "hybrid_rerank"]


class CollectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class CollectionOut(BaseModel):
    id: str
    name: str
    created_at: datetime
    document_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class DocumentOut(BaseModel):
    id: str
    collection_id: str
    filename: str
    status: DocStatus
    status_message: str
    page_count: int
    chunk_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuestionIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    retrieval_mode: RetrievalMode | None = None
    top_k: int | None = None


class CitationOut(BaseModel):
    document_id: str
    document_filename: str
    page_number: int
    chunk_id: str
    quote: str


class ClaimOut(BaseModel):
    claim_text: str
    citation: CitationOut | None
    verification_status: VerificationStatus
    explanation: str


class AnswerOut(BaseModel):
    refused: bool
    refusal_reason: str | None = None
    answer_text: str
    claims: list[ClaimOut]
    retrieved_passages: list[CitationOut]
    retrieval_mode: str
    retry_count: int
    timings_ms: dict[str, int]


class SourcePageOut(BaseModel):
    document_id: str
    filename: str
    page_number: int
    page_count: int
    page_text: str
    excerpt: str | None = None


class EvaluationRunOut(BaseModel):
    id: str
    collection_id: str
    status: str
    num_cases: int
    created_at: datetime
    finished_at: datetime | None
    report_path: str

    model_config = ConfigDict(from_attributes=True)
