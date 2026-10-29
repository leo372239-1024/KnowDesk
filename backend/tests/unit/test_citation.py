"""引用硬门禁测试：无效引用裁掉，有效引用保留。"""
from app.agent.citation import build_citations, validate_citations


def test_validate_removes_invalid_citations():
    answer = "额定电流是 10A [doc1#0]，电压 220V [doc1#1]，功率未知 [doc9#9]。"
    cleaned, cited, invalid = validate_citations(answer, {"doc1#0", "doc1#1"})
    assert invalid == 1
    assert cited == ["doc1#0", "doc1#1"]
    assert "[doc9#9]" not in cleaned
    assert "[doc1#0]" in cleaned


def test_validate_all_invalid():
    answer = "答案 [doc9#9]"
    cleaned, cited, invalid = validate_citations(answer, {"doc1#0"})
    assert invalid == 1
    assert cited == []
    assert "[" not in cleaned


def test_build_citations_has_location():
    retrieved = [
        {
            "chunk": {
                "chunk_id": "doc1#0",
                "document_id": "doc1",
                "content": "额定电流 10A",
                "section_path": "## 1. 电气参数",
                "page_num": 1,
                "bbox": {"x": 0, "y": 0},
            }
        }
    ]
    citations = build_citations(retrieved)
    assert citations[0]["chunk_id"] == "doc1#0"
    assert citations[0]["page_num"] == 1
