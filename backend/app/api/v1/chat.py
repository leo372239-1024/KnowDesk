"""问答路由：非流式 / 流式 / 反馈 / 会话。"""
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.container import get_agent
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    FeedbackRequest,
    MessageResponse,
)
from app.services.chat_service import ChatService

router = APIRouter()


@router.post("/ask", response_model=ChatResponse)
async def ask(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    service = ChatService(get_agent(), db)
    # admin 角色跨部门可见（department=None 表示不过滤部门），普通用户仅本部门
    department = None if user.role == "admin" else user.department
    return await service.ask(
        query=payload.query,
        user_id=str(user.id),
        tenant_id=user.tenant_id,
        department=department,
        acl_tags=list(user.acl_tags or []),
        conversation_id=payload.conversation_id,
    )


@router.post("/stream")
async def stream_ask(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    service = ChatService(get_agent(), db)
    department = None if user.role == "admin" else user.department
    gen = service.stream_ask(
        query=payload.query,
        user_id=str(user.id),
        tenant_id=user.tenant_id,
        department=department,
        acl_tags=list(user.acl_tags or []),
        conversation_id=payload.conversation_id,
    )
    return StreamingResponse(gen, media_type="text/event-stream")


@router.post("/feedback")
async def feedback(
    payload: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    msg = await db.get(Message, uuid.UUID(payload.message_id))
    if msg is None:
        raise NotFoundError("消息不存在")
    msg.feedback = payload.rating
    msg.feedback_comment = payload.comment
    await db.commit()
    return {"status": "ok"}


@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Conversation:
    conv = Conversation(user_id=user.id, title=payload.title)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(result.scalars().all())


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Message]:
    conv = await db.get(Conversation, uuid.UUID(conversation_id))
    if conv is None or conv.user_id != user.id:
        raise NotFoundError("会话不存在")
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == uuid.UUID(conversation_id))
        .order_by(Message.created_at.asc())
    )
    return list(result.scalars().all())
