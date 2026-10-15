"""The repeatable evaluation command.

Seeds (or reuses) the demo collection with the three sample documents, runs the
full evaluation (retrieval-mode comparison + generation/verification pipeline),
saves a JSON report under data/eval_reports/, and prints a human-readable summary.

Usage (from backend/, with the venv activated):
    python scripts/run_eval.py
    python scripts/run_eval.py --collection-id <existing-collection-id>
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import SessionLocal, init_db
from app.evaluation.runner import run_full_evaluation
from scripts.seed_demo import seed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the EvidenceDesk evaluation harness.")
    parser.add_argument("--collection-id", help="Existing collection id to evaluate. If omitted, seeds/reuses the demo collection.")
    args = parser.parse_args()

    init_db()

    collection_id = args.collection_id or seed()

    db = SessionLocal()
    try:
        print(f"\nRunning evaluation against collection {collection_id} ...")
        report = run_full_evaluation(db, collection_id, settings.eval_reports_dir)
    finally:
        db.close()

    print(f"\nReport saved to: {report['_report_path']}")
    print(f"Cases: {report['num_cases']}")

    print("\nRetrieval comparison (Recall@k / MRR):")
    for mode, m in report["retrieval_comparison"].items():
        print(f"  {mode:16s} recall@k={m['recall_at_k']:.2f}  mrr={m['mrr']:.2f}  p50={m['retrieval_latency_ms']['p50_ms']}ms")

    g = report["generation_evaluation"]
    print(f"\nGeneration pipeline (primary mode: {g['primary_mode']}):")
    print(f"  citation precision: {g['citation_precision']:.2f}")
    print(f"  citation recall:    {g['citation_recall']:.2f}")
    print(f"  refusal accuracy (unanswerable): {g['refusal']['refusal_accuracy_on_unanswerable']:.2f}")
    print(f"  false refusal rate (answerable): {g['refusal']['false_refusal_rate_on_answerable']:.2f}")
    print(f"  verification outcomes: {g['verification_outcomes']}")
    print(f"  latency p50/p95: {g['latency_ms']['p50_ms']}ms / {g['latency_ms']['p95_ms']}ms")
    print(f"  mean retry count: {g['mean_retry_count']:.2f}")
    print(f"\n  reranker available: {report['reranker_available']}")


if __name__ == "__main__":
    main()
