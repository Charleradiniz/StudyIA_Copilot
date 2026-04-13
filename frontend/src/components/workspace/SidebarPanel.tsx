import { formatRelativeTime, getChatPreview } from "../../app/chat-utils";
import type { AppDocument, ChatSession } from "../../app/types";

type Props = {
  activeChatId: string;
  activeDocIds: string[];
  activeNav: "workspace" | "documents" | "activity";
  chats: ChatSession[];
  documents: AppDocument[];
  clearingChats: boolean;
  clearingDocuments: boolean;
  deletingChatId: string | null;
  deletingDocId: string | null;
  isDesktop: boolean;
  mobileOpen: boolean;
  uploading: boolean;
  userEmail: string;
  userName: string;
  onChangeNav: (nav: "workspace" | "documents" | "activity") => void;
  onClearChats: () => void;
  onClearDocuments: () => void;
  onCloseMobile: () => void;
  onDeleteChat: (chatId: string) => void;
  onDeleteDocument: (docId: string) => void;
  onLogout: () => void;
  onNewChat: () => void;
  onOpenUpload: () => void;
  onSelectChat: (chatId: string) => void;
  onToggleDocument: (docId: string) => void;
};

export default function SidebarPanel({
  activeChatId,
  activeDocIds,
  activeNav,
  chats,
  clearingChats,
  clearingDocuments,
  deletingChatId,
  deletingDocId,
  documents,
  isDesktop,
  mobileOpen,
  uploading,
  userEmail,
  userName,
  onChangeNav,
  onClearChats,
  onClearDocuments,
  onCloseMobile,
  onDeleteChat,
  onDeleteDocument,
  onLogout,
  onNewChat,
  onOpenUpload,
  onSelectChat,
  onToggleDocument,
}: Props) {
  const hasMeaningfulHistory = (chat: ChatSession) =>
    chat.messages.some((message) => message.role === "user");
  const getChatDocumentSummary = (chat: ChatSession) => {
    const linkedDocuments = documents.filter((doc) => chat.activeDocIds.includes(doc.id));

    if (linkedDocuments.length === 0) {
      return "No document linked";
    }

    if (linkedDocuments.length === 1) {
      return linkedDocuments[0].name;
    }

    return `${linkedDocuments.length} documents linked`;
  };

  const canManageChats = chats.length > 1 || chats.some(hasMeaningfulHistory);
  const showDocuments = activeNav === "workspace" || activeNav === "documents";
  const showChats = activeNav === "workspace" || activeNav === "activity";
  const closeMobilePanel = () => {
    if (!isDesktop) {
      onCloseMobile();
    }
  };

  return (
    <>
      <button
        type="button"
        aria-label="Close workspace panel"
        aria-hidden={!mobileOpen}
        tabIndex={mobileOpen ? 0 : -1}
        onClick={onCloseMobile}
        className={`fixed inset-0 z-40 bg-slate-950/70 transition duration-300 lg:hidden ${
          mobileOpen ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <aside
        aria-label="Workspace panel"
        aria-hidden={!isDesktop && !mobileOpen}
        className={`fixed inset-y-0 left-0 z-50 flex h-[100dvh] w-[min(92vw,380px)] max-w-[380px] shrink-0 flex-col border-r border-white/10 bg-[var(--panel-strong)]/95 pb-[env(safe-area-inset-bottom)] pt-[env(safe-area-inset-top)] backdrop-blur transition-transform duration-300 lg:static lg:z-auto lg:h-full lg:w-[300px] lg:max-w-none lg:translate-x-0 lg:border-b-0 xl:w-[320px] ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-full min-h-0 flex-col">
          <div className="border-b border-white/10 px-5 py-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.24em] text-[var(--muted-foreground)]">
                  Study Copilot
                </p>
                <h1 className="mt-2 text-2xl font-semibold tracking-tight text-white">
                  Research workspace
                </h1>
                <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                  {userName} - {userEmail}
                </p>
              </div>

              <div className="flex flex-col items-end gap-2">
                {!isDesktop && (
                  <button
                    type="button"
                    onClick={onCloseMobile}
                    className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-medium text-[var(--muted-foreground)] transition hover:border-white/20 hover:bg-white/10 hover:text-white"
                  >
                    Close
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    onNewChat();
                    closeMobilePanel();
                  }}
                  className="inline-flex items-center rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium text-white transition hover:border-white/20 hover:bg-white/10"
                >
                  New chat
                </button>
                <button
                  type="button"
                  onClick={() => {
                    onLogout();
                    closeMobilePanel();
                  }}
                  className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[11px] font-medium text-[var(--muted-foreground)] transition hover:border-white/20 hover:bg-white/10 hover:text-white"
                >
                  Log out
                </button>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-3 gap-2 rounded-2xl border border-white/10 bg-black/10 p-1">
              {[
                ["workspace", "Workspace"],
                ["documents", "Documents"],
                ["activity", "Activity"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => onChangeNav(value as Props["activeNav"])}
                  className={`rounded-xl px-3 py-2 text-sm transition ${
                    activeNav === value
                      ? "bg-white text-[var(--panel-strong)] shadow-sm"
                      : "text-[var(--muted-foreground)] hover:bg-white/5 hover:text-white"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() => {
                onOpenUpload();
                closeMobilePanel();
              }}
              disabled={uploading}
              className="mt-5 flex w-full items-center justify-between rounded-2xl border border-[var(--accent-soft)] bg-[var(--accent-surface)] px-4 py-3 text-left text-sm font-medium text-white transition hover:border-[var(--accent)] hover:bg-[var(--accent-soft)] disabled:cursor-not-allowed disabled:opacity-70"
            >
              <span>{uploading ? "Uploading document..." : "Upload a new PDF"}</span>
              <span className="rounded-full bg-white/10 px-2 py-1 text-xs text-[var(--muted-foreground)]">
                PDF
              </span>
            </button>
          </div>

          <div className="flex-1 space-y-6 overflow-y-auto px-4 py-5">
            {showDocuments && (
              <section className="rounded-3xl border border-white/10 bg-[var(--panel)] p-4 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.8)]">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-white">Document library</h2>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {documents.length} document{documents.length === 1 ? "" : "s"} indexed,{" "}
                    {activeDocIds.length} active in this chat
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  {uploading && (
                    <div className="h-2 w-16 overflow-hidden rounded-full bg-white/10">
                      <div className="h-full w-1/2 animate-pulse rounded-full bg-[var(--accent)]" />
                    </div>
                  )}
                  {documents.length > 0 && (
                    <button
                      type="button"
                      onClick={onClearDocuments}
                      disabled={uploading || clearingDocuments || Boolean(deletingDocId)}
                      className="rounded-full border border-rose-400/20 bg-rose-400/10 px-3 py-1.5 text-[11px] font-medium text-rose-100 transition hover:border-rose-300/40 hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {clearingDocuments ? "Clearing..." : "Clear all"}
                    </button>
                  )}
                </div>
              </div>

              <div className="space-y-2">
                {documents.length === 0 ? (
                  <div className="rounded-2xl border border-dashed border-white/10 px-4 py-6 text-center text-sm text-[var(--muted-foreground)]">
                    Upload your first PDF to build the workspace.
                  </div>
                ) : (
                  documents.map((document) => {
                    const isActive = activeDocIds.includes(document.id);
                    const isDeleting = deletingDocId === document.id;

                    return (
                      <div
                        key={document.id}
                        className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                          isActive
                            ? "border-[var(--accent)] bg-[var(--accent-surface)]"
                            : "border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.06]"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <button
                            type="button"
                            onClick={() => {
                              onToggleDocument(document.id);
                              closeMobilePanel();
                            }}
                            aria-pressed={isActive}
                            className="min-w-0 flex-1 text-left"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <div className="min-w-0">
                                <p className="truncate text-sm font-medium text-white">
                                  {document.name}
                                </p>
                                <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                                  Added {formatRelativeTime(document.uploadedAt)}. Click to{" "}
                                  {isActive ? "remove from" : "include in"} active answers.
                                </p>
                              </div>
                              {isActive && (
                                <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] font-medium text-white">
                                  Included
                                </span>
                              )}
                            </div>

                            <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                              <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[var(--muted-foreground)]">
                                {document.pageCount} pages
                              </span>
                              <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[var(--muted-foreground)]">
                                {document.chunkCount} chunks
                              </span>
                              {!document.pdfAvailable && (
                                <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-2 py-1 text-amber-100">
                                  pdf unavailable
                                </span>
                              )}
                              <span
                                className={`rounded-full px-2 py-1 ${
                                  document.vectorReady
                                    ? "border border-emerald-400/30 bg-emerald-400/10 text-emerald-100"
                                    : "border border-amber-300/20 bg-amber-300/10 text-amber-100"
                                }`}
                              >
                                {document.vectorReady ? "vector ready" : "lexical fallback"}
                              </span>
                            </div>

                            {document.preview && (
                              <p className="mt-3 line-clamp-2 text-xs leading-5 text-[var(--muted-foreground)]">
                                {document.preview}
                              </p>
                            )}
                          </button>

                          <button
                            type="button"
                            onClick={() => onDeleteDocument(document.id)}
                            disabled={uploading || clearingDocuments || isDeleting}
                            aria-label={`Delete ${document.name}`}
                            className="shrink-0 rounded-full border border-rose-400/20 bg-rose-400/10 px-3 py-1.5 text-[11px] font-medium text-rose-100 transition hover:border-rose-300/40 hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {isDeleting ? "Deleting..." : "Delete"}
                          </button>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
              </section>
            )}

          {showChats && (
            <section className="rounded-3xl border border-white/10 bg-[var(--panel)] p-4">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-white">Chat history</h2>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Recent conversations stay one tap away
                  </p>
                </div>

                {canManageChats && (
                  <button
                    type="button"
                    onClick={onClearChats}
                    disabled={clearingChats || Boolean(deletingChatId)}
                    className="rounded-full border border-rose-400/20 bg-rose-400/10 px-3 py-1.5 text-[11px] font-medium text-rose-100 transition hover:border-rose-300/40 hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {clearingChats ? "Clearing..." : "Clear chats"}
                  </button>
                )}
              </div>

              <div className="space-y-2">
                {chats.map((chat) => {
                  const isCurrent = chat.id === activeChatId;
                  const isDeleting = deletingChatId === chat.id;
                  const canDeleteChat = chats.length > 1 || hasMeaningfulHistory(chat);

                  return (
                    <div
                      key={chat.id}
                      className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                        isCurrent
                          ? "border-white/20 bg-white/[0.07]"
                          : "border-white/10 bg-transparent hover:border-white/15 hover:bg-white/[0.04]"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <button
                          type="button"
                          onClick={() => {
                            onSelectChat(chat.id);
                            closeMobilePanel();
                          }}
                          className="min-w-0 flex-1 text-left"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-white">
                                {chat.title}
                              </p>
                              <p className="mt-1 line-clamp-2 text-xs text-[var(--muted-foreground)]">
                                {getChatPreview(chat.messages)}
                              </p>
                            </div>
                            <span className="shrink-0 text-[11px] text-[var(--muted-foreground)]">
                              {formatRelativeTime(chat.updatedAt)}
                            </span>
                          </div>

                          <div className="mt-3 flex items-center justify-between text-[11px] text-[var(--muted-foreground)]">
                            <span>{chat.messages.length} messages</span>
                            <span>{getChatDocumentSummary(chat)}</span>
                          </div>
                        </button>

                        {canDeleteChat && (
                          <button
                            type="button"
                            onClick={() => onDeleteChat(chat.id)}
                            disabled={clearingChats || isDeleting}
                            aria-label={`Delete chat ${chat.title}`}
                            className="shrink-0 rounded-full border border-rose-400/20 bg-rose-400/10 px-3 py-1.5 text-[11px] font-medium text-rose-100 transition hover:border-rose-300/40 hover:bg-rose-400/15 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {isDeleting ? "Deleting..." : "Delete"}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}
          </div>
        </div>
      </aside>
    </>
  );
}
