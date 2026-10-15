import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { SourcePage } from "../types";

interface Props {
  documentId: string;
  page: number;
  quote?: string;
  onClose: () => void;
  onNavigatePage: (page: number) => void;
}

export function SourceViewerModal({ documentId, page, quote, onClose, onNavigatePage }: Props) {
  const [data, setData] = useState<SourcePage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getSourcePage(documentId, page)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load this page.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [documentId, page]);

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Source page viewer" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <header className="modal-header">
          <h3>{data?.filename ?? "Source"}</h3>
          <button className="icon-button" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </header>

        {quote && (
          <div className="quote-callout">
            <span className="quote-label">Cited quote</span>
            <p>&ldquo;{quote}&rdquo;</p>
          </div>
        )}

        {loading && <p className="muted">Loading page…</p>}
        {error && <p className="error-text">{error}</p>}

        {data && (
          <>
            <div className="page-nav">
              <button disabled={page <= 1} onClick={() => onNavigatePage(page - 1)}>
                ← Previous
              </button>
              <span>
                Page {data.page_number} of {data.page_count}
              </span>
              <button disabled={page >= data.page_count} onClick={() => onNavigatePage(page + 1)}>
                Next →
              </button>
            </div>
            <pre className="page-text">{data.page_text}</pre>
          </>
        )}
      </div>
    </div>
  );
}
