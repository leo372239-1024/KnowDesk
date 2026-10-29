import { useCallback, useRef, useState } from "react";
import { streamAsk, submitFeedback } from "../api/chat";
import { ChatMessage } from "../types/chat";

let idCounter = 0;
const nextId = () => `msg-${++idCounter}`;

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const messagesRef = useRef<ChatMessage[]>([]);
  messagesRef.current = messages;

  const patch = useCallback((id: string, updater: (m: ChatMessage) => ChatMessage) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? updater(m) : m)));
  }, []);

  const send = useCallback(
    async (query: string, conversationId?: string) => {
      const userMsg: ChatMessage = {
        id: nextId(),
        role: "user",
        content: query,
        citations: [],
        refused: false,
      };
      const assistantId = nextId();
      setMessages((prev) => [
        ...prev,
        userMsg,
        { id: assistantId, role: "assistant", content: "", citations: [], refused: false },
      ]);
      setLoading(true);
      try {
        await streamAsk(
          query,
          {
            onDelta: (chunk) =>
              patch(assistantId, (m) => ({ ...m, content: m.content + chunk })),
            onDone: ({ refused, citations, trace_id, message_id }) =>
              patch(assistantId, (m) => ({ ...m, refused, citations, trace_id, message_id })),
            onError: (err) =>
              patch(assistantId, (m) => ({ ...m, content: `请求失败：${err.message}`, refused: true })),
          },
          conversationId,
        );
      } catch (e) {
        const msg = e instanceof Error ? e.message : "请求失败";
        patch(assistantId, (m) => ({ ...m, content: `请求失败：${msg}`, refused: true }));
      } finally {
        setLoading(false);
      }
    },
    [patch],
  );

  const feedback = useCallback(async (messageId: string, rating: number) => {
    await submitFeedback(messageId, rating);
    // 找到本地 message_id 匹配的消息并更新 feedback 标记
    setMessages((prev) =>
      prev.map((m) => (m.message_id === messageId ? { ...m, feedback: rating } : m)),
    );
  }, []);

  const reset = useCallback(() => setMessages([]), []);

  const load = useCallback((msgs: ChatMessage[]) => setMessages(msgs), []);

  return { messages, loading, send, feedback, reset, load };
}
