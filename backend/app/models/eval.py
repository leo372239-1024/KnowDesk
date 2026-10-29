"""评测集与跑分结果模型。"""
import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class EvalDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "eval_datasets"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    questions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    # JSON: [{id, question, task_type, checkpoints, must_cite, unanswerable}]


class EvalRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "eval_runs"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("eval_datasets.id", ondelete="CASCADE"), index=True
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)  # JSON
    report: Mapped[str] = mapped_column(Text, default="", nullable=False)
