import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { EvaluationRun } from "../types";

interface Props {
  collectionId: string;
}

function pct(v: number | undefined | null): string {
  if (v === undefined || v === null || Number.isNaN(v)) return "—";
  return `${Math.round(v * 100)}%`;
}

const MODE_LABELS: Record<string, string> = {
  vector: "Vector only",
  keyword: "Keyword only",
  hybrid: "Hybrid (RRF)",
  hybrid_rerank: "Hybrid + rerank",
};

export function EvaluationPanel({ collectionId }: Props) {
  const [run, setRun] = useState<EvaluationRun | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedCase, setExpandedCase] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    api
      .listEvaluations()
      .then((runs) => {
        const latest = runs.find((r) => r.collection_id === collectionId);
        if (latest) loadRun(latest.id);
      })
      .catch(() => {});
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collectionId]);

  function loadRun(runId: string) {
    api.getEvaluation(runId).then((r) => {
      setRun(r);
      if (r.status === "running" && !pollRef.current) {
        pollRef.current = window.setInterval(async () => {
          const updated = await api.getEvaluation(runId);
          setRun(updated);
          if (updated.status !== "running" && pollRef.current) {
            window.clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }, 5000);
      }
    });
  }

  async function handleStart() {
    setStarting(true);
    setError(null);
    try {
      const started = await api.startEvaluation(collectionId);
      loadRun(started.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not start the evaluation run.");
    } finally {
      setStarting(false);
    }
  }

  const report = run?.report;

  return (
    <section className="panel">
      <header className="panel-header">
        <h2>Evaluation</h2>
        <button onClick={handleStart} disabled={starting || run?.status === "running"}>
          {run?.status === "running" ? "Running…" : starting ? "Starting…" : "Run evaluation"}
        </button>
      </header>

      {error && <p className="error-text">{error}</p>}

      {!run && (
        <p className="muted empty-state">
          No evaluation has been run yet for this collection. Running it executes the labelled question set
          against the current documents and reports retrieval, citation, refusal, and latency metrics.
        </p>
      )}

      {run && run.status === "running" && (
        <p className="muted loading-note">
          Running {run.num_cases} evaluation cases against a local model — this compares 4 retrieval modes and
          runs the full generation+verification pipeline, so it can take several minutes.
        </p>
      )}

      {run && run.status === "failed" && <p className="error-text">Evaluation run failed: {run.error_message}</p>}

      {report && (
        <div className="eval-report">
          <p className="muted">
            {report.num_cases} cases · generated {new Date(report.generated_at).toLocaleString()} · reranker{" "}
            {report.reranker_available ? "available" : "unavailable (fell back to unranked order)"}
          </p>

          <h3>Retrieval comparison (Recall@k / MRR)</h3>
          <table className="eval-table">
            <thead>
              <tr>
                <th>Mode</th>
                <th>Recall@k</th>
                <th>MRR</th>
                <th>p50 latency</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(report.retrieval_comparison).map(([mode, m]) => (
                <tr key={mode}>
                  <td>{MODE_LABELS[mode] ?? mode}</td>
                  <td>{pct(m.recall_at_k)}</td>
                  <td>{m.mrr?.toFixed(2) ?? "—"}</td>
                  <td>{m.retrieval_latency_ms?.p50_ms ?? "—"} ms</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Generation pipeline (primary mode: {MODE_LABELS[report.generation_evaluation.primary_mode] ?? report.generation_evaluation.primary_mode})</h3>
          <div className="eval-stat-grid">
            <div className="eval-stat">
              <span className="eval-stat-value">{pct(report.generation_evaluation.citation_precision)}</span>
              <span className="eval-stat-label">Citation precision</span>
            </div>
            <div className="eval-stat">
              <span className="eval-stat-value">{pct(report.generation_evaluation.citation_recall)}</span>
              <span className="eval-stat-label">Citation recall</span>
            </div>
            <div className="eval-stat">
              <span className="eval-stat-value">{pct(report.generation_evaluation.refusal.refusal_accuracy_on_unanswerable)}</span>
              <span className="eval-stat-label">Refusal accuracy</span>
            </div>
            <div className="eval-stat">
              <span className="eval-stat-value">{pct(report.generation_evaluation.refusal.false_refusal_rate_on_answerable)}</span>
              <span className="eval-stat-label">False refusal rate</span>
            </div>
            <div className="eval-stat">
              <span className="eval-stat-value">{report.generation_evaluation.latency_ms.p50_ms} ms</span>
              <span className="eval-stat-label">p50 latency</span>
            </div>
            <div className="eval-stat">
              <span className="eval-stat-value">{report.generation_evaluation.latency_ms.p95_ms} ms</span>
              <span className="eval-stat-label">p95 latency</span>
            </div>
          </div>

          <h3>Verification outcomes (claims across all cases)</h3>
          <div className="verification-bar">
            {(["supported", "weak", "not_found"] as const).map((status) => (
              <span key={status} className={`verification-count status-${status}`}>
                {status.replace("_", " ")}: {report.generation_evaluation.verification_outcomes[status] ?? 0}
              </span>
            ))}
          </div>

          <h3>Case-by-case results ({report.generation_evaluation.cases.length})</h3>
          <ul className="eval-case-list">
            {report.generation_evaluation.cases.map((c) => (
              <li key={c.id} className="eval-case-row">
                <button className="eval-case-summary" onClick={() => setExpandedCase(expandedCase === c.id ? null : c.id)}>
                  <span className={`case-outcome ${c.refused === !c.expected_answerable ? "ok" : "mismatch"}`}>
                    {c.refused ? "Refused" : "Answered"}
                  </span>
                  <span className="case-question">{c.question}</span>
                  <span className="muted case-category">{c.category}</span>
                </button>
                {expandedCase === c.id && (
                  <div className="eval-case-detail">
                    <p>
                      <strong>Expected answerable:</strong> {String(c.expected_answerable)} ·{" "}
                      <strong>Latency:</strong> {c.latency_ms} ms ·<strong> Retries:</strong> {c.retry_count}
                    </p>
                    {c.answer_text && <p className="muted">{c.answer_text}</p>}
                    {c.refusal_reason && <p className="muted">Refusal reason: {c.refusal_reason}</p>}
                    {c.claims.length > 0 && (
                      <ul className="eval-claims">
                        {c.claims.map((claim, i) => (
                          <li key={i} className={`status-${claim.status}`}>
                            [{claim.status}] {claim.claim_text} — {claim.document ? `${claim.document} p.${claim.page}` : "no citation"}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
