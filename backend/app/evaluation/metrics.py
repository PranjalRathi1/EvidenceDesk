"""Evaluation metrics. Each function is documented with what it actually measures
so results aren't over-claimed."""
import statistics


def recall_at_k(retrieved_pages: list[set[tuple[str, int]]], expected_pages: list[set[tuple[str, int]]]) -> float:
    """Fraction of answerable cases where AT LEAST ONE expected (document, page) pair
    appears anywhere in that case's retrieved set. Cases with empty expected_pages are skipped."""
    scored = [1.0 if (exp & ret) else 0.0 for ret, exp in zip(retrieved_pages, expected_pages) if exp]
    return sum(scored) / len(scored) if scored else float("nan")


def mean_reciprocal_rank(retrieved_ordered_pages: list[list[tuple[str, int]]], expected_pages: list[set[tuple[str, int]]]) -> float:
    """Mean of 1/rank of the first retrieved (document, page) that is in the expected set,
    using the retrieved order. 0 contribution if no expected page was retrieved."""
    scores = []
    for ordered, exp in zip(retrieved_ordered_pages, expected_pages):
        if not exp:
            continue
        rank = next((i + 1 for i, p in enumerate(ordered) if p in exp), None)
        scores.append(1.0 / rank if rank else 0.0)
    return sum(scores) / len(scores) if scores else float("nan")


def citation_precision_recall(cited_pages_per_case: list[set[tuple[str, int]]], expected_pages_per_case: list[set[tuple[str, int]]]) -> tuple[float, float]:
    """Annotation rule: a cited (document, page) is 'correct' if it is in that case's
    expected-evidence set. Precision = correct citations / all citations produced across
    answerable cases. Recall = correct citations / all expected evidence pages across
    answerable cases (did the answer's citations cover the known evidence?)."""
    total_cited = 0
    correct_cited = 0
    total_expected = 0
    covered_expected = 0
    for cited, expected in zip(cited_pages_per_case, expected_pages_per_case):
        if not expected:
            continue
        total_cited += len(cited)
        correct_cited += len(cited & expected)
        total_expected += len(expected)
        covered_expected += len(cited & expected)
    precision = correct_cited / total_cited if total_cited else float("nan")
    recall = covered_expected / total_expected if total_expected else float("nan")
    return precision, recall


def refusal_accuracy(refused_flags: list[bool], expected_answerable: list[bool]) -> dict:
    """On unanswerable cases: refusal_accuracy = fraction correctly refused.
    On answerable cases: false_refusal_rate = fraction incorrectly refused."""
    unanswerable = [r for r, a in zip(refused_flags, expected_answerable) if not a]
    answerable = [r for r, a in zip(refused_flags, expected_answerable) if a]
    return {
        "refusal_accuracy_on_unanswerable": (sum(unanswerable) / len(unanswerable)) if unanswerable else float("nan"),
        "false_refusal_rate_on_answerable": (sum(answerable) / len(answerable)) if answerable else float("nan"),
        "num_unanswerable_cases": len(unanswerable),
        "num_answerable_cases": len(answerable),
    }


def latency_percentiles(latencies_ms: list[int]) -> dict:
    if not latencies_ms:
        return {"p50_ms": None, "p95_ms": None, "mean_ms": None, "n": 0}
    sorted_vals = sorted(latencies_ms)
    return {
        "p50_ms": int(statistics.median(sorted_vals)),
        "p95_ms": int(sorted_vals[min(len(sorted_vals) - 1, int(round(0.95 * (len(sorted_vals) - 1))))]),
        "mean_ms": int(statistics.mean(sorted_vals)),
        "n": len(sorted_vals),
    }


def verification_outcome_counts(statuses: list[str]) -> dict:
    return {
        "supported": statuses.count("supported"),
        "weak": statuses.count("weak"),
        "not_found": statuses.count("not_found"),
        "total_claims": len(statuses),
    }
