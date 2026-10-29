"""文档与 chunk 模型。"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    department: Mapped[str] = mapped_column(String(64), default="general", index=True)
    acl_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # 密级标签
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    authority_level: Mapped[int] = mapped_column(Integer, default=0)  # 越大越权威
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    # pending / parsing / indexed / failed
    object_key: Mapped[str | None] = mapped_column(String(255), nullable=True)  # MinIO key
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)  # pdf/word/md/xlsx/txt
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)


class Chunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunks_doc_index"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    section_path: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(16), default="text", nullable=False)
    # text / table / clause
    page_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # PDF 坐标
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_score: Mapped[float | None] = mapped_column(Float, nullable=True)
