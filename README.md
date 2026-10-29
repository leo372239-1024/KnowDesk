# KnowDesk — GraphRAG 模式的 Agent 编排企业知识库智能问答系统

> 把企业散落在文档中的非结构化知识，变成一个「能引用出处、承认不知道、不瞎编」的问答 Agent。
> 「知识入库 → 问答 → 反馈 → 评测 → 改进」完整闭环，前后端全栈，生产级 MVP。

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 + TanStack Query + Zustand + Zod |
| 后端 | Python 3.12+ + FastAPI + SQLAlchemy 2.0(async) + Alembic + Pydantic v2 |
| Agent | LangGraph 状态机（查询理解 → 检索 → 证据门控 → 生成/拒答 + 网络补充 + 熔断） |
| 存储 | PostgreSQL(pgvector) + Milvus（可切换内存）+ MinIO + Redis |
| 检索 | dense + 词级 BM25 + 字符级 BM25 → RRF 融合 → HybridRerank 精排 |
| LLM | DeepSeek（OpenAI 兼容，可换 Ollama/vLLM）；无 Key 时离线抽取式问答 |

> **一套代码、两种部署**：默认离线自洽（无需 GPU/模型/外网），配置 `LLM_API_KEY` /
> `EMBEDDING_PROVIDER=sentence_transformer` 后无缝切换到真实模型。离线模式是自洽的
> 检索 + 抽取式问答系统，能产出正确结果与真实指标，而非「糊弄的桩」。

## 四个技术深化亮点（重点突破 + 实测）

| # | 亮点 | 做法 | 实测（Golden Dataset 50 题） |
|---|---|---|---|
| 1 | 知识存储策略 | 结构化分块（标题树 + 表格独立成块全量保留表头 + 条款级 chunk） | 表格参数查询 q001–q008 accuracy **100%**（表格不腰斩） |
| 2 | 检索召回策略 | 三路召回（dense + 词级 BM25 + 字符级 BM25）→ RRF → HybridRerank → 证据门控 | 相关/不相关分离度 **1.5x → 5.2x**；Recall@10 **100%** |
| 3 | 引用标注 | 每个断言强制绑定 `[chunk_id]`，无引用断言硬裁切 | faithfulness **100%** |
| 4 | Agent 步骤规划 | 状态机 + 证据门控驱动自适应检索 + 知识库/网络双检索 + 拒答 | refusal_correctness **0% → 100%** |

## 快速开始

### 0. 环境说明
本机 5432/6379 端口被其他项目占用，KnowDesk 使用 **5433（Postgres）/ 6380（Redis）**，
后端 API 跑在 **8001**。详见 `docker-compose.yml` 与 `backend/.env`。

### 1. 启动基础设施
```bash
docker compose up -d postgres redis    # 5433/6380
```

### 2. 后端
```bash
cd backend
cp .env.example .env                   # 已提供默认 .env（5433/6380，离线模式）
# 安装依赖（本机已用 .venv314 虚拟环境，可用 uv sync 或 pip）
alembic upgrade head                   # 建表（alembic.ini 由 env.py 读应用配置）
python -m scripts.seed                 # 种子用户 admin/admin123, user/user123
python -m scripts.seed_docs            # 入库 3 份样例文档
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

### 3. 前端
```bash
cd frontend
npm install
npm run dev                            # http://localhost:5173（proxy → 8001）
```

### 4. 启用真实模型（可选，默认离线可跑）
```bash
# backend/.env
LLM_API_KEY=sk-xxx                     # 真实 LLM（OpenAI 兼容）
# 云端 embedding（OpenAI 兼容接口，推荐；无需本地模型）
EMBEDDING_PROVIDER=openai_compat
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_API_KEY=sk-xxx
EMBEDDING_DIM=1024
# 或本地 BGE-M3（需 pip install -e ".[ml]"）
# EMBEDDING_PROVIDER=sentence_transformer
# RERANK_PROVIDER=sentence_transformer     # 真实 bge-reranker-v2-m3
```

## 评测

```bash
cd backend
python -m scripts.seed_docs
python scripts/run_offline_eval.py     # baseline（纯 dense+无门控）vs 改进版对比
```

输出指标（离线抽取式，`run_offline_eval.py`）：

| 指标 | 基线 | 改进版 | 目标 |
|---|---|---|---|
| answer_accuracy | 0.950 | **0.983** | ≥0.85 |
| refusal_correctness | 0.0 | **1.0** | ≥0.9 |
| false_refusal_rate | 0.0 | **0.0** | ≤0.05 |
| recall_at_10 | 1.0 | **1.0** | ≥0.9 |
| faithfulness | 1.0 | **1.0** | ≥0.95 |

真实模型指标（`run_eval.py`，`text-embedding-v4` + DeepSeek，Golden Dataset 50 题）：

| 指标 | 实测 | 目标 |
|---|---|---|
| answer_accuracy | **1.0** | ≥0.85 |
| faithfulness | **1.0** | ≥0.95 |
| refusal_correctness | **1.0** | ≥0.9 |
| false_refusal_rate | **0.0** | ≤0.05 |
| recall_at_10 | **1.0** | ≥0.9 |

> 真实 embedding 会放大「通用属性词」的语义匹配，导致语料外实体问题漏拒（如
> `q040`），已通过**实体标识符校验**（ADR-17）修复，最终全满分。

## 测试

```bash
cd backend
python -m pytest                       # 28 个用例
```

覆盖：分块策略、混合重排分离度、抽取式问答/多行表格解析、RRF 融合、引用硬门禁、
ACL 前置过滤、Agent 拒答/生成、入库全链路、越权与注入。

## API 一览（`/api/v1`）

- `POST /auth/login` / `POST /auth/refresh` / `GET /auth/me` — 认证（双令牌）
- `POST /documents/upload` / `GET /documents/` / `GET /documents/{id}` — 文档入库
- `POST /chat/ask` / `POST /chat/stream`（SSE）— 问答
- `POST /chat/feedback` — 反馈（点赞/点踩 → Bad Case 池）
- `POST /chat/conversations` / `GET /chat/conversations` / `GET /chat/conversations/{id}/messages` — 会话
- `GET /observability/trace/{id}` / `GET /observability/audit` / `GET /observability/badcases` — 可观测/合规
- `GET/POST /eval/*` — 评测集与跑分

## 目录结构

```
backend/   FastAPI 后端（api/services/agent/retrieval/ingestion/eval/core 分层）
frontend/  React 前端（pages/components/hooks/api/types/store）
.trellis/  Trellis 工程治理（spec 编码规范 + tasks 任务 + ADR 架构决策记录）
Raw Requirement Record/  原始需求（PRD + X1 安全治理横切）
```

## 安全与治理（X1 横切）

- ACL 检索前置过滤（租户/部门/密级标签，非生成后脱敏）；工具透传用户身份。
- 提示词注入防御：检索内容 `<untrusted_document>`、网络内容 `<untrusted_content>` 包裹。
- PII 脱敏（手机号/身份证/邮箱）；审计日志 180 天可查询；全链路 trace 可回溯。
- 模型降级链：主模型超时 → 备用模型（`degraded` 标记）。

## 架构决策

关键设计取舍与权衡见 `.trellis/tasks/10-28-knowdesk-mvp/ADR.md`（10 条 ADR）。

## 许可（License）

本项目源码公开可见，但**不是 OSI 定义的开放源代码（Open Source）**，准确表述为
**source-available（源码可见）**。原因是 OSI《开源定义》第 5、6 条明确禁止许可协议限制
使用领域与使用人群，因此任何「禁止商用」的许可都不被 OSI 承认为开源。

- 许可协议：**PolyForm Noncommercial License 1.0.0**，官方全文
  <https://polyformproject.org/licenses/noncommercial/1.0.0>，本仓库副本见 [`LICENSE`](LICENSE)。
- **允许**：个人学习、研究、实验、业余项目；教学、慈善、公共研究、公共安全/卫生、环保、
  政府机构等非商业组织使用；阅读、修改、创建衍生作品，并按同等条款分发。
- **禁止**：任何商业用途，包括在企业内部业务中使用。商用须另行取得书面授权。
- 随附专利授权（Patent License）；若被许可方书面主张本项目侵犯其专利，专利授权立即终止。
- 第三方依赖沿用各自许可证，不受本项目许可影响。

商用授权与例外咨询：GitHub [@leo372239-1024](https://github.com/leo372239-1024)。
