# implement.md — KnowDesk MVP 执行清单

> 有序实现步骤。每个子任务产出可运行、可验证的增量。完成即跑验证命令，不跳步。

## 执行顺序总览

```
S1 脚手架 → S2 数据层 → S3 入库Pipeline → S4 检索子系统 → S5 Agent编排
  → S6 API层 → S7 前端 → S8 评测harness → S9 安全治理(贯穿) → S10 健壮性验证
```

## S1 项目脚手架

**产出**：`backend/`、`frontend/` 目录、依赖清单、`docker-compose.yml`、`.env.example`、根 `README.md`。

- `backend/pyproject.toml`（uv 管理，依赖：fastapi、uvicorn、sqlalchemy[asyncio]、asyncpg、alembic、pydantic-settings、pymilvus、rank_bm25、structlog、celery、redis、httpx、python-multipart、passlib、pyjwt、sentence-transformers/FlagEmbedding、pytest、pytest-asyncio、ruff）
- `frontend/package.json`（react、react-dom、antd、@tanstack/react-query、zustand、zod、axios、react-router-dom、react-markdown、vite、typescript、eslint、prettier、vitest、@testing-library/react）
- `docker-compose.yml`：postgres(16+pgvector)、milvus-standalone、minio、redis（本地开发编排）
- `backend/app/main.py` 空应用 + `app/core/config.py`

**验证**：`uv sync` / `npm install` 无报错；`docker compose up -d postgres redis` 可起。

## S2 数据层

**产出**：`app/models/`（users/documents/chunks/conversations/messages/audit_logs/eval_datasets/eval_runs/trace_records）、`alembic/` 迁移、`app/schemas/` 基础 schema。

- ORM 模型按 design.md §3 字段定义；UUID 主键；`documents.content_hash` 唯一、`chunks.(document_id, chunk_index)` 联合唯一。
- Alembic 首版迁移 + seed 脚本（测试用户、样例文档元数据）。

**验证**：`alembic upgrade head` 成功；`pytest tests/unit/test_models.py` 通过。

## S3 入库 Pipeline

**产出**：`app/ingestion/`（parser/chunker/embedder/pipeline）、`app/tasks/`（Celery 解析任务）。

- `parser.py`：多格式路由（PDF 用 pypdf/pdfplumber、Word 用 python-docx、MD 纯文本、Excel 用 openpyxl）。
- 解析质量门禁：表格错行/页序倒置/低置信度 → `DocumentParseError` 拒入。
- `chunker.py`：结构化分块（标题树 + 表格独立成块全量保留表头 + 条款级），chunk 带 `section_path/page_num/bbox/chunk_type`。
- `embedder.py`：`BaseEmbedding` 抽象（BGE-M3 实现 + fake 实现用于测试）。
- `pipeline.py`：解析→门禁→分块→embedding→写 PG + Milvus + BM25。
- PII 脱敏（`core/security.py`）。

**验证**：`pytest tests/unit/test_chunker.py`（表格不腰斩、不跨章节、条款号对齐）；`pytest tests/integration/test_ingestion.py`（上传→入库→可检索）。

## S4 检索子系统

**产出**：`app/retrieval/`（vector_store/bm25/rerank/fusion）。

- `vector_store.py`：`BaseVector` 抽象 + Milvus 实现（collection `chunks`，dense+sparse 字段 + ACL 过滤）。
- `bm25.py`：内存 BM25（rank_bm25）+ 中文分词。
- `rerank.py`：bge-reranker 调用 + 超时降级纯 RRF。
- `fusion.py`：RRF 融合。
- ACL 前置过滤（tenant_id/department/acl_tags pre-filter）。

**验证**：`pytest tests/unit/test_fusion.py`（RRF 正确）；`pytest tests/integration/test_retrieval.py`（三路召回 + ACL 过滤）。

## S5 Agent 编排

**产出**：`app/agent/`（graph/state/nodes/tools）。

- `state.py`：AgentState（query/rewritten_queries/plan/retrieved/evidence_score/answer/citations/refused/rounds）。
- `nodes.py`：understand（指代消解/术语归一/拆子问题/HyDE）、plan、retrieve、judge（证据门控）、generate（强制引用）、refuse。
- `graph.py`：LangGraph 状态机 + 条件边（充分→generate；不足≤2→rewrite；不足+知识库无→web_search；仍不足→refuse）+ 循环熔断（最大步数/Token/时长）。
- `tools.py`：`retrieve_kb`、`web_search` 工具定义（透传 user_id）。

**验证**：`pytest tests/unit/test_graph.py`（状态流转、拒答分支、熔断）；`pytest tests/integration/test_agent.py`（问答全链路，mock LLM）。

## S6 API 层

**产出**：`app/api/`（deps/auth/documents/chat/eval）+ `app/services/`（chat_service/document_service）+ `app/core/observability.py`（trace）。

- `auth.py`：JWT 双令牌（access+refresh）、登录/刷新。
- `documents.py`：上传（触发 Celery）、解析状态查询、文档列表。
- `chat.py`：REST 问答 + WS 流式；生成 trace_id；审计落库。
- `eval.py`：评测集管理 + 触发跑分。
- `observability.py`：trace span 落库（阶段/耗时/token/top-k/拒答原因）。

**验证**：`pytest tests/integration/test_api.py`（auth/chat/documents/eval 路由）；`uv run uvicorn app.main:app` 启动，`/docs` 可访问。

## S7 前端

**产出**：`frontend/src/`（api/types/hooks/store/pages/components）。

- 四页：`ChatPage`（流式问答 + 引用高亮 + 拒答提示）、`DocumentsPage`（上传/解析状态/列表）、`EvalPage`（跑分结果）、`TracePage`（链路回放）。
- `api/client.ts`（axios + token 注入 + 错误码转提示）、`chat.ts`（WS 客户端）。
- `components/Citation`（分组高亮跳转）、`components/TraceViewer`。
- markdown 渲染（react-markdown + sanitize 防 XSS）。

**验证**：`npm run typecheck` / `npm run lint` 通过；`npm run test` 组件测试通过；`npm run dev` 可访问四页。

## S8 评测 harness

**产出**：`app/eval/`（dataset/metrics/runner）+ `backend/data/golden_dataset.jsonl`（≥50 题）。

- `dataset.py`：Golden Dataset 加载/校验（5 类任务 + 不可答样本）。
- `metrics.py`：accuracy/faithfulness/refusal/recall/hallucination 计算（checklist 要点法）。
- `runner.py`：`run_eval.py` 入口，输出指标表 + 存 `eval_runs/{date}.json`。
- 失败模式 6 类归因。

**验证**：`python -m app.eval.runner --dataset data/golden_dataset.jsonl` 跑通并输出指标。

## S9 安全治理（贯穿各层）

**产出**：`core/security.py`（JWT/ACL/脱敏）、注入防御、审计、降级链。

- ACL 检索前置过滤；工具透传 user_id；提示词注入防御（`<untrusted_document>` 包裹）；审计 180 天；模型降级链。

**验证**：`pytest tests/integration/test_security.py`（越权检索=0、注入样本、降级、审计）。

## S10 健壮性验证

**产出**：全量测试 + 评测跑分 + 4 亮点对比数据。

- 单测 + 集成测试全绿；异常输入/边界值/降级/重试覆盖。
- 跑 Golden Dataset 出 4 组「基线 vs 改进」量化对比。
- **不做高并发/压测**。

**验证**：`pytest` 全绿；`run_eval.py` 出指标；`README.md` 记录亮点对比数字。

## 风险文件与回滚点

- `app/agent/graph.py`：状态机边定义，改动影响全部问答流程，改后必须重跑 `test_graph.py` + 全量评测。
- `app/ingestion/chunker.py`：分块策略改动影响检索质量，改后重跑 `test_chunker.py` + Recall 评测。
- `app/retrieval/fusion.py`：融合/重排改动影响 NDCG，改后重跑 `test_fusion.py` + NDCG 评测。
- Alembic 迁移：只追加不改已合并脚本；回滚用 `alembic downgrade -1`。

## 进入实现前的检查（task.py start 前）

- [x] prd.md / design.md / implement.md 齐全（复杂任务）
- [ ] implement.jsonl / check.jsonl 含真实 spec 条目（非空）
- [ ] spec 文件无占位符、index 与文件集一致
