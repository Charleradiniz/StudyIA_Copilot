import type { RefObject } from "react";
import type {
  AppDocument,
  ChatMessage,
  ChatSession,
  Source,
  SystemStatus,
} from "../../app/types";

function MessageSkeleton() {
  return (
    <div className="space-y-2">
      <div className="h-3 w-40 animate-pulse rounded-full bg-white/10" />
      <div className="h-3 w-full animate-pulse rounded-full bg-white/10" />
      <div className="h-3 w-5/6 animate-pulse rounded-full bg-white/10" />
    </div>
  );
}

type Props = {
  activeChat: ChatSession;
  activeDocuments: AppDocument[];
  documentsCount: number;
  input: string;
  isDesktop: boolean;
  loading: boolean;
  systemStatus: SystemStatus | null;
  viewerDocument: AppDocument | null;
  viewerDocId: string | null;
  onChangeInput: (value: string) => void;
  onOpenPdf: () => void;
  onOpenUpload: () => void;
  onSelectSource: (source: Source) => void;
  onSend: () => void;
  chatEndRef: RefObject<HTMLDivElement | null>;
};

function renderMessageContent(message: ChatMessage) {
  if (message.streaming && !message.content) {
    return <MessageSkeleton />;
  }

  return (
    <p className="whitespace-pre-wrap text-[15px] leading-7 text-white/95">
      {message.content}
      {message.streaming && <span className="ml-0.5 animate-pulse">|</span>}
    </p>
  );
}

export default function ChatWorkspace({
  activeChat,
  activeDocuments,
  documentsCount,
  input,
  isDesktop,
  loading,
  systemStatus,
  viewerDocument,
  viewerDocId,
  onChangeInput,
  onOpenPdf,
  onOpenUpload,
  onSelectSource,
  onSend,
  chatEndRef,
}: Props) {
  const hasActiveDocuments = activeDocuments.length > 0;
  const activeDocumentSummary =
    activeDocuments.length === 0
      ? "Link documents to start grounded Q&A"
      : activeDocuments.length === 1
        ? `Grounded on ${activeDocuments[0].name}`
        : `Grounded on ${activeDocuments.length} PDFs at once`;

  return (
    <section className="flex min-h-0 flex-1 flex-col border-b border-white/10 lg:h-full lg:border-b-0 lg:border-r">
      <div className="shrink-0 border-b border-white/10 bg-[var(--panel)]/85 px-5 py-5 backdrop-blur">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.22em] text-[var(--muted-foreground)]">
              Active chat
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">
              {activeChat.title}
            </h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              {activeDocumentSummary}
            </p>

            {hasActiveDocuments && (
              <div className="mt-4 flex flex-wrap gap-2">
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-[var(--muted-foreground)]">
                  {activeDocuments.length} active PDF{activeDocuments.length === 1 ? "" : "s"}
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-[var(--muted-foreground)]">
                  {activeDocuments.reduce((total, document) => total + document.pageCount, 0)} pages
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-[var(--muted-foreground)]">
                  {activeDocuments.reduce((total, document) => total + document.chunkCount, 0)} chunks
                </span>
                <span
                  className={`rounded-full px-3 py-1.5 text-xs font-medium ${
                    activeDocuments.every((document) => document.vectorReady)
                      ? "border border-emerald-400/30 bg-emerald-400/10 text-emerald-100"
                      : "border border-amber-300/20 bg-amber-300/10 text-amber-100"
                  }`}
                >
                  {activeDocuments.every((document) => document.vectorReady)
                    ? "Vector retrieval ready"
                    : "Mixed retrieval modes active"}
                </span>
                {systemStatus && (
                  <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-[var(--muted-foreground)]">
                    {systemStatus.ragMode} mode
                  </span>
                )}
                {activeDocuments.map((document) => (
                  <span
                    key={document.id}
                    className={`rounded-full border px-3 py-1.5 text-xs font-medium ${
                      viewerDocId === document.id
                        ? "border-[var(--accent)] bg-[var(--accent-surface)] text-white"
                        : "border-white/10 bg-white/5 text-[var(--muted-foreground)]"
                    }`}
                  >
                    {document.name}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-[var(--muted-foreground)]">
              {documentsCount} docs
            </span>
            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-[var(--muted-foreground)]">
              {activeChat.messages.length} messages
            </span>
            {!isDesktop && viewerDocId && (
              <button
                type="button"
                onClick={onOpenPdf}
                className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white transition hover:border-white/20 hover:bg-white/10"
              >
                Open PDF
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-6">
        <div className="mx-auto flex max-w-4xl flex-col gap-4">
          {activeChat.messages.map((message) => {
            const isUser = message.role === "user";

            return (
              <div
                key={message.id}
                className={`flex transition-all duration-300 ${
                  isUser ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-3xl rounded-[28px] border px-5 py-4 shadow-[0_20px_70px_-42px_rgba(15,23,42,0.9)] transition duration-300 ${
                    isUser
                      ? "border-[var(--accent)]/40 bg-[linear-gradient(180deg,rgba(45,212,191,0.32),rgba(14,116,144,0.18))] text-white"
                      : "border-white/10 bg-[var(--panel)] text-[var(--app-foreground)]"
                  }`}
                >
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <span className="text-xs font-medium uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
                      {isUser ? "You" : "Copilot"}
                    </span>
                    {message.streaming && (
                      <span className="flex items-center gap-1 text-xs text-[var(--muted-foreground)]">
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--accent)]" />
                        Streaming
                      </span>
                    )}
                  </div>

                  {renderMessageContent(message)}

                  {message.sources && message.sources.length > 0 && (
                    <div className="mt-5 space-y-2">
                      <p className="text-xs font-medium uppercase tracking-[0.16em] text-[var(--muted-foreground)]">
                        Highlights
                      </p>
                      {message.sources.map((source) => (
                        <button
                          key={`${message.id}-${source.id}`}
                          type="button"
                          onClick={() => onSelectSource(source)}
                          className="group w-full rounded-2xl border border-white/10 bg-white/[0.03] p-3 text-left transition hover:border-white/20 hover:bg-white/[0.06]"
                        >
                          <div className="mb-2 flex items-center justify-between gap-3">
                            <span className="rounded-full bg-white/10 px-2 py-1 text-[11px] font-medium text-white">
                              Source {source.id}
                            </span>
                            <span className="text-[11px] text-[var(--muted-foreground)] transition group-hover:text-white/80">
                              {[
                                activeDocuments.find((document) => document.id === source.doc_id)?.name,
                                typeof source.page === "number" ? `Page ${source.page + 1}` : null,
                              ]
                                .filter(Boolean)
                                .join(" - ") || "Open in PDF"}
                            </span>
                          </div>
                          <p className="line-clamp-3 text-sm leading-6 text-[var(--muted-foreground)] group-hover:text-white/90">
                            {source.text}
                          </p>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={chatEndRef} />
        </div>
      </div>

      <div className="shrink-0 border-t border-white/10 bg-[var(--panel)]/85 px-5 py-4 backdrop-blur">
        <div className="mx-auto max-w-4xl rounded-[28px] border border-white/10 bg-black/20 p-3 shadow-[0_18px_60px_-42px_rgba(15,23,42,0.9)]">
          <div className="mb-3 flex items-center justify-between gap-3 px-2">
            <div>
              <p className="text-sm font-medium text-white">
                {viewerDocument?.name ?? (hasActiveDocuments ? "Select a PDF in the viewer" : "No document selected")}
              </p>
              <p className="text-xs text-[var(--muted-foreground)]">
                {hasActiveDocuments
                  ? "Ask across all active PDFs and inspect the exact source document in the viewer."
                  : "Use the sidebar to upload or activate one or more documents."}
              </p>
              {viewerDocument?.preview && (
                <p className="mt-2 max-w-2xl line-clamp-2 text-xs leading-5 text-[var(--muted-foreground)]">
                  {viewerDocument.preview}
                </p>
              )}
            </div>
            <button
              type="button"
              onClick={onOpenUpload}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white transition hover:border-white/20 hover:bg-white/10"
            >
              Upload PDF
            </button>
          </div>

          <div className="flex flex-col gap-3 md:flex-row md:items-end">
            <label className="flex-1">
              <span className="sr-only">Message</span>
              <textarea
                value={input}
                onChange={(event) => onChangeInput(event.target.value)}
                placeholder={
                  hasActiveDocuments
                    ? "Ask a precise question across the active PDFs..."
                    : "Upload or select PDFs to unlock grounded answers..."
                }
                rows={3}
                className="min-h-[104px] w-full resize-none rounded-[22px] border border-white/10 bg-[var(--panel)] px-4 py-3 text-sm text-white outline-none transition placeholder:text-[var(--muted-foreground)] focus:border-[var(--accent)]"
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    onSend();
                  }
                }}
                disabled={loading}
              />
            </label>

            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={onSend}
                disabled={loading}
                className="inline-flex h-12 items-center justify-center rounded-[20px] bg-[var(--accent)] px-5 text-sm font-medium text-slate-950 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? "Thinking..." : "Send"}
              </button>
              <p className="text-center text-[11px] text-[var(--muted-foreground)]">
                Enter to send, Shift+Enter for a new line
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
