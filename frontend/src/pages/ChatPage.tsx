import { useRef, useState } from "react";
import {
  Alert,
  Button,
  Empty,
  Input,
  List,
  Space,
  Spin,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  DislikeOutlined,
  LikeOutlined,
  PlusOutlined,
  SendOutlined,
  ProfileOutlined,
} from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useChat } from "../hooks/useChat";
import { useConversations } from "../hooks/useConversations";
import { Citation } from "../components/Citation";
import { TracePanel } from "../components/TracePanel";
import { ChatMessage } from "../types/chat";

function AssistantMessage({
  msg,
  onFeedback,
  onTrace,
}: {
  msg: ChatMessage;
  onFeedback: (rating: number) => void;
  onTrace: () => void;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 16 }}>
      <div style={{ maxWidth: "82%", padding: "12px 16px", borderRadius: 8, background: "#f5f5f5" }}>
        {msg.refused ? (
          <Alert type="warning" showIcon message={msg.content} />
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
        )}
        {msg.citations.length > 0 && (
          <Space wrap style={{ marginTop: 8 }}>
            {msg.citations.map((c) => (
              <Citation key={c.chunk_id} citation={c} />
            ))}
          </Space>
        )}
        {(msg.message_id || msg.trace_id) && (
          <Space style={{ marginTop: 8, width: "100%", justifyContent: "flex-end" }}>
            {msg.trace_id && (
              <Tooltip title="查看调用链路">
                <Button type="text" size="small" icon={<ProfileOutlined />} onClick={onTrace}>
                  Trace
                </Button>
              </Tooltip>
            )}
            {msg.message_id && (
              <Space size={4}>
                <Button
                  type="text"
                  size="small"
                  icon={<LikeOutlined />}
                  style={{ color: msg.feedback === 1 ? "#1677ff" : undefined }}
                  onClick={() => onFeedback(1)}
                />
                <Button
                  type="text"
                  size="small"
                  icon={<DislikeOutlined />}
                  style={{ color: msg.feedback === -1 ? "#ff4d4f" : undefined }}
                  onClick={() => onFeedback(-1)}
                />
              </Space>
            )}
          </Space>
        )}
      </div>
    </div>
  );
}

export default function ChatPage() {
  const { messages, loading, send, feedback, reset, load } = useChat();
  const { conversations, currentId, setCurrentId, select, create } = useConversations();
  const [input, setInput] = useState("");
  const [traceId, setTraceId] = useState<string | null>(null);
  const [traceOpen, setTraceOpen] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  const handleSend = async () => {
    const q = input.trim();
    if (!q) return;
    setInput("");
    await send(q, currentId ?? undefined);
  };

  const handleSelectConversation = async (id: string) => {
    const msgs = await select(id);
    load(msgs);
  };

  const handleNewConversation = async () => {
    await create("新对话");
    reset();
    setCurrentId(null);
  };

  const handleFeedback = (msg: ChatMessage, rating: number) => {
    if (!msg.message_id) return;
    void feedback(msg.message_id, rating);
    message.success(rating === 1 ? "已反馈：有帮助" : "已反馈：待改进");
  };

  return (
    <div style={{ display: "flex", gap: 16, height: "calc(100vh - 112px)" }}>
      {/* 会话侧栏 */}
      <div style={{ width: 240, borderRight: "1px solid #f0f0f0", display: "flex", flexDirection: "column" }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => void handleNewConversation()} block>
          新对话
        </Button>
        <div style={{ flex: 1, overflowY: "auto", marginTop: 8 }}>
          <List
            size="small"
            dataSource={conversations}
            renderItem={(conv) => (
              <List.Item
                style={{
                  cursor: "pointer",
                  background: conv.id === currentId ? "#e6f4ff" : undefined,
                  padding: "8px 12px",
                }}
                onClick={() => void handleSelectConversation(conv.id)}
              >
                <Typography.Text ellipsis>{conv.title}</Typography.Text>
              </List.Item>
            )}
          />
        </div>
      </div>

      {/* 问答区 */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <div ref={listRef} style={{ flex: 1, overflowY: "auto", padding: 8 }}>
          {messages.length === 0 && (
            <Empty description="输入问题开始问答，例如：XG-2000A 的额定电流是多少？" style={{ marginTop: 80 }} />
          )}
          {messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
                <div style={{ maxWidth: "82%", padding: "12px 16px", borderRadius: 8, background: "#e6f4ff" }}>
                  {m.content}
                </div>
              </div>
            ) : (
              <AssistantMessage
                key={m.id}
                msg={m}
                onFeedback={(rating) => handleFeedback(m, rating)}
                onTrace={() => {
                  setTraceId(m.trace_id ?? null);
                  setTraceOpen(true);
                }}
              />
            ),
          )}
          {loading && <Spin />}
        </div>
        <Space.Compact style={{ width: "100%" }}>
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                void handleSend();
              }
            }}
            placeholder="输入你的问题，Shift+Enter 换行"
            autoSize={{ minRows: 2, maxRows: 6 }}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={() => void handleSend()} loading={loading}>
            发送
          </Button>
        </Space.Compact>
      </div>

      <TracePanel traceId={traceId} open={traceOpen} onClose={() => setTraceOpen(false)} />
    </div>
  );
}
