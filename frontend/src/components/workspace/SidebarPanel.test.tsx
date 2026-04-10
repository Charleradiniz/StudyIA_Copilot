import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SidebarPanel from "./SidebarPanel";

describe("SidebarPanel", () => {
  it("renders readiness signals and indexed document metadata", () => {
    render(
      <SidebarPanel
        activeChatId="chat-1"
        activeDocId="doc-1"
        activeNav="workspace"
        chats={[
          {
            id: "chat-1",
            title: "AI Portfolio Review",
            activeDocId: "doc-1",
            messages: [
              {
                id: "msg-1",
                role: "assistant",
                content: "Upload a PDF to begin.",
              },
              {
                id: "msg-2",
                role: "user",
                content: "Summarize the architecture.",
              },
            ],
            createdAt: Date.now(),
            updatedAt: Date.now(),
          },
        ]}
        documents={[
          {
            id: "doc-1",
            name: "Architecture Notes.pdf",
            uploadedAt: Date.now(),
            chunkCount: 11,
            pageCount: 4,
            ragMode: "full",
            vectorReady: true,
            preview: "This document explains the architecture, retrieval path, and UX choices.",
          },
        ]}
        systemStatus={{
          status: "ok",
          ragMode: "full",
          geminiModel: "gemini-2.5-flash-lite",
          llmConfigured: true,
          embeddingModelLoaded: true,
          rerankerLoaded: true,
          vectorSearchEnabled: true,
          documentsIndexed: 1,
          workspaceDataAvailable: true,
        }}
        clearingChats={false}
        clearingDocuments={false}
        deletingChatId={null}
        deletingDocId={null}
        uploading={false}
        onChangeNav={() => {}}
        onClearChats={() => {}}
        onClearDocuments={() => {}}
        onDeleteChat={() => {}}
        onDeleteDocument={() => {}}
        onNewChat={() => {}}
        onOpenUpload={() => {}}
        onSelectChat={() => {}}
        onSelectDocument={() => {}}
      />,
    );

    expect(screen.getByText("Platform readiness")).toBeInTheDocument();
    expect(screen.getByText("Configured")).toBeInTheDocument();
    expect(screen.getByText("Vector")).toBeInTheDocument();
    expect(screen.getAllByText("Architecture Notes.pdf")).toHaveLength(2);
    expect(screen.getByText("11 chunks")).toBeInTheDocument();
    expect(screen.getByText("4 pages")).toBeInTheDocument();
    expect(screen.getByText("vector ready")).toBeInTheDocument();
    expect(screen.getByText(/Model: gemini-2\.5-flash-lite/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clear all" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete Architecture Notes.pdf" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clear chats" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete chat AI Portfolio Review" })).toBeInTheDocument();
  });
});
