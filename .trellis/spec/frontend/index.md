# Frontend Development Guidelines

> KnowDesk 前端的编码规范。所有前端代码（`frontend/` 目录）必须遵循本目录下的规范。

## 技术栈基线（已确定）

| 层 | 选型 | 备注 |
|---|---|---|
| 框架 | React 18 + TypeScript | 函数组件 + Hooks，不用 class 组件 |
| 构建 | Vite | 开发/生产统一 |
| UI 组件库 | Ant Design 5 | 主题走 ConfigProvider token |
| 服务端状态 | TanStack Query (React Query) | 请求缓存、重试、失效 |
| 全局状态 | Zustand | 仅放少量跨组件 UI 状态 |
| 运行时校验 | Zod | 与后端 schema 对齐 |
| HTTP | axios | 统一拦截器注入 token |
| 流式输出 | WebSocket | 问答流式渲染 |
| 测试 | Vitest + React Testing Library | 组件与 hook 测试 |
| 风格 | ESLint + Prettier | 见 quality |

## 架构原则

1. **服务端数据一律走 React Query**，不手写 `useEffect` 发请求、不手写缓存。
2. **Zustand 只放 UI 状态**（如侧栏折叠、当前选中文档），不放服务端数据副本。
3. **类型单一来源**：后端 Pydantic schema 与前端 Zod/TS 类型通过约定对齐，前端不凭字符串猜字段。
4. **流式问答**用 WebSocket 增量渲染（markdown 逐 token 追加 + 引用实时高亮）。

## 目录

| 文件 | 主题 |
|---|---|
| [Directory Structure](./directory-structure.md) | 目录组织 |
| [Component Guidelines](./component-guidelines.md) | 组件模式、props、样式 |
| [Hook Guidelines](./hook-guidelines.md) | 自定义 hook、数据获取 |
| [State Management](./state-management.md) | 状态分类与归属 |
| [Type Safety](./type-safety.md) | 类型与运行时校验 |
| [Quality Guidelines](./quality-guidelines.md) | lint、测试、a11y、禁用模式 |
