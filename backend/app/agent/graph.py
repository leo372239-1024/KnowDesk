"""LangGraph 状态机与 Agent 门面（亮点 4：步骤规划 + 双检索 + 熔断）。"""
from functools import partial
from typing import Any

from langgraph.graph import END, StateGraph

from app.agent.nodes import (
    generate_node,
    judge_node,
    plan_node,
    refuse_node,
    retrieve_node,
    understand_node,
    web_search_node,
)
from app.agent.state import AgentState
from app.core.config import settings
from app.core.llm import BaseLLM
from app.core.observability import trace_span
from app.retrieval.retriever import RetrievalService


def _rewrite_node(state: AgentState) -> dict[str, Any]:
    """改写重检：检索证据不足时 rounds+1，用原 query 重检（≤2 轮）。"""
    return {"rounds": state.get("rounds", 0) + 1}


def _route_after_judge(state: AgentState) -> str:
    if state.get("sufficient"):
        return "generate"
    if state.get("rounds", 0) < settings.agent_max_rounds:
        return "rewrite"
    return "web_search"


def _route_after_web(state: AgentState) -> str:
    if state.get("web_search_results"):
        return "generate"
    return "refuse"


def build_graph(llm: BaseLLM, retrieval: RetrievalService):
    g = StateGraph(AgentState)
    g.add_node("understand", partial(understand_node, llm=llm))
    g.add_node("plan", partial(plan_node, llm=llm))
    g.add_node("retrieve", partial(retrieve_node, retrieval=retrieval))
    g.add_node("judge", partial(judge_node, retrieval=retrieval))
    g.add_node("rewrite", _rewrite_node)
    g.add_node("web_search", web_search_node)
    g.add_node("generate", partial(generate_node, llm=llm))
    g.add_node("refuse", refuse_node)

    g.set_entry_point("understand")
    g.add_edge("understand", "plan")
    g.add_edge("plan", "retrieve")
    g.add_edge("retrieve", "judge")
    g.add_conditional_edges(
        "judge",
        _route_after_judge,
        {"generate": "generate", "rewrite": "rewrite", "web_search": "web_search"},
    )
    g.add_edge("rewrite", "retrieve")
    g.add_conditional_edges("web_search", _route_after_web, {"generate": "generate", "refuse": "refuse"})
    g.add_edge("generate", END)
    g.add_edge("refuse", END)
    return g.compile()


class KnowDeskAgent:
    """Agent 门面：封装图 + 模型 + 检索，供 service 调用。"""

    def __init__(self, llm: BaseLLM, retrieval: RetrievalService) -> None:
        self.llm = llm
        self.retrieval = retrieval
        self.graph = build_graph(llm, retrieval)

    async def arun(
        self,
        query: str,
        tenant_id: str = "default",
        department: str | None = None,
        acl_tags: list[str] | None = None,
    ) -> AgentState:
        initial: AgentState = {
            "query": query,
            "tenant_id": tenant_id,
            "department": department,
            "acl_tags": acl_tags or [],
            "rounds": 0,
        }
        with trace_span("agent.total", max_steps=settings.agent_max_steps):
            # recursion_limit 需覆盖完整合法流程（understand+plan + (retrieve+judge+rewrite)*rounds
            # + web_search + 生成/拒答），并留出安全余量；业务层循环上限由 agent_max_rounds 控制。
            recursion_limit = settings.agent_max_rounds * 4 + 12
            result = await self.graph.ainvoke(
                initial, config={"recursion_limit": recursion_limit}
            )
        return result
