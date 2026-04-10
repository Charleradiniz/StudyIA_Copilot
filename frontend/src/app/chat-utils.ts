import type { ChatMessage, ChatSession } from "./types";

export function createId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function createAssistantMessage(
  content: string,
  options?: Partial<Pick<ChatMessage, "sources" | "streaming">>,
): ChatMessage {
  return {
    id: createId(),
    role: "assistant",
    content,
    sources: options?.sources,
    streaming: options?.streaming,
  };
}

export function createChat(title = "New conversation"): ChatSession {
  const now = Date.now();

  return {
    id: createId(),
    title,
    activeDocIds: [],
    createdAt: now,
    updatedAt: now,
    messages: [
      createAssistantMessage(
        "Welcome back. Upload PDFs, pick one or more documents, and ask anything about them.",
      ),
    ],
  };
}

export function getChatPreview(messages: ChatMessage[]) {
  const firstUserMessage = messages.find((message) => message.role === "user");
  return firstUserMessage?.content ?? "Waiting for your first question";
}

export function formatRelativeTime(timestamp: number) {
  const diff = Date.now() - timestamp;

  if (diff < 60_000) return "Just now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}
