import { useRef, useState } from "react";
import { api, ApiError } from "../api";
import type { DocumentItem } from "../types";

interface Props {
  collectionId: string;
  documents: DocumentItem[];
  onChanged: () => Promise<void>;
  onOpenPage: (documentId: string, page: number) => void;
}

const STATUS_LABEL: Record<string, string> = {
  pending: "Pending",
  processing: "Processing…",
  indexed: "Indexed",
  failed: "Failed",
  unsupported: "Unsupported",
};

export function DocumentsPanel({ collectionId, documents, onChanged, onOpenPage }: Props) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadError(null);
    for (const file of Array.from(files)) {
      try {
        await api.uploadDocument(collectionId, file);
      } catch (err) {
        setUploadError(err instanceof ApiError ? `${file.name}: ${err.message}` : `${file.name}: upload failed.`);
      }
    }
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
    await onChanged();
  }

  async function handleDelete(doc: DocumentItem) {
    if (!window.confirm(`Delete "${doc.filename}"? Its indexed content will be removed.`)) return;
    await api.deleteDocument(doc.id);
    await onChanged();
  }

  return (
    <section className="panel">
      <header className="panel-header">
        <h2>Documents</h2>
        <label className={`upload-button ${uploading ? "disabled" : ""}`}>
          {uploading ? "Uploading…" : "Upload PDF"}
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            multiple
            disabled={uploading}
            onChange={(e) => handleFiles(e.target.files)}
            style={{ display: "none" }}
          />
        </label>
      </header>

      {uploadError && <p className="error-text">{uploadError}</p>}

      {documents.length === 0 ? (
        <p className="muted empty-state">
          No documents yet. Upload a text-based PDF to start asking questions about it.
        </p>
      ) : (
        <ul className="document-list">
          {documents.map((doc) => (
            <li key={doc.id} className={`document-row status-${doc.status}`}>
              <div className="document-info">
                <span className="document-name">{doc.filename}</span>
                <span className={`status-badge status-${doc.status}`}>{STATUS_LABEL[doc.status] ?? doc.status}</span>
              </div>
              {doc.status === "indexed" && (
                <div className="document-sub">
                  {doc.page_count} pages · {doc.chunk_count} chunks
                  {doc.status_message && <span className="document-note"> — {doc.status_message}</span>}
                  <button className="link-button" onClick={() => onOpenPage(doc.id, 1)}>
                    View source
                  </button>
                </div>
              )}
              {(doc.status === "failed" || doc.status === "unsupported") && doc.status_message && (
                <p className="document-note document-note-warning">{doc.status_message}</p>
              )}
              <button className="icon-button danger" aria-label={`Delete ${doc.filename}`} onClick={() => handleDelete(doc)}>
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
