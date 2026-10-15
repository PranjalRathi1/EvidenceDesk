"""Answer generation with grounded claims, verification, retry, and refusal.

Plain Python control flow (no agent framework) implements the conditional
retry-then-refuse workflow described in the spec:

  retrieve -> generate structured claims -> verify each claim
      -> if evidence support is too low: regenerate once with feedback -> re-verify
      -> if still too low: refuse

LangGraph was deliberately not used: this is a single linear branch with one
bounded retry, which plain functions express more simply, and the task calls
for using LangGraph only when the workflow actually benefits from it.
"""
import json
import time
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.config import settings
from app.llm_client import LLMError, provider
from app.models import Document
from app.retrieval import RetrievedChunk, retrieve
from app.verification import SupportVerdict, verify_claim

_WEIGHT = {"supported": 1.0, "weak": 0.5, "not_found": 0.0}

_GENERATION_SYSTEM_PROMPT = """You are EvidenceDesk, an evidence-first research assistant. \
You answer ONLY using the SOURCE PASSAGES provided below. Never use outside knowledge. \
Never invent a quote that is not verbatim in a passage.

If the passages do not contain enough information to answer the question, set \
"answerable" to false and leave "claims" empty.

Otherwise, break your answer into one or more atomic CLAIMS. For each claim, quote the \
exact supporting sentence(s) verbatim from exactly one passage, and reference that \
passage's chunk_id.

Respond with ONLY a JSON object of this exact shape:
{
  "answerable": true,
  "answer_text": "<concise answer in plain language>",
  "claims": [
    {"claim_text": "<one factual statement>", "chunk_id": "<chunk id from a passage>", "quote": "<verbatim quote from that passage>"}
  ]
}"""


class _ClaimLLM(BaseModel):
    claim_text: str
    chunk_id: str
    quote: str


class _AnswerLLM(BaseModel):
    answerable: bool
    answer_text: str = ""
    claims: list[_ClaimLLM] = []


@dataclass
class VerifiedClaim:
    claim_text: str
    chunk_id: str | None
    document_id: str | None
    document_filename: str | None
    page_number: int | None
    quote: str
    verdict: SupportVerdict


@dataclass
class GenerationResult:
    refused: bool
    refusal_reason: str | None
    answer_text: str
    claims: list[VerifiedClaim]
    retrieved: list[RetrievedChunk]
    retrieval_mode: str
    retry_count: int
    timings_ms: dict[str, int]


def _build_passages_block(chunks: list[RetrievedChunk], doc_names: dict[str, str]) -> str:
    parts = []
    for c in chunks:
        fname = doc_names.get(c.document_id, "unknown")
        parts.append(f"[chunk_id={c.chunk_id} | document={fname} | page={c.page_number}]\n{c.text}")
    return "\n\n".join(parts)


def _call_llm_for_answer(question: str, passages_block: str, feedback: str | None = None) -> _AnswerLLM:
    user_prompt = f"SOURCE PASSAGES:\n{passages_block}\n\nQUESTION: {question}"
    if feedback:
        user_prompt += f"\n\nYour previous attempt had issues: {feedback}\nPlease try again, quoting ONLY verbatim text from the passages above."
    raw = provider.chat(_GENERATION_SYSTEM_PROMPT, user_prompt, json_mode=True, temperature=0.0)
    data = json.loads(raw)
    return _AnswerLLM.model_validate(data)


def _verify_claims(claims: list[_ClaimLLM], chunks_by_id: dict[str, RetrievedChunk], doc_names: dict[str, str]) -> list[VerifiedClaim]:
    verified: list[VerifiedClaim] = []
    for claim in claims:
        chunk = chunks_by_id.get(claim.chunk_id)
        if chunk is None:
            verified.append(
                VerifiedClaim(
                    claim_text=claim.claim_text,
                    chunk_id=claim.chunk_id,
                    document_id=None,
                    document_filename=None,
                    page_number=None,
                    quote=claim.quote,
                    verdict=SupportVerdict(
                        status="not_found",
                        explanation="The model cited a chunk_id that was not among the retrieved passages.",
                        method="invalid_chunk_reference",
                    ),
                )
            )
            continue
        verdict = verify_claim(claim.claim_text, claim.quote, chunk.text)
        verified.append(
            VerifiedClaim(
                claim_text=claim.claim_text,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_filename=doc_names.get(chunk.document_id, "unknown"),
                page_number=chunk.page_number,
                quote=claim.quote,
                verdict=verdict,
            )
        )
    return verified


def _support_score(claims: list[VerifiedClaim]) -> float:
    if not claims:
        return 0.0
    total = sum(_WEIGHT[c.verdict.status] for c in claims)
    return total / len(claims)


def answer_question(db: Session, collection_id: str, question: str, retrieval_mode: str | None = None, top_k: int | None = None) -> GenerationResult:
    timings: dict[str, int] = {}

    t0 = time.perf_counter()
    retrieved = retrieve(db, collection_id, question, mode=retrieval_mode, top_k=top_k)
    timings["retrieval_ms"] = int((time.perf_counter() - t0) * 1000)

    mode_used = retrieval_mode or settings.retrieval_mode

    if not retrieved:
        timings["generation_ms"] = 0
        timings["verification_ms"] = 0
        return GenerationResult(
            refused=True,
            refusal_reason="No relevant passages were found in this collection's documents for this question.",
            answer_text="I couldn't find sufficient evidence in your documents to answer this question.",
            claims=[],
            retrieved=[],
            retrieval_mode=mode_used,
            retry_count=0,
            timings_ms=timings,
        )

    doc_ids = {c.document_id for c in retrieved}
    doc_names = {d.id: d.filename for d in db.query(Document).filter(Document.id.in_(doc_ids)).all()}
    chunks_by_id = {c.chunk_id: c for c in retrieved}
    passages_block = _build_passages_block(retrieved, doc_names)

    t0 = time.perf_counter()
    retry_count = 0
    feedback = None
    verified_claims: list[VerifiedClaim] = []
    answer_text = ""
    llm_refusal: str | None = None
    generation_failed = False

    for attempt in range(settings.max_retry + 1):
        try:
            parsed = _call_llm_for_answer(question, passages_block, feedback=feedback)
        except (LLMError, json.JSONDecodeError, ValidationError) as exc:
            generation_failed = True
            if attempt < settings.max_retry:
                retry_count += 1
                feedback = f"Your last response could not be parsed as valid JSON ({exc}). Return ONLY the JSON object described."
                continue
            break

        generation_failed = False
        if not parsed.answerable or not parsed.claims:
            llm_refusal = "The model determined the available passages do not contain enough information to answer."
            answer_text = parsed.answer_text
            break

        verified_claims = _verify_claims(parsed.claims, chunks_by_id, doc_names)
        answer_text = parsed.answer_text
        score = _support_score(verified_claims)
        if score >= settings.weak_support_threshold:
            break
        if attempt < settings.max_retry:
            retry_count += 1
            failed_quotes = [c.quote for c in verified_claims if c.verdict.status == "not_found"]
            feedback = (
                "Some of your quotes could not be verified against the source passages: "
                + "; ".join(repr(q) for q in failed_quotes[:3])
                + ". Quote text VERBATIM from the passages only."
            )
            verified_claims = []
            continue
        llm_refusal = "The generated answer's citations did not hold up under evidence verification."
    timings["generation_ms"] = int((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    timings["verification_ms"] = int((time.perf_counter() - t0) * 1000)

    if generation_failed:
        return GenerationResult(
            refused=True,
            refusal_reason="The model's response could not be parsed after retrying.",
            answer_text="I couldn't generate a reliable answer right now. Please try rephrasing your question.",
            claims=[],
            retrieved=retrieved,
            retrieval_mode=mode_used,
            retry_count=retry_count,
            timings_ms=timings,
        )

    if llm_refusal is not None and not verified_claims:
        return GenerationResult(
            refused=True,
            refusal_reason=llm_refusal,
            answer_text="I couldn't find sufficient evidence in your documents to answer this question.",
            claims=[],
            retrieved=retrieved,
            retrieval_mode=mode_used,
            retry_count=retry_count,
            timings_ms=timings,
        )

    score = _support_score(verified_claims)
    if score < settings.weak_support_threshold:
        return GenerationResult(
            refused=True,
            refusal_reason="The generated answer's citations did not hold up under evidence verification after retrying.",
            answer_text="I couldn't find sufficient verifiable evidence in your documents to answer this question.",
            claims=verified_claims,
            retrieved=retrieved,
            retrieval_mode=mode_used,
            retry_count=retry_count,
            timings_ms=timings,
        )

    return GenerationResult(
        refused=False,
        refusal_reason=None,
        answer_text=answer_text,
        claims=verified_claims,
        retrieved=retrieved,
        retrieval_mode=mode_used,
        retry_count=retry_count,
        timings_ms=timings,
    )
