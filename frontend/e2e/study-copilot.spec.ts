import { expect, test } from "@playwright/test";

const TEST_PDF_BASE64 =
  "JVBERi0xLjcKJcK1wrYKCjEgMCBvYmoKPDwvVHlwZS9DYXRhbG9nL1BhZ2VzIDIgMCBSPj4KZW5kb2JqCgoyIDAgb2JqCjw8L1R5cGUvUGFnZXMvQ291bnQgMS9LaWRzWzQgMCBSXT4+CmVuZG9iagoKMyAwIG9iago8PC9Gb250PDwvaGVsdiA1IDAgUj4+Pj4KZW5kb2JqCgo0IDAgb2JqCjw8L1R5cGUvUGFnZS9NZWRpYUJveFswIDAgNTk1IDg0Ml0vUm90YXRlIDAvUmVzb3VyY2VzIDMgMCBSL1BhcmVudCAyIDAgUi9Db250ZW50c1s2IDAgUl0+PgplbmRvYmoKCjUgMCBvYmoKPDwvVHlwZS9Gb250L1N1YnR5cGUvVHlwZTEvQmFzZUZvbnQvSGVsdmV0aWNhL0VuY29kaW5nL1dpbkFuc2lFbmNvZGluZz4+CmVuZG9iagoKNiAwIG9iago8PC9MZW5ndGggODA+PgpzdHJlYW0KCnEKQlQKMSAwIDAgMSA3MiA3NzAgVG0KL2hlbHYgMTEgVGYgWzw1Mzc0NzU2NDc5NDk0MTIwNTQ2NTczNzQyMDUwNDQ0Nj5dVEoKRVQKUQoKZW5kc3RyZWFtCmVuZG9iagoKeHJlZgowIDcKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDE2IDAwMDAwIG4gCjAwMDAwMDAwNjIgMDAwMDAgbiAKMDAwMDAwMDExNCAwMDAwMCBuIAowMDAwMDAwMTU1IDAwMDAwIG4gCjAwMDAwMDAyNjIgMDAwMDAgbiAKMDAwMDAwMDM1MSAwMDAwMCBuIAoKdHJhaWxlcgo8PC9TaXplIDcvUm9vdCAxIDAgUi9JRFs8QzI4NDFFMTAxRjQ2MzBDMzhGMUNDMjkwQzM5MjBFQzI+PDE5NUY0RTIzNDg3NzBGNkI5MDFCQTBBMjE5QTczMUNDPl0+PgpzdGFydHhyZWYKNDgwCiUlRU9GCg==";

test("uploads a PDF and completes the grounded Q&A flow", async ({ page }) => {
  const pdfBytes = Buffer.from(TEST_PDF_BASE64, "base64");

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
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        doc_id: "doc-e2e",
        name: "Study Flow.pdf",
        chunks: 6,
        pages: 2,
        rag_mode: "full",
        vector_ready: true,
        uploaded_at: "2026-04-09T12:00:00.000Z",
        preview: "A generated preview used in the end-to-end browser flow.",
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/ask", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        question: "What makes this product portfolio-ready?",
        answer: "Grounded answer.",
        sources: [
          {
            id: 1,
            text: "This source backs the grounded answer and powers the viewer focus state.",
            doc_id: "doc-e2e",
            chunk_id: 1,
            page: 0,
          },
        ],
      }),
    });
  });

  await page.route("http://127.0.0.1:8000/api/pdf/doc-e2e", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/pdf",
      body: pdfBytes,
    });
  });

  await page.goto("/");

  await expect(page.getByText("Research workspace")).toBeVisible();
  await expect(page.getByText("Platform readiness")).toBeVisible();
  await expect(page.getByText("Vector")).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles({
    name: "Study Flow.pdf",
    mimeType: "application/pdf",
    buffer: pdfBytes,
  });

  await expect(page.getByText(/indexed with 6 chunks across 2 pages/i)).toBeVisible();

  await page
    .getByRole("textbox", { name: "Message" })
    .fill("What makes this product portfolio-ready?");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("Grounded answer.")).toBeVisible();

  const sourceButton = page.locator('button:has-text("Source 1")').first();
  await sourceButton.click();

  await expect(page.getByText("Focused on page 1")).toBeVisible();
});
