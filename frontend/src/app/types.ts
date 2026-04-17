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

export type AppUser = {
  id: string;
  email: string;
  fullName: string;
  createdAt: number;
};

export type AuthSession = {
  expiresAt: number;
  user: AppUser;
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
  pdfAvailable: boolean;
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

export type WorkspaceNav = "workspace" | "documents" | "activity";
