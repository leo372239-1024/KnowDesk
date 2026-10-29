"""审计日志模型（X1 合规：只追加，保留 180 天，可导出）。"""
import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    doc_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    refused: Mapped[bool] = mapped_column(Boolean, default=False)
    trace_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
