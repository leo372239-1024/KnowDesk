# KnowDesk 后端

FastAPI + LangGraph + Milvus 的企业知识库智能问答后端。

## 快速开始

```bash
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed
uv run python -m scripts.seed_docs
uv run uvicorn app.main:app --reload
```

详见根目录 `README.md`。
