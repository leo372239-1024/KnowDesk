"""问答服务：编排 Agent、落审计与 trace、返回响应。"""
import asyncio
import json
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import KnowDeskAgent
from app.core.logging import get_logger, get_trace_id, new_trace_id, set_trace_id
from app.core.observability import get_spans, start_trace
from app.models.audit import AuditLog
from app.models.conversation import Conversation, Message
from app.models.trace import TraceRecord
from app.schemas.chat import ChatResponse, Citation

logger = get_logger(__name__)

_STREAM_CHUNK = 16  # 流式分块字符数（抽取式答案按块回放）


class ChatService:
    def __init__(self, agent: KnowDeskAgent, db: AsyncSession) -> None:
        self.agent = agent
        self.db = db

    async def ask(
        self,
        query: str,
        user_id: str,
        tenant_id: str,
        department: str,
        acl_tags: list[str],
        conversation_id: str | None = None,
    ) -> ChatResponse:
        trace_id = new_trace_id()
        set_trace_id(trace_id)
        start_trace()

        result = await self.agent.arun(
            query, tenant_id=tenant_id, department=department, acl_tags=acl_tags
        )

        citations = [
            Citation(**c) for c in result.get("citations", [])
        ]
        doc_ids = [c.document_id for c in citations if c.document_id]

        message_id = await self._persist(
            trace_id=trace_id,
            query=query,
            user_id=user_id,
            tenant_id=tenant_id,
            answer=result.get("answer", ""),
            citations=result.get("citations", []),
            doc_ids=doc_ids,
            refused=result.get("refused", False),
            conversation_id=conversation_id,
        )

        return ChatResponse(
            answer=result.get("answer", ""),
            citations=citations,
            refused=result.get("refused", False),
            trace_id=trace_id,
            evidence_score=result.get("evidence_score", 0.0),
            message_id=message_id,
        )

    async def stream_ask(
        self,
        query: str,
        user_id: str,
        tenant_id: str,
        department: str | None,
        acl_tags: list[str],
        conversation_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式问答：跑 Agent → 落库 → 以 SSE 事件流逐块回放答案。"""
        trace_id = new_trace_id()
        set_trace_id(trace_id)
        start_trace()

        result = await self.agent.arun(
            query, tenant_id=tenant_id, department=department, acl_tags=acl_tags
        )
        answer = result.get("answer", "")
        refused = result.get("refused", False)
        citations = result.get("citations", [])
        evidence_score = result.get("evidence_score", 0.0)
        doc_ids = [c.get("document_id", "") for c in citations if c.get("document_id")]

        message_id = await self._persist(
            trace_id=trace_id,
            query=query,
            user_id=user_id,
            tenant_id=tenant_id,
            answer=answer,
            citations=citations,
            doc_ids=doc_ids,
            refused=refused,
            conversation_id=conversation_id,
        )

        def _sse(payload: dict) -> str:
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        yield _sse({"type": "start", "trace_id": trace_id})
        # 逐块回放答案（抽取式答案整体生成，这里模拟流式输出；真实 LLM 模式可改为逐 token）
        for i in range(0, len(answer), _STREAM_CHUNK):
            yield _sse({"type": "delta", "content": answer[i : i + _STREAM_CHUNK]})
            await asyncio.sleep(0)
        yield _sse(
            {
                "type": "done",
                "refused": refused,
                "citations": citations,
                "evidence_score": evidence_score,
                "message_id": message_id,
            }
        )

    async def _persist(
        self,
        trace_id: str,
        query: str,
        user_id: str,
        tenant_id: str,
        answer: str,
        citations: list,
        doc_ids: list,
        refused: bool,
        conversation_id: str | None,
    ) -> str | None:
        # 审计（追加）
        self.db.add(
            AuditLog(
                user_id=uuid.UUID(user_id),
                tenant_id=tenant_id,
                query=query,
                doc_ids=doc_ids,
                answer=answer,
                citations=citations,
                refused=refused,
                trace_id=trace_id,
            )
        )
        # trace 记录
        self.db.add(TraceRecord(trace_id=trace_id, spans=get_spans()))
        # 消息
        assistant_msg: Message | None = None
        if conversation_id:
            self.db.add(Message(conversation_id=uuid.UUID(conversation_id), role="user", content=query))
            assistant_msg = Message(
                conversation_id=uuid.UUID(conversation_id),
                role="assistant",
                content=answer,
                citations=citations,
                refused=refused,
                trace_id=trace_id,
            )
            self.db.add(assistant_msg)
        await self.db.commit()
        logger.info("chat.completed", trace_id=trace_id, refused=refused, citations=len(citations))
        return str(assistant_msg.id) if assistant_msg else None
