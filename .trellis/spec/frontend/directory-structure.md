# Directory Structure

> KnowDesk 前端如何组织代码。按「页面 / 功能模块 / 共享」三层划分。

## 目录布局

```
frontend/
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
└── src/
    ├── main.tsx                 # 入口：挂载 QueryClientProvider、Router、ConfigProvider
    ├── App.tsx                  # 路由表与全局布局
    ├── api/                     # 后端接口封装（每域一个文件）
    │   ├── client.ts            # axios 实例 + 拦截器
    │   ├── chat.ts              # 问答（含 WS 客户端）
    │   ├── documents.ts
    │   └── eval.ts
    ├── types/                   # 与后端对齐的 TS 类型 + Zod schema
    │   ├── chat.ts
    │   └── document.ts
    ├── hooks/                   # 自定义 hook（use* 命名）
    │   ├── useChat.ts           # 问答流式 hook
    │   └── useDocuments.ts      # React Query 封装
    ├── store/                   # Zustand store
    │   └── uiStore.ts
    ├── pages/                   # 路由级页面
    │   ├── ChatPage/
    │   ├── DocumentsPage/
    │   └── EvalPage/
    ├── components/              # 跨页面复用的通用组件
    │   ├── Citation/            # 引用高亮/跳转
    │   ├── TraceViewer/         # 可观测性 trace 面板
    │   └── DocumentUpload/
    ├── features/                # 某功能专属但非路由级的模块（可选）
    ├── utils/                   # 纯函数工具
    └── styles/                  # 全局样式与主题 token
```

## 组织规则

- **页面（`pages/`）**：对应路由，组合 feature 组件 + 通用组件；页面内只做编排，不写复杂业务 hook。
- **通用组件（`components/`）**：跨页面复用、无业务领域绑定（如 `Citation`、`TraceViewer`）。
- **功能模块（`features/`）**：与某一业务域强绑定但被多处使用；每个 feature 内可自含 `components/`、`hooks/`、`api/`。
- **`api/`**：所有网络请求集中，业务组件不直接 `fetch`/`axios`。

## 命名约定

| 对象 | 规则 | 示例 |
|---|---|---|
| 组件文件 | PascalCase `.tsx` | `Citation.tsx` |
| hook 文件 | `useXxx.ts` | `useChat.ts` |
| 类型/schema | 域分类 `.ts` | `types/chat.ts` |
| 非组件工具 | camelCase `.ts` | `formatToken.ts` |
| 组件导出 | 命名导出，禁 default | `export function Citation()` |
| 页面目录 | PascalCase | `ChatPage/` |

## 反模式

- ❌ 组件内直接 `axios`/`fetch`（必须经 `api/`）。
- ❌ 页面目录与通用组件目录混放（先判断复用性再落位）。
- ❌ default export（用命名导出，便于重构与 tree-shaking）。
- ❌ 在 `utils/` 里放有副作用/依赖 React 的代码。
