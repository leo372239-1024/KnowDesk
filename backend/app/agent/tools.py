"""Agent 工具：知识库检索 + 网络检索补充（透传用户身份，不越权）。"""
import httpx

from app.core.logging import get_logger
from app.retrieval.retriever import RetrievalService
from app.retrieval.vector_store import SearchResult

logger = get_logger(__name__)

_WEB_TIMEOUT = 6.0
_WEB_UA = "KnowDesk/0.1 (+knowledge-base assistant)"


def retrieve_kb(
    retrieval: RetrievalService,
    query: str,
    tenant_id: str,
    department: str | None,
    acl_tags: list[str],
) -> list[SearchResult]:
    """知识库检索：权限 = 用户身份（tenant/department/acl_tags），非 Agent 身份。"""
    return retrieval.retrieve(
        query, tenant_id=tenant_id, department=department, acl_tags=acl_tags
    )


async def web_search(query: str) -> str:
    """网络检索补充（DuckDuckGo，无需 Key）。失败/超时优雅降级返回空串 → 触发拒答。

    检索到的外部内容必须以 <untrusted_content> 包裹（X1 注入防御：外部内容视为
    不可信，仅作为补充，不进入系统提示词）。
    """
    try:
        async with httpx.AsyncClient(timeout=_WEB_TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                headers={"User-Agent": _WEB_UA},
            )
            resp.raise_for_status()
            data = resp.json()
        abstract = (data.get("AbstractText") or "").strip()
        answer = (data.get("Answer") or "").strip()
        text = abstract or answer
        if not text:
            return ""
        return f"<untrusted_content>\n{text[:1000]}\n</untrusted_content>"
    except Exception:  # noqa: BLE001  网络不可用/解析失败均降级
        logger.info("web_search.degraded", query=query[:50])
        return ""
