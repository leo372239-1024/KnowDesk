# KnowDesk 技术架构设计（design.md）

> 本文定义 KnowDesk 的架构边界、数据流契约、4 个技术深化亮点方案、关键 trade-off 与运维回滚。

## 1. 总体架构

```
┌───────────────────────────────────────────────────────────────────┐
│                        前端 React + AntD5                          │
│  问答页 / 文档管理 / 评测面板 / Trace 面板（WebSocket 流式）          │
└──────────────────────────┬────────────────────────────────────────┘
                           │ REST + WS（JWT 双令牌）
┌──────────────────────────▼────────────────────────────────────────┐
│                    后端 FastAPI（api → services）                   │
│   auth / documents / chat / eval 路由 · 依赖注入 · 全局异常         │
└──────────┬─────────────────────────────────────────────────────────┘
           │
┌──────────▼─────────────────────────────────────────────────────────┐
│                   Agent 编排层 LangGraph（状态机）                   │
│  INIT → QUERY_UNDERSTAND → PLAN → RETRIEVE → RERANK → JUDGE        │
│       → (REWRITE ≤2 | WEB_SEARCH | REFUSE | GENERATE) → END        │
└──┬──────────────────┬──────────────────┬────────────────────────────┘
   ▼                  ▼                  ▼
┌─────────┐   ┌─────────────────┐   ┌──────────────────────────────┐
│ 检索子系统 │   │  入库 Pipeline   │   │  模型网关（多模型路由+降级）    │
│dense+sparse│   │ 解析→门禁→分块    │   │ DeepSeek 主 / Qwen 本地备    │
│+BM25+rerank│   │ →embedding→索引   │   │ embedding: BGE-M3          │
└────┬────┘   └────────┬────────┘   │ rerank: bge-reranker-v2-m3  │
     │                 │            └──────────────────────────────┘
┌────▼─────────────────▼────────────────────────────────────────────┐
│ 存储层：PostgreSQL(元数据/审计/评测/ACL) · Milvus(向量) · Redis(缓存) │
│        · MinIO(文档本体) · ES/PG-FTS(BM25)                          │
└────────────────────────────────────────────────────────────────────┘
```

## 2. 技术栈（最终确定，含选型理由）

| 层 | 选型 | 理由 |
|---|---|---|
| 前端 | React18 + TS + Vite + AntD5 + TanStack Query + Zustand + Zod | 需求指定；Query 管服务端状态，Zustand 仅 UI 状态 |
| 后端 | Python3.11 + FastAPI + uv + SQLAlchemy2.0(async) + Alembic + Pydantic2 | 需求指定；async 优先 |
| 编排 | LangGraph | 2026 生产级首选；显式状态机支持证据门控/拒答/重规划/回放 |
| 关系库 | PostgreSQL 16 + pgvector | 元数据/审计/评测/ACL；pgvector 单机兜底 |
| 向量库 | Milvus（本机 milvus-standalone:19530） | 生产级；统一 `BaseVector` 接口可替换 |
| 关键词 | BM25（in-memory + ES 可选） | MVP 用内存 BM25，避免维护 keyword table |
| Embedding | BGE-M3 | 一套模型同时产出 dense+sparse，中文 Recall@10 93.7%，成本极低 |
| Rerank | bge-reranker-v2-m3 | 中文效果好，可本地跑 |
| LLM | DeepSeek 主 + 本地 Qwen2.5 备 | 成本/稳定性双轨，超时降级 |
| 异步 | Celery + Redis | 文档解析/索引耗时任务 |
| 对象存储 | MinIO（复用 milvus-minio） | 文档本体 |
| 日志 | structlog + trace_id | 结构化 + 可观测 |

**暂缓（升级项）**：Kafka/K8s/ELK/SkyWalking/语义缓存/GraphRAG 全量多跳/多模态。

## 3. 数据模型（核心实体）

| 实体 | 关键字段 | 说明 |
|---|---|---|
| `users` | id(UUID), username, hashed_password, role | RBAC 角色 |
| `documents` | id, tenant_id, title, content_hash(唯一), department, acl_tags[], authority_level, effective_date, version, status, object_key | 元数据 + ACL |
| `chunks` | id, document_id, chunk_index(联合唯一), content, section_path, chunk_type(text/table/clause), page_num, bbox, token_count | 结构化分块结果 |
| `conversations` | id, user_id, title | 会话 |
| `messages` | id, conversation_id, role, content, citations(json), trace_id | 问答消息 |
| `audit_logs` | id, user_id, query, doc_ids, answer, citations, refused, created_at | 审计（追加，180 天） |
| `eval_datasets` | id, name, questions(json) | 评测集 |
| `eval_runs` | id, dataset_id, metrics(json), created_at | 跑分结果 |
| `trace_records` | id, trace_id, spans(json), created_at | 全链路 trace |

**向量存储（Milvus）**：collection `chunks`，字段 `chunk_id`(pk) + `dense`(1024, bge-m3) + `sparse`(SPARSE_FLOAT_VECTOR) + `tenant_id`/`department`/`acl_tags`（pre-filter 用）。

## 4. 关键数据流契约

### 4.1 问答链路（一次请求的完整数据流）

```
用户 query + user_id
  → api/chat（生成 trace_id，鉴权）
  → services.chat_service（装 LangGraph）
  → agent.nodes.understand：query → 改写/拆子问题（LLM）
  → agent.nodes.plan：生成检索计划（主步骤）
  → agent.tools.retrieve：调 retrieval（dense+sparse+BM25 → RRF → rerank）
  → agent.nodes.judge：证据充分度评分
      ├─ 充分 → generate → 强制引用 → citation_check → 返回
      ├─ 不足(≤2轮) → rewrite → 回 retrieve
      ├─ 不足 + 知识库无 → web_search（网络补充）
      └─ 仍不足 → refuse（拒答话术 + 建议）
  → 每步落 trace（span: 耗时/token/top-k/拒答原因）
  → 审计落库（query/doc_ids/answer/citations）
```

### 4.2 入库链路

```
上传文件 → MinIO（object_key）
  → Celery task: parse（按类型路由）→ 解析质量门禁 → PII 脱敏
  → chunk（结构化分块）→ embed（BGE-M3 dense+sparse）
  → 写 PG（documents/chunks）+ Milvus（向量）+ BM25 索引
  → 更新文档 status
```

## 5. 四个技术深化亮点方案（重点突破）

### 亮点 1：外部知识库存储策略——「结构感知 + 多模态存储」

**问题**：固定长度切分把表格腰斩、把「例外条款」与「主条款」拆到不同 chunk，知识含义丢失；单一向量库无法表达结构关系。

**方案**：
1. **结构化分块**：先按标题层级切大块，再按语义断点二次切；`chunk_type` 区分 text/table/clause。
2. **表格独立成块 + 全量保留表头**：表格 chunk 头部冗余表头，保证检索命中时表头语义完整。
3. **条款级 chunk**：法条/合同按「条/款/项」编号对齐，chunk 携带条款号元数据（`section_path`）。
4. **章节路径元数据**：每个 chunk 带 `第3章 > 3.2 费用标准 > 3.2.1 住宿` 路径，检索时进上下文。
5. **四路存储分工**：PG 存结构/元数据 + Milvus 存 dense+sparse 向量 + BM25 存精确匹配 + MinIO 存原文（bbox 定位）。

**量化目标**：结构化分块 vs 固定 512-token 分块，Recall@10 从 0.71 → ≥0.90。

### 亮点 2：检索召回策略——「三路召回 + RRF + Rerank + 证据门控」

**问题**：纯向量对专有名词/型号/编号召回差；单一路召回无法兼顾语义与精确；融合权重难调。

**方案**：
1. **三路召回**：BGE-M3 dense（语义）+ BGE-M3 sparse（稀疏向量精确词项）+ BM25（关键词）。
2. **sparse 复用 BGE-M3**：一套模型同时产出 dense+sparse，免额外部署，天然对齐。
3. **RRF 融合**：免调权重，对专有名词/编号类 query 显著优于纯向量。
4. **bge-reranker-v2-m3 重排**：精排 TopK，提升 NDCG。
5. **阈值延后**：融合/重排前不做 embedding 分数阈值过滤（分数体系不可比），阈值延后到 rerank 后。
6. **证据充分度评分**：`rerank top1 分数 + top1/top3 差 + 子问题覆盖比例` 驱动判定层。

**量化目标**：混合检索 vs 纯向量，Recall@10 提升 ≥5pt；rerank 后 NDCG@5 提升 ≥8pt。

### 亮点 3：引用标注——「硬门禁 + bbox 定位 + 事实校验」

**问题**：「提示词说别编造」遵守率不稳定；引用只有 doc_id 无法定位到页；数值断言可能张冠李戴。

**方案**：
1. **生成约束**：结构化输出模板，每个断言必须挂 `[doc_id#chunk_id]`。
2. **引用硬门禁（后置裁切）**：解析输出中所有引用，无引用的断言直接裁掉——「无引用断言数 = 0」是硬指标而非软指标。
3. **bbox 定位**：chunk 携带 `page_num` + `bbox`，前端点击引用跳转 PDF 对应坐标高亮。
4. **事实后置校验**：数值/日期/专有名词抽取后与原文 chunk 精确匹配，不匹配拦截或标红。
5. **前端交互**：`Citation` 组件按 doc_id 分组，hover 弹出 chunk 内容，点击跳原文。

**量化目标**：引用可回溯率 100%；引用支持率 ≥0.95；hallucination rate ≤2%。

### 亮点 4：Agent 步骤规划与执行——「Plan-and-Execute + ReAct + 双检索 + 熔断」

**问题**：单一检索无法处理「知识库没有、需网络补充」的问题；无规划的多轮检索易跑偏；易陷入循环。

**方案**：
1. **混合分解**：程序化定主线（Plan-and-Execute 主步骤）+ LLM 驱动子步骤（CoT/ReAct）+ 每子步骤后重规划。
2. **LangGraph 状态机**：`INIT → UNDERSTAND → PLAN → RETRIEVE → RERANK → JUDGE → (REWRITE|WEB_SEARCH|REFUSE|GENERATE) → END`，显式可控可回放。
3. **证据门控驱动自适应检索**：充分度不足才改写重检（≤2 轮），避免无谓检索。
4. **知识库/网络双检索**：知识库召回不足 → 触发网络搜索工具补充（`<untrusted_content>` 包裹防注入）。
5. **循环熔断**：最大步数/最大 Token/最大时长三重上限，连续两次相同动作检测。

**量化目标**：多跳/综合类任务成功率提升；拒答正确率 ≥90%、误拒率 ≤5%。

## 6. 安全与治理（X1 横切落地）

| 风险 | 落地手段 |
|---|---|
| 间接提示注入 | 检索内容包 `<untrusted_document>` + 指令/数据分离 + 输出 PII 检测 |
| 越权检索 | ACL 在 Milvus/BM25 **pre-filter**（非 post-filter），tenant_id 前置 |
| 工具越权 | 工具透传 user_id 身份，权限 = 用户权限 ∩ 场景允许工具集 |
| 循环失控 | 三重上限熔断 |
| 幻觉 | 三道闸门（证据门控 → 引用裁切 → 事实校验） |
| 审计缺失 | 全链路审计 180 天，可导出 |

## 7. 关键 trade-off 与决策

| 决策 | 选择 | 理由 | 代价 |
|---|---|---|---|
| 向量库 | Milvus（非 pgvector 唯一） | 本机已有、生产级 | 需维护统一 `BaseVector` 接口 |
| 关键词 | 内存 BM25（非 ES） | 免 ES 部署，MVP 数据量小 | 大数据量后需换 ES |
| embedding | BGE-M3（非 OpenAI） | 中文好、成本低、dense+sparse 一体 | 需本地推理资源 |
| LLM | DeepSeek 主 + Qwen 备 | 成本/稳定双轨 | 需管理降级链路 |
| 评测 | 自研 harness（非 RAGAS） | 可控、可解释、无外部依赖 | 需自己实现指标 |
| 任务队列 | Celery（非 Kafka） | 轻量、够用 | 大数据量后需换消息中间件 |

## 8. 运维与回滚

- **可回放**：`trace_id` + 索引快照版本可重跑同一 query，检索结果一致（生成允许不同）。
- **降级链**：主模型超时 → 重试 1 次 → 降级备用模型（`degraded=true` 写 trace）；rerank 超时 → 纯 RRF。
- **回滚点**：每次改 Prompt/换模型/换分块 → 跑全量评测，指标下降 >2pt 阻断上线。
- **配置外置**：所有模型/向量库/embedding 参数经 `core/config.py`（环境变量），不硬编码。
