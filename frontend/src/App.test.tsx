import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./components/PdfModal", () => ({
  default: () => null,
}));

vi.mock("./components/workspace/ViewerPanel", () => ({
  default: ({
    activeDocuments,
    onSelectViewerDoc,
    viewerDocId,
    selectedSource,
  }: {
    activeDocuments: { id: string; name: string }[];
    onSelectViewerDoc: (docId: string) => void;
    viewerDocId: string | null;
    selectedSource: { page?: number } | null;
  }) => (
    <div data-testid="viewer-panel">
      viewer:{viewerDocId ?? "none"}|page:
      {typeof selectedSource?.page === "number" ? selectedSource.page + 1 : "none"}
      {activeDocuments.map((document) => (
        <button
          key={document.id}
          type="button"
          onClick={() => onSelectViewerDoc(document.id)}
        >
          view:{document.name}
        </button>
      ))}
    </div>
  ),
}));

import App from "./App";

const AUTH_STORAGE_KEY = "studyiacopilot.auth.v1";
const WORKSPACE_STORAGE_KEY = "studyiacopilot.workspace.v3.user-1";

afterEach(() => {
  window.history.replaceState({}, "", "/");
});

function jsonResponse(data: unknown, init?: ResponseInit) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
    },
    ...init,
  });
}

function handleDefaultChatRequests(url: string, method: string) {
  if (url.endsWith("/api/chats") && method === "GET") {
    return jsonResponse({
      chats: [],
      deleted: [],
    });
  }

  if (url.endsWith("/api/chats/sync") && method === "POST") {
    return jsonResponse({
      synced_chat_ids: [],
      skipped_chat_ids: [],
    });
  }

  return null;
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

function createUser(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "user-1",
    email: "charles@example.com",
    full_name: "Charles Study",
    created_at: "2026-04-09T11:00:00.000Z",
    ...overrides,
  };
}

function persistAuth() {
  window.localStorage.setItem(
    AUTH_STORAGE_KEY,
    JSON.stringify({
      token: "token-123",
      expiresAt: Date.parse("2026-05-09T12:00:00.000Z"),
      user: {
        id: "user-1",
        email: "charles@example.com",
        fullName: "Charles Study",
        createdAt: Date.parse("2026-04-09T11:00:00.000Z"),
      },
    }),
  );
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
    pdf_available: true,
    ...overrides,
  };
}

function persistWorkspace(overrides: Partial<Record<string, unknown>> = {}) {
  window.localStorage.setItem(
    WORKSPACE_STORAGE_KEY,
    JSON.stringify({
      chats: [
        {
          id: "chat-seeded",
          title: "Strategy Review",
          activeDocIds: ["doc-1"],
          messages: [
            {
              id: "msg-1",
              role: "assistant",
              content: "Upload a PDF to begin.",
            },
            {
              id: "msg-2",
              role: "user",
              content: "Summarize the strategy.",
            },
          ],
          createdAt: Date.parse("2026-04-09T12:00:00.000Z"),
          updatedAt: Date.parse("2026-04-09T12:10:00.000Z"),
        },
      ],
      activeChatId: "chat-seeded",
      activeNav: "workspace",
      viewerDocId: "doc-1",
      ...overrides,
    }),
  );
}

describe("App", () => {
  it("hydrates runtime status and remote documents on load", async () => {
    persistAuth();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url.endsWith("/api/auth/me") && method === "GET") {
          return jsonResponse({
            user: createUser(),
          });
        }

        if (url.endsWith("/api/documents") && method === "GET") {
          return jsonResponse({
            documents: [createDocument()],
          });
        }

        if (url.endsWith("/api/system/status") && method === "GET") {
          return jsonResponse(createSystemStatus());
        }

        if (url.endsWith("/api/chats/chat-seeded") && method === "DELETE") {
          return jsonResponse({
            chat_id: "chat-seeded",
            deleted: true,
          });
        }

        const chatResponse = handleDefaultChatRequests(url, method);
        if (chatResponse) {
          return chatResponse;
        }

        throw new Error(`Unhandled request: ${method} ${url}`);
      }),
    );

    render(<App />);

    expect(await screen.findByText("Research Plan.pdf")).toBeInTheDocument();
    expect(screen.getByText("Document library")).toBeInTheDocument();
    expect(screen.getByText("Chat history")).toBeInTheDocument();
    expect(screen.getByText("8 chunks")).toBeInTheDocument();
    expect(screen.getByText("3 pages")).toBeInTheDocument();
  });

  it("switches sidebar content across workspace, documents, and activity", async () => {
    persistAuth();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url.endsWith("/api/auth/me") && method === "GET") {
          return jsonResponse({
            user: createUser(),
          });
        }

        if (url.endsWith("/api/documents") && method === "GET") {
          return jsonResponse({
            documents: [createDocument()],
          });
        }

        if (url.endsWith("/api/system/status") && method === "GET") {
          return jsonResponse(createSystemStatus());
        }

        if (url.endsWith("/api/chats/chat-seeded") && method === "DELETE") {
          return jsonResponse({
            chat_id: "chat-seeded",
            deleted: true,
          });
        }

        const chatResponse = handleDefaultChatRequests(url, method);
        if (chatResponse) {
          return chatResponse;
        }

        throw new Error(`Unhandled request: ${method} ${url}`);
      }),
    );

    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText("Document library")).toBeInTheDocument();
    expect(screen.getByText("Chat history")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Documents" }));

    expect(screen.getByText("Document library")).toBeInTheDocument();
    expect(screen.queryByText("Chat history")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Activity" }));

    expect(screen.getByText("Chat history")).toBeInTheDocument();
    expect(screen.queryByText("Document library")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Workspace" }));

    expect(screen.getByText("Document library")).toBeInTheDocument();
    expect(screen.getByText("Chat history")).toBeInTheDocument();
  });

  it("asks across multiple active PDFs and switches the viewer to the sourced file", async () => {
    persistAuth();

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.endsWith("/api/auth/me") && method === "GET") {
        return jsonResponse({
          user: createUser(),
        });
      }

      if (url.endsWith("/api/documents") && method === "GET") {
        return jsonResponse({
          documents: [
            createDocument(),
            createDocument({
              doc_id: "doc-2",
              name: "System Notes.pdf",
              chunks: 5,
              pages: 2,
              uploaded_at: "2026-04-10T12:00:00.000Z",
              preview: "A second document to validate multi-PDF reasoning.",
            }),
          ],
        });
      }

      if (url.endsWith("/api/system/status") && method === "GET") {
        return jsonResponse(createSystemStatus({ documents_indexed: 2 }));
      }

      if (url.endsWith("/api/ask") && method === "POST") {
        const body = JSON.parse(String(init?.body));
        expect(body.doc_ids).toEqual(["doc-1", "doc-2"]);

        return jsonResponse({
          question: body.question,
          answer: "Compared answer.",
          sources: [
            {
              id: 1,
              text: "This source came from the second active PDF.",
              doc_id: "doc-2",
              page: 1,
              chunk_id: 4,
            },
          ],
        });
      }

      const chatResponse = handleDefaultChatRequests(url, method);
      if (chatResponse) {
        return chatResponse;
      }

      throw new Error(`Unhandled request: ${method} ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText("Research Plan.pdf")).toBeInTheDocument();
    expect(screen.getByText("System Notes.pdf")).toBeInTheDocument();

    const firstDocumentButton = screen
      .getAllByText("Research Plan.pdf")
      .find((node) => node.closest("button"))?.closest("button");
    const secondDocumentButton = screen
      .getAllByText("System Notes.pdf")
      .find((node) => node.closest("button"))?.closest("button");

    expect(firstDocumentButton).toBeTruthy();
    expect(secondDocumentButton).toBeTruthy();

    await user.click(firstDocumentButton as HTMLButtonElement);
    await user.click(secondDocumentButton as HTMLButtonElement);

    await user.type(
      screen.getByRole("textbox", { name: "Message" }),
      "Compare both PDFs",
    );
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Compared answer.")).toBeInTheDocument();

    await user.click(screen.getByText("Source 1").closest("button") as HTMLButtonElement);

    await waitFor(() => {
      expect(screen.getByTestId("viewer-panel")).toHaveTextContent("viewer:doc-2");
      expect(screen.getByTestId("viewer-panel")).toHaveTextContent("page:2");
    });

    await user.click(screen.getByRole("button", { name: "view:Research Plan.pdf" }));

    await waitFor(() => {
      expect(screen.getByTestId("viewer-panel")).toHaveTextContent("viewer:doc-1");
      expect(screen.getByTestId("viewer-panel")).toHaveTextContent("page:none");
    });
  });

  it("uploads a document and answers a grounded question", async () => {
    persistAuth();

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

      if (url.endsWith("/api/auth/me") && method === "GET") {
        return jsonResponse({
          user: createUser(),
        });
      }

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
        expect(body.doc_ids).toEqual(["doc-uploaded"]);
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

      const chatResponse = handleDefaultChatRequests(url, method);
      if (chatResponse) {
        return chatResponse;
      }

      throw new Error(`Unhandled request: ${method} ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByText("Research workspace");

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

  it("deletes a document from the library and clears the active viewer", async () => {
    persistAuth();
    vi.stubGlobal("confirm", vi.fn(() => true));

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.endsWith("/api/auth/me") && method === "GET") {
        return jsonResponse({
          user: createUser(),
        });
      }

      if (url.endsWith("/api/documents") && method === "GET") {
        return jsonResponse({
          documents: [createDocument()],
        });
      }

      if (url.endsWith("/api/system/status") && method === "GET") {
        return jsonResponse(createSystemStatus());
      }

      if (url.endsWith("/api/documents/doc-1") && method === "DELETE") {
        return jsonResponse({
          doc_id: "doc-1",
          removed: true,
          removed_files: [
            "backend/uploads/doc-1.pdf",
            "backend/data/doc-1.json",
          ],
        });
      }

      const chatResponse = handleDefaultChatRequests(url, method);
      if (chatResponse) {
        return chatResponse;
      }

      throw new Error(`Unhandled request: ${method} ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(<App />);

    const documentTitle = await screen.findByText("Research Plan.pdf");
    await user.click(documentTitle.closest("button") as HTMLButtonElement);

    await waitFor(() => {
      expect(screen.getByTestId("viewer-panel")).toHaveTextContent("viewer:doc-1");
    });

    await user.click(screen.getByRole("button", { name: "Delete Research Plan.pdf" }));

    await waitFor(() => {
      expect(screen.getByText("Upload your first PDF to build the workspace.")).toBeInTheDocument();
      expect(screen.getByTestId("viewer-panel")).toHaveTextContent("viewer:none");
    });
  });

  it("deletes the active chat and recreates a clean workspace session", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    persistAuth();
    persistWorkspace();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url.endsWith("/api/auth/me") && method === "GET") {
          return jsonResponse({
            user: createUser(),
          });
        }

        if (url.endsWith("/api/documents") && method === "GET") {
          return jsonResponse({
            documents: [createDocument()],
          });
        }

        if (url.endsWith("/api/system/status") && method === "GET") {
          return jsonResponse(createSystemStatus());
        }

        if (url.endsWith("/api/chats/chat-seeded") && method === "DELETE") {
          return jsonResponse({
            chat_id: "chat-seeded",
            deleted: true,
          });
        }

        const chatResponse = handleDefaultChatRequests(url, method);
        if (chatResponse) {
          return chatResponse;
        }

        throw new Error(`Unhandled request: ${method} ${url}`);
      }),
    );

    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Strategy Review" })).toBeInTheDocument();
    expect(screen.getByTestId("viewer-panel")).toHaveTextContent("viewer:doc-1");

    await user.click(screen.getByRole("button", { name: "Delete chat Strategy Review" }));

    await waitFor(() => {
      expect(screen.getByText("Welcome back. Upload PDFs, pick one or more documents, and ask anything about them.")).toBeInTheDocument();
      expect(screen.getByTestId("viewer-panel")).toHaveTextContent("viewer:none");
      expect(screen.getByRole("heading", { name: "New conversation" })).toBeInTheDocument();
    });
  });

  it("shows the authentication screen and signs in", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.endsWith("/api/auth/login") && method === "POST") {
        return jsonResponse({
          token: "token-123",
          expires_at: "2026-05-09T12:00:00.000Z",
          user: createUser(),
        });
      }

      if (url.endsWith("/api/auth/me") && method === "GET") {
        return jsonResponse({
          user: createUser(),
        });
      }

      if (url.endsWith("/api/documents") && method === "GET") {
        return jsonResponse({
          documents: [createDocument()],
        });
      }

      if (url.endsWith("/api/system/status") && method === "GET") {
        return jsonResponse(createSystemStatus());
      }

      const chatResponse = handleDefaultChatRequests(url, method);
      if (chatResponse) {
        return chatResponse;
      }

      throw new Error(`Unhandled request: ${method} ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByText("Private AI research workspaces for every user.")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Email"), "charles@example.com");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getAllByRole("button", { name: "Sign in" })[1]);

    expect(await screen.findByText("Research Plan.pdf")).toBeInTheDocument();
    expect(screen.getByText(/Charles Study/i)).toBeInTheDocument();
  });

  it("requests a password reset email from the sign-in screen", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.endsWith("/api/auth/password-reset/request") && method === "POST") {
        const body = JSON.parse(String(init?.body));
        expect(body.email).toBe("charles@example.com");

        return jsonResponse({
          sent: true,
          message: "Recovery link sent.",
        });
      }

      const chatResponse = handleDefaultChatRequests(url, method);
      if (chatResponse) {
        return chatResponse;
      }

      throw new Error(`Unhandled request: ${method} ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Forgot password?" }));
    await user.type(screen.getByLabelText("Email"), "charles@example.com");
    await user.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByText("Recovery link sent.")).toBeInTheDocument();
  });

  it("opens the reset-password form from the URL token and updates the password", async () => {
    window.history.replaceState({}, "", "/?reset_password_token=reset-token-123");

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.endsWith("/api/auth/password-reset/confirm") && method === "POST") {
        const body = JSON.parse(String(init?.body));
        expect(body).toEqual({
          token: "reset-token-123",
          password: "new-password-456",
        });

        return jsonResponse({
          password_reset: true,
          message: "Password updated. You can sign in now.",
        });
      }

      const chatResponse = handleDefaultChatRequests(url, method);
      if (chatResponse) {
        return chatResponse;
      }

      throw new Error(`Unhandled request: ${method} ${url}`);
    });

    vi.stubGlobal("fetch", fetchMock);

    const user = userEvent.setup();
    render(<App />);

    expect(screen.getByText("Choose a new password")).toBeInTheDocument();

    await user.type(screen.getByLabelText("New password"), "new-password-456");
    await user.type(screen.getByLabelText("Confirm new password"), "new-password-456");
    await user.click(screen.getByRole("button", { name: "Update password" }));

    expect(await screen.findByText("Password updated. You can sign in now.")).toBeInTheDocument();
    expect(window.location.search).toBe("");
  });
});
