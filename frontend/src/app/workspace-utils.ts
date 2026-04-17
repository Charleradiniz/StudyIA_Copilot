import type {
  ApiUserResponse,
  AuthResponse,
  ChatResponse,
  DeletedChatResponse,
  DocumentSummaryResponse,
  SystemStatusResponse,
} from "../services/api";
import type {
  AppDocument,
  AppUser,
  AuthSession,
  ChatMessage,
  ChatSession,
  Source,
  SystemStatus,
  WorkspaceNav,
} from "./types";

const WORKSPACE_STORAGE_PREFIX = "studyiacopilot.workspace.v3";

export type PersistedWorkspace = {
  chats: ChatSession[];
  activeChatId: string;
  activeNav: WorkspaceNav;
  viewerDocId: string | null;
};

export type DeletedChatTombstone = {
  id: string;
  deletedAt: number;
};

export function toTimestamp(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string") {
    const parsed = Date.parse(value);
    if (!Number.isNaN(parsed)) {
      return parsed;
    }
  }

  return Date.now();
}

export function mapApiUser(user: ApiUserResponse): AppUser {
  return {
    id: user.id,
    email: user.email,
    fullName: user.full_name,
    createdAt: toTimestamp(user.created_at),
  };
}

export function mapAuthSession(response: AuthResponse): AuthSession {
  return {
    expiresAt: toTimestamp(response.expires_at),
    user: mapApiUser(response.user),
  };
}

export function normalizeActiveDocIds(value: unknown, legacyValue?: unknown) {
  const ids = Array.isArray(value)
    ? value
    : typeof legacyValue === "string" && legacyValue
      ? [legacyValue]
      : [];

  return [...new Set(ids)].filter(
    (docId): docId is string => typeof docId === "string" && docId.trim().length > 0,
  );
}

function normalizeChatMessage(value: unknown) {
  if (!value || typeof value !== "object") {
    return null;
  }

  const message = value as Partial<ChatMessage> & {
    id?: unknown;
    role?: unknown;
    content?: unknown;
    sources?: unknown;
    streaming?: unknown;
  };

  if (
    typeof message.id !== "string" ||
    (message.role !== "user" && message.role !== "assistant") ||
    typeof message.content !== "string"
  ) {
    return null;
  }

  return {
    id: message.id,
    role: message.role,
    content: message.content,
    sources: Array.isArray(message.sources)
      ? message.sources.filter((source): source is Source => Boolean(source) && typeof source === "object")
      : undefined,
    streaming: Boolean(message.streaming),
  };
}

export function normalizeChat(value: unknown): ChatSession | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const chat = value as {
    id?: unknown;
    title?: unknown;
    activeDocIds?: unknown;
    activeDocId?: unknown;
    messages?: unknown;
    createdAt?: unknown;
    updatedAt?: unknown;
  };

  if (
    typeof chat.id !== "string" ||
    typeof chat.title !== "string" ||
    !Array.isArray(chat.messages)
  ) {
    return null;
  }

  const messages = chat.messages
    .map((message) => normalizeChatMessage(message))
    .filter((message): message is NonNullable<ReturnType<typeof normalizeChatMessage>> => Boolean(message));

  if (messages.length === 0) {
    return null;
  }

  return {
    id: chat.id,
    title: chat.title,
    activeDocIds: normalizeActiveDocIds(chat.activeDocIds, chat.activeDocId),
    messages,
    createdAt: toTimestamp(chat.createdAt),
    updatedAt: toTimestamp(chat.updatedAt),
  };
}

export function mapApiChat(chat: ChatResponse): ChatSession | null {
  return normalizeChat({
    id: chat.id,
    title: chat.title,
    activeDocIds: chat.active_doc_ids,
    messages: chat.messages,
    createdAt: chat.created_at,
    updatedAt: chat.updated_at,
  });
}

export function mapDeletedChat(deleted: DeletedChatResponse): DeletedChatTombstone {
  return {
    id: deleted.id,
    deletedAt: toTimestamp(deleted.deleted_at),
  };
}

export function sortChats(chats: ChatSession[]) {
  return [...chats].sort((left, right) => right.updatedAt - left.updatedAt);
}

export function mergeChatCollections(
  remoteChats: ChatSession[],
  localChats: ChatSession[],
  deletedChats: DeletedChatTombstone[],
) {
  const deletedIds = new Set(deletedChats.map((deletedChat) => deletedChat.id));
  const merged = new Map<string, ChatSession>();

  for (const chat of sortChats(remoteChats)) {
    merged.set(chat.id, chat);
  }

  for (const chat of sortChats(localChats.filter((localChat) => !deletedIds.has(localChat.id)))) {
    const existingChat = merged.get(chat.id);

    if (!existingChat || chat.updatedAt > existingChat.updatedAt) {
      merged.set(chat.id, chat);
    }
  }

  return sortChats([...merged.values()]);
}

export function serializeChatForApi(chat: ChatSession) {
  return {
    id: chat.id,
    title: chat.title,
    active_doc_ids: normalizeActiveDocIds(chat.activeDocIds),
    messages: chat.messages
      .filter((message) => message.content.trim().length > 0)
      .map((message) => ({
        id: message.id,
        role: message.role,
        content: message.content,
        sources: (message.sources ?? []).map((source) => ({
          id: source.id,
          text: source.text,
          score: source.score,
          doc_id: source.doc_id,
          chunk_id: source.chunk_id,
          page: source.page,
          bbox: source.bbox,
          line_boxes: source.line_boxes,
        })),
      })),
    created_at: new Date(chat.createdAt).toISOString(),
    updated_at: new Date(chat.updatedAt).toISOString(),
  };
}

export function hasStreamingChatMessages(chats: ChatSession[]) {
  return chats.some((chat) => chat.messages.some((message) => message.streaming));
}

export function resolveAvailableChatId(
  chats: ChatSession[],
  ...candidates: Array<string | null | undefined>
) {
  for (const candidate of candidates) {
    if (candidate && chats.some((chat) => chat.id === candidate)) {
      return candidate;
    }
  }

  return chats[0]?.id ?? "";
}

export function areChatCollectionsEquivalent(left: ChatSession[], right: ChatSession[]) {
  if (left.length !== right.length) {
    return false;
  }

  return (
    JSON.stringify(left.map((chat) => serializeChatForApi(chat))) ===
    JSON.stringify(right.map((chat) => serializeChatForApi(chat)))
  );
}

export function mapApiDocument(document: DocumentSummaryResponse): AppDocument {
  return {
    id: document.doc_id,
    name: document.name,
    uploadedAt: toTimestamp(document.uploaded_at),
    chunkCount: document.chunks,
    pageCount: document.pages,
    ragMode: document.rag_mode,
    vectorReady: document.vector_ready,
    preview: document.preview,
    pdfAvailable: document.pdf_available ?? true,
  };
}

export function mapSystemStatus(status: SystemStatusResponse): SystemStatus {
  return {
    status: status.status,
    ragMode: status.rag_mode,
    geminiModel: status.gemini_model,
    llmConfigured: status.llm_configured,
    embeddingModelLoaded: status.embedding_model_loaded,
    rerankerLoaded: status.reranker_loaded,
    vectorSearchEnabled: status.vector_search_enabled,
    documentsIndexed: status.documents_indexed,
    workspaceDataAvailable: status.workspace_data_available,
  };
}

export function mergeDocuments(...collections: AppDocument[][]) {
  const merged = new Map<string, AppDocument>();

  for (const collection of collections) {
    for (const document of collection) {
      const current = merged.get(document.id);
      merged.set(document.id, current ? { ...current, ...document } : document);
    }
  }

  return [...merged.values()].sort((left, right) => right.uploadedAt - left.uploadedAt);
}

function serializeDocumentForCompare(document: AppDocument) {
  return {
    id: document.id,
    name: document.name,
    uploadedAt: document.uploadedAt,
    chunkCount: document.chunkCount,
    pageCount: document.pageCount,
    ragMode: document.ragMode,
    vectorReady: document.vectorReady,
    preview: document.preview,
    pdfAvailable: document.pdfAvailable,
  };
}

export function areDocumentCollectionsEquivalent(left: AppDocument[], right: AppDocument[]) {
  if (left.length !== right.length) {
    return false;
  }

  return (
    JSON.stringify(left.map((document) => serializeDocumentForCompare(document))) ===
    JSON.stringify(right.map((document) => serializeDocumentForCompare(document)))
  );
}

export function pruneChatsForAvailableDocuments(chats: ChatSession[], documents: AppDocument[]) {
  const availableDocIds = new Set(documents.map((document) => document.id));

  return chats.map((chat) => {
    const nextActiveDocIds = chat.activeDocIds.filter((docId) => availableDocIds.has(docId));
    if (nextActiveDocIds.length === chat.activeDocIds.length) {
      return chat;
    }

    return {
      ...chat,
      activeDocIds: nextActiveDocIds,
      updatedAt: Date.now(),
    };
  });
}

export function resolveViewerDocumentId(
  chats: ChatSession[],
  activeChatId: string,
  currentViewerDocId: string | null,
) {
  const activeChat = chats.find((chat) => chat.id === activeChatId) ?? chats[0] ?? null;
  const activeDocIds = activeChat?.activeDocIds ?? [];

  if (currentViewerDocId && activeDocIds.includes(currentViewerDocId)) {
    return currentViewerDocId;
  }

  return activeDocIds[0] ?? null;
}

export function getWorkspaceStorageKey(userId: string) {
  return `${WORKSPACE_STORAGE_PREFIX}.${userId}`;
}

export function clearPersistedWorkspace(userId: string | null | undefined) {
  if (typeof window === "undefined" || !userId) {
    return;
  }

  window.localStorage.removeItem(getWorkspaceStorageKey(userId));
}

export function loadPersistedWorkspace(userId: string): PersistedWorkspace | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(getWorkspaceStorageKey(userId));
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as Partial<PersistedWorkspace> & {
      chats?: unknown[];
    };
    if (!Array.isArray(parsed.chats) || parsed.chats.length === 0) {
      return null;
    }

    const chats = parsed.chats
      .map((chat) => normalizeChat(chat))
      .filter((chat): chat is ChatSession => Boolean(chat));

    if (chats.length === 0) {
      return null;
    }

    const activeNav =
      parsed.activeNav === "documents" || parsed.activeNav === "activity"
        ? parsed.activeNav
        : "workspace";

    return {
      chats,
      activeChatId:
        typeof parsed.activeChatId === "string" && parsed.activeChatId
          ? parsed.activeChatId
          : chats[0].id,
      activeNav,
      viewerDocId: typeof parsed.viewerDocId === "string" ? parsed.viewerDocId : null,
    };
  } catch (error) {
    console.error("Failed to load persisted workspace", error);
    return null;
  }
}
