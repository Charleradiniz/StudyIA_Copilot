import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SidebarPanel from "./SidebarPanel";

const baseProps = {
  activeChatId: "chat-1",
  activeDocId: "doc-1",
  chats: [
    {
      id: "chat-1",
      title: "AI Portfolio Review",
      activeDocId: "doc-1",
      messages: [
        {
          id: "msg-1",
          role: "assistant" as const,
          content: "Upload a PDF to begin.",
        },
        {
          id: "msg-2",
          role: "user" as const,
          content: "Summarize the architecture.",
        },
      ],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    },
  ],
  documents: [
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
  ],
  clearingChats: false,
  clearingDocuments: false,
  deletingChatId: null,
  deletingDocId: null,
  uploading: false,
  onChangeNav: () => {},
  onClearChats: () => {},
  onClearDocuments: () => {},
  onDeleteChat: () => {},
  onDeleteDocument: () => {},
  onNewChat: () => {},
  onOpenUpload: () => {},
  onSelectChat: () => {},
  onSelectDocument: () => {},
};

describe("SidebarPanel", () => {
  it("shows both documents and chat history on workspace", () => {
    render(<SidebarPanel {...baseProps} activeNav="workspace" />);

    expect(screen.getByText("Document library")).toBeInTheDocument();
    expect(screen.getByText("Chat history")).toBeInTheDocument();
    expect(screen.getAllByText("Architecture Notes.pdf")).toHaveLength(2);
    expect(screen.getByText("11 chunks")).toBeInTheDocument();
    expect(screen.getByText("4 pages")).toBeInTheDocument();
    expect(screen.getByText("vector ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clear all" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete Architecture Notes.pdf" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clear chats" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete chat AI Portfolio Review" })).toBeInTheDocument();
  });

  it("shows only documents on the documents tab", () => {
    render(<SidebarPanel {...baseProps} activeNav="documents" />);

    expect(screen.getByText("Document library")).toBeInTheDocument();
    expect(screen.queryByText("Chat history")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete Architecture Notes.pdf" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Delete chat AI Portfolio Review" }),
    ).not.toBeInTheDocument();
  });

  it("shows only chat history on the activity tab", () => {
    render(<SidebarPanel {...baseProps} activeNav="activity" />);

    expect(screen.getByText("Chat history")).toBeInTheDocument();
    expect(screen.queryByText("Document library")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete chat AI Portfolio Review" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Delete Architecture Notes.pdf" }),
    ).not.toBeInTheDocument();
  });
});
