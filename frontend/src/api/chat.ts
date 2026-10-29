import { client, getToken } from "./client";
import {
  ChatResponse,
  ChatResponseSchema,
  Citation,
  Conversation,
  MessageRecord,
  TraceDetail,
} from "../types/chat";

export async function ask(query: string, conversationId?: string): Promise<ChatResponse> {
  const { data } = await client.post("/chat/ask", { query, conversation_id: conversationId ?? null });
  return ChatResponseSchema.parse(data);
}

export interface StreamHandlers {
  onDelta: (chunk: string) => void;
  onDone: (done: {
    refused: boolean;
    citations: Citation[];
    evidence_score: number;
    trace_id: string;
    message_id?: string;
  }) => void;
  onError: (err: Error) => void;
}

/**
 * 流式问答：POST /chat/stream（SSE）。用 fetch + ReadableStream 消费。
 */
export async function streamAsk(
  query: string,
  handlers: StreamHandlers,
  conversationId?: string,
): Promise<void> {
  const token = getToken();
  const resp = await fetch("/api/v1/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: token ? `Bearer ${token}` : "",
    },
    body: JSON.stringify({ query, conversation_id: conversationId ?? null }),
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`请求失败：${resp.status}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  let traceId = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;
      const payload = JSON.parse(line.slice(6));
      if (payload.type === "start") {
        traceId = payload.trace_id;
      } else if (payload.type === "delta") {
        handlers.onDelta(payload.content);
      } else if (payload.type === "done") {
        handlers.onDone({
          refused: payload.refused,
          citations: payload.citations,
          evidence_score: payload.evidence_score,
          trace_id: traceId,
          message_id: payload.message_id,
        });
      }
    }
  }
}

export async function submitFeedback(
  messageId: string,
  rating: number,
  comment?: string,
): Promise<void> {
  await client.post("/chat/feedback", { message_id: messageId, rating, comment });
}

export async function listConversations(): Promise<Conversation[]> {
  const { data } = await client.get("/chat/conversations");
  return data;
}

export async function createConversation(title: string): Promise<Conversation> {
  const { data } = await client.post("/chat/conversations", { title });
  return data;
}

export async function listMessages(conversationId: string): Promise<MessageRecord[]> {
  const { data } = await client.get(`/chat/conversations/${conversationId}/messages`);
  return data;
}

export async function getTrace(traceId: string): Promise<TraceDetail> {
  const { data } = await client.get(`/observability/trace/${traceId}`);
  return data;
}
