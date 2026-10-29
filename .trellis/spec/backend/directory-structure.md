# Directory Structure

> KnowDesk 后端如何组织代码。所有新增模块必须落位到下面某一层，禁止在 `api/` 里写业务逻辑。

## 目录布局

```
backend/
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── alembic/
│   └── versions/              # 迁移脚本（每张表变更一个脚本）
├── app/
│   ├── main.py                # FastAPI 入口：装配路由、中间件、异常处理器
│   ├── api/                   # 路由层（薄层）
│   │   ├── deps.py            # 依赖注入（当前用户、DB session、向量库）
│   │   └── v1/
│   │       ├── auth.py        # 认证/授权
│   │       ├── documents.py   # 文档上传/解析/索引
│   │       ├── chat.py        # 问答（REST + WS 流式）
│   │       └── eval.py        # 评测集管理 + 跑分
│   ├── core/                  # 横切基础设施
│   │   ├── config.py          # pydantic-settings 配置
│   │   ├── security.py        # JWT、ACL、脱敏
│   │   ├── logging.py         # structlog 装配
│   │   ├── exceptions.py      # 异常体系（唯一异常定义点）
│   │   └── observability.py   # trace/span 埋点 + 落库
│   ├── models/                # SQLAlchemy ORM（纯表映射，无业务逻辑）
│   ├── schemas/               # Pydantic v2（请求/响应/Agent 状态，与 ORM 分离）
│   ├── services/              # 业务逻辑层（api 与 agent 共用）
│   ├── agent/                 # LangGraph 编排（只此一层 import LangGraph）
│   │   ├── graph.py           # 状态机与边定义
│   │   ├── state.py           # AgentState（Pydantic/TypedDict）
│   │   ├── nodes.py           # 节点实现：理解/检索/判定/生成/拒答
│   │   └── tools.py           # 工具：知识库检索、网络检索
│   ├── retrieval/             # 检索子系统（可独立评测，不依赖 agent）
│   │   ├── vector_store.py    # Milvus/pgvector 统一接口
│   │   ├── bm25.py            # BM25 / ES / PG 全文
│   │   ├── rerank.py          # reranker 调用 + 降级
│   │   └── fusion.py          # RRF / 重排融合
│   ├── ingestion/             # 文档入库 pipeline
│   │   ├── parser.py          # 多格式解析（PDF/Word/MD/Excel/OCR）
│   │   ├── chunker.py         # 结构化分块（标题树 + 表格独立成块）
│   │   ├── embedder.py        # embedding 调用
│   │   └── pipeline.py        # 解析→分块→embedding→索引 编排
│   ├── eval/                  # 评测 harness（自研，不依赖 LangSmith）
│   │   ├── dataset.py         # Golden Dataset 加载/校验
│   │   ├── metrics.py         # accuracy/faithfulness/refusal/recall
│   │   └── runner.py          # run_eval 入口
│   ├── tasks/                 # Celery 任务（文档解析、批量索引）
│   └── utils/                 # 无副作用纯函数工具
├── tests/
│   ├── unit/
│   └── integration/
└── data/                      # 评测集、语料（gitignore 大文件，保留样本）
```

## 分层职责与依赖方向

```
api ──► services ──► agent ──► retrieval / ingestion
   │         │
   └─────────┴──────► models / schemas / core（横切，被所有人引用）
```

- **`api/`**：只做参数解析（依赖 Pydantic schema）、鉴权（依赖 `core/security`）、调用 service、拼响应。**禁止**直接写检索/生成逻辑。
- **`services/`**：可被 `api` 和 `agent` 复用的业务用例（如 `chat_service`、`document_service`）。编排 LangGraph 之外的一切事务逻辑。
- **`agent/`**：唯一允许 import LangGraph 的层。节点内部通过 `services`/`retrieval` 完成工作，不直接碰 ORM。
- **`retrieval/`**：纯检索能力，输入 query + 过滤条件，输出候选 chunk 列表。**不 import `agent/`、不 import `services/`**，保证可独立跑分。
- **`ingestion/`**：纯入库能力，不依赖 `agent/`。
- **`models/`**：ORM 表映射，**禁止**写业务方法、禁止 import `services/`。
- **`core/`**：无业务含义的横切件，**禁止**反向 import 其他层。

## 命名约定

| 对象 | 规则 | 示例 |
|---|---|---|
| 文件/模块 | snake_case | `vector_store.py` |
| 类 | PascalCase | `VectorStore`、`ChatService` |
| 函数/方法 | snake_case | `retrieve_chunks()` |
| 常量 | UPPER_SNAKE | `MAX_RETRIEVE_ROUNDS` |
| 私有成员 | 单下划线前缀 | `_embed_batch()` |
| ORM 模型 | PascalCase 单数 | `Document` |
| Pydantic schema | 后缀 `Schema`/`Request`/`Response` | `ChatRequest`、`DocumentResponse` |

## 反模式

- ❌ 在 `api/` 路由函数里写检索、调用 embedding、拼 prompt。
- ❌ 在 `models/` 里写业务逻辑或 `from app.services import ...`。
- ❌ 在 `retrieval/` 里 import LangGraph 或 `agent/`（会破坏检索的可独立评测性）。
- ❌ 把配置硬编码散落在各文件；一律经 `core/config.py` 读取。
- ❌ 跨层传递 ORM 对象到 `api` 响应；`api` 只出 Pydantic schema。
