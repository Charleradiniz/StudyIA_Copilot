import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("./components/PdfModal", () => ({
  default: () => null,
}));

vi.mock("./components/workspace/ViewerPanel", () => ({
  default: ({
    viewerDocId,
    selectedSource,
  }: {
    viewerDocId: string | null;
    selectedSource: { page?: number } | null;
  }) => (
    <div data-testid="viewer-panel">
      viewer:{viewerDocId ?? "none"}|page:
      {typeof selectedSource?.page === "number" ? selectedSource.page + 1 : "none"}
    </div>
  ),
}));

import App from "./App";

function jsonResponse(data: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
    },
    ...init,
  });
}

function createSystemStatus(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    status: "ok",
    rag_mode: "full",
    gemini_model: "gemini-2.5-flash-lite",
    llm_configured: true,
    embedding_model_loaded: true,
    reranker_loaded: true,
    vector_search_enabled: true,
    documents_indexed: 1,
    workspace_data_available: true,
    ...overrides,
  };
}

function createDocument(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    doc_id: "doc-1",
    name: "Research Plan.pdf",
    chunks: 8,
    pages: 3,
    rag_mode: "full",
    vector_ready: true,
    uploaded_at: "2026-04-09T12:00:00.000Z",
    preview: "A concise technical preview for the indexed document.",
    ...overrides,
  };
}

describe("App", () => {
  it("hydrates runtime status and remote documents on load", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);

        if (url.endsWith("/api/documents")) {
          return jsonResponse({
            documents: [createDocument()],
          });
        }

        if (url.endsWith("/api/system/status")) {
          return jsonResponse(createSystemStatus());
        }

        throw new Error(`Unhandled request: ${url}`);
      }),
    );

    render(<App />);

    expect(await screen.findByText("Research Plan.pdf")).toBeInTheDocument();
    expect(screen.getByText("Platform readiness")).toBeInTheDocument();
    expect(screen.getByText("Configured")).toBeInTheDocument();
    expect(screen.getByText("Vector")).toBeInTheDocument();
    expect(screen.getByText("8 chunks")).toBeInTheDocument();
    expect(screen.getByText("3 pages")).toBeInTheDocument();
    expect(screen.getByText(/Model: gemini-2\.5-flash-lite/i)).toBeInTheDocument();
  });

  it("uploads a document and answers a grounded question", async () => {
    const uploadedDocument = createDocument({
      doc_id: "doc-uploaded",
      name: "Study Guide.pdf",
      chunks: 6,
      pages: 2,
      vector_ready: false,
      preview: "Study guide preview generated after upload.",
    });

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.endsWith("/api/documents") && method === "GET") {
        return jsonResponse({ documents: [] });
      }

      if (url.endsWith("/api/system/status") && method === "GET") {
        return jsonResponse(
          createSystemStatus({
            rag_mode: "lite",
            embedding_model_loaded: false,
            reranker_loaded: false,
            vector_search_enabled: false,
            documents_indexed: 0,
            workspace_data_available: false,
          }),
        );
      }

      if (url.endsWith("/api/upload") && method === "POST") {
        return jsonResponse(uploadedDocument);
      }

      if (url.endsWith("/api/ask") && method === "POST") {
        const body = JSON.parse(String(init?.body));
        expect(body.doc_id).toBe("doc-uploaded");
        expect(body.question).toBe("What is the core promise?");

        return jsonResponse({
          question: body.question,
          answer: "Ready.",
          sources: [
            {
              id: 1,
              text: "This source shows the grounded evidence behind the answer.",
              doc_id: "doc-uploaded",
              page: 0,
              chunk_id: 2,
            },
          ],
        });
      }

      throw new Error(`Unhandled request: ${method} ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    const { container } = render(<App />);

    const fileInput = container.querySelector('input[type="file"]');
    expect(fileInput).not.toBeNull();

    await user.upload(
      fileInput as HTMLInputElement,
      new File(["fake-pdf"], "Study Guide.pdf", { type: "application/pdf" }),
    );

    expect(
      await screen.findByText(/indexed with 6 chunks across 2 pages/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Lexical fallback is active/i)).toBeInTheDocument();

    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "What is the core promise?",
    );
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Ready.")).toBeInTheDocument();

    const sourceLabel = await screen.findByText("Source 1");
    await user.click(sourceLabel.closest("button") as HTMLButtonElement);

    await waitFor(() => {
      expect(screen.getByTestId("viewer-panel")).toHaveTextContent("viewer:doc-uploaded");
      expect(screen.getByTestId("viewer-panel")).toHaveTextContent("page:1");
    });
  });
});
