"""入库全链路集成测试：解析 → 分块 → 索引 → 检索。"""
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.retriever import RetrievalService
from app.retrieval.vector_store import InMemoryVectorStore

SAMPLE_MD = """# XG-2000A 设备手册

## 1. 技术参数

| 参数 | 数值 |
|------|------|
| 额定电流 | 10A |
| 额定电压 | 220V |

## 2. 维护保养

每月检查一次接线端子是否松动。
""".encode("utf-8")


def test_ingestion_end_to_end():
    retrieval = RetrievalService(vector_store=InMemoryVectorStore())
    pipeline = IngestionPipeline(retrieval)
    result = pipeline.process(
        raw=SAMPLE_MD,
        file_type="md",
        document_id="doc-test",
        tenant_id="default",
        department="general",
        acl_tags=[],
    )
    assert result.chunk_count >= 3
    # 表格独立成块
    assert any(r.chunk_type == "table" for r, _ in result.chunk_records)

    # 索引后可检索
    results = retrieval.retrieve("额定电流是多少", tenant_id="default", department="general")
    assert results
    assert any("10A" in r.chunk.content for r in results)


def test_ingestion_empty_content_raises():
    from app.core.exceptions import DocumentParseError

    retrieval = RetrievalService(vector_store=InMemoryVectorStore())
    pipeline = IngestionPipeline(retrieval)
    try:
        pipeline.process(
            raw=b"   ",
            file_type="txt",
            document_id="doc-empty",
            tenant_id="default",
            department="general",
            acl_tags=[],
        )
        raise AssertionError("应抛出 DocumentParseError")
    except DocumentParseError:
        pass
