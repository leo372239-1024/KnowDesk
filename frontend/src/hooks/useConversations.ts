import { useCallback, useEffect, useState } from "react";
import { createConversation, listConversations, listMessages } from "../api/chat";
import { ChatMessage, Conversation, MessageRecord } from "../types/chat";

let localId = 0;

function recordToMessage(r: MessageRecord): ChatMessage {
  return {
    id: `server-${++localId}`,
    role: r.role,
    content: r.content,
    citations: r.citations,
    refused: r.refused,
    message_id: r.id,
    feedback: r.feedback,
  };
}

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [loadingMessages, setLoadingMessages] = useState(false);

  const refreshList = useCallback(async () => {
    const list = await listConversations();
    setConversations(list);
  }, []);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  const select = useCallback(
    async (conversationId: string): Promise<ChatMessage[]> => {
      setCurrentId(conversationId);
      setLoadingMessages(true);
      try {
        const records = await listMessages(conversationId);
        return records.map(recordToMessage);
      } finally {
        setLoadingMessages(false);
      }
    },
    [],
  );

  const create = useCallback(async (title: string): Promise<Conversation> => {
    const conv = await createConversation(title);
    await refreshList();
    setCurrentId(conv.id);
    return conv;
  }, [refreshList]);

  return { conversations, currentId, setCurrentId, select, create, loadingMessages, refreshList };
}
