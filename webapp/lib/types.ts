export type Role = "user" | "assistant";

export interface ChatMessage {
  role: Role;
  content: string;
}

export interface Health {
  ollama_running: boolean;
  selected_model: string;
  selected_model_available: boolean;
  available_models: string[];
}

export interface SourceRef {
  citation: string;
  similarity_score: number;
  text: string;
}

export interface VerificationItem {
  claim: string;
  supported: boolean;
  confidence: number;
  reason: string;
}

export interface Stats {
  latency_ms: number;
  claims_checked: number;
  claims_supported: number;
  support_rate: number;
  model: string;
}

export type Mode = "LLM" | "RAG" | "ABSTAIN";

export interface ChatResponse {
  answer: string;
  latency_ms: number;
  model: string;
}

export interface RAGResponse {
  answer: string;
  mode: Mode;
  confidence: number;
  sources: SourceRef[];
  verification: VerificationItem[];
  abstained: boolean;
  reason?: string;
  stats?: Partial<Stats>;
  latency_ms?: number;
  model?: string;
  fallback_unavailable?: boolean;
}

export type RenderedMeta = Partial<RAGResponse> & ChatResponse;

/** A chat message rendered in a view, with optional pipeline metadata. */
export interface ViewMessage extends ChatMessage {
  meta?: RenderedMeta;
}

export interface SourcesStatus {
  files: string[];
  chunk_count: number;
  index_ready: boolean;
}

export interface IngestResult {
  files: string[];
  source_count: number;
  chunk_count: number;
}