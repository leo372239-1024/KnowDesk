"""把样例文档入库（用固定 ID，供评测 recall 计算）。

用法：uv run python -m scripts.seed_docs
"""
import asyncio
import uuid
from pathlib import Path

from app.core.database import async_session_factory, engine
from app.eval.known_docs import DOC_CONTRACT, DOC_EXPENSE, DOC_TITLES, DOC_XG2000A
from app.models.document import Chunk, Document
from app.retrieval.retriever import RetrievalService
from app.services.document_service import DocumentService, _content_hash

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_docs"

DOC_FILES = {
    DOC_XG2000A: "XG-2000A设备手册.md",
    DOC_EXPENSE: "出差报销制度.md",
    DOC_CONTRACT: "合同盖章流程.md",
}


async def seed_docs() -> None:
    retrieval = RetrievalService()
    async with async_session_factory() as db:
        service = DocumentService(db, retrieval)
        for doc_id, filename in DOC_FILES.items():
            path = SAMPLE_DIR / filename
            raw = path.read_bytes()
            title = DOC_TITLES[doc_id]
            # 检查是否已存在
            doc = await db.get(Document, uuid.UUID(doc_id))
            if doc is None:
                doc = await service.upload(
                    title=title,
                    file_type="md",
                    raw=raw,
                    tenant_id="default",
                    department="general",
                    acl_tags=[],
                    document_id=doc_id,
                )
                print(f"已入库：{title} ({doc.chunk_count} chunks)")
            else:
                print(f"已存在，跳过：{title}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_docs())
