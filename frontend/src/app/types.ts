export type Source = {
  id: number;
  text: string;
  score?: number;
  doc_id?: string;
  chunk_id?: number;
  page?: number;
  bbox?: number[];
  line_boxes?: number[][];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  streaming?: boolean;
};

export type ConversationTurn = {
  role: "user" | "assistant";
  content: string;
};

export type ChatSession = {
  id: string;
  title: string;
  activeDocIds: string[];
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
};

export type AppDocument = {
  id: string;
  name: string;
  uploadedAt: number;
  chunkCount: number;
  pageCount: number;
  ragMode: string;
  vectorReady: boolean;
  preview: string;
};

export type SystemStatus = {
  status: string;
  ragMode: string;
  geminiModel: string;
  llmConfigured: boolean;
  embeddingModelLoaded: boolean;
  rerankerLoaded: boolean;
  vectorSearchEnabled: boolean;
  documentsIndexed: number;
  workspaceDataAvailable: boolean;
};
