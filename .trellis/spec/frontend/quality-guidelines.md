# Quality Guidelines

> KnowDesk 前端的代码质量、测试与禁用模式。

## 风格与 lint

- ESLint + Prettier 统一，`npm run lint` / `typecheck`（`tsc --noEmit`）在提交前必须通过。
- 关键规则：`@typescript-eslint/no-explicit-any` 报错、`react-hooks/exhaustive-deps` 报错、未使用变量报错。
- 组件、hook、类型文件按 directory-structure 的命名约定组织。

## 测试（Vitest + RTL，健壮性验证）

用户约束：只做健壮性验证，不做高并发/压测。前端测试聚焦：

- **组件**：引用组件（点击跳转、高亮）、拒答提示、流式答案渲染（含半截 token 不崩）。
- **hook**：`useChat` 的 WS 断线重连、`abort` 终止、`useDocuments` 的缓存失效。
- **类型边界**：Zod schema 对脏数据的拒绝（非法响应不崩溃）。

- 交互断言从用户视角写（`screen.getByRole`），不依赖 DOM 结构细节。
- mock 后端接口，测试离线可跑、可重复。

## 可访问性与体验

- 所有图标按钮 `aria-label`；流式答案状态用 `aria-live` 播报。
- 引用点击后能跳转到原文高亮（核心业务体验，必须有测试）。

## 反模式

- ❌ `any`、`// @ts-ignore`、`eslint-disable` 无理由滥用。
- ❌ 提交未跑 `typecheck` 的代码（类型错误视为失败）。
- ❌ 用 `dangerouslySetInnerHTML` 渲染 LLM 输出（必须走 sanitize + markdown 渲染器，防 XSS）。
- ❌ 组件里写内联 `style` 魔法数字。
- ❌ 复制粘贴大段相似组件（先看 components/ 是否可复用）。
