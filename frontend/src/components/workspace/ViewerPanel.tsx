import { Suspense, lazy } from "react";
import type { AppDocument, Source } from "../../app/types";

const PdfViewer = lazy(() => import("../PdfViewer"));

type Props = {
  documents: AppDocument[];
  focusToken: number;
  pdfUrl: string;
  selectedSource: Source | null;
  viewerDocId: string | null;
  onClearFocus: () => void;
};

export default function ViewerPanel({
  documents,
  focusToken,
  pdfUrl,
  selectedSource,
  viewerDocId,
  onClearFocus,
}: Props) {
  return (
    <section className="hidden h-full min-h-0 w-[44%] min-w-[380px] max-w-[720px] flex-col bg-[var(--panel-strong)] lg:flex">
      <div className="shrink-0 border-b border-white/10 px-5 py-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
              PDF viewer
            </p>
            <h3 className="mt-2 text-xl font-semibold text-white">
              {documents.find((document) => document.id === viewerDocId)?.name ?? "No document open"}
            </h3>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              {selectedSource && typeof selectedSource.page === "number"
                ? `Focused on page ${selectedSource.page + 1}`
                : "Select a source to jump straight to the referenced passage"}
            </p>
          </div>

          {selectedSource && (
            <button
              type="button"
              onClick={onClearFocus}
              className="rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs font-medium text-white transition hover:border-white/20 hover:bg-white/10"
            >
              Clear focus
            </button>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden p-4">
        <div className="h-full overflow-hidden rounded-[28px] border border-white/10 bg-[var(--panel)] shadow-[0_30px_90px_-48px_rgba(15,23,42,0.9)]">
          {viewerDocId ? (
            <Suspense
              fallback={
                <div className="flex h-full items-center justify-center text-sm text-[var(--muted-foreground)]">
                  Loading viewer...
                </div>
              }
            >
              <PdfViewer
                key={pdfUrl}
                fileUrl={pdfUrl}
                targetChunk={selectedSource?.chunk_id}
                highlight={selectedSource ?? undefined}
                focusToken={focusToken}
              />
            </Suspense>
          ) : (
            <div className="flex h-full flex-col items-center justify-center px-8 text-center">
              <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium uppercase tracking-[0.18em] text-[var(--muted-foreground)]">
                Viewer idle
              </div>
              <h4 className="mt-5 text-2xl font-semibold text-white">
                Open a document to inspect exact passages
              </h4>
              <p className="mt-3 max-w-sm text-sm leading-6 text-[var(--muted-foreground)]">
                As soon as a PDF is active, this panel becomes a persistent reference view with source highlights.
              </p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
