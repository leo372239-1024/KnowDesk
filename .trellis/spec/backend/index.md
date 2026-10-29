# Backend Development Guidelines

> KnowDesk 后端的编码规范。所有后端代码（`backend/` 目录）必须遵循本目录下的规范。

## 技术栈基线（已确定）

| 层 | 选型 | 备注 |
|---|---|---|
| 语言 | Python 3.11+ | 3.12 可选，CI 以 3.11 为准 |
| Web 框架 | FastAPI + Uvicorn | 异步优先，REST + WebSocket |
| 依赖管理 | uv（`pyproject.toml`） | 锁文件 `uv.lock` 入库 |
| ORM | SQLAlchemy 2.0（async + asyncpg） | 不用同步 session |
| 迁移 | Alembic | 迁移脚本必须可正反执行 |
| 数据校验 | Pydantic v2 | 请求/响应/Agent 状态统一走 Pydantic |
| Agent 编排 | LangGraph | 显式状态机，可回放可观测 |
| 关系型数据库 | PostgreSQL 16（含 pgvector） | 元数据、审计、评测、ACL |
| 向量库 | Milvus（生产）/ pgvector（单机兜底） | 通过统一 `VectorStore` 接口抽象 |
| 关键词检索 | Elasticsearch BM25 | MVP 可用 PG 全文检索兜底 |
| 缓存 | Redis | 语义缓存、短期记忆、限流 |
| 异步任务 | Celery + Redis broker | 文档解析/索引是耗时任务 |
| 日志 | structlog（JSON） | 结构化 + trace_id 贯穿 |

**暂缓（系统升级项，MVP 不实现）**：Kafka/RocketMQ、SkyWalking、ELK、K8s/Istio/Helm、语义缓存、GraphRAG 全量。这些不得在 MVP 代码里提前引入依赖。

## 架构原则

1. **分层单向依赖**：`api → services → (agent | retrieval | ingestion)`，`models/schemas/core` 是横切基础，不被上层反向依赖。
2. **检索与生成解耦**：`retrieval/` 是可独立评测的子系统，不 import `agent/`。
3. **可观测性一等公民**：每次问答、每次 LLM/工具调用都必须落 trace（`trace_id` + `span_id` + 阶段耗时），可离线重放。
4. **安全横切（X1）**：ACL 在检索阶段前置过滤（非生成后脱敏）；工具调用透传用户身份而非 Agent 身份；审计日志 180 天。
5. **引用可溯源**：每个事实断言必须绑定 `[doc_id#chunk_id]`，无引用的断言不输出。

## 目录

| 文件 | 主题 |
|---|---|
| [Directory Structure](./directory-structure.md) | 分层目录与模块职责 |
| [Database Guidelines](./database-guidelines.md) | ORM、迁移、命名、幂等、ACL |
| [Error Handling](./error-handling.md) | 异常体系、降级、API 错误格式 |
| [Logging Guidelines](./logging-guidelines.md) | 结构化日志、trace、审计、脱敏 |
| [Quality Guidelines](./quality-guidelines.md) | 代码标准、测试、Agent 特有质量闸门 |
