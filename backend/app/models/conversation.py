"""会话与消息模型。"""
import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="新对话")


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    # [{doc_id, chunk_id, page_num, bbox, snippet}]
    refused: Mapped[bool] = mapped_column(default=False)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # 反馈闭环：1=点赞，-1=点踩（点踩进入 Bad Case 池），null=未评价
    feedback: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    feedback_comment: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
