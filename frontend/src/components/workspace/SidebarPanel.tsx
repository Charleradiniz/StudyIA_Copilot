import { formatRelativeTime, getChatPreview } from "../../app/chat-utils";
import type { AppDocument, ChatSession, SystemStatus } from "../../app/types";

type Props = {
  activeChatId: string;
  activeDocId: string | null;
  activeNav: "workspace" | "documents" | "activity";
  chats: ChatSession[];
  documents: AppDocument[];
  systemStatus: SystemStatus | null;
  clearingDocuments: boolean;
  deletingDocId: string | null;
  uploading: boolean;
  onChangeNav: (nav: "workspace" | "documents" | "activity") => void;
  onClearDocuments: () => void;
  onDeleteDocument: (docId: string) => void;
  onNewChat: () => void;
  onOpenUpload: () => void;
  onSelectChat: (chatId: string) => void;
  onSelectDocument: (docId: string) => void;
};

export default function SidebarPanel({
  activeChatId,
  activeDocId,
  activeNav,
  chats,
  clearingDocuments,
  deletingDocId,
  documents,
  systemStatus,
  uploading,
  onChangeNav,
  onClearDocuments,
  onDeleteDocument,
  onNewChat,
  onOpenUpload,
  onSelectChat,
  onSelectDocument,
}: Props) {
  return (
    <aside className="w-full shrink-0 border-b border-white/10 bg-[var(--panel-strong)]/95 backdrop-blur lg:h-full lg:w-[300px] lg:border-b-0 lg:border-r xl:w-[320px]">
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
            </div>

            <button
              type="button"
              onClick={onNewChat}
              className="inline-flex items-center rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm font-medium text-white transition hover:border-white/20 hover:bg-white/10"
            >
              New chat
            </button>
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
            onClick={onOpenUpload}
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
          <section className="rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.9),rgba(10,15,26,0.74))] p-4 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.8)]">
            <div className="mb-4">
              <h2 className="text-sm font-semibold text-white">Platform readiness</h2>
              <p className="text-xs text-[var(--muted-foreground)]">
                The signals recruiters look for in an AI product demo
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2">
              {[
                {
                  label: "LLM",
                  value: systemStatus?.llmConfigured ? "Configured" : "Missing",
                  active: Boolean(systemStatus?.llmConfigured),
                },
                {
                  label: "Embeddings",
                  value: systemStatus?.embeddingModelLoaded ? "Ready" : "Fallback",
                  active: Boolean(systemStatus?.embeddingModelLoaded),
                },
                {
                  label: "Reranker",
                  value: systemStatus?.rerankerLoaded ? "Ready" : "Disabled",
                  active: Boolean(systemStatus?.rerankerLoaded),
                },
                {
                  label: "Search",
                  value: systemStatus?.vectorSearchEnabled ? "Vector" : "Lexical",
                  active: Boolean(systemStatus?.vectorSearchEnabled),
                },
              ].map(({ label, value, active }) => (
                <div
                  key={label}
                  className={`rounded-2xl border px-3 py-3 ${
                    active
                      ? "border-emerald-400/30 bg-emerald-400/10"
                      : "border-amber-300/20 bg-amber-300/10"
                  }`}
                >
                  <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
                    {label}
                  </p>
                  <p className="mt-2 text-sm font-medium text-white">{value}</p>
                </div>
              ))}
            </div>

            <div className="mt-4 rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-3">
              <p className="text-[11px] uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
                Runtime
              </p>
              <div className="mt-2 flex items-center justify-between gap-3 text-sm text-white">
                <span>{systemStatus?.ragMode ?? "loading"} mode</span>
                <span>{systemStatus?.documentsIndexed ?? documents.length} docs indexed</span>
              </div>
              <p className="mt-2 text-xs leading-5 text-[var(--muted-foreground)]">
                {systemStatus?.geminiModel
                  ? `Model: ${systemStatus.geminiModel}`
                  : "Loading system configuration..."}
              </p>
            </div>
          </section>

          <section className="rounded-3xl border border-white/10 bg-[var(--panel)] p-4 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.8)]">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-white">Document library</h2>
                <p className="text-xs text-[var(--muted-foreground)]">
                  {documents.length} document{documents.length === 1 ? "" : "s"} indexed
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
                  const isActive = activeDocId === document.id;
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
                          onClick={() => onSelectDocument(document.id)}
                          className="min-w-0 flex-1 text-left"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-white">
                                {document.name}
                              </p>
                              <p className="mt-1 text-xs text-[var(--muted-foreground)]">
                                Added {formatRelativeTime(document.uploadedAt)}
                              </p>
                            </div>
                            {isActive && (
                              <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] font-medium text-white">
                                Active
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

          <section className="rounded-3xl border border-white/10 bg-[var(--panel)] p-4">
            <div className="mb-4">
              <h2 className="text-sm font-semibold text-white">Chat history</h2>
              <p className="text-xs text-[var(--muted-foreground)]">
                Recent conversations stay one tap away
              </p>
            </div>

            <div className="space-y-2">
              {chats.map((chat) => {
                const linkedDocument = documents.find((doc) => doc.id === chat.activeDocId);
                const isCurrent = chat.id === activeChatId;

                return (
                  <button
                    key={chat.id}
                    type="button"
                    onClick={() => onSelectChat(chat.id)}
                    className={`w-full rounded-2xl border px-4 py-3 text-left transition ${
                      isCurrent
                        ? "border-white/20 bg-white/[0.07]"
                        : "border-white/10 bg-transparent hover:border-white/15 hover:bg-white/[0.04]"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-white">{chat.title}</p>
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
                      <span>{linkedDocument?.name ?? "No document linked"}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        </div>
      </div>
    </aside>
  );
}
