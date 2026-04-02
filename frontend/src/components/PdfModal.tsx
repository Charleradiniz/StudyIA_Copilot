import { useEffect } from "react";
import PdfViewer from "./PdfViewer";

type Highlight = {
  chunk_id?: number;
  page?: number;
  bbox?: number[];
  line_boxes?: number[][];
};

type Props = {
  open: boolean;
  onClose: () => void;
  fileUrl: string;
  highlight?: Highlight | null;
  focusToken: number;
};

export default function PdfModal({
  open,
  onClose,
  fileUrl,
  highlight,
  focusToken,
}: Props) {
  const isValidUrl = fileUrl.trim().length > 0;

  useEffect(() => {
    if (isValidUrl) {
      console.log("PDF MODAL LOAD URL:", fileUrl);
    }
  }, [fileUrl, isValidUrl]);

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
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />

      <div
        className="relative flex h-[95vh] w-[95vw] flex-col overflow-hidden rounded-2xl bg-neutral-900 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between border-b border-neutral-700 px-4 py-3">
          <span className="text-sm text-neutral-300">Viewing PDF</span>

          <button
            onClick={onClose}
            className="rounded bg-red-500 px-3 py-1 text-sm hover:bg-red-600"
          >
            Close
          </button>
        </div>

        <div className="flex h-full w-full flex-1 overflow-hidden">
          {isValidUrl ? (
            <PdfViewer
              key={`${fileUrl}-${focusToken}`}
              fileUrl={fileUrl}
              targetChunk={
                typeof highlight?.chunk_id === "number"
                  ? highlight.chunk_id
                  : undefined
              }
              highlight={highlight ?? undefined}
              focusToken={focusToken}
            />
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
