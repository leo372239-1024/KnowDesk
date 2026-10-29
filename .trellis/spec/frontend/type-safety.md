# Type Safety

> KnowDesk 前端的类型与运行时校验约定。目标：后端字段变更在前端编译期暴露。

## 类型系统

- TypeScript `strict: true`，禁止 `any`（确需时用 `unknown` + 类型守卫）。
- 类型集中放 `src/types/`，按业务域分文件（`chat.ts`、`document.ts`）。
- 与后端 Pydantic schema 对齐：字段名、可空性、枚举值保持一致，字段变更时两端同步。

## 运行时校验（Zod）

服务端返回的数据在边界处用 Zod 校验，而不是盲信 `as` 断言：

```tsx
const ChatMessageSchema = z.object({
  id: z.string(),
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  citations: z.array(CitationSchema),
});
type ChatMessage = z.infer<typeof ChatMessageSchema>;
```

- HTTP 响应在 `api/` 层用 `schema.parse(resp.data)` 校验后再返回给调用方。
- 表单输入用 Zod 校验（配合 AntD Form 的 `rules`），提交前拦非法值。

## 类型守卫与断言

- 用类型守卫（`isXxx`）窄化 `unknown`/联合类型，禁止裸 `as`。
- 仅在确知其来源可信（如已 parse 过）时才用 `as`，并注释理由。

## 反模式

- ❌ `const data = res.data as any`。
- ❌ 前端凭字符串猜字段（`resp["some_field"]`），应走 schema parse。
- ❌ 类型与后端 schema 漂移后不修正（会导致运行时才崩）。
- ❌ `!` 非空断言滥用掩盖真实可空性。
