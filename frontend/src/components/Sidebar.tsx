import { useState } from "react";
import type { Collection } from "../types";

interface Props {
  collections: Collection[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreate: (name: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  loading: boolean;
}

export function Sidebar({ collections, selectedId, onSelect, onCreate, onDelete, loading }: Props) {
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    setError(null);
    try {
      await onCreate(name);
      setNewName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create collection.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1>EvidenceDesk</h1>
        <p className="tagline">Evidence-first document Q&amp;A</p>
      </div>

      <form className="new-collection-form" onSubmit={handleCreate}>
        <input
          aria-label="New collection name"
          placeholder="New collection (e.g. Biology 101)"
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
          maxLength={200}
        />
        <button type="submit" disabled={creating || !newName.trim()}>
          {creating ? "Creating…" : "Create"}
        </button>
      </form>
      {error && <p className="error-text">{error}</p>}

      <nav className="collection-list" aria-label="Collections">
        {loading && <p className="muted">Loading collections…</p>}
        {!loading && collections.length === 0 && (
          <p className="muted empty-state">No collections yet. Create one above to get started.</p>
        )}
        {collections.map((c) => (
          <div key={c.id} className={`collection-row ${c.id === selectedId ? "active" : ""}`}>
            <button className="collection-select" onClick={() => onSelect(c.id)}>
              <span className="collection-name">{c.name}</span>
              <span className="collection-meta">
                {c.document_count} doc{c.document_count === 1 ? "" : "s"}
              </span>
            </button>
            <button
              className="icon-button danger"
              aria-label={`Delete collection ${c.name}`}
              title="Delete collection"
              onClick={() => {
                if (window.confirm(`Delete collection "${c.name}" and all its documents? This cannot be undone.`)) {
                  onDelete(c.id);
                }
              }}
            >
              ×
            </button>
          </div>
        ))}
      </nav>
    </aside>
  );
}
