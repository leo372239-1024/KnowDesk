"""轻量依赖容器：进程内单例（测试可自行构造注入，绕过单例）。"""
from app.agent.graph import KnowDeskAgent
from app.core.llm import get_llm
from app.retrieval.retriever import RetrievalService

_retrieval: RetrievalService | None = None
_agent: KnowDeskAgent | None = None


def get_retrieval() -> RetrievalService:
    global _retrieval
    if _retrieval is None:
        _retrieval = RetrievalService()
    return _retrieval


def get_agent() -> KnowDeskAgent:
    global _agent
    if _agent is None:
        _agent = KnowDeskAgent(get_llm(), get_retrieval())
    return _agent
