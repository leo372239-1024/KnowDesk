# KnowDesk 企业知识库智能问答 Agent（MVP）— PRD

| 项 | 值 |
|---|---|
| 任务 | `10-28-knowdesk-mvp` |
| 定位 | GraphRAG 模式的 Agent 编排企业知识库智能问答系统 |
| 对标 | ima + learnbuddy（学生/企业培训/专业知识问答） |
| 文档基线 | `Raw Requirement Record/项目需求原始记录.md`、`PRD-P1-*.md`、`X1-安全与治理横切规范.md` |

## 1. Goal 与用户价值

**一句话**：把企业散落在文档中的非结构化知识，变成「**能引用出处、承认不知道、不瞎编**」的问答 Agent，并让「知识入库 → 问答 → 反馈 → 评测 → 改进」形成**完整闭环**。

**用户价值**：
- 一线员工：平均查找耗时 15min → ≤30s（P90），一次找对率 62% → ≥85%。
- 知识管理员：文档更新后可定位「哪条答案用了过时文档」，可追溯可审计。
- 企业信息化：私有化部署 + 引用可审计 + 拒答兜底，满足等保/合规。

**核心验收的一句话**：交付一个「业务闭环完整、健壮稳定、生产级」的前后端全栈 MVP，且 4 个技术模块有相对基线**≥5% 可量化提升**。

## 2. 背景与依据（confirmed facts）

- 技术栈已由需求文档明确并经验证：React18+AntD5 / FastAPI / LangGraph / PostgreSQL(pgvector) / Milvus / ES / Redis（详见 `design.md` §2）。
- 调研证据：LangGraph 是 2026 生产级 Agent 编排首选；dense+sparse+BM25 混合检索 + rerank 是生产级 RAG 主流；BGE-M3 中文 Recall@10 93.7% 且成本极低（本机调研 + 网络调研，见 `implement.jsonl`）。
- 本机已有基础设施：Docker Compose、Milvus(19530)、MinIO(milvus-minio)、MySQL(可复用或另起 PG)。

## 3. 需求（按模块拆解）

### M1 知识入库（Ingestion）
- FR-1 多格式解析：PDF（含双栏/表格）、Word、Markdown、Excel、TXT；扫描件 OCR 作为可选项。
- FR-2 解析质量门禁：表格错行、页序倒置、OCR 低置信度 → 拒绝入库并告警。
- FR-3 结构化分块：按标题层级 + 表格独立成块（全量保留表头）+ 列表切分；chunk 不跨章节、表格不被腰斩。
- FR-4 chunk 元数据：携带「章节路径 / 页码 / bbox / 条款号 / 文档类型」。
- FR-5 索引：dense + sparse（BGE-M3）+ BM25 倒排 + PG 元数据，四路落库。
- FR-6 幂等：文档 `content_hash` 唯一；chunk `(doc_id, chunk_index)` 唯一。
- FR-7 PII 脱敏 + 文档级 ACL 标签（tenant/department/acl_tags）。

### M2 检索子系统（Retrieval，可独立评测）
- FR-8 三路召回：dense 向量 + sparse 向量 + BM25 关键词。
- FR-9 RRF 融合 → bge-reranker 重排 → TopK。
- FR-10 ACL 前置过滤（检索阶段 pre-filter，非生成后脱敏）。
- FR-11 rerank 超时降级为纯 RRF 排序。

### M3 Agent 编排（LangGraph）
- FR-12 查询理解：指代消解 + 术语归一 + 拆子问题 + HyDE。
- FR-13 检索计划：主步骤 Plan-and-Execute + 子步骤 CoT/ReAct + 每步重规划。
- FR-14 证据门控：充分度不足 → 改写重检（≤2 轮）→ 仍不足 → 网络检索补充 → 仍不足 → 拒答。
- FR-15 生成：结构化输出（结论/依据/例外/建议），强制引用。
- FR-16 循环熔断：最大步数 / 最大 Token / 最大时长三重上限。

### M4 引用溯源（Citation）
- FR-17 每个断言强制绑定 `[doc_id#chunk_id]`；无引用断言裁掉（硬门禁）。
- FR-18 引用可定位：页码 + PDF bbox 坐标，前端点击高亮原文。
- FR-19 数值/日期/专有名词后置精确校验，不匹配拦截或标红。

### M5 评测体系（Eval）
- FR-20 Golden Dataset ≥50 条，覆盖 5 类任务（参数查询/制度判定/多文档综合/流程指引/拒答判定），含不可答样本。
- FR-21 自研 harness：accuracy / faithfulness / refusal / recall / hallucination，一键跑分。
- FR-22 失败模式 6 类归因：RETRIEVE_MISS / CHUNK_BROKEN / EVIDENCE_WEAK / CONFLICT / CITE_WRONG / OVER_REFUSE。

### M6 前端（Web）
- FR-23 问答页：流式渲染 + 引用高亮跳转 + 拒答提示。
- FR-24 文档管理：上传、解析状态、索引进度、版本。
- FR-25 评测面板：跑分结果 + 指标对比。
- FR-26 Trace 面板：一次问答的完整链路（阶段耗时/token/top-k/拒答原因）。

### M7 安全与治理（X1 横切）
- FR-27 认证：JWT 双令牌（access + refresh）。
- FR-28 权限：RBAC + 文档级 ACL 前置过滤；工具透传用户身份。
- FR-29 提示词注入防御：检索内容包 `<untrusted_document>` + 指令/数据分离 + 输出 PII 检测。
- FR-30 审计：全链路审计日志（谁/何时/问什么/命中什么/答什么/引用），保留 180 天。

### M8 可观测性
- FR-31 全链路 trace：`trace_id` + 各阶段 span（耗时/token/top-k/拒答原因），可离线重放。

## 4. Acceptance Criteria（可测试）

| 编号 | 验收标准 |
|---|---|
| AC-1 | 20 份真实文档解析入库，表格结构保留率 ≥90%，chunk 平均 300–600 token 且不跨章节 |
| AC-2 | 构造 10 份坏 PDF（表格错行/页序倒置/低质）100% 被解析门禁拦截并告警 |
| AC-3 | 50 题评测集上 Recall@10 ≥0.90 |
| AC-4 | Rerank 后 NDCG@5 相对未 rerank 提升 ≥8pt |
| AC-5 | 引用可回溯率 100%（抽查 50 条），无引用断言数 =0 |
| AC-6 | 混入 20 题语料外问题，拒答正确率 ≥90%，可答误拒率 ≤5% |
| AC-7 | 越权检索率 =0（20 条跨部门/跨租户问题全部拒答且不泄露标题） |
| AC-8 | 4 个亮点模块各出 1 组「基线 vs 改进」量化数字，效果提升 ≥5% |
| AC-9 | 全链路 trace 可回放：同一 query + 索引快照重跑检索结果一致 |
| AC-10 | 健壮性验证通过（异常输入/边界值/降级/重试），**不做高并发测试** |

## 5. Out of Scope（MVP 不做，列为升级项）

- Kafka/RocketMQ、K8s/Istio/Helm、SkyWalking、ELK（用 Celery + structlog + PG 替代）。
- 多租户计费/额度、40+ 向量库插件化、多模态 embedding/检索。
- 语义缓存、GraphRAG 全量多跳（仅做可演示子集）、表格 Text2SQL。
- 高并发/压测/性能基准。

## 6. 任务拆解（交付物分解）

| 子任务 | 交付物 | 依赖 |
|---|---|---|
| S1 项目脚手架 | backend + frontend 目录、依赖、Docker Compose | — |
| S2 数据层 | PG 模型 + Alembic 迁移 + 种子数据 | S1 |
| S3 入库 Pipeline | 解析/分块/embedding/索引 + 门禁 + Celery | S2 |
| S4 检索子系统 | 三路召回 + RRF + rerank + ACL | S2 |
| S5 Agent 编排 | LangGraph 状态机 + 工具 + 证据门控 + 拒答 | S4 |
| S6 API 层 | auth/documents/chat/eval 路由 + trace | S5 |
| S7 前端 | 问答/文档/评测/trace 四页 | S6 |
| S8 评测 harness | Golden Dataset + run_eval + 指标 | S4 |
| S9 安全治理 | ACL/注入防御/审计/降级 | 贯穿 |
| S10 健壮性验证 | 单测 + 集成测试 + 评测跑分 + 亮点对比 | 全部 |

## 7. 备注

- 测试仅做功能逻辑健壮性验证（异常输入、边界值、失败恢复、降级重试），不做并发/压测。
- 需求文档中 Java 生态选型（Spring Security/Shiro/SLF4J/Logback）不适用 Python 后端，已映射为 FastAPI 依赖注入 + structlog 等价实现。
