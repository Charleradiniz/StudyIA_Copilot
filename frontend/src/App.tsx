import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
} from "react";
import { buildAssistantStreamPlan } from "./app/assistant-stream";
import { createAssistantMessage, createChat, createId } from "./app/chat-utils";
import {
  clearPersistedWorkspace,
  mergeDocuments,
  sortChats,
} from "./app/workspace-utils";
import type {
  AppDocument,
  ChatSession,
  ConversationTurn,
  Source,
  SystemStatus,
  WorkspaceNav,
} from "./app/types";
import AuthScreen from "./components/auth/AuthScreen";
import PdfModal from "./components/PdfModal";
import ChatWorkspace from "./components/workspace/ChatWorkspace";
import SidebarPanel from "./components/workspace/SidebarPanel";
import ViewerPanel from "./components/workspace/ViewerPanel";
import { useAuthSession } from "./hooks/useAuthSession";
import { useWorkspaceSync } from "./hooks/useWorkspaceSync";
import {
  askQuestion,
  buildPdfRequest,
  clearChatHistory,
  clearDocuments,
  deleteChatHistory,
  deleteDocument,
  uploadPdf,
} from "./services/api";

function mapUploadedDocument(document: Awaited<ReturnType<typeof uploadPdf>>): AppDocument {
  return {
    id: document.doc_id,
    name: document.name,
    uploadedAt: Date.parse(document.uploaded_at || new Date().toISOString()),
    chunkCount: document.chunks,
    pageCount: document.pages,
    ragMode: document.rag_mode,
    vectorReady: document.vector_ready,
    preview: document.preview,
    pdfAvailable: document.pdf_available ?? true,
  };
}

export default function App() {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const [documents, setDocuments] = useState<AppDocument[]>([]);
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [activeChatId, setActiveChatId] = useState("");
  const [input, setInput] = useState("");
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeNav, setActiveNav] = useState<WorkspaceNav>("workspace");
  const [viewerDocId, setViewerDocId] = useState<string | null>(null);
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
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const resetWorkspaceState = useCallback((signedOutUserId: string | null) => {
    clearPersistedWorkspace(signedOutUserId);
    setDocuments([]);
    setChats([]);
    setActiveChatId("");
    setActiveNav("workspace");
    setViewerDocId(null);
    setSelectedSource(null);
    setPdfOpen(false);
    setSystemStatus(null);
    setInput("");
    setLoading(false);
    setUploading(false);
    setDeletingChatId(null);
    setClearingChats(false);
    setDeletingDocId(null);
    setClearingDocuments(false);
    setMobileSidebarOpen(false);
  }, []);

  const {
    authLoading,
    authSubmitting,
    currentUser,
    isAuthenticated,
    passwordResetToken,
    clearPasswordResetToken,
    handleAuthSubmit,
    handlePasswordResetRequest,
    handlePasswordResetConfirm,
    handleLogout,
    handleUnauthorized,
  } = useAuthSession({
    onSignedOut: resetWorkspaceState,
  });

  const {
    workspaceReady,
    chatsRef,
    documentsRef,
  } = useWorkspaceSync({
    userId: currentUser?.id ?? null,
    isAuthenticated,
    uploading,
    chats,
    documents,
    activeChatId,
    activeNav,
    viewerDocId,
    setChats,
    setDocuments,
    setActiveChatId,
    setActiveNav,
    setViewerDocId,
    setSelectedSource,
    setPdfOpen,
    setSystemStatus,
    handleUnauthorized,
  });

  const activeChat = useMemo(
    () => chats.find((chat) => chat.id === activeChatId) ?? chats[0] ?? null,
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
    const mediaQuery = window.matchMedia("(min-width: 1024px)");
    const syncLayoutMode = () => {
      const nextIsDesktop = mediaQuery.matches;
      setIsDesktop(nextIsDesktop);
      if (nextIsDesktop) {
        setMobileSidebarOpen(false);
      }
    };

    syncLayoutMode();
    mediaQuery.addEventListener("change", syncLayoutMode);

    return () => mediaQuery.removeEventListener("change", syncLayoutMode);
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({
      behavior: loading ? "auto" : "smooth",
      block: "end",
    });
  }, [activeChat?.messages, loading]);

  const pdfRequest = useMemo(
    () =>
      viewerDocId && viewerDocument?.pdfAvailable
        ? buildPdfRequest(viewerDocId)
        : null,
    [viewerDocId, viewerDocument?.pdfAvailable],
  );

  const setViewerDocument = useCallback((docId: string) => {
    setViewerDocId(docId);
    setSelectedSource(null);
    setPdfFocusToken((current) => current + 1);
  }, []);

  const updateChat = useCallback(
    (chatId: string, updater: (chat: ChatSession) => ChatSession) => {
      setChats((currentChats) =>
        sortChats(
          currentChats.map((chat) => (chat.id === chatId ? updater(chat) : chat)),
        ),
      );
    },
    [],
  );

  const activateChat = useCallback(
    (chat: ChatSession, options?: { clearInput?: boolean }) => {
      const nextViewerDocId =
        viewerDocId && chat.activeDocIds.includes(viewerDocId)
          ? viewerDocId
          : chat.activeDocIds[0] ?? null;

      setActiveChatId(chat.id);
      setViewerDocId(nextViewerDocId);
      setSelectedSource(null);
      setPdfOpen(false);

      if (options?.clearInput) {
        setInput("");
      }

      if (!isDesktop) {
        setMobileSidebarOpen(false);
      }
    },
    [isDesktop, viewerDocId],
  );

  const toggleActiveChatDocument = (docId: string) => {
    if (!activeChat) {
      return;
    }

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
    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const streamPlan = buildAssistantStreamPlan(fullText, {
      prefersReducedMotion,
    });

    if (streamPlan.immediate) {
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
      return;
    }

    let index = streamPlan.charsPerUpdate;

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

      await new Promise((resolve) => window.setTimeout(resolve, streamPlan.intervalMs));
      index += streamPlan.charsPerUpdate;
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
      const nextDocument = mapUploadedDocument(data);

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

      const nextDocuments = mergeDocuments(documentsRef.current, [nextDocument]);
      setDocuments(nextDocuments);

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
              documentsIndexed: Math.max(currentStatus.documentsIndexed, nextDocuments.length),
              workspaceDataAvailable: true,
            }
          : currentStatus,
      );
      setViewerDocId(data.doc_id);
      setSelectedSource(null);
    } catch (error) {
      console.error(error);
      if (handleUnauthorized(error)) {
        return;
      }

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
    if (!input.trim() || loading || !activeChat) {
      return;
    }

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
      if (handleUnauthorized(error)) {
        return;
      }

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
      if (handleUnauthorized(error)) {
        return;
      }

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
      if (handleUnauthorized(error)) {
        return;
      }

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

  const handleDeleteChat = async (chatId: string) => {
    const targetChat = chats.find((chat) => chat.id === chatId);
    if (!targetChat) {
      return;
    }

    const shouldDelete = window.confirm(
      `Delete "${targetChat.title}"? This removes the full conversation history from every signed-in device.`,
    );
    if (!shouldDelete) {
      return;
    }

    setDeletingChatId(chatId);

    try {
      await deleteChatHistory(chatId);
      applyRemovedChats([chatId]);
    } catch (error) {
      console.error(error);
      if (handleUnauthorized(error)) {
        return;
      }

      if (activeChat) {
        updateChat(activeChat.id, (chat) => ({
          ...chat,
          updatedAt: Date.now(),
          messages: [
            ...chat.messages,
            createAssistantMessage(
              error instanceof Error
                ? error.message
                : "There was an error deleting the conversation.",
            ),
          ],
        }));
      }
    } finally {
      setDeletingChatId(null);
    }
  };

  const handleClearChats = async () => {
    if (chats.length === 0) {
      return;
    }

    const shouldClear = window.confirm(
      `Delete all ${chats.length} conversation${chats.length === 1 ? "" : "s"}? This clears the shared chat history on every signed-in device.`,
    );
    if (!shouldClear) {
      return;
    }

    setClearingChats(true);

    try {
      await clearChatHistory();
      applyRemovedChats(chats.map((chat) => chat.id));
    } catch (error) {
      console.error(error);
      if (handleUnauthorized(error)) {
        return;
      }

      if (activeChat) {
        updateChat(activeChat.id, (chat) => ({
          ...chat,
          updatedAt: Date.now(),
          messages: [
            ...chat.messages,
            createAssistantMessage(
              error instanceof Error
                ? error.message
                : "There was an error clearing the shared conversations.",
            ),
          ],
        }));
      }
    } finally {
      setClearingChats(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--app-bg)] px-6 text-white">
        <div className="rounded-[28px] border border-white/10 bg-[var(--panel)] px-6 py-5 text-sm text-[var(--muted-foreground)] shadow-[0_24px_80px_-48px_rgba(15,23,42,0.8)]">
          Restoring your private workspace...
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <AuthScreen
        loading={authSubmitting}
        passwordResetToken={passwordResetToken}
        onSubmit={handleAuthSubmit}
        onRequestPasswordReset={handlePasswordResetRequest}
        onConfirmPasswordReset={handlePasswordResetConfirm}
        onClearPasswordResetToken={clearPasswordResetToken}
      />
    );
  }

  if (!workspaceReady || !activeChat || !currentUser) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--app-bg)] px-6 text-white">
        <div className="rounded-[28px] border border-white/10 bg-[var(--panel)] px-6 py-5 text-sm text-[var(--muted-foreground)] shadow-[0_24px_80px_-48px_rgba(15,23,42,0.8)]">
          Loading your private workspace...
        </div>
      </div>
    );
  }

  return (
    <div className="h-[100dvh] min-h-[100dvh] overflow-hidden bg-[var(--app-bg)] text-[var(--app-foreground)]">
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
          isDesktop={isDesktop}
          mobileOpen={mobileSidebarOpen}
          uploading={uploading}
          userName={currentUser.fullName}
          userEmail={currentUser.email}
          onChangeNav={setActiveNav}
          onClearChats={handleClearChats}
          onClearDocuments={handleClearDocuments}
          onCloseMobile={() => setMobileSidebarOpen(false)}
          onOpenMobile={() => setMobileSidebarOpen(true)}
          onDeleteChat={handleDeleteChat}
          onDeleteDocument={handleDeleteDocument}
          onLogout={handleLogout}
          onNewChat={startNewChat}
          onOpenUpload={() => fileInputRef.current?.click()}
          onSelectChat={(chatId) => {
            const nextChat = chatsRef.current.find((chat) => chat.id === chatId);
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
            onOpenSidebar={() => setMobileSidebarOpen(true)}
            onOpenUpload={() => fileInputRef.current?.click()}
            onSelectSource={handleSelectSource}
            onSend={handleSend}
            chatEndRef={chatEndRef}
          />

          <ViewerPanel
            activeDocuments={activeDocuments}
            focusToken={pdfFocusToken}
            pdfRequest={pdfRequest}
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
        fileRequest={pdfRequest}
        highlight={selectedSource}
        focusToken={pdfFocusToken}
        viewerDocId={viewerDocId}
        onSelectViewerDoc={setViewerDocument}
      />
    </div>
  );
}
