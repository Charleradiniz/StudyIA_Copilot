import { Suspense, lazy, useEffect } from "react";
import type { AppDocument } from "../app/types";
import type { PdfRequestSource } from "../services/api";

const PdfViewer = lazy(() => import("./PdfViewer"));

type Highlight = {
  chunk_id?: number;
  page?: number;
  bbox?: number[];
  line_boxes?: number[][];
};

type Props = {
  activeDocuments: AppDocument[];
  open: boolean;
  onClose: () => void;
  fileRequest: PdfRequestSource | null;
  highlight?: Highlight | null;
  focusToken: number;
  viewerDocId: string | null;
  onSelectViewerDoc: (docId: string) => void;
};

export default function PdfModal({
  activeDocuments,
  open,
  onClose,
  fileRequest,
  highlight,
  focusToken,
  viewerDocId,
  onSelectViewerDoc,
}: Props) {
  const isValidFileRequest = Boolean(fileRequest?.url);
  const viewerDocument =
    activeDocuments.find((document) => document.id === viewerDocId) ?? activeDocuments[0] ?? null;

  useEffect(() => {
    if (!open) return;

    const handleEsc = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;

      const active = document.activeElement;
      const isTyping =
        active instanceof HTMLInputElement ||
        active instanceof HTMLTextAreaElement;

      if (isTyping) return;

      onClose();
    };

    window.addEventListener("keydown", handleEsc);
    return () => window.removeEventListener("keydown", handleEsc);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 lg:hidden">
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      <div
        className="relative flex h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-[28px] border border-white/10 bg-[var(--panel-strong)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="PDF viewer"
      >
        <div className="flex shrink-0 items-center justify-between border-b border-white/10 px-4 py-4">
          <span className="text-sm font-medium text-white">Viewing PDF</span>

          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-white transition hover:border-white/20 hover:bg-white/10"
          >
            Close
          </button>
        </div>

        {activeDocuments.length > 1 && (
          <div className="flex shrink-0 flex-wrap gap-2 border-b border-white/10 px-4 py-3">
            {activeDocuments.map((document) => (
              <button
                key={document.id}
                type="button"
                onClick={() => onSelectViewerDoc(document.id)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                  viewerDocId === document.id
                    ? "border-[var(--accent)] bg-[var(--accent-surface)] text-white"
                    : "border-white/10 bg-white/5 text-[var(--muted-foreground)]"
                }`}
              >
                {document.name}
              </button>
            ))}
          </div>
        )}

        <div className="flex h-full w-full flex-1 overflow-hidden">
          {isValidFileRequest && fileRequest ? (
            <Suspense
              fallback={
                <div className="flex h-full w-full items-center justify-center text-neutral-400">
                  Loading PDF viewer...
                </div>
              }
            >
              <PdfViewer
                key={fileRequest.url}
                fileRequest={fileRequest}
                targetChunk={
                  typeof highlight?.chunk_id === "number"
                    ? highlight.chunk_id
                    : undefined
                }
                highlight={highlight ?? undefined}
                focusToken={focusToken}
              />
            </Suspense>
          ) : (
            <div className="flex h-full w-full flex-col items-center justify-center px-8 text-center text-neutral-400">
              <p className="text-base font-medium text-white">
                {viewerDocument ? "PDF unavailable" : "No PDF selected"}
              </p>
              <p className="mt-3 max-w-sm text-sm leading-6 text-[var(--muted-foreground)]">
                {viewerDocument
                  ? "The indexed text is still available, but the original PDF file is no longer on the server."
                  : "Select a document to open the mobile PDF viewer."}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
