"""文档服务：上传、解析入库、列表查询。"""
import hashlib
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.pipeline import IngestionPipeline
from app.models.document import Chunk, Document
from app.retrieval.retriever import RetrievalService


def _content_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class DocumentService:
    def __init__(self, db: AsyncSession, retrieval: RetrievalService) -> None:
        self.db = db
        self.pipeline = IngestionPipeline(retrieval)

    async def upload(
        self,
        title: str,
        file_type: str,
        raw: bytes,
        tenant_id: str,
        department: str,
        acl_tags: list[str],
        document_id: str | None = None,
    ) -> Document:
        """上传：写元数据 + 同步解析入库（MVP 数据量下同步足够）。

        document_id 可选：seed/评测场景用固定 ID 以复现 must_cite 关联。
        """
        digest = _content_hash(raw)
        # 幂等：同内容不重复入库
        existing = await self.db.execute(select(Document).where(Document.content_hash == digest))
        doc = existing.scalar_one_or_none()
        if doc is not None:
            return doc

        doc = Document(
            title=title,
            file_type=file_type,
            content_hash=digest,
            tenant_id=tenant_id,
            department=department,
            acl_tags=acl_tags,
            status="parsing",
        )
        if document_id:
            doc.id = uuid.UUID(document_id)
        self.db.add(doc)
        await self.db.flush()  # 拿到 doc.id

        try:
            result = self.pipeline.process(
                raw=raw,
                file_type=file_type,
                document_id=str(doc.id),
                tenant_id=tenant_id,
                department=department,
                acl_tags=acl_tags,
            )
            # 写 chunk 到 PG
            for i, (record, _vec) in enumerate(result.chunk_records):
                self.db.add(
                    Chunk(
                        id=uuid.uuid4(),
                        document_id=doc.id,
                        chunk_index=i,
                        content=record.content,
                        section_path=record.section_path,
                        chunk_type=record.chunk_type,
                        page_num=record.page_num,
                        bbox=record.bbox,
                        token_count=len(record.content),
                    )
                )
            doc.chunk_count = result.chunk_count
            doc.status = "indexed"
        except Exception:  # noqa: BLE001
            doc.status = "failed"
            raise
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def list_documents(self, tenant_id: str) -> tuple[list[Document], int]:
        stmt = select(Document).where(Document.tenant_id == tenant_id).order_by(Document.created_at.desc())
        result = await self.db.execute(stmt)
        docs = list(result.scalars().all())
        count_stmt = select(func.count()).select_from(Document).where(Document.tenant_id == tenant_id)
        total = (await self.db.execute(count_stmt)).scalar_one()
        return docs, int(total)

    async def get_document(self, document_id: str) -> Document | None:
        result = await self.db.execute(select(Document).where(Document.id == uuid.UUID(document_id)))
        return result.scalar_one_or_none()
