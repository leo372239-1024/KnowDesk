"""全链路 trace 记录模型。"""
from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class TraceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trace_records"

    trace_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    spans: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)  # JSON
