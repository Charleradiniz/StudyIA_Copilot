import {
  startTransition,
  useEffect,
  useEffectEvent,
  useRef,
  useState,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from "react";
import { createChat } from "../app/chat-utils";
import {
  areChatCollectionsEquivalent,
  areDocumentCollectionsEquivalent,
  getWorkspaceStorageKey,
  hasStreamingChatMessages,
  loadPersistedWorkspace,
  mapApiChat,
  mapApiDocument,
  mapDeletedChat,
  mapSystemStatus,
  mergeChatCollections,
  mergeDocuments,
  pruneChatsForAvailableDocuments,
  resolveAvailableChatId,
  resolveViewerDocumentId,
  serializeChatForApi,
} from "../app/workspace-utils";
import type {
  AppDocument,
  ChatSession,
  Source,
  SystemStatus,
  WorkspaceNav,
} from "../app/types";
import { getSystemStatus, listChats, listDocuments, syncChats } from "../services/api";

const REMOTE_CHAT_REFRESH_INTERVAL_MS = 12_000;

type StateSetter<T> = Dispatch<SetStateAction<T>>;

type UseWorkspaceSyncOptions = {
  userId: string | null;
  isAuthenticated: boolean;
  uploading: boolean;
  chats: ChatSession[];
  documents: AppDocument[];
  activeChatId: string;
  activeNav: WorkspaceNav;
  viewerDocId: string | null;
  setChats: StateSetter<ChatSession[]>;
  setDocuments: StateSetter<AppDocument[]>;
  setActiveChatId: StateSetter<string>;
  setActiveNav: StateSetter<WorkspaceNav>;
  setViewerDocId: StateSetter<string | null>;
  setSelectedSource: StateSetter<Source | null>;
  setPdfOpen: StateSetter<boolean>;
  setSystemStatus: StateSetter<SystemStatus | null>;
  handleUnauthorized: (error: unknown) => boolean;
};

type UseWorkspaceSyncResult = {
  workspaceReady: boolean;
  chatsRef: MutableRefObject<ChatSession[]>;
  documentsRef: MutableRefObject<AppDocument[]>;
};

export function useWorkspaceSync({
  userId,
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
}: UseWorkspaceSyncOptions): UseWorkspaceSyncResult {
  const chatsRef = useRef<ChatSession[]>([]);
  const documentsRef = useRef<AppDocument[]>([]);
  const activeChatIdRef = useRef("");
  const viewerDocIdRef = useRef<string | null>(null);
  const documentsLoadedRef = useRef(false);
  const remoteRefreshInFlightRef = useRef(false);
  const remoteWorkspaceRefreshInFlightRef = useRef(false);

  const [workspaceReady, setWorkspaceReady] = useState(false);

  useEffect(() => {
    chatsRef.current = chats;
  }, [chats]);

  useEffect(() => {
    documentsRef.current = documents;
  }, [documents]);

  useEffect(() => {
    activeChatIdRef.current = activeChatId;
  }, [activeChatId]);

  useEffect(() => {
    viewerDocIdRef.current = viewerDocId;
  }, [viewerDocId]);

  useEffect(() => {
    if (userId) {
      return;
    }

    documentsLoadedRef.current = false;
    remoteRefreshInFlightRef.current = false;
    remoteWorkspaceRefreshInFlightRef.current = false;
    setWorkspaceReady(false);
  }, [userId]);

  const applyRemoteChatSnapshot = useEffectEvent(
    (
      remoteChats: ChatSession[],
      deletedChats: { id: string; deletedAt: number }[],
      options?: {
        preferredActiveChatId?: string | null;
        fallbackActiveChatId?: string | null;
        resetWorkspaceUi?: boolean;
      },
    ) => {
      const currentChats = chatsRef.current;
      const mergedChats = mergeChatCollections(remoteChats, currentChats, deletedChats);
      const hydratedChats = documentsLoadedRef.current
        ? pruneChatsForAvailableDocuments(mergedChats, documentsRef.current)
        : mergedChats;
      const nextChats = hydratedChats.length > 0 ? hydratedChats : [createChat()];
      const nextActiveChatId = resolveAvailableChatId(
        nextChats,
        options?.preferredActiveChatId,
        activeChatIdRef.current,
        options?.fallbackActiveChatId,
      );
      const chatsChanged = !areChatCollectionsEquivalent(nextChats, currentChats);
      const activeChatChanged = nextActiveChatId !== activeChatIdRef.current;
      const shouldResetWorkspaceUi = Boolean(options?.resetWorkspaceUi || activeChatChanged);

      if (!chatsChanged && !activeChatChanged && !shouldResetWorkspaceUi) {
        return;
      }

      startTransition(() => {
        if (chatsChanged) {
          setChats(nextChats);
        }

        if (activeChatChanged) {
          setActiveChatId(nextActiveChatId);
        }

        if (shouldResetWorkspaceUi) {
          setSelectedSource(null);
          setPdfOpen(false);
        }
      });
    },
  );

  const refreshRemoteChats = useEffectEvent(async () => {
    if (
      remoteRefreshInFlightRef.current ||
      !userId ||
      !workspaceReady ||
      hasStreamingChatMessages(chatsRef.current)
    ) {
      return;
    }

    remoteRefreshInFlightRef.current = true;

    try {
      const response = await listChats();
      const remoteChats = response.chats
        .map((chat) => mapApiChat(chat))
        .filter((chat): chat is ChatSession => Boolean(chat));
      const deletedChats = response.deleted.map(mapDeletedChat);

      applyRemoteChatSnapshot(remoteChats, deletedChats);
    } catch (error) {
      console.error("Failed to refresh remote chat history", error);
      handleUnauthorized(error);
    } finally {
      remoteRefreshInFlightRef.current = false;
    }
  });

  const applyRemoteDocumentsSnapshot = useEffectEvent(
    (remoteDocuments: AppDocument[], nextStatus?: SystemStatus | null) => {
      documentsLoadedRef.current = true;

      const nextDocuments = mergeDocuments(remoteDocuments);
      const currentDocuments = documentsRef.current;
      const currentChats = chatsRef.current;
      const prunedChats = pruneChatsForAvailableDocuments(currentChats, nextDocuments);
      const nextActiveChatId = resolveAvailableChatId(
        prunedChats,
        activeChatIdRef.current,
        prunedChats[0]?.id,
      );
      const nextViewerDocId = resolveViewerDocumentId(
        prunedChats,
        nextActiveChatId,
        viewerDocIdRef.current,
      );
      const documentsChanged = !areDocumentCollectionsEquivalent(nextDocuments, currentDocuments);
      const chatsChanged = !areChatCollectionsEquivalent(prunedChats, currentChats);
      const activeChatChanged = nextActiveChatId !== activeChatIdRef.current;
      const viewerChanged = nextViewerDocId !== viewerDocIdRef.current;

      if (
        !documentsChanged &&
        !chatsChanged &&
        !activeChatChanged &&
        !viewerChanged &&
        nextStatus === undefined
      ) {
        return;
      }

      startTransition(() => {
        if (documentsChanged) {
          setDocuments(nextDocuments);
        }

        if (chatsChanged) {
          setChats(prunedChats);
        }

        if (activeChatChanged) {
          setActiveChatId(nextActiveChatId);
        }

        if (viewerChanged) {
          setViewerDocId(nextViewerDocId);
        }

        if (documentsChanged || chatsChanged || viewerChanged) {
          setSelectedSource(null);
          if (!nextViewerDocId) {
            setPdfOpen(false);
          }
        }

        if (nextStatus !== undefined) {
          setSystemStatus(nextStatus ?? null);
        }
      });
    },
  );

  const refreshRemoteWorkspaceData = useEffectEvent(async () => {
    if (
      remoteWorkspaceRefreshInFlightRef.current ||
      !userId ||
      !workspaceReady ||
      uploading
    ) {
      return;
    }

    remoteWorkspaceRefreshInFlightRef.current = true;

    try {
      const [documentsResponse, statusResponse] = await Promise.all([
        listDocuments(),
        getSystemStatus(),
      ]);
      const remoteDocuments = documentsResponse.documents.map(mapApiDocument);

      applyRemoteDocumentsSnapshot(remoteDocuments, mapSystemStatus(statusResponse));
    } catch (error) {
      console.error("Failed to refresh remote workspace data", error);
      handleUnauthorized(error);
    } finally {
      remoteWorkspaceRefreshInFlightRef.current = false;
    }
  });

  useEffect(() => {
    if (!userId) {
      setWorkspaceReady(false);
      return;
    }

    let ignore = false;
    const persistedWorkspace = loadPersistedWorkspace(userId);
    setWorkspaceReady(false);

    listChats()
      .then((response) => {
        if (ignore) {
          return;
        }

        const remoteChats = response.chats
          .map((chat) => mapApiChat(chat))
          .filter((chat): chat is ChatSession => Boolean(chat));
        const deletedChats = response.deleted.map(mapDeletedChat);
        const fallbackChats = persistedWorkspace?.chats ?? [createChat()];
        const mergedChats = mergeChatCollections(remoteChats, fallbackChats, deletedChats);
        const nextChats = mergedChats.length > 0 ? mergedChats : [createChat()];
        const nextActiveChatId = resolveAvailableChatId(
          nextChats,
          persistedWorkspace?.activeChatId,
          nextChats[0]?.id,
        );

        startTransition(() => {
          setChats(nextChats);
          setActiveChatId(nextActiveChatId);
          setActiveNav(persistedWorkspace?.activeNav ?? "workspace");
          setViewerDocId(persistedWorkspace?.viewerDocId ?? null);
          setSelectedSource(null);
          setPdfOpen(false);
          setWorkspaceReady(true);
        });
      })
      .catch((error) => {
        if (ignore) {
          return;
        }

        if (handleUnauthorized(error)) {
          return;
        }

        console.error("Failed to restore chat history", error);

        const fallbackChats = persistedWorkspace?.chats ?? [createChat()];
        const nextChats = fallbackChats.length > 0 ? fallbackChats : [createChat()];
        const nextActiveChatId = resolveAvailableChatId(
          nextChats,
          persistedWorkspace?.activeChatId,
          nextChats[0]?.id,
        );

        startTransition(() => {
          setChats(nextChats);
          setActiveChatId(nextActiveChatId);
          setActiveNav(persistedWorkspace?.activeNav ?? "workspace");
          setViewerDocId(persistedWorkspace?.viewerDocId ?? null);
          setSelectedSource(null);
          setPdfOpen(false);
          setWorkspaceReady(true);
        });
      });

    return () => {
      ignore = true;
    };
  }, [
    handleUnauthorized,
    setActiveChatId,
    setActiveNav,
    setChats,
    setPdfOpen,
    setSelectedSource,
    setViewerDocId,
    userId,
  ]);

  useEffect(() => {
    if (!userId) {
      return;
    }

    let ignore = false;

    Promise.allSettled([listDocuments(), getSystemStatus()]).then((results) => {
      if (ignore) {
        return;
      }

      const [documentsResult, systemResult] = results;
      const nextSystemStatus =
        systemResult.status === "fulfilled"
          ? mapSystemStatus(systemResult.value)
          : null;

      if (documentsResult.status === "fulfilled") {
        applyRemoteDocumentsSnapshot(
          documentsResult.value.documents.map(mapApiDocument),
          nextSystemStatus,
        );
        return;
      }

      console.error("Failed to restore remote documents", documentsResult.reason);
      if (handleUnauthorized(documentsResult.reason)) {
        return;
      }

      if (systemResult.status === "rejected") {
        console.error("Failed to restore system status", systemResult.reason);
        handleUnauthorized(systemResult.reason);
      } else {
        setSystemStatus(nextSystemStatus);
      }
    });

    return () => {
      ignore = true;
    };
  }, [handleUnauthorized, setSystemStatus, userId]);

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      !userId ||
      chats.length === 0
    ) {
      return;
    }

    const activeChat = chats.find((chat) => chat.id === activeChatId) ?? chats[0] ?? null;
    if (!activeChat) {
      return;
    }

    const payload = {
      chats,
      activeChatId,
      activeNav,
      viewerDocId,
    };

    window.localStorage.setItem(getWorkspaceStorageKey(userId), JSON.stringify(payload));
  }, [activeChatId, activeNav, chats, userId, viewerDocId]);

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      !workspaceReady ||
      !userId ||
      chats.length === 0 ||
      hasStreamingChatMessages(chats)
    ) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void syncChats(chats.map((chat) => serializeChatForApi(chat))).catch((error) => {
        console.error("Failed to sync chat history", error);
        handleUnauthorized(error);
      });
    }, 700);

    return () => window.clearTimeout(timeoutId);
  }, [chats, handleUnauthorized, userId, workspaceReady]);

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      !isAuthenticated ||
      !workspaceReady
    ) {
      return;
    }

    const refreshIfVisible = () => {
      if (document.visibilityState === "visible") {
        void refreshRemoteChats();
        void refreshRemoteWorkspaceData();
      }
    };

    const intervalId = window.setInterval(() => {
      void refreshRemoteChats();
      void refreshRemoteWorkspaceData();
    }, REMOTE_CHAT_REFRESH_INTERVAL_MS);

    window.addEventListener("focus", refreshIfVisible);
    document.addEventListener("visibilitychange", refreshIfVisible);

    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("focus", refreshIfVisible);
      document.removeEventListener("visibilitychange", refreshIfVisible);
    };
  }, [isAuthenticated, workspaceReady]);

  return {
    workspaceReady,
    chatsRef,
    documentsRef,
  };
}
