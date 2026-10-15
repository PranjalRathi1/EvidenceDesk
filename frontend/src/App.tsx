import { useEffect, useState } from "react";
import { api, ApiError } from "./api";
import { AskPanel } from "./components/AskPanel";
import { DocumentsPanel } from "./components/DocumentsPanel";
import { EvaluationPanel } from "./components/EvaluationPanel";
import { Sidebar } from "./components/Sidebar";
import { SourceViewerModal } from "./components/SourceViewerModal";
import type { Collection, DocumentItem } from "./types";

type Tab = "documents" | "ask" | "evaluation";

export default function App() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [collectionsLoading, setCollectionsLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [tab, setTab] = useState<Tab>("documents");
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [backendReachable, setBackendReachable] = useState(true);
  const [viewerState, setViewerState] = useState<{ documentId: string; page: number; quote?: string } | null>(null);

  useEffect(() => {
    api
      .health()
      .catch(() => setBackendReachable(false));
    refreshCollections();
  }, []);

  useEffect(() => {
    if (selectedId) {
      refreshDocuments(selectedId);
    } else {
      setDocuments([]);
    }
  }, [selectedId]);

  async function refreshCollections() {
    setCollectionsLoading(true);
    try {
      const list = await api.listCollections();
      setCollections(list);
      if (!selectedId && list.length > 0) setSelectedId(list[0].id);
      if (selectedId && !list.some((c) => c.id === selectedId)) {
        setSelectedId(list.length > 0 ? list[0].id : null);
      }
    } catch (err) {
      setGlobalError(err instanceof ApiError ? err.message : "Could not reach the EvidenceDesk API.");
    } finally {
      setCollectionsLoading(false);
    }
  }

  async function refreshDocuments(collectionId: string) {
    try {
      const docs = await api.listDocuments(collectionId);
      setDocuments(docs);
    } catch {
      setDocuments([]);
    }
  }

  async function handleCreateCollection(name: string) {
    const created = await api.createCollection(name);
    await refreshCollections();
    setSelectedId(created.id);
  }

  async function handleDeleteCollection(id: string) {
    await api.deleteCollection(id);
    await refreshCollections();
  }

  const selectedCollection = collections.find((c) => c.id === selectedId) ?? null;
  const hasIndexedDocuments = documents.some((d) => d.status === "indexed");

  return (
    <div className="app-shell">
      <Sidebar
        collections={collections}
        selectedId={selectedId}
        onSelect={(id) => {
          setSelectedId(id);
          setTab("documents");
        }}
        onCreate={handleCreateCollection}
        onDelete={handleDeleteCollection}
        loading={collectionsLoading}
      />

      <main className="main-area">
        {!backendReachable && (
          <div className="banner banner-error">
            Can't reach the EvidenceDesk backend at the configured API URL. Make sure the backend server is
            running (see README) and reload.
          </div>
        )}
        {globalError && backendReachable && <div className="banner banner-error">{globalError}</div>}

        {!selectedCollection ? (
          <div className="empty-state-centered">
            <h2>No collection selected</h2>
            <p className="muted">Create a collection in the sidebar to upload documents and start asking questions.</p>
          </div>
        ) : (
          <>
            <div className="collection-heading">
              <h2>{selectedCollection.name}</h2>
            </div>
            <nav className="tab-bar" aria-label="Collection sections">
              <button className={tab === "documents" ? "active" : ""} onClick={() => setTab("documents")}>
                Documents
              </button>
              <button className={tab === "ask" ? "active" : ""} onClick={() => setTab("ask")}>
                Ask
              </button>
              <button className={tab === "evaluation" ? "active" : ""} onClick={() => setTab("evaluation")}>
                Evaluation
              </button>
            </nav>

            {tab === "documents" && (
              <DocumentsPanel
                collectionId={selectedCollection.id}
                documents={documents}
                onChanged={async () => {
                  await refreshDocuments(selectedCollection.id);
                  await refreshCollections();
                }}
                onOpenPage={(documentId, page) => setViewerState({ documentId, page })}
              />
            )}
            {tab === "ask" && (
              <AskPanel
                collectionId={selectedCollection.id}
                hasDocuments={hasIndexedDocuments}
                onOpenPage={(documentId, page, quote) => setViewerState({ documentId, page, quote })}
              />
            )}
            {tab === "evaluation" && <EvaluationPanel collectionId={selectedCollection.id} />}
          </>
        )}
      </main>

      {viewerState && (
        <SourceViewerModal
          documentId={viewerState.documentId}
          page={viewerState.page}
          quote={viewerState.quote}
          onClose={() => setViewerState(null)}
          onNavigatePage={(page) => setViewerState((v) => (v ? { ...v, page } : v))}
        />
      )}
    </div>
  );
}
