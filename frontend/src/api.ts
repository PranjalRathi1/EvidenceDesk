import type { AnswerResult, Collection, DocumentItem, EvaluationRun, RetrievalMode, SourcePage } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, init);
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      // ignore
    }
    throw new ApiError(resp.status, detail || `Request failed with status ${resp.status}`);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  health: () => request<{ status: string; ollama: { available: boolean; message: string } }>("/api/health"),

  listCollections: () => request<Collection[]>("/api/collections"),
  createCollection: (name: string) =>
    request<Collection>("/api/collections", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }),
  deleteCollection: (id: string) => request<void>(`/api/collections/${id}`, { method: "DELETE" }),

  listDocuments: (collectionId: string) => request<DocumentItem[]>(`/api/collections/${collectionId}/documents`),
  uploadDocument: async (collectionId: string, file: File): Promise<DocumentItem> => {
    const form = new FormData();
    form.append("file", file);
    return request<DocumentItem>(`/api/collections/${collectionId}/documents`, { method: "POST", body: form });
  },
  deleteDocument: (documentId: string) => request<void>(`/api/documents/${documentId}`, { method: "DELETE" }),
  getSourcePage: (documentId: string, pageNumber: number) =>
    request<SourcePage>(`/api/documents/${documentId}/pages/${pageNumber}`),

  askQuestion: (collectionId: string, question: string, retrievalMode?: RetrievalMode) =>
    request<AnswerResult>(`/api/collections/${collectionId}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, retrieval_mode: retrievalMode ?? null }),
    }),

  startEvaluation: (collectionId: string) =>
    request<EvaluationRun>(`/api/collections/${collectionId}/evaluate`, { method: "POST" }),
  listEvaluations: () => request<EvaluationRun[]>("/api/evaluations"),
  getEvaluation: (runId: string) => request<EvaluationRun>(`/api/evaluations/${runId}`),
};
