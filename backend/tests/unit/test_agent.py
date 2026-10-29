"""Agent 状态机测试：生成、拒答、熔断。"""
import pytest

from app.agent.graph import KnowDeskAgent
from app.core.llm import FakeLLM
from app.retrieval.embedding import get_embedding
from app.retrieval.retriever import RetrievalService
from app.retrieval.vector_store import ChunkRecord, InMemoryVectorStore


def _make_agent() -> KnowDeskAgent:
    retrieval = RetrievalService(vector_store=InMemoryVectorStore())
    emb = get_embedding()
    records = [
        ChunkRecord(
            chunk_id="a#0", document_id="a",
            content="XG-2000A 设备额定电流为 10A，额定电压 220V，额定功率 2.2kW。",
            tenant_id="default", department="general", acl_tags=[],
        ),
        ChunkRecord(
            chunk_id="a#1", document_id="a",
            content="出差报销制度：一线城市住宿标准 500 元，其他城市 300 元。",
            tenant_id="default", department="general", acl_tags=[],
        ),
    ]
    retrieval.index_chunks([(r, emb.embed_query(r.content)) for r in records])
    llm = FakeLLM()
    return KnowDeskAgent(llm, retrieval)


@pytest.mark.asyncio
async def test_agent_generates_answer_with_citation():
    agent = _make_agent()
    result = await agent.arun("XG-2000A 的额定电流是多少")
    assert result["refused"] is False
    assert result.get("answer")


@pytest.mark.asyncio
async def test_agent_refuses_when_no_evidence():
    agent = _make_agent()
    result = await agent.arun("明年 Q3 的销售目标是多少？")
    assert result["refused"] is True
    # 拒答不应有引用
    assert result.get("citations") == []


@pytest.mark.asyncio
async def test_agent_respects_acl():
    agent = _make_agent()
    # 财务部门用户问普通部门内容，应能答；但 confidential 内容应被拒
    result = await agent.arun("高管薪酬是多少", department="general", acl_tags=[])
    assert result["refused"] is True
