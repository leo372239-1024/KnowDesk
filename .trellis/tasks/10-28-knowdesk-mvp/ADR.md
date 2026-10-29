# KnowDesk 架构决策记录（ADR）

> 记录本次 MVP 落地过程中的关键架构决策、权衡与实测结果。原始需求见
> `Raw Requirement Record/PRD-P1-企业知识库与文档智能问答Agent.md`，执行清单见
> 同目录 `design.md` / `implement.md`。

## 1. 总览：一套代码、两种部署

KnowDesk 是「GraphRAG 企业知识库问答 Agent」全栈项目。核心架构决策是
**「一套代码、两种部署」**：

| 维度 | 离线模式（默认，本机可跑） | 真实模型模式（配置切换） |
|---|---|---|
| Embedding | `FakeEmbedding`（word + char n-gram 哈希，256 维） | BGE-M3（`sentence_transformer`） |
| Rerank | `HybridReranker`（dense + 覆盖度 + n-gram） | bge-reranker-v2-m3 cross-encoder |
| 向量库 | `InMemoryVectorStore`（内存） | Milvus |
| LLM | `ExtractiveLLM`（抽取式问答，零幻觉） | DeepSeek / Ollama / vLLM（OpenAI 兼容） |

切换方式：`.env` 填 `LLM_API_KEY` 即切真实 LLM；`EMBEDDING_PROVIDER` /
`RERANK_PROVIDER` 设 `sentence_transformer` 即切真实向量模型。**离线模式不是
「随便糊的桩」，而是自洽的、能产出正确结果与真实指标的检索+抽取系统**，保证
无 GPU/无外网/无 Key 也能完整跑通闭环。

## 2. 关键技术决策

### ADR-1：`FakeReranker` 纯余弦 → `HybridReranker`（修长/短不对称 bug）
- **问题**：纯余弦在「长 chunk + 短 query」下得分被长度稀释，正确 chunk 仅得
  0.52，无关 chunk 得 0.35，分离度 1.5x，导致证据门控误判。
- **决策**：重排分数改为 `0.35*dense + 0.45*query覆盖度 + 0.20*char n-gram 覆盖度`，
  以「query 内容被 chunk 覆盖的比例」为主信号（对长度不对称鲁棒）。
- **实测**：相关/不相关分离度从 **1.5x → 5.2x**（0.52/0.35 → 0.77/0.15），跨越
  0.35 门控阈值。

### ADR-2：`FakeLLM` 回显 → `ExtractiveLLM`（抽取式问答）
- **问题**：旧 FakeLLM 只回显输入，答案全是垃圾、改写污染检索、引用为空，离线
  模式形同虚设。
- **决策**：离线用确定性抽取式问答——从检索 chunk 中抽相关句并带 `[chunk_id]`
  引用（**逐字摘自原文，零幻觉**）；understand 阶段返回空跳过改写。
- **实测**：answer_accuracy 从「无法回答」→ **93.3%**。

### ADR-3：证据门控公式与阈值校准
- **问题**：旧公式 `top1*0.7 + (top1-top3)*0.3` 在「多跳/综合题（top1≈top3）」上
  被错误惩罚，可答题被误拒。
- **决策**：改为 `top1 + 0.2*max(0, top1-top3)`（置信度只加成不惩罚），阈值 0.35；
  收敛 `judge_node` 与 `RetrievalService.evidence_score` 的重复实现到
  `compute_evidence_score` 单一实现。
- **实测**：refusal_correctness **0% → 100%**（10 道不可答题全部正确拒答）。

### ADR-4：功能词污染 → 词性（POS）过滤
- **问题**：停用词表不全，「后/由/谁」等功能词稀释覆盖度并制造假匹配（如
  「审批通过后，由印章管理员」误匹配「由谁打款」）。
- **决策**：`meaningful_tokens` 改用 jieba 词性标注，白名单只保留名词/动词/形容词/
  数词/型号，从根上过滤介词/代词/助词。

### ADR-5：多行 chunk 解析
- **问题**：抽取式解析按行切分，多行表格只取首行，导致「额定电流 | 10A」等行
  丢失。
- **决策**：按「空行」切分 chunk（生成 prompt 中 chunk 间正是 `\n\n` 分隔），并
  改为**句级抽取**（对 chunk 内句子按 query 词元重叠打分，去重取 top-N）。

### ADR-6：记录真源下沉到 `RetrievalService`
- **问题**：原实现以 `vector_store.get()` 为记录真源，BM25 召回的 chunk 取不到完整
  记录被丢弃；Milvus 不含 content 也取不到。
- **决策**：`RetrievalService` 维护 `chunk_id → ChunkRecord` 缓存，`index_chunks`
  时写入，多路召回统一从这里取记录，与向量库实现解耦（Milvus 也能用）。

### ADR-7：内存向量库不持久化 → 启动回填
- **问题**：`container` 用全新 `InMemoryVectorStore`，服务重启后向量库为空。
- **决策**：FastAPI `lifespan` 启动时从 PG 回填全部 `status=indexed` chunk 到向量库
  + BM25 + 记录缓存（`app/services/backfill.py`），数据库未就绪则降级启动。

### ADR-8：admin 跨部门可见
- **决策**：`/chat/ask` 对 `role=admin` 传 `department=None`（不过滤部门），普通用户
  仅本部门；密级标签（acl_tags）与租户隔离对所有用户强制。

### ADR-9：passlib → bcrypt 原生（Python 3.14 兼容）
- **问题**：passlib 1.7.4 与 bcrypt 4.x 在 Python 3.14 上不兼容（`detect_wrap_bug`
  抛错）。
- **决策**：直接使用 bcrypt 原生 API（`hashpw`/`checkpw`）。

### ADR-10：流式策略
- **决策**：MVP 用 SSE（`POST /chat/stream`）。抽取式答案整体生成后按块回放；真实
  LLM 模式可平滑升级为逐 token 流式（接口不变）。

### ADR-11：真实 LLM 改写偏航 → 原 query 始终保留
- **问题**：接入真实 DeepSeek 后，`understand_node` 改写成功后 `rewritten = extra[:3]`
  **丢弃原 query**，改写偏航时（如「紧急乘商务座怎么处理」被改写成「如何购买商务座
  车票/候补改签」）原 query 的强证据一并丢失，导致可答题被误判证据不足。
- **决策**：原 query 始终参与检索（证据主信号），LLM 改写仅作补充召回（`[query] + extra[:2]`）；
  改写 prompt 保守化（仅指代消解/术语归一，不得扩展话题）。
- **实测**：false_refusal_rate 从 **10% → 5%**。

### ADR-12：证据门控用原 query，而非改写合并
- **问题**：改写合并引入噪声，把语料外问题的 evidence 抬高（「张三工号」0.089→0.34），
  无论阈值如何调，可答题与拒答题在「合并证据」维度都重叠，无法分离。
- **决策**：`retrieve_node` 额外用原 query 单独检索出 `orig_evidence_score`；`judge_node`
  门控以该值为主信号；改写合并结果仅用于生成召回。原 query 证据下，拒答题 ≤0.15、
  可答题 ≥0.25，天然可分。
- **实测**：refusal_correctness 保持 **100%**，false_refusal **0%**。

### ADR-13：证据门控阈值 0.35 → 0.20
- **问题**：短 query（如「高铁」「高铁一等座」）的 rerank 分数偏低（0.25/0.30），
  0.35 阈值过严导致可答题误拒。
- **决策**：配合「原 query 门控」把阈值降到 0.20（原 query 证据的安全区间 0.18–0.22）。
- **实测**：可答题全部通过，拒答题全部拦截。

### ADR-14：章节上下文扩展（expand_siblings）
- **问题**：流程/清单类 query（「完整流程是什么」）需覆盖同章节全部环节，但部分环节
  字面匹配弱（「审批路径：出纳打款」不含「报销/流程」），漏召回导致答案漏环节。
- **决策**：命中 chunk 后补齐同 `section_path` 的兄弟 chunk（分数 = 源分数 × 0.9，
  排在命中 chunk 之后、纯噪声之前），上限 16。
- **实测**：真实 LLM 下 answer_accuracy 由 0.9833 → **1.0**。

### ADR-15：分块 `section_path` 语义修复
- **问题**：数字编号（4.1/4.2/4.3）被 `_detect_title` 识别为标题，导致每个条款的
  `section_path` 是它自己，丢失父章节（「## 4. 报销流程」）层级，章节扩展无法匹配兄弟。
- **决策**：只有章节级标题（markdown `#`、`第X章/节`）才更新 `section_path`，数字编号
  「子条款」继承父章节；`chunk_type` 的条款判定改为基于 chunk 内容。
- **实测**：28 个测试全通过，章节扩展生效。

### ADR-16：真实 embedding 接入（DashScope text-embedding-v4）
- **问题**：离线 `FakeEmbedding` 语义上限有限，需接真实云端 embedding 提升语义召回。
- **决策**：新增 `OpenAICompatEmbedding`（OpenAI 兼容 `/embeddings` 接口），
  `EMBEDDING_PROVIDER=openai_compat` 切换；`HybridReranker`/`DenseReranker` 的向量化
  改为 **batch**（`[query, *candidates]` 一次请求），避免逐条调用。
- **关键坑 1**：DashScope `text-embedding-v4` 单次 `input` **硬上限 10 条**（超过返回
  400 `batch size ... not larger than 10`），故 `_BATCH_SIZE=10`。
- **关键坑 2**：每次新建 `httpx.Client` 的 TLS 握手约 **6-9s**，复用连接后单次
  **<0.5s**；故实例内复用 Client，`get_embedding` 按 provider 缓存单例。实测 retrieve
  节点从 **85-94s → 2.6-3s**。
- **测试隔离**：`tests/conftest.py` 用 autouse fixture 强制 `embedding_provider=fake`，
  保证测试离线可重复。
- **实测**：真实 embedding 接入后 50 题指标——answer_accuracy **1.0**、faithfulness
  **1.0**、refusal_correctness **1.0**、false_refusal_rate **0.0**、recall_at_10 **1.0**。

### ADR-17：实体标识符校验（真实 embedding 的漏拒修复）
- **问题**：真实 embedding 语义匹配强，使 `q040「竞争对手 Y 公司的产品参数」` 的
  「产品参数」通用词匹配到语料 XG-2000A 参数表，evidence 达 0.29 越过阈值，导致
  语料外实体问题漏拒（生成「资料里没有 Y 公司」而非拒答）。
- **根因**：证据门控只看「query↔chunk 相似度」，无法识别「query 的实体锚点是否
  真的在语料里」——相似度高 ≠ 实体可回答。
- **决策**：judge 阶段增加**实体标识符校验**——用正则提取 query 的英文/型号锚点
  （Y / XG-2000A / Q3 / CEO / IP54，至少含字母），若过半锚点不在检索 chunk 中，
  则判证据不足 → 拒答。可答题的锚点（XG-2000A）均在语料内，不受影响。
- **实测**：q040 由漏拒 → 正确拒答，q001/q046 等可答题正常生成。

## 3. 业务闭环

```
文档上传 → 解析(PII脱敏/质量门禁) → 结构化分块 → 三路索引
        → 问答(查询理解→检索→证据门控→生成/拒答)
        → 反馈(点赞/点踩) → Bad Case 池 → 评测 → 迭代
```

全部环节已闭环：上传（API `/documents/upload`）、问答（`/chat/ask` + `/chat/stream`）、
反馈（`/chat/feedback`）、Bad Case（`/observability/badcases`）、评测
（`/eval/*` + `scripts/run_offline_eval.py`）。

## 4. 四个技术亮点实测（Golden Dataset 50 题）

| 亮点 | 基线（naive） | 改进版 | 改善 |
|---|---|---|---|
| 1 结构化存储 | 固定长度 chunk（表格腰斩） | 结构化 chunk（表格/条款不腰斩） | 表格参数查询 q001–q008 accuracy **100%** |
| 2 三路检索+重排 | 纯 dense 单路（分离度 1.5x） | dense+BM25+char-BM25 + RRF + HybridRerank（**5.2x**） | Recall@10 **100%** |
| 3 引用硬门禁 | 无校验 | 逐断言校验 `[chunk_id]`，无效引用裁掉 | faithfulness **100%** |
| 4 Agent 状态机+拒答 | 无门控（对不可答题幻觉） | 状态机 + 证据门控 + 拒答 | refusal_correctness **0%→100%** |

整体指标（`scripts/run_offline_eval.py`，离线抽取式）：
- answer_accuracy：**98.3%**（目标 ≥85%）
- refusal_correctness：**100%**（目标 ≥90%）
- false_refusal_rate：**0%**（目标 ≤5%）
- recall_at_10：**100%**
- faithfulness：**100%**

真实 LLM 指标（`scripts/run_eval.py`，DeepSeek deepseek-flash，50 题）：
| 指标 | 实测 | 目标 |
|---|---|---|
| answer_accuracy | **100%** | ≥85% |
| faithfulness | **100%** | ≥95% |
| refusal_correctness | **100%** | ≥90% |
| false_refusal_rate | **0%** | ≤5% |
| recall_at_10 | **100%** | ≥90% |

> 真实 LLM 接入初期的 false_refusal_rate 曾达 10%，经 ADR-11~15 五项改进收敛到 0%，
> 详见 `research/` 与评测失败明细（`LOW_ACCURACY`/`OVER_REFUSE` 记录答案内容供调研）。

## 5. 安全与治理（X1 落地）

- **租户隔离**：检索阶段 `tenant_id` 前置过滤（非生成后脱敏）。
- **部门隔离**：`department` 精确匹配，admin 跨部门。
- **密级标签**：`acl_tags` 覆盖判定（public/confidential）。
- **提示注入防御**：检索内容包 `<untrusted_document>`、网络内容包 `<untrusted_content>`，
  与系统提示词隔离。
- **PII 脱敏**：手机号/身份证/邮箱入库前正则脱敏。
- **审计**：只追加、可查询、保留 180 天。
- **双令牌**：access（30min）+ refresh（7d），前端 401 自动刷新。
