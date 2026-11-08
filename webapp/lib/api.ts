import type {
  ChatMessage,
  ChatResponse,
  Health,
  IngestResult,
  RAGResponse,
  SourcesStatus,
} from "./types";

const rawUrl = process.env.NEXT_PUBLIC_API_URL?.trim();
const API_URL = rawUrl
  ? rawUrl.startsWith("http://") || rawUrl.startsWith("https://")
    ? rawUrl.replace(/\/+$/, "")
    : `https://${rawUrl.replace(/\/+$/, "")}`
  : "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const detail =
      typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);
    return new ApiError(detail || `Request failed (${res.status})`, res.status);
  } catch {
    return new ApiError(`Request failed (${res.status})`, res.status);
  }
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as T;
}

export function getHealth(): Promise<Health> {
  return fetch(`${API_URL}/health`).then(async (res) => {
    if (!res.ok) throw await parseError(res);
    return (await res.json()) as Health;
  });
}

export function normalChat(question: string, history: ChatMessage[]): Promise<ChatResponse> {
  return post<ChatResponse>("/chat/normal", { question, history: history.slice(-12) });
}

export function hybridChat(question: string, history: ChatMessage[]): Promise<RAGResponse> {
  return post<RAGResponse>("/chat/hybrid", { question, history: history.slice(-12) });
}

export function hallufixAsk(question: string, history: ChatMessage[]): Promise<RAGResponse> {
  return post<RAGResponse>("/ask", { question, history: history.slice(-12) });
}

export function getSourcesStatus(): Promise<SourcesStatus> {
  return fetch(`${API_URL}/sources`).then(async (res) => {
    if (!res.ok) throw await parseError(res);
    return (await res.json()) as SourcesStatus;
  });
}

export async function ingestFiles(files: File[]): Promise<IngestResult> {
  const form = new FormData();
  for (const file of files) form.append("files", file, file.name);
  const res = await fetch(`${API_URL}/ingest`, { method: "POST", body: form });
  if (!res.ok) throw await parseError(res);
  return (await res.json()) as IngestResult;
}