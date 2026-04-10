import { Suspense, lazy, useEffect } from "react";
import type { AppDocument } from "../app/types";

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
  fileUrl: string;
  highlight?: Highlight | null;
  focusToken: number;
  viewerDocId: string | null;
  onSelectViewerDoc: (docId: string) => void;
};

export default function PdfModal({
  activeDocuments,
  open,
  onClose,
  fileUrl,
  highlight,
  focusToken,
  viewerDocId,
  onSelectViewerDoc,
}: Props) {
  const isValidUrl = fileUrl.trim().length > 0;

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
          {isValidUrl ? (
            <Suspense
              fallback={
                <div className="flex h-full w-full items-center justify-center text-neutral-400">
                  Loading PDF viewer...
                </div>
              }
            >
              <PdfViewer
                key={fileUrl}
                fileUrl={fileUrl}
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
            <div className="flex h-full w-full items-center justify-center text-neutral-400">
              No PDF file specified
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
