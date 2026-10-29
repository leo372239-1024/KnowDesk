# Logging Guidelines

> KnowDesk 用 structlog 输出结构化 JSON。日志同时服务三件事：排障、可观测性（trace）、审计（X1 合规）。

## 装配

- 全局在 `app/core/logging.py` 装配 structlog，业务代码只 `logger = structlog.get_logger()`。
- 输出统一 JSON（生产）；本地开发可切换到彩色 console。
- 日志写 stdout（容器环境由编排层收集），不写本地文件轮转。

## 必需字段

每条日志至少携带（在装配层绑定，不靠调用者手传）：

| 字段 | 说明 |
|---|---|
| `timestamp` | ISO8601 UTC |
| `level` | debug/info/warning/error |
| `logger` | 模块路径 |
| `trace_id` | 一次问答的全局链路 ID（从请求上下文注入） |
| `span_id` | 当前阶段/节点 ID |
| `event` | 事件名 |

## trace_id 贯穿（可观测性核心）

- 每次问答入口生成 `trace_id`（UUID），经 contextvar 注入到整个 Agent 执行链路。
- LangGraph 每个节点、每次 LLM 调用、每次检索、每次 rerank 都是一个 span，落日志并写 `observability.py` 的 trace 表。
- 关键 span 必须记录：**阶段名、耗时、prompt_tokens/completion_tokens、top-k doc_id、拒答原因**（对应 P6 特征补齐要求）。

```python
# 正确：经上下文绑定，节点内无需手传 trace_id
logger.info("retrieve.completed", stage="retrieve", elapsed_ms=42, top_k=8)
```

## 日志级别

| 级别 | 用途 |
|---|---|
| `debug` | 分块细节、召回候选全量（本地排障） |
| `info` | 关键节点进出、问答完成、索引完成 |
| `warning` | 降级发生、重试、解析质量告警、缓存未命中但可恢复 |
| `error` | 异常、检索/模型不可用、解析门禁拦截 |

## 审计日志（X1 必做，与普通日志分离）

审计走独立的 `audit_logs` 表（见 database 规范），**不是**普通日志。每次问答必须记录：

- 谁（user_id）· 何时 · 问了什么 · 命中了哪些 doc_id · 生成答案 · 引用列表 · 是否拒答。
- 保留 180 天，只追加，可导出报表。

## 禁止记录（脱敏硬要求）

以下内容**严禁**进入日志或 trace：

- 用户密码、JWT token、API key。
- 完整文档正文（PII 未脱敏前）。
- 员工的身份证/薪资/联系方式等 PII。

**规则**：入库前文档先过 PII 脱敏（`core/security`），日志里只记 `doc_id` 不记原文；确需记原文片段时截断并标 `redacted`。

## 反模式

- ❌ `print(...)` 代替 logger。
- ❌ 日志里拼 `f-string` 塞敏感值；用 structlog 的 key=value 参数绑定。
- ❌ 每层自己 `import logging; logging.basicConfig(...)` 重复初始化。
- ❌ 用日志记录大对象/全量向量。
- ❌ trace_id 用全局变量（多并发会串号）；必须 contextvar 隔离。
