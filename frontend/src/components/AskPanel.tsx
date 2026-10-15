import { useState } from "react";
import { api, ApiError } from "../api";
import type { AnswerResult, RetrievalMode } from "../types";

interface Props {
  collectionId: string;
  hasDocuments: boolean;
  onOpenPage: (documentId: string, page: number, quote?: string) => void;
}

const STATUS_LABEL: Record<string, string> = {
  supported: "Supported",
  weak: "Weak",
  not_found: "Not found",
};

const MODE_OPTIONS: { value: RetrievalMode | ""; label: string }[] = [
  { value: "", label: "Default (configured)" },
  { value: "vector", label: "Vector only" },
  { value: "keyword", label: "Keyword only (BM25)" },
  { value: "hybrid", label: "Hybrid (RRF fusion)" },
  { value: "hybrid_rerank", label: "Hybrid + reranking" },
];

export function AskPanel({ collectionId, hasDocuments, onOpenPage }: Props) {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<RetrievalMode | "">("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [showPassages, setShowPassages] = useState(false);

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const answer = await api.askQuestion(collectionId, question.trim(), mode || undefined);
      setResult(answer);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong answering this question.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <header className="panel-header">
        <h2>Ask a question</h2>
      </header>

      {!hasDocuments && (
        <p className="muted empty-state">Upload at least one indexed document before asking questions.</p>
      )}

      <form className="ask-form" onSubmit={handleAsk}>
        <textarea
          aria-label="Question"
          placeholder="Ask something about the documents in this collection…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={!hasDocuments || loading}
          rows={3}
        />
        <div className="ask-controls">
          <label className="mode-select">
            Retrieval mode
            <select value={mode} onChange={(e) => setMode(e.target.value as RetrievalMode | "")} disabled={loading}>
              {MODE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <button type="submit" disabled={!hasDocuments || loading || !question.trim()}>
            {loading ? "Thinking…" : "Ask"}
          </button>
        </div>
      </form>

      {loading && <p className="muted loading-note">Retrieving evidence and generating a verified answer — this runs a local model and can take up to a minute…</p>}
      {error && <p className="error-text">{error}</p>}

      {result && (
        <div className={`answer-card ${result.refused ? "refused" : ""}`}>
          {result.refused ? (
            <div className="refusal-block">
              <strong>Refused.</strong> {result.answer_text}
              {result.refusal_reason && <p className="muted refusal-reason">{result.refusal_reason}</p>}
            </div>
          ) : (
            <>
              <p className="answer-text">{result.answer_text}</p>
              <ul className="claims-list">
                {result.claims.map((claim, i) => (
                  <li key={i} className={`claim-row status-${claim.verification_status}`}>
                    <p className="claim-text">{claim.claim_text}</p>
                    <div className="claim-meta">
                      <span className={`status-chip status-${claim.verification_status}`}>
                        {STATUS_LABEL[claim.verification_status] ?? claim.verification_status}
                      </span>
                      {claim.citation && (
                        <button
                          className="link-button citation-chip"
                          onClick={() => onOpenPage(claim.citation!.document_id, claim.citation!.page_number, claim.citation!.quote)}
                        >
                          {claim.citation.document_filename} · p.{claim.citation.page_number}
                        </button>
                      )}
                    </div>
                    {claim.verification_status !== "supported" && (
                      <p className="claim-explanation muted">{claim.explanation}</p>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}

          <div className="answer-footer">
            <button className="link-button" onClick={() => setShowPassages((v) => !v)}>
              {showPassages ? "Hide" : "Show"} retrieved passages ({result.retrieved_passages.length})
            </button>
            <span className="muted timing-note">
              {result.retrieval_mode} · {result.timings_ms.total_ms}ms
              {result.retry_count > 0 ? ` · retried ${result.retry_count}×` : ""}
            </span>
          </div>

          {showPassages && (
            <ul className="passages-list">
              {result.retrieved_passages.map((p, i) => (
                <li key={i}>
                  <button className="link-button" onClick={() => onOpenPage(p.document_id, p.page_number)}>
                    p.{p.page_number}
                  </button>
                  <span className="passage-excerpt muted">{p.quote}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
