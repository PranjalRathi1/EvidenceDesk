export type DocStatus = "pending" | "processing" | "indexed" | "failed" | "unsupported";
export type VerificationStatus = "supported" | "weak" | "not_found";
export type RetrievalMode = "vector" | "keyword" | "hybrid" | "hybrid_rerank";

export interface Collection {
  id: string;
  name: string;
  created_at: string;
  document_count: number;
}

export interface DocumentItem {
  id: string;
  collection_id: string;
  filename: string;
  status: DocStatus;
  status_message: string;
  page_count: number;
  chunk_count: number;
  created_at: string;
}

export interface Citation {
  document_id: string;
  document_filename: string;
  page_number: number;
  chunk_id: string;
  quote: string;
}

export interface Claim {
  claim_text: string;
  citation: Citation | null;
  verification_status: VerificationStatus;
  explanation: string;
}

export interface AnswerResult {
  refused: boolean;
  refusal_reason: string | null;
  answer_text: string;
  claims: Claim[];
  retrieved_passages: Citation[];
  retrieval_mode: string;
  retry_count: number;
  timings_ms: Record<string, number>;
}

export interface SourcePage {
  document_id: string;
  filename: string;
  page_number: number;
  page_count: number;
  page_text: string;
  excerpt?: string | null;
}

export interface EvaluationRun {
  id: string;
  collection_id: string;
  status: "running" | "completed" | "failed";
  num_cases: number;
  created_at: string;
  finished_at: string | null;
  report_path: string;
  error_message?: string;
  report?: EvaluationReport | null;
}

export interface EvaluationReport {
  generated_at: string;
  collection_id: string;
  num_cases: number;
  dataset_description: string;
  retrieval_comparison: Record<
    string,
    { recall_at_k: number; mrr: number; retrieval_latency_ms: Record<string, number>; top_k: number }
  >;
  generation_evaluation: {
    primary_mode: string;
    citation_precision: number;
    citation_recall: number;
    refusal: Record<string, number>;
    verification_outcomes: Record<string, number>;
    latency_ms: Record<string, number>;
    mean_retry_count: number;
    cases: EvaluationCaseResult[];
  };
  reranker_available: boolean;
}

export interface EvaluationCaseResult {
  id: string;
  question: string;
  category: string;
  expected_answerable: boolean;
  refused: boolean;
  refusal_reason: string | null;
  answer_text: string;
  retry_count: number;
  latency_ms: number;
  cited_pages: [string, number][];
  expected_pages: [string, number][];
  claims: { claim_text: string; status: VerificationStatus; method: string; quote: string; page: number | null; document: string | null }[];
}
