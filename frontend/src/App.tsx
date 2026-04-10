import { startTransition, useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { createAssistantMessage, createChat, createId } from "./app/chat-utils";
import type {
  AppDocument,
  ChatMessage,
  ChatSession,
  ConversationTurn,
  Source,
  SystemStatus,
} from "./app/types";
import PdfModal from "./components/PdfModal";
import ChatWorkspace from "./components/workspace/ChatWorkspace";
import SidebarPanel from "./components/workspace/SidebarPanel";
import ViewerPanel from "./components/workspace/ViewerPanel";
import {
  API_URL,
  askQuestion,
  clearDocuments,
  deleteDocument,
  getSystemStatus,
  listDocuments,
  uploadPdf,
  type DocumentSummaryResponse,
  type SystemStatusResponse,
} from "./services/api";

const WORKSPACE_STORAGE_KEY = "studyiacopilot.workspace.v2";
const LEGACY_WORKSPACE_STORAGE_KEY = "studyiacopilot.workspace.v1";

type PersistedWorkspace = {
  documents: AppDocument[];
  chats: ChatSession[];
  activeChatId: string;
  activeNav: "workspace" | "documents" | "activity";
  viewerDocId: string | null;
};

function toTimestamp(value: unknown) {
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

function normalizeDocument(
  value: Partial<AppDocument> & { id?: unknown; name?: unknown },
): AppDocument | null {
  if (typeof value.id !== "string" || typeof value.name !== "string") {
    return null;
  }

  return {
    id: value.id,
    name: value.name,
    uploadedAt: toTimestamp(value.uploadedAt),
    chunkCount:
      typeof value.chunkCount === "number"
        ? value.chunkCount
        : typeof value.chunkCount === "string"
          ? Number(value.chunkCount) || 0
          : 0,
    pageCount:
      typeof value.pageCount === "number"
        ? value.pageCount
        : typeof value.pageCount === "string"
          ? Number(value.pageCount) || 0
          : 0,
    ragMode: typeof value.ragMode === "string" ? value.ragMode : "lite",
    vectorReady: Boolean(value.vectorReady),
    preview: typeof value.preview === "string" ? value.preview : "",
  };
}

function normalizeActiveDocIds(value: unknown, legacyValue?: unknown) {
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

function normalizeChat(value: unknown): ChatSession | null {
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

function mapApiDocument(document: DocumentSummaryResponse): AppDocument {
  return {
    id: document.doc_id,
    name: document.name,
    uploadedAt: toTimestamp(document.uploaded_at),
    chunkCount: document.chunks,
    pageCount: document.pages,
    ragMode: document.rag_mode,
    vectorReady: document.vector_ready,
    preview: document.preview,
  };
}

function mapSystemStatus(status: SystemStatusResponse): SystemStatus {
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

function mergeDocuments(...collections: AppDocument[][]) {
  const merged = new Map<string, AppDocument>();

  for (const collection of collections) {
    for (const document of collection) {
      const current = merged.get(document.id);
      merged.set(document.id, current ? { ...current, ...document } : document);
    }
  }

  return [...merged.values()].sort((left, right) => right.uploadedAt - left.uploadedAt);
}

function loadPersistedWorkspace(): PersistedWorkspace | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw =
      window.localStorage.getItem(WORKSPACE_STORAGE_KEY) ??
      window.localStorage.getItem(LEGACY_WORKSPACE_STORAGE_KEY);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as Partial<PersistedWorkspace> & {
      chats?: unknown[];
    };
    if (!Array.isArray(parsed.documents) || !Array.isArray(parsed.chats) || parsed.chats.length === 0) {
      return null;
    }

    const documents = parsed.documents
      .map((document) => normalizeDocument(document as Partial<AppDocument>))
      .filter((document): document is AppDocument => Boolean(document));
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
      documents,
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

export default function App() {
  const persistedWorkspace = loadPersistedWorkspace();
  const initialChatRef = useRef<ChatSession>(persistedWorkspace?.chats[0] ?? createChat());
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const [documents, setDocuments] = useState<AppDocument[]>(persistedWorkspace?.documents ?? []);
  const [chats, setChats] = useState<ChatSession[]>(
    persistedWorkspace?.chats ?? [initialChatRef.current],
  );
  const [activeChatId, setActiveChatId] = useState(
    persistedWorkspace?.activeChatId ?? initialChatRef.current.id,
  );
  const [input, setInput] = useState("");
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeNav, setActiveNav] = useState<"workspace" | "documents" | "activity">(
    persistedWorkspace?.activeNav ?? "workspace",
  );
  const [viewerDocId, setViewerDocId] = useState<string | null>(persistedWorkspace?.viewerDocId ?? null);
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);
  const [pdfOpen, setPdfOpen] = useState(false);
  const [pdfFocusToken, setPdfFocusToken] = useState(0);
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [deletingChatId, setDeletingChatId] = useState<string | null>(null);
  const [clearingChats, setClearingChats] = useState(false);
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null);
  const [clearingDocuments, setClearingDocuments] = useState(false);
  const [isDesktop, setIsDesktop] = useState(() =>
    typeof window !== "undefined" ? window.innerWidth >= 1024 : true,
  );

  const activeChat = useMemo(
    () => chats.find((chat) => chat.id === activeChatId) ?? chats[0],
    [activeChatId, chats],
  );

  const activeDocuments = useMemo(
    () =>
      (activeChat?.activeDocIds ?? [])
        .map((docId) => documents.find((document) => document.id === docId) ?? null)
        .filter((document): document is AppDocument => Boolean(document)),
    [activeChat?.activeDocIds, documents],
  );

  const viewerDocument = useMemo(
    () => documents.find((doc) => doc.id === viewerDocId) ?? null,
    [documents, viewerDocId],
  );

  useEffect(() => {
    if (!activeChat) return;
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeChat]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    const mediaQuery = window.matchMedia("(min-width: 1024px)");
    const syncLayoutMode = (event?: MediaQueryListEvent) => {
      setIsDesktop(event?.matches ?? mediaQuery.matches);
    };

    syncLayoutMode();
    mediaQuery.addEventListener("change", syncLayoutMode);

    return () => mediaQuery.removeEventListener("change", syncLayoutMode);
  }, []);

  useEffect(() => {
    const nextActiveDocIds = activeChat?.activeDocIds ?? [];

    if (nextActiveDocIds.length === 0) {
      setViewerDocId(null);
      setPdfOpen(false);
      return;
    }

    setViewerDocId((current) =>
      current && nextActiveDocIds.includes(current) ? current : nextActiveDocIds[0],
    );
  }, [activeChat?.activeDocIds]);

  useEffect(() => {
    if (typeof window === "undefined" || chats.length === 0 || !activeChat) return;

    const payload: PersistedWorkspace = {
      documents,
      chats,
      activeChatId: activeChat.id,
      activeNav,
      viewerDocId,
    };

    window.localStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify(payload));
  }, [activeChat, activeNav, chats, documents, viewerDocId]);

  useEffect(() => {
    let ignore = false;

    Promise.allSettled([listDocuments(), getSystemStatus()]).then((results) => {
      if (ignore) {
        return;
      }

      const [documentsResult, systemResult] = results;

      if (documentsResult.status === "fulfilled") {
        const remoteDocuments = documentsResult.value.documents.map(mapApiDocument);
        startTransition(() => {
          setDocuments((currentDocuments) => mergeDocuments(currentDocuments, remoteDocuments));
        });
      } else {
        console.error("Failed to load indexed documents", documentsResult.reason);
      }

      if (systemResult.status === "fulfilled") {
        setSystemStatus(mapSystemStatus(systemResult.value));
      } else {
        console.error("Failed to load system status", systemResult.reason);
      }
    });

    return () => {
      ignore = true;
    };
  }, []);

  const pdfUrl = viewerDocId ? `${API_URL}/api/pdf/${viewerDocId}` : "";

  const updateChat = (chatId: string, updater: (chat: ChatSession) => ChatSession) => {
    setChats((currentChats) =>
      currentChats.map((chat) => (chat.id === chatId ? updater(chat) : chat)),
    );
  };

  const activateChat = (chat: ChatSession, options?: { clearInput?: boolean }) => {
    setActiveChatId(chat.id);
    setViewerDocId(chat.activeDocIds[0] ?? null);
    setSelectedSource(null);
    setPdfOpen(false);

    if (options?.clearInput) {
      setInput("");
    }
  };

  const setViewerDocument = (docId: string) => {
    setViewerDocId(docId);
    setSelectedSource((currentSource) =>
      currentSource?.doc_id && currentSource.doc_id !== docId ? null : currentSource,
    );
    setPdfFocusToken((current) => current + 1);
  };

  const toggleActiveChatDocument = (docId: string) => {
    if (!activeChat) return;

    const isActive = activeChat.activeDocIds.includes(docId);
    const nextActiveDocIds = isActive
      ? activeChat.activeDocIds.filter((activeDocId) => activeDocId !== docId)
      : [...activeChat.activeDocIds, docId];

    updateChat(activeChat.id, (chat) => ({
      ...chat,
      activeDocIds: isActive
        ? chat.activeDocIds.filter((activeDocId) => activeDocId !== docId)
        : [...chat.activeDocIds, docId],
      updatedAt: Date.now(),
    }));

    if (!isActive) {
      setViewerDocId(docId);
    } else if (viewerDocId === docId) {
      setViewerDocId(nextActiveDocIds[0] ?? null);
    }

    if (isActive && nextActiveDocIds.length === 0) {
      setPdfOpen(false);
    }

    setSelectedSource(null);
  };

  const startNewChat = () => {
    const newChat = createChat();
    setChats((currentChats) => [newChat, ...currentChats]);
    activateChat(newChat, { clearInput: true });
  };

  const applyRemovedChats = (removedChatIds: string[]) => {
    if (removedChatIds.length === 0) {
      return;
    }

    const removedChats = new Set(removedChatIds);
    const remainingChats = chats.filter((chat) => !removedChats.has(chat.id));

    if (remainingChats.length === 0) {
      const replacementChat = createChat();
      setChats([replacementChat]);
      activateChat(replacementChat, { clearInput: true });
      return;
    }

    setChats(remainingChats);

    if (removedChats.has(activeChatId)) {
      activateChat(remainingChats[0], { clearInput: true });
    }
  };

  const applyRemovedDocuments = (removedDocIds: string[]) => {
    if (removedDocIds.length === 0) {
      return;
    }

    const removedDocuments = new Set(removedDocIds);
    const remainingDocuments = documents.filter((document) => !removedDocuments.has(document.id));
    const shouldCloseViewer = Boolean(viewerDocId && removedDocuments.has(viewerDocId));

    setDocuments(remainingDocuments);
    setChats((currentChats) =>
      currentChats.map((chat) =>
        chat.activeDocIds.some((docId) => removedDocuments.has(docId))
          ? {
              ...chat,
              activeDocIds: chat.activeDocIds.filter((docId) => !removedDocuments.has(docId)),
              updatedAt: Date.now(),
            }
          : chat,
      ),
    );
    setSystemStatus((currentStatus) =>
      currentStatus
        ? {
            ...currentStatus,
            documentsIndexed: remainingDocuments.length,
            workspaceDataAvailable: remainingDocuments.length > 0,
          }
        : currentStatus,
    );

    if (shouldCloseViewer) {
      const fallbackViewerDocId =
        activeChat?.activeDocIds.find((docId) => !removedDocuments.has(docId)) ?? null;

      setViewerDocId(fallbackViewerDocId);
      setSelectedSource(null);
      setPdfOpen(false);
      return;
    }

    setSelectedSource((currentSource) => {
      const sourceDocId = currentSource?.doc_id;
      return sourceDocId && removedDocuments.has(sourceDocId) ? null : currentSource;
    });
  };

  const streamAssistantResponse = async (
    chatId: string,
    messageId: string,
    fullText: string,
    sources: Source[],
  ) => {
    const step = fullText.length > 320 ? 3 : 1;
    let index = step;

    while (index < fullText.length) {
      const nextSlice = fullText.slice(0, index);

      updateChat(chatId, (chat) => ({
        ...chat,
        updatedAt: Date.now(),
        messages: chat.messages.map((message) =>
          message.id === messageId
            ? {
                ...message,
                content: nextSlice,
                sources: index >= fullText.length ? sources : [],
                streaming: index < fullText.length,
              }
            : message,
        ),
      }));

      await new Promise((resolve) => window.setTimeout(resolve, 14));
      index += step;
    }

    updateChat(chatId, (chat) => ({
      ...chat,
      updatedAt: Date.now(),
      messages: chat.messages.map((message) =>
        message.id === messageId
          ? {
              ...message,
              content: fullText,
              sources,
              streaming: false,
            }
          : message,
      ),
    }));
  };

  const handleFileUpload = async (file: File) => {
    if (!activeChat) {
      return;
    }

    const targetChatId = activeChat.id;
    setUploading(true);

    try {
      const data = await uploadPdf(file);
      const nextDocument = mapApiDocument(data);

      if (!data.doc_id) {
        updateChat(targetChatId, (chat) => ({
          ...chat,
          updatedAt: Date.now(),
          messages: [
            ...chat.messages,
            createAssistantMessage(
              "The upload finished, but no valid document id came back.",
            ),
          ],
        }));
        return;
      }

      setDocuments((currentDocuments) => {
        return mergeDocuments(currentDocuments, [nextDocument]);
      });

      updateChat(targetChatId, (chat) => ({
        ...chat,
        activeDocIds: chat.activeDocIds.includes(data.doc_id)
          ? chat.activeDocIds
          : [...chat.activeDocIds, data.doc_id],
        title: chat.title === "New conversation" ? data.name || file.name : chat.title,
        updatedAt: Date.now(),
        messages: [
          ...chat.messages,
          createAssistantMessage(
            `"${data.name || file.name}" indexed with ${data.chunks} chunks across ${data.pages} pages. ${data.vector_ready ? "Vector retrieval is ready." : "Lexical fallback is active for this document."}`,
          ),
        ],
      }));

      setSystemStatus((currentStatus) =>
        currentStatus
          ? {
              ...currentStatus,
              documentsIndexed: Math.max(currentStatus.documentsIndexed, documents.length + 1),
              workspaceDataAvailable: true,
            }
          : currentStatus,
      );
      setViewerDocId(data.doc_id);
      setSelectedSource(null);
    } catch (error) {
      console.error(error);

      updateChat(targetChatId, (chat) => ({
        ...chat,
        updatedAt: Date.now(),
        messages: [
          ...chat.messages,
          createAssistantMessage(
            error instanceof Error ? error.message : "There was an error uploading the document.",
          ),
        ],
      }));
    } finally {
      setUploading(false);
    }
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    if (files.length > 0) {
      void (async () => {
        for (const file of files) {
          await handleFileUpload(file);
        }
      })();
    }

    event.target.value = "";
  };

  const handleSelectSource = (source: Source) => {
    const targetDocId = source.doc_id || activeChat?.activeDocIds[0] || null;

    setSelectedSource({
      ...source,
      bbox: source.bbox ? [...source.bbox] : undefined,
      line_boxes: source.line_boxes?.map((box) => [...box]) ?? undefined,
    });
    setViewerDocId(targetDocId);
    setPdfFocusToken((current) => current + 1);

    if (!isDesktop) {
      setPdfOpen(true);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading || !activeChat) return;

    if (activeChat.activeDocIds.length === 0) {
      updateChat(activeChat.id, (chat) => ({
        ...chat,
        updatedAt: Date.now(),
        messages: [
          ...chat.messages,
          createAssistantMessage("Select one or more documents before asking questions."),
        ],
      }));
      return;
    }

    const question = input.trim();
    const targetChatId = activeChat.id;
    const targetDocIds = activeChat.activeDocIds;
    const placeholderId = createId();
    const history: ConversationTurn[] = activeChat.messages
      .filter((message) => !message.streaming && message.content.trim())
      .slice(-6)
      .map((message) => ({
        role: message.role,
        content: message.content,
      }));

    setInput("");
    setLoading(true);

    updateChat(targetChatId, (chat) => ({
      ...chat,
      title: chat.title === "New conversation" ? question.slice(0, 40) : chat.title,
      updatedAt: Date.now(),
      messages: [
        ...chat.messages,
        { id: createId(), role: "user", content: question },
        { id: placeholderId, role: "assistant", content: "", streaming: true, sources: [] },
      ],
    }));

    try {
      const data = await askQuestion(question, targetDocIds, history);
      await streamAssistantResponse(
        targetChatId,
        placeholderId,
        data.answer || "No response from the server.",
        data.sources || [],
      );
    } catch (error) {
      console.error(error);

      updateChat(targetChatId, (chat) => ({
        ...chat,
        updatedAt: Date.now(),
        messages: chat.messages.map((message) =>
          message.id === placeholderId
            ? { ...message, content: "There was an error fetching the answer.", streaming: false }
            : message,
        ),
      }));
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDocument = async (docId: string) => {
    const targetDocument = documents.find((document) => document.id === docId);
    if (!targetDocument) {
      return;
    }

    const shouldDelete = window.confirm(
      `Delete "${targetDocument.name}"? This removes the PDF and indexed data from the workspace.`,
    );
    if (!shouldDelete) {
      return;
    }

    setDeletingDocId(docId);

    try {
      await deleteDocument(docId);
      applyRemovedDocuments([docId]);
    } catch (error) {
      console.error(error);

      if (activeChat) {
        updateChat(activeChat.id, (chat) => ({
          ...chat,
          updatedAt: Date.now(),
          messages: [
            ...chat.messages,
            createAssistantMessage(
              error instanceof Error
                ? error.message
                : "There was an error deleting the document.",
            ),
          ],
        }));
      }
    } finally {
      setDeletingDocId(null);
    }
  };

  const handleClearDocuments = async () => {
    if (documents.length === 0) {
      return;
    }

    const shouldClear = window.confirm(
      `Delete all ${documents.length} document${documents.length === 1 ? "" : "s"}? This removes PDFs and indexed data from the workspace.`,
    );
    if (!shouldClear) {
      return;
    }

    setClearingDocuments(true);

    try {
      const response = await clearDocuments();
      const removedDocIds =
        response.removed_doc_ids.length > 0
          ? response.removed_doc_ids
          : documents.map((document) => document.id);

      applyRemovedDocuments(removedDocIds);
    } catch (error) {
      console.error(error);

      if (activeChat) {
        updateChat(activeChat.id, (chat) => ({
          ...chat,
          updatedAt: Date.now(),
          messages: [
            ...chat.messages,
            createAssistantMessage(
              error instanceof Error
                ? error.message
                : "There was an error clearing the library.",
            ),
          ],
        }));
      }
    } finally {
      setClearingDocuments(false);
    }
  };

  const handleDeleteChat = (chatId: string) => {
    const targetChat = chats.find((chat) => chat.id === chatId);
    if (!targetChat) {
      return;
    }

    const shouldDelete = window.confirm(
      `Delete "${targetChat.title}"? This removes the full conversation history from this browser.`,
    );
    if (!shouldDelete) {
      return;
    }

    setDeletingChatId(chatId);

    try {
      applyRemovedChats([chatId]);
    } finally {
      setDeletingChatId(null);
    }
  };

  const handleClearChats = () => {
    if (chats.length === 0) {
      return;
    }

    const shouldClear = window.confirm(
      `Delete all ${chats.length} conversation${chats.length === 1 ? "" : "s"}? This clears the local chat history and starts a fresh session.`,
    );
    if (!shouldClear) {
      return;
    }

    setClearingChats(true);

    try {
      applyRemovedChats(chats.map((chat) => chat.id));
    } finally {
      setClearingChats(false);
    }
  };

  if (!activeChat) return null;

  return (
    <div className="h-screen overflow-hidden bg-[var(--app-bg)] text-[var(--app-foreground)]">
      <div className="flex h-full min-h-0 flex-col lg:flex-row">
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          multiple
          onChange={handleFileChange}
          className="hidden"
          disabled={uploading}
        />

        <SidebarPanel
          activeChatId={activeChat.id}
          activeDocIds={activeChat.activeDocIds}
          activeNav={activeNav}
          chats={chats}
          clearingChats={clearingChats}
          clearingDocuments={clearingDocuments}
          deletingChatId={deletingChatId}
          deletingDocId={deletingDocId}
          documents={documents}
          uploading={uploading}
          onChangeNav={setActiveNav}
          onClearChats={handleClearChats}
          onClearDocuments={handleClearDocuments}
          onDeleteChat={handleDeleteChat}
          onDeleteDocument={handleDeleteDocument}
          onNewChat={startNewChat}
          onOpenUpload={() => fileInputRef.current?.click()}
          onSelectChat={(chatId) => {
            const nextChat = chats.find((chat) => chat.id === chatId);
            if (nextChat) {
              activateChat(nextChat);
            }
          }}
          onToggleDocument={(docId) => toggleActiveChatDocument(docId)}
        />

        <main className="flex min-h-0 flex-1 flex-col overflow-hidden bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.14),transparent_26%),radial-gradient(circle_at_top_right,rgba(16,185,129,0.12),transparent_22%)] lg:flex-row">
          <ChatWorkspace
            activeChat={activeChat}
            activeDocuments={activeDocuments}
            documentsCount={documents.length}
            input={input}
            isDesktop={isDesktop}
            loading={loading}
            systemStatus={systemStatus}
            viewerDocument={viewerDocument}
            viewerDocId={viewerDocId}
            onChangeInput={setInput}
            onOpenPdf={() => setPdfOpen(true)}
            onOpenUpload={() => fileInputRef.current?.click()}
            onSelectSource={handleSelectSource}
            onSend={handleSend}
            chatEndRef={chatEndRef}
          />

          <ViewerPanel
            activeDocuments={activeDocuments}
            focusToken={pdfFocusToken}
            pdfUrl={pdfUrl}
            selectedSource={selectedSource}
            viewerDocId={viewerDocId}
            onSelectViewerDoc={setViewerDocument}
            onClearFocus={() => {
              setSelectedSource(null);
              setPdfFocusToken((current) => current + 1);
            }}
          />
        </main>
      </div>

      <PdfModal
        activeDocuments={activeDocuments}
        open={pdfOpen && !isDesktop}
        onClose={() => setPdfOpen(false)}
        fileUrl={pdfUrl}
        highlight={selectedSource}
        focusToken={pdfFocusToken}
        viewerDocId={viewerDocId}
        onSelectViewerDoc={setViewerDocument}
      />
    </div>
  );
}
