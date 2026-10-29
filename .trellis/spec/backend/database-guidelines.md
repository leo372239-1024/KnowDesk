# Database Guidelines

> KnowDesk 的数据库约定：PostgreSQL（元数据/审计/评测/ACL）+ Milvus/pgvector（向量）+ ES/PG FTS（关键词）。

## 技术组件分工

| 存储 | 存什么 | 不存什么 |
|---|---|---|
| PostgreSQL | 用户、租户、文档元数据、chunk 元数据、会话、审计日志、评测集、eval 结果 | 不存向量（除非单机兜底用 pgvector）、不存大文件本体 |
| Milvus | chunk 向量（dense + sparse） | 不存可被 PG 表达的业务元数据 |
| ES / PG FTS | 关键词倒排（BM25） | 不存向量 |
| 对象存储（MinIO/S3） | 原始文档文件本体 | — |

> 文件本体存对象存储，PG 只存 `object_key` + 元数据。禁止把 PDF 二进制塞进 PG。

## ORM 约定（SQLAlchemy 2.0 + async）

- 统一 async engine + `async_sessionmaker`；禁止混用同步 session。
- 所有查询走 ORM 2.0 风格（`select(...)`），禁止拼接原生 SQL 字符串（除必须的 `pgvector` 距离算子等，需注释说明）。
- 会话由 `api/deps.py` 的依赖注入提供，业务函数不自己创建 session。
- **禁止**：在 ORM 模型里写业务方法、在请求周期外持有 session、用 `session.commit()` 散落在业务里（事务边界放 service 层）。

```python
# 正确：依赖注入 session
async def get_document(doc_id: str, db: AsyncSession = Depends(get_db)) -> Document:
    stmt = select(Document).where(Document.id == doc_id)
    return (await db.execute(stmt)).scalar_one_or_none()
```

## 迁移（Alembic）

- 每张表/每次 schema 变更一个迁移脚本，`alembic revision --autogenerate` 生成后**人工 review**。
- 迁移必须可 `upgrade` 和 `downgrade`。
- 不手改已合并的迁移；新变更只追加新脚本。
- 上线前跑 `alembic upgrade head`，不允许靠 `create_all()` 建表。

## 命名约定

| 对象 | 规则 | 示例 |
|---|---|---|
| 表名 | snake_case 复数 | `documents`、`chunks`、`audit_logs` |
| 列名 | snake_case | `created_at`、`tenant_id` |
| 主键 | `id`，UUID（`uuid4`），非自增 | `id UUID PRIMARY KEY` |
| 外键 | `<表单数>_id` | `document_id` |
| 时间戳 | `created_at` / `updated_at`（带时区） | `timestamptz` |
| 索引 | `ix_<表>_<列>` | `ix_chunks_document_id` |

## 幂等与唯一约束（X1/消息幂等要求）

需求原始记录要求消息幂等，落地到本项目的数据库手段：

1. **文档入库幂等**：`documents.content_hash`（文件内容 SHA-256）加唯一约束；重复上传同内容文件不重复入库，只更新元数据。
2. **chunk 幂等**：`chunks.(document_id, chunk_index)` 联合唯一；重跑索引不产生重复 chunk。
3. **审计追加**：`audit_logs` 只插入不更新，靠 `trace_id` 关联一次问答的完整链路。

## ACL 前置过滤（X1 硬要求）

- `documents` 带 `tenant_id`、`department`、`acl_tags`（密级/权限标签）。
- 检索**必须在召回阶段**用这些列做 **pre-filter**（`WHERE tenant_id = :t AND department IN (...) AND acl_tags && :allowed`），禁止召回后再脱敏（post-filter 会泄露文档标题）。

## 反模式

- ❌ 把向量和业务元数据都塞进 Milvus（会导致元数据无法 join/审计）。
- ❌ 用 `create_all()` 代替 Alembic 迁移。
- ❌ 同步 session 与 async session 混用。
- ❌ 在循环里逐条 `insert`（批量用 `bulk_insert_mappings` 或分批）。
- ❌ post-filter ACL（检索后再过滤权限）。
