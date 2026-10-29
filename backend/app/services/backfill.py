"""启动回填：把 PG 中已入库的 chunk 重建到检索服务（向量库 + BM25 + 记录缓存）。

内存向量库不持久化，服务重启后需从 PG 回填；Milvus 模式则依赖 PG 作为
chunk 内容的唯一真源（Milvus 只存向量，不含 content）。
"""
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.document import Chunk, Document
from app.retrieval.embedding import get_embedding
from app.retrieval.retriever import RetrievalService
from app.retrieval.vector_store import ChunkRecord


async def backfill_retrieval(retrieval: RetrievalService) -> int:
    """从 PG 回填所有 status=indexed 文档的 chunk，返回回填 chunk 数。"""
    async with async_session_factory() as db:
        result = await db.execute(
            select(Chunk, Document)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.status == "indexed")
            .order_by(Chunk.document_id, Chunk.chunk_index)
        )
        rows = result.all()

    if not rows:
        return 0

    embedding = get_embedding()
    contents = [chunk.content for chunk, _doc in rows]
    vectors = embedding.embed_documents(contents)

    records: list[tuple[ChunkRecord, list[float]]] = []
    for (chunk, doc), vector in zip(rows, vectors):
        record = ChunkRecord(
            chunk_id=f"{doc.id}#{chunk.chunk_index}",
            document_id=str(doc.id),
            content=chunk.content,
            section_path=chunk.section_path,
            chunk_type=chunk.chunk_type,
            page_num=chunk.page_num,
            bbox=chunk.bbox,
            tenant_id=doc.tenant_id,
            department=doc.department,
            acl_tags=doc.acl_tags or [],
        )
        records.append((record, vector))

    retrieval.index_chunks(records)
    return len(records)
