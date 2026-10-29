"""Agent 状态定义（LangGraph StateGraph 状态）。"""
from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    query: str
    tenant_id: str
    department: str | None
    acl_tags: list[str]

    # 查询理解
    rewritten_queries: list[str]
    plan: list[str]

    # 检索结果（序列化后的 SearchResult，避免跨节点传对象）
    retrieved: list[dict[str, Any]]
    evidence_score: float
    # 原 query 单独检索的证据分（证据门控主信号，不混入改写噪声）
    orig_evidence_score: float
    sufficient: bool

    # 生成
    answer: str
    citations: list[dict[str, Any]]
    refused: bool
    refuse_reason: str

    # 控制
    rounds: int
    need_web_search: bool
    web_search_results: str
    error: str | None
