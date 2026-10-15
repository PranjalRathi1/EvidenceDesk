"""Two-layer evidence verification.

Layer 1 (exact quote validation) is deterministic: the quoted text must actually
appear in the chunk it claims to come from, modulo whitespace normalization only.
This never accepts fabricated text.

Layer 2 (semantic support) asks an LLM judge whether the *verified* quote actually
supports the claim being made. The judge is not infallible -- its verdict and the
method used are recorded on every claim so the result can be audited, and judge
failures fail safe (never auto-upgrade to "supported").
"""
import json
import re
from dataclasses import dataclass

from app.config import settings
from app.llm_client import LLMError, provider

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def quote_exists_in_text(quote: str, source_text: str) -> bool:
    """Deterministic check: does the quote appear verbatim (whitespace-normalized)
    in the source text? Returns False for empty/whitespace-only quotes."""
    q = normalize_whitespace(quote)
    if not q:
        return False
    s = normalize_whitespace(source_text)
    return q.lower() in s.lower()


@dataclass
class SupportVerdict:
    status: str  # "supported" | "weak" | "not_found"
    explanation: str
    method: str  # "exact_quote_failed" | "llm_judge" | "judge_unavailable"


_JUDGE_SYSTEM_PROMPT = """You are a strict fact-checking judge. You will be given a CLAIM and an \
EVIDENCE passage that was quoted in support of that claim. Decide whether the evidence \
passage actually supports the claim.

Respond with ONLY a JSON object of the form:
{"status": "supported" | "weak" | "not_found", "explanation": "<one short sentence>"}

Rules:
- "supported": the evidence passage directly and clearly supports the claim.
- "weak": the evidence is related but only partially or ambiguously supports the claim.
- "not_found": the evidence does not support the claim at all.
Do not use outside knowledge. Judge only whether the evidence supports the claim."""


def semantic_support_check(claim_text: str, evidence_text: str) -> SupportVerdict:
    user_prompt = f"CLAIM:\n{claim_text}\n\nEVIDENCE:\n{evidence_text}"
    try:
        raw = provider.chat(_JUDGE_SYSTEM_PROMPT, user_prompt, json_mode=True, temperature=0.0)
        data = json.loads(raw)
        status = data.get("status")
        explanation = str(data.get("explanation", ""))
        if status not in ("supported", "weak", "not_found"):
            raise ValueError(f"judge returned invalid status: {status!r}")
        return SupportVerdict(status=status, explanation=explanation, method="llm_judge")
    except (LLMError, json.JSONDecodeError, ValueError, KeyError) as exc:
        return SupportVerdict(
            status="not_found",
            explanation=f"Semantic support check unavailable ({exc}); failing safe.",
            method="judge_unavailable",
        )


def verify_claim(claim_text: str, quote: str, source_chunk_text: str) -> SupportVerdict:
    """Run both verification layers for a single claim."""
    if not quote_exists_in_text(quote, source_chunk_text):
        return SupportVerdict(
            status="not_found",
            explanation="The quoted text could not be located verbatim in the cited source passage.",
            method="exact_quote_failed",
        )
    return semantic_support_check(claim_text, source_chunk_text)
