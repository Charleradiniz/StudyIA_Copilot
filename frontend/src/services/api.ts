export const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export type ConversationTurn = {
  role: "user" | "assistant";
  content: string;
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

async function parseResponse<T>(res: Response): Promise<T> {
  const data = await res.json();

  if (!res.ok) {
    const message =
      (typeof data?.detail === "string" && data.detail) ||
      (typeof data?.error === "string" && data.error) ||
      "Unexpected API error.";

    throw new Error(message);
  }

  return data as T;
}

export async function uploadPdf(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_URL}/api/upload`, {
    method: "POST",
    body: formData,
  });

  return parseResponse<UploadPdfResponse>(res);
}

export async function askQuestion(
  question: string,
  docId: string,
  history: ConversationTurn[] = [],
) {
  const res = await fetch(`${API_URL}/api/ask`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question,
      doc_id: docId,
      history,
    }),
  });

  return parseResponse<AskQuestionResponse>(res);
}

export async function listDocuments() {
  const res = await fetch(`${API_URL}/api/documents`);
  return parseResponse<DocumentsResponse>(res);
}

export async function getSystemStatus() {
  const res = await fetch(`${API_URL}/api/system/status`);
  return parseResponse<SystemStatusResponse>(res);
}
