export const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

let authToken: string | null = null;

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export type ConversationTurn = {
  role: "user" | "assistant";
  content: string;
};

export type ApiUserResponse = {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
};

export type AuthResponse = {
  token: string;
  expires_at: string;
  user: ApiUserResponse;
};

export type AuthMeResponse = {
  user: ApiUserResponse;
};

export type UploadPdfResponse = {
  doc_id: string;
  name: string;
  chunks: number;
  pages: number;
  rag_mode: string;
  vector_ready: boolean;
  uploaded_at: string;
  preview: string;
};

export type DocumentSummaryResponse = {
  doc_id: string;
  name: string;
  chunks: number;
  pages: number;
  rag_mode: string;
  vector_ready: boolean;
  uploaded_at?: string;
  preview: string;
};

export type DocumentsResponse = {
  documents: DocumentSummaryResponse[];
};

export type DeleteDocumentResponse = {
  doc_id: string;
  removed: boolean;
  removed_files: string[];
};

export type ClearDocumentsResponse = {
  removed_count: number;
  removed_doc_ids: string[];
};

export type SystemStatusResponse = {
  status: string;
  rag_mode: string;
  gemini_model: string;
  llm_configured: boolean;
  embedding_model_loaded: boolean;
  reranker_loaded: boolean;
  vector_search_enabled: boolean;
  documents_indexed: number;
  workspace_data_available: boolean;
};

export type AskQuestionResponse = {
  question: string;
  answer: string;
  sources: {
    id: number;
    text: string;
    score?: number;
    doc_id?: string;
    chunk_id?: number;
    page?: number;
    bbox?: number[];
    line_boxes?: number[][];
  }[];
};

export function setAuthToken(token: string | null) {
  authToken = token;
}

async function parseResponse<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const message =
      (typeof data?.detail === "string" && data.detail) ||
      (typeof data?.error === "string" && data.error) ||
      "Unexpected API error.";

    throw new ApiError(message, res.status);
  }

  return data as T;
}

function createHeaders(headers?: HeadersInit) {
  const nextHeaders = new Headers(headers);

  if (authToken) {
    nextHeaders.set("Authorization", `Bearer ${authToken}`);
  }

  return nextHeaders;
}

async function apiFetch(path: string, init?: RequestInit) {
  const headers = createHeaders(init?.headers);

  return fetch(`${API_URL}${path}`, {
    ...init,
    headers,
  });
}

export async function registerUser(payload: {
  fullName: string;
  email: string;
  password: string;
}) {
  const res = await apiFetch("/api/auth/register", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      full_name: payload.fullName,
      email: payload.email,
      password: payload.password,
    }),
  });

  return parseResponse<AuthResponse>(res);
}

export async function loginUser(payload: { email: string; password: string }) {
  const res = await apiFetch("/api/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return parseResponse<AuthResponse>(res);
}

export async function getCurrentUser() {
  const res = await apiFetch("/api/auth/me");
  return parseResponse<AuthMeResponse>(res);
}

export async function logoutUser() {
  const res = await apiFetch("/api/auth/logout", {
    method: "POST",
  });

  return parseResponse<{ logged_out: boolean }>(res);
}

export async function uploadPdf(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await apiFetch("/api/upload", {
    method: "POST",
    body: formData,
  });

  return parseResponse<UploadPdfResponse>(res);
}

export async function askQuestion(
  question: string,
  docIds: string[],
  history: ConversationTurn[] = [],
) {
  const normalizedDocIds = [...new Set(docIds.filter(Boolean))];
  const res = await apiFetch("/api/ask", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question,
      doc_id: normalizedDocIds[0] ?? null,
      doc_ids: normalizedDocIds,
      history,
    }),
  });

  return parseResponse<AskQuestionResponse>(res);
}

export async function listDocuments() {
  const res = await apiFetch("/api/documents");
  return parseResponse<DocumentsResponse>(res);
}

export async function getSystemStatus() {
  const res = await apiFetch("/api/system/status");
  return parseResponse<SystemStatusResponse>(res);
}

export async function deleteDocument(docId: string) {
  const res = await apiFetch(`/api/documents/${encodeURIComponent(docId)}`, {
    method: "DELETE",
  });

  return parseResponse<DeleteDocumentResponse>(res);
}

export async function clearDocuments() {
  const res = await apiFetch("/api/documents", {
    method: "DELETE",
  });

  return parseResponse<ClearDocumentsResponse>(res);
}
