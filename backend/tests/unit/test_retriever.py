"""检索与 ACL 前置过滤测试。"""
from app.retrieval.embedding import get_embedding
from app.retrieval.retriever import RetrievalService
from app.retrieval.vector_store import ChunkRecord, InMemoryVectorStore


def _make_service() -> RetrievalService:
    return RetrievalService(vector_store=InMemoryVectorStore())


def _index_docs(service: RetrievalService) -> None:
    emb = get_embedding()
    records = [
        ChunkRecord(
            chunk_id="a#0", document_id="a", content="XG-2000A 设备额定电流为 10A，额定电压 220V",
            tenant_id="default", department="general", acl_tags=[],
        ),
        ChunkRecord(
            chunk_id="b#0", document_id="b", content="财务报表显示公司净利润为 500 万元",
            tenant_id="default", department="finance", acl_tags=[],
        ),
        ChunkRecord(
            chunk_id="c#0", document_id="c", content="高管薪酬属于机密信息，年薪 200 万元",
            tenant_id="default", department="general", acl_tags=["confidential"],
        ),
        ChunkRecord(
            chunk_id="d#0", document_id="d", content="A 公司机密文档内容",
            tenant_id="other-tenant", department="general", acl_tags=[],
        ),
    ]
    service.index_chunks([(r, emb.embed_query(r.content)) for r in records])


def test_retrieve_hits_relevant_chunk():
    service = _make_service()
    _index_docs(service)
    results = service.retrieve("XG-2000A 的额定电流是多少", tenant_id="default", department="general")
    assert results, "应召回内容"
    assert results[0].chunk.chunk_id == "a#0"


def test_acl_filters_department():
    service = _make_service()
    _index_docs(service)
    results = service.retrieve("净利润是多少", tenant_id="default", department="general")
    # finance 部门的文档不应泄露给 general 部门
    assert all(r.chunk.chunk_id != "b#0" for r in results)


def test_acl_filters_confidential():
    service = _make_service()
    _index_docs(service)
    results = service.retrieve("高管薪酬是多少", tenant_id="default", department="general", acl_tags=[])
    # 无 confidential 权限，不应命中机密文档
    assert all(r.chunk.chunk_id != "c#0" for r in results)


def test_acl_filters_tenant():
    service = _make_service()
    _index_docs(service)
    results = service.retrieve("机密文档", tenant_id="default", department="general")
    # 其他租户文档绝不可见
    assert all(r.chunk.chunk_id != "d#0" for r in results)
