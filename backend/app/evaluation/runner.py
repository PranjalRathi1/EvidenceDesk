"""Evaluation harness: loads the labelled dataset, runs retrieval-mode comparisons,
and runs the full generation+verification pipeline for the primary configured mode.

Retrieval-only metrics (Recall@k, MRR) are computed for every mode being compared,
because that only requires an embedding call per question and is cheap.

Generation-level metrics (citation precision/recall, refusal accuracy, verification
outcome counts, latency) are computed only for the PRIMARY mode, because each case
requires at least one local LLM call (and up to one retry plus one semantic-verification
call per claim). Running the full generation pipeline for every retrieval mode as well
would multiply local LLM inference time with no corresponding gain in what the metric
teaches us about retrieval quality, so this scoping is deliberate, not a shortcut taken
to hide cost -- it is reported explicitly in the output.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app import reranker, retrieval
from app.config import settings
from app.evaluation import metrics
from app.generation import answer_question
from app.models import Document

DATASET_PATH = Path(__file__).parent / "dataset.json"
ALL_RETRIEVAL_MODES = ["vector", "keyword", "hybrid", "hybrid_rerank"]


def load_dataset() -> dict:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _doc_filename_map(db: Session, collection_id: str) -> dict[str, str]:
    docs = db.query(Document).filter(Document.collection_id == collection_id).all()
    return {d.id: d.filename for d in docs}


def _expected_pages(case: dict) -> set[tuple[str, int]]:
    return {(e["document"], e["page"]) for e in case.get("expected_evidence", [])}


def run_retrieval_comparison(db: Session, collection_id: str, cases: list[dict], modes: list[str]) -> dict:
    doc_names = _doc_filename_map(db, collection_id)
    report: dict = {}
    for mode in modes:
        retrieved_sets = []
        retrieved_ordered = []
        expected_sets = []
        latencies = []
        for case in cases:
            expected = _expected_pages(case)
            expected_sets.append(expected)
            t0 = time.perf_counter()
            results = retrieval.retrieve(db, collection_id, case["question"], mode=mode, top_k=settings.retrieval_top_k)
            latencies.append(int((time.perf_counter() - t0) * 1000))
            ordered_pages = [(doc_names.get(r.document_id, "?"), r.page_number) for r in results]
            retrieved_ordered.append(ordered_pages)
            retrieved_sets.append(set(ordered_pages))

        report[mode] = {
            "recall_at_k": metrics.recall_at_k(retrieved_sets, expected_sets),
            "mrr": metrics.mean_reciprocal_rank(retrieved_ordered, expected_sets),
            "retrieval_latency_ms": metrics.latency_percentiles(latencies),
            "top_k": settings.retrieval_top_k,
        }
    return report


def run_generation_pipeline(db: Session, collection_id: str, cases: list[dict], primary_mode: str) -> dict:
    doc_names = _doc_filename_map(db, collection_id)
    latencies, refused_flags, expected_answerable = [], [], []
    cited_pages_per_case, expected_pages_per_case = [], []
    all_verification_statuses = []
    per_case_results = []
    retry_counts = []

    for case in cases:
        t0 = time.perf_counter()
        result = answer_question(db, collection_id, case["question"], retrieval_mode=primary_mode)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        latencies.append(elapsed_ms)
        refused_flags.append(result.refused)
        expected_answerable.append(case["answerable"])
        retry_counts.append(result.retry_count)

        cited = set()
        for c in result.claims:
            all_verification_statuses.append(c.verdict.status)
            if c.document_id and c.page_number is not None:
                fname = doc_names.get(c.document_id, "?")
                cited.add((fname, c.page_number))
        cited_pages_per_case.append(cited)
        expected_pages_per_case.append(_expected_pages(case))

        per_case_results.append(
            {
                "id": case["id"],
                "question": case["question"],
                "category": case["category"],
                "expected_answerable": case["answerable"],
                "refused": result.refused,
                "refusal_reason": result.refusal_reason,
                "answer_text": result.answer_text,
                "retry_count": result.retry_count,
                "latency_ms": elapsed_ms,
                "cited_pages": sorted(cited),
                "expected_pages": sorted(_expected_pages(case)),
                "claims": [
                    {
                        "claim_text": c.claim_text,
                        "status": c.verdict.status,
                        "method": c.verdict.method,
                        "quote": c.quote,
                        "page": c.page_number,
                        "document": doc_names.get(c.document_id, "?") if c.document_id else None,
                    }
                    for c in result.claims
                ],
            }
        )

    precision, recall = metrics.citation_precision_recall(cited_pages_per_case, expected_pages_per_case)
    refusal_stats = metrics.refusal_accuracy(refused_flags, expected_answerable)

    return {
        "primary_mode": primary_mode,
        "citation_precision": precision,
        "citation_recall": recall,
        "refusal": refusal_stats,
        "verification_outcomes": metrics.verification_outcome_counts(all_verification_statuses),
        "latency_ms": metrics.latency_percentiles(latencies),
        "mean_retry_count": sum(retry_counts) / len(retry_counts) if retry_counts else 0,
        "cases": per_case_results,
    }


def run_full_evaluation(db: Session, collection_id: str, out_dir: str, primary_mode: str | None = None) -> dict:
    dataset = load_dataset()
    cases = dataset["cases"]
    primary_mode = primary_mode or settings.retrieval_mode

    retrieval_report = run_retrieval_comparison(db, collection_id, cases, ALL_RETRIEVAL_MODES)
    generation_report = run_generation_pipeline(db, collection_id, cases, primary_mode)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collection_id": collection_id,
        "num_cases": len(cases),
        "dataset_description": dataset["description"],
        "retrieval_comparison": retrieval_report,
        "generation_evaluation": generation_report,
        "reranker_available": reranker.load_error() is None,
    }

    out_path = Path(out_dir) / f"eval_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["_report_path"] = str(out_path)
    return report
