# Hook Guidelines

> KnowDesk 前端自定义 hook 的约定与数据获取模式。

## 数据获取（一律 React Query）

所有服务端数据经 TanStack Query 封装成 hook，业务组件不手写 `useEffect` + 请求：

```tsx
export function useDocuments(tenantId: string) {
  return useQuery({
    queryKey: ["documents", tenantId],
    queryFn: () => api.documents.list(tenantId),
  });
}
```

- `queryKey` 采用 `[域, 主键/过滤条件]` 数组，保证缓存可失效。
- 写操作用 `useMutation`，成功后 `queryClient.invalidateQueries(...)` 使相关列表失效。
- 请求错误统一在 `api/client.ts` 拦截器处理（鉴权失效跳登录、错误码转提示），hook 内不重复 try/catch。

## 流式问答（WebSocket）

问答流式输出封装为专用 hook，管理连接生命周期与增量状态：

```tsx
export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  // 内部管理 WS 连接、心跳、重连、逐 token 追加
  return { messages, streaming, send, abort };
}
```

- WS 断开自动重连（指数退避），重连后恢复会话上下文。
- `abort()` 必须真实终止服务端生成（发取消帧），而非仅前端丢弃。
- 流式增量追加要处理 markdown 半截 token 的渲染（保留原始 buffer，渲染时截断到安全边界）。

## 命名与结构

- 自定义 hook 一律 `use` 前缀，文件名 `useXxx.ts`。
- hook 内部若用 `useState`/`useEffect` 组合，优先复用已有 hook，避免重复造轮子（见 guides）。
- hook 只做「状态 + 副作用」，不返回 JSX；返回对象字段稳定，调用方按需解构。

## 反模式

- ❌ 在组件里 `useEffect(() => { fetch().then(setState) }, [])` 手写数据获取。
- ❌ hook 内 `console.log` 泄漏（用统一的日志/上报工具）。
- ❌ 把服务端数据复制进 Zustand（重复状态源，见 state-management）。
- ❌ 忘记清理 WS/定时器（hook 返回的 cleanup 必须处理）。
- ❌ hook 返回 `any`。
