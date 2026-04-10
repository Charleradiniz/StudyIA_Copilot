import { expect, test } from "@playwright/test";

const TEST_PDF_BASE64 =
  "JVBERi0xLjcKJcK1wrYKCjEgMCBvYmoKPDwvVHlwZS9DYXRhbG9nL1BhZ2VzIDIgMCBSPj4KZW5kb2JqCgoyIDAgb2JqCjw8L1R5cGUvUGFnZXMvQ291bnQgMS9LaWRzWzQgMCBSXT4+CmVuZG9iagoKMyAwIG9iago8PC9Gb250PDwvaGVsdiA1IDAgUj4+Pj4KZW5kb2JqCgo0IDAgb2JqCjw8L1R5cGUvUGFnZS9NZWRpYUJveFswIDAgNTk1IDg0Ml0vUm90YXRlIDAvUmVzb3VyY2VzIDMgMCBSL1BhcmVudCAyIDAgUi9Db250ZW50c1s2IDAgUl0+PgplbmRvYmoKCjUgMCBvYmoKPDwvVHlwZS9Gb250L1N1YnR5cGUvVHlwZTEvQmFzZUZvbnQvSGVsdmV0aWNhL0VuY29kaW5nL1dpbkFuc2lFbmNvZGluZz4+CmVuZG9iagoKNiAwIG9iago8PC9MZW5ndGggODA+PgpzdHJlYW0KCnEKQlQKMSAwIDAgMSA3MiA3NzAgVG0KL2hlbHYgMTEgVGYgWzw1Mzc0NzU2NDc5NDk0MTIwNTQ2NTczNzQyMDUwNDQ0Nj5dVEoKRVQKUQoKZW5kc3RyZWFtCmVuZG9iagoKeHJlZgowIDcKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDE2IDAwMDAwIG4gCjAwMDAwMDAwNjIgMDAwMDAgbiAKMDAwMDAwMDExNCAwMDAwMCBuIAowMDAwMDAwMTU1IDAwMDAwIG4gCjAwMDAwMDAyNjIgMDAwMDAgbiAKMDAwMDAwMDM1MSAwMDAwMCBuIAoKdHJhaWxlcgo8PC9TaXplIDcvUm9vdCAxIDAgUi9JRFs8QzI4NDFFMTAxRjQ2MzBDMzhGMUNDMjkwQzM5MjBFQzI+PDE5NUY0RTIzNDg3NzBGNkI5MDFCQTBBMjE5QTczMUNDPl0+PgpzdGFydHhyZWYKNDgwCiUlRU9GCg==";

test("uploads a PDF and completes the grounded Q&A flow", async ({ page }) => {
  const pdfBytes = Buffer.from(TEST_PDF_BASE64, "base64");
  let uploadCount = 0;

  await page.addInitScript(() => {
    window.localStorage.setItem(
      "studyiacopilot.auth.v1",
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
  });

  await page.route("http://127.0.0.1:8000/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: {
          id: "user-1",
          email: "charles@example.com",
          full_name: "Charles Study",
          created_at: "2026-04-09T11:00:00.000Z",
        },
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/system/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        rag_mode: "full",
        gemini_model: "gemini-2.5-flash-lite",
        llm_configured: true,
        embedding_model_loaded: true,
        reranker_loaded: true,
        vector_search_enabled: true,
        documents_indexed: 0,
        workspace_data_available: false,
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/documents", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ documents: [] }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/upload", async (route) => {
    uploadCount += 1;
    const suffix = String(uploadCount);

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        doc_id: `doc-e2e-${suffix}`,
        name: uploadCount === 1 ? "Study Flow.pdf" : "Evidence Pack.pdf",
        chunks: 6,
        pages: 2,
        rag_mode: "full",
        vector_ready: true,
        uploaded_at: "2026-04-09T12:00:00.000Z",
        preview: uploadCount === 1
          ? "A generated preview used in the end-to-end browser flow."
          : "A second active PDF to validate multi-document answers.",
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/ask", async (route) => {
    const body = route.request().postDataJSON();

    expect(body.doc_ids).toEqual(["doc-e2e-1", "doc-e2e-2"]);

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        question: "Why portfolio-ready?",
        answer: "Grounded answer.",
        sources: [
          {
            id: 1,
            text: "This source backs the grounded answer and powers the viewer focus state.",
            doc_id: "doc-e2e-2",
            chunk_id: 1,
            page: 0,
          },
        ],
      }),
    });
  });

  await page.route(/http:\/\/127\.0\.0\.1:8000\/api\/pdf\/doc-e2e-(1|2)(\?token=.*)?/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/pdf",
      body: pdfBytes,
    });
  });

  await page.route(/http:\/\/127\.0\.0\.1:8000\/api\/documents\/doc-e2e-(1|2)/, async (route) => {
    const docId = route.request().url().split("/").pop();

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        doc_id: docId,
        removed: true,
        removed_files: [
          `backend/uploads/${docId}.pdf`,
          `backend/data/${docId}.json`,
        ],
      }),
    });
  });

  await page.goto("/");
  page.on("dialog", (dialog) => dialog.accept());

  await expect(page.getByText("Research workspace")).toBeVisible();
  await expect(page.getByText("Charles Study")).toBeVisible();
  await expect(page.getByText("Document library")).toBeVisible();
  await expect(page.getByText("Chat history")).toBeVisible();

  await page.getByRole("button", { name: "Documents" }).click();
  await expect(page.getByText("Document library")).toBeVisible();
  await expect(page.getByText("Upload your first PDF to build the workspace.")).toBeVisible();
  await expect(page.getByText("Chat history")).not.toBeVisible();

  await page.getByRole("button", { name: "Activity" }).click();
  await expect(page.getByText("Chat history")).toBeVisible();
  await expect(page.getByText("No document linked")).toBeVisible();
  await expect(page.getByText("Document library")).not.toBeVisible();

  await page.getByRole("button", { name: "Workspace" }).click();
  await expect(page.getByText("Document library")).toBeVisible();
  await expect(page.getByText("Chat history")).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles({
    name: "Study Flow.pdf",
    mimeType: "application/pdf",
    buffer: pdfBytes,
  });
  await page.locator('input[type="file"]').setInputFiles({
    name: "Evidence Pack.pdf",
    mimeType: "application/pdf",
    buffer: pdfBytes,
  });

  await expect(page.getByText(/indexed with 6 chunks across 2 pages/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence Pack.pdf" })).toBeVisible();
  await expect(page.getByText("2 active in this chat")).toBeVisible();

  await page
    .getByRole("textbox", { name: "Message" })
    .fill("Why portfolio-ready?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Grounded answer.")).toBeVisible();

  const sourceButton = page.locator('button:has-text("Source 1")').first();
  await sourceButton.click();

  await expect(page.getByRole("heading", { name: "Evidence Pack.pdf" })).toBeVisible();
  await expect(page.getByText("Focused on page 1")).toBeVisible();
  await expect(page.getByRole("button", { name: "Study Flow.pdf", exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Evidence Pack.pdf", exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Delete chat Study Flow.pdf" }).click();

  await expect(page.getByRole("heading", { name: "New conversation" })).toBeVisible();
  await expect(
    page.getByText("Welcome back. Upload PDFs, pick one or more documents, and ask anything about them."),
  ).toBeVisible();

  while ((await page.getByRole("button", { name: /Delete .*\.pdf/ }).count()) > 0) {
    await page.getByRole("button", { name: /Delete .*\.pdf/ }).first().click();
  }

  await expect(page.getByText("Upload your first PDF to build the workspace.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "No document open" })).toBeVisible();
});
