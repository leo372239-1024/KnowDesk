# State Management

> KnowDesk 前端如何决定状态归属：服务端状态 / 全局 UI 状态 / 本地状态 / URL 状态。

## 状态四分类

| 分类 | 存哪 | 示例 |
|---|---|---|
| 服务端状态 | TanStack Query 缓存 | 文档列表、chunk 详情、评测结果、会话历史 |
| 全局 UI 状态 | Zustand | 侧栏折叠、全局 loading 遮罩、当前租户选择 |
| 本地状态 | `useState` | 表单输入、弹窗开关、组件内临时态 |
| URL 状态 | 路由参数 | 当前会话 id、当前页面/过滤条件（可分享、可回退） |

## 归属判定（先问再写）

新增状态时按此顺序决策：

1. 来自后端接口？→ React Query（不要存副本）。
2. 跨多个不相关组件共享且非服务端数据？→ Zustand。
3. 只被当前组件或子树用？→ `useState`/`useContext`。
4. 需要可分享/可回退（如当前会话、筛选条件）？→ URL query 参数。

## Zustand 使用约束

- 只放**少量**跨组件 UI 状态；slice 按领域拆分（如 `uiStore`）。
- store 里不放请求逻辑、不放服务端数据缓存（那是 React Query 的职责）。
- 派生数据用 selector（`useUiStore(s => s.collapsed)`）避免无关重渲染。

## 反模式

- ❌ 把服务端数据同时存进 React Query 和 Zustand（双份真相，会漂移）。
- ❌ 用全局 store 存表单临时态。
- ❌ 在组件里 `useEffect` 同步 props→state（React 反模式，用派生值）。
- ❌ 忽略 URL 状态，导致刷新/分享丢失上下文。
