"""问答相关 schema。"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    section_path: str = ""
    page_num: int | None = None
    bbox: dict[str, Any] | None = None
    snippet: str = ""


class ChatRequest(BaseModel):
    query: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    refused: bool
    trace_id: str
    evidence_score: float = 0.0
    degraded: bool = False
    message_id: str | None = None


class FeedbackRequest(BaseModel):
    message_id: str
    rating: int  # 1=点赞，-1=点踩
    comment: str | None = None


class ConversationCreate(BaseModel):
    title: str = "新对话"


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list[dict[str, Any]]
    refused: bool
    feedback: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
