"""可观测性与合规路由：trace 查询、审计查询、Bad Case 池（X1 合规）。"""
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models.audit import AuditLog
from app.models.conversation import Message
from app.models.trace import TraceRecord
from app.models.user import User

router = APIRouter()


def _require_admin(user: User) -> None:
    if user.role != "admin":
        raise PermissionDeniedError("仅管理员可访问")


@router.get("/trace/{trace_id}")
async def get_trace(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    result = await db.execute(
        select(TraceRecord).where(TraceRecord.trace_id == trace_id).limit(1)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise NotFoundError("trace 不存在")
    return {
        "trace_id": record.trace_id,
        "spans": record.spans,
        "created_at": record.created_at.isoformat(),
    }


@router.get("/audit")
async def list_audit(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_admin(user)
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if tenant_id:
        stmt = stmt.where(AuditLog.tenant_id == tenant_id)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    logs = list(result.scalars().all())
    return {
        "items": [
            {
                "id": str(log.id),
                "user_id": str(log.user_id),
                "tenant_id": log.tenant_id,
                "query": log.query,
                "doc_ids": log.doc_ids,
                "refused": log.refused,
                "trace_id": log.trace_id,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
        "total": len(logs),
    }


@router.get("/badcases")
async def list_badcases(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    """Bad Case 池：点踩（feedback=-1）的 assistant 消息，用于后续迭代评测。"""
    _require_admin(user)
    stmt = (
        select(Message)
        .where(Message.feedback == -1)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    return {
        "items": [
            {
                "id": str(m.id),
                "content": m.content,
                "citations": m.citations,
                "feedback_comment": m.feedback_comment,
                "trace_id": m.trace_id,
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ],
        "total": len(rows),
    }
