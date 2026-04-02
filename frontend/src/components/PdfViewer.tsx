import { useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import type { PDFDocumentProxy, PDFPageProxy } from "pdfjs-dist";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).toString();

type Props = {
  fileUrl: string;
  targetChunk?: number;
  focusToken: number;
  highlight?: {
    page?: number;
    bbox?: number[];
    line_boxes?: number[][];
  };
};

type PageMetrics = {
  width: number;
  height: number;
};

export default function PdfViewer({ fileUrl, targetChunk, focusToken, highlight }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const pageRefs = useRef<(HTMLDivElement | null)[]>([]);
  const lastPageScrollKeyRef = useRef<string>("");
  const lastHighlightScrollKeyRef = useRef<string>("");

  const [numPages, setNumPages] = useState(0);
  const [pageWidth, setPageWidth] = useState(800);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [pageMetrics, setPageMetrics] = useState<Record<number, PageMetrics>>({});
  const [highlightElement, setHighlightElement] = useState<HTMLDivElement | null>(null);
  const file = useMemo(() => ({ url: fileUrl }), [fileUrl]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const updateWidth = () => {
      setPageWidth(Math.max(320, Math.floor(container.clientWidth - 32)));
    };

    updateWidth();

    const resizeObserver = new ResizeObserver(updateWidth);
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  useEffect(() => {
    setNumPages(0);
    setError(null);
    setIsLoading(Boolean(fileUrl));
    setPageMetrics({});
    pageRefs.current = [];
    setHighlightElement(null);
    lastPageScrollKeyRef.current = "";
    lastHighlightScrollKeyRef.current = "";
  }, [fileUrl]);

  const handleLoadSuccess = ({ numPages: nextNumPages }: PDFDocumentProxy) => {
    setNumPages(nextNumPages);
    setError(null);
    setIsLoading(false);
  };

  const handleLoadError = (loadError: Error) => {
    console.error("PDF RENDER ERROR:", loadError);
    setError("Error rendering PDF.");
    setIsLoading(false);
  };

  const highlightPageNumber =
    typeof highlight?.page === "number" ? highlight.page + 1 : null;

  const highlightRect = useMemo(() => {
    if (!highlight?.bbox || highlightPageNumber === null) {
      return null;
    }

    const [x0, y0, x1, y1] = highlight.bbox;
    const metrics = pageMetrics[highlightPageNumber];

    if (!metrics || x1 <= x0 || y1 <= y0) {
      return null;
    }

    const scale = pageWidth / metrics.width;

    return {
      left: x0 * scale,
      top: y0 * scale,
      width: (x1 - x0) * scale,
      height: Math.max((y1 - y0) * scale, 18),
    };
  }, [highlight?.bbox, highlightPageNumber, pageMetrics, pageWidth]);

  const highlightLineRects = useMemo(() => {
    if (!highlight?.line_boxes?.length || highlightPageNumber === null) {
      return [];
    }

    const metrics = pageMetrics[highlightPageNumber];
    if (!metrics) {
      return [];
    }

    const scale = pageWidth / metrics.width;

    return highlight.line_boxes
      .filter((box): box is number[] => Array.isArray(box) && box.length === 4)
      .map(([x0, y0, x1, y1]) => ({
        left: x0 * scale,
        top: y0 * scale,
        width: Math.max((x1 - x0) * scale, 24),
        height: Math.max((y1 - y0) * scale, 18),
      }));
  }, [highlight?.line_boxes, highlightPageNumber, pageMetrics, pageWidth]);

  const highlightKey = useMemo(() => {
    const bboxKey = highlight?.bbox?.join(",") ?? "no-bbox";
    const pageKey = highlightPageNumber ?? "no-page";
    const chunkKey = targetChunk ?? "no-chunk";

    return `${fileUrl}|${pageKey}|${bboxKey}|${chunkKey}|${focusToken}`;
  }, [fileUrl, focusToken, highlight?.bbox, highlightPageNumber, targetChunk]);

  const handlePageLoadSuccess = (page: PDFPageProxy) => {
    setPageMetrics((current) => {
      if (
        current[page.pageNumber]?.width === page.view[2] &&
        current[page.pageNumber]?.height === page.view[3]
      ) {
        return current;
      }

      return {
        ...current,
        [page.pageNumber]: {
          width: page.view[2],
          height: page.view[3],
        },
      };
    });
  };

  useEffect(() => {
    if (numPages === 0) return;

    const highlightedPage =
      typeof highlight?.page === "number" ? highlight.page + 1 : undefined;
    const targetPageNumber =
      highlightedPage ??
      (targetChunk
        ? Math.max(1, Math.min(numPages, Math.floor(targetChunk / 4) + 1))
        : undefined);

    if (!targetPageNumber) return;

    const targetPage = pageRefs.current[targetPageNumber - 1];
    if (!targetPage) return;

    if (lastPageScrollKeyRef.current === highlightKey) {
      return;
    }

    lastPageScrollKeyRef.current = highlightKey;

    requestAnimationFrame(() => {
      targetPage.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    });
  }, [
    highlight?.page,
    highlightKey,
    numPages,
    targetChunk,
  ]);

  useEffect(() => {
    if (!highlightElement || !highlightRect || highlightPageNumber === null) {
      return;
    }

    if (lastHighlightScrollKeyRef.current === highlightKey) {
      return;
    }

    const container = containerRef.current;
    if (!container) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      const containerRect = container.getBoundingClientRect();
      const markerRect = highlightElement.getBoundingClientRect();
      const currentScrollTop = container.scrollTop;
      const markerCenter =
        markerRect.top - containerRect.top + currentScrollTop + markerRect.height / 2;
      const targetScrollTop = markerCenter - container.clientHeight / 2;
      const maxScrollTop = Math.max(0, container.scrollHeight - container.clientHeight);

      lastHighlightScrollKeyRef.current = highlightKey;
      container.scrollTo({
        top: Math.min(Math.max(0, targetScrollTop), maxScrollTop),
        behavior: "smooth",
      });
    }, 120);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [highlightElement, highlightKey, highlightPageNumber, highlightRect]);

  if (!fileUrl) {
    return <div className="p-4 text-red-400">No PDF selected.</div>;
  }

  if (error) {
    return <div className="p-4 text-red-400">{error}</div>;
  }

  return (
    <div ref={containerRef} className="h-full w-full overflow-auto bg-neutral-900 p-4">
      <Document
        file={file}
        loading={<div className="mb-4 text-gray-400">Loading PDF...</div>}
        error={<div className="p-4 text-red-400">Error loading PDF.</div>}
        onLoadSuccess={handleLoadSuccess}
        onLoadError={handleLoadError}
      >
        {Array.from({ length: numPages }, (_, index) => (
          <div
            key={`page_${index + 1}`}
            ref={(element) => {
              pageRefs.current[index] = element;
            }}
            className="relative mb-4 flex justify-center"
          >
            <Page
              pageNumber={index + 1}
              width={pageWidth}
              loading={index === 0 && isLoading ? "Rendering page..." : ""}
              onLoadSuccess={handlePageLoadSuccess}
              renderAnnotationLayer
              renderTextLayer
            />
            {highlightRect && highlightPageNumber === index + 1 ? (
              <div
                aria-hidden="true"
                className="pointer-events-none absolute"
                ref={setHighlightElement}
                style={{
                  left: highlightRect.left,
                  top: highlightRect.top,
                  width: highlightRect.width,
                  height: highlightRect.height,
                }}
              >
                {(highlightLineRects.length > 0 ? highlightLineRects : [highlightRect]).map(
                  (lineRect, lineIndex) => (
                    <div
                      key={`${highlightKey}-line-${lineIndex}`}
                      className="absolute rounded-sm"
                      style={{
                        left: lineRect.left - highlightRect.left,
                        top: lineRect.top - highlightRect.top,
                        width: lineRect.width,
                        height: lineRect.height,
                        background:
                          "linear-gradient(180deg, rgba(255,250,180,0.12) 0%, rgba(255,241,118,0.44) 16%, rgba(255,235,59,0.82) 38%, rgba(255,230,40,0.76) 62%, rgba(255,241,118,0.46) 84%, rgba(255,250,180,0.10) 100%)",
                        boxShadow:
                          "0 0 10px rgba(255, 235, 59, 0.20), 0 1px 0 rgba(255, 248, 180, 0.28) inset",
                        opacity: lineIndex % 2 === 0 ? 0.93 : 0.88,
                        borderRadius:
                          lineIndex % 2 === 0 ? "7px 11px 8px 10px" : "10px 7px 11px 8px",
                        filter: "saturate(1.08)",
                        transform: `rotate(${lineIndex % 2 === 0 ? "-0.9deg" : "0.7deg"}) scaleY(${lineIndex % 2 === 0 ? "1.02" : "0.98"})`,
                        transformOrigin: "center",
                        mixBlendMode: "multiply",
                      }}
                    />
                  ),
                )}
              </div>
            ) : null}
          </div>
        ))}
      </Document>
    </div>
  );
}
