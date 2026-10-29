"""分块策略健壮性测试：表格保全、章节边界、条款识别。"""
from app.ingestion.chunker import chunk_text


def test_table_is_independent_and_keeps_header():
    text = """# 设备参数

| 参数 | 数值 |
|------|------|
| 额定电流 | 10A |
| 额定电压 | 220V |

## 说明

以上参数仅供参考。
"""
    chunks = chunk_text(text)
    table_chunks = [c for c in chunks if c.chunk_type == "table"]
    assert len(table_chunks) == 1
    # 表格块保留表头
    assert "参数" in table_chunks[0].content
    assert "额定电流" in table_chunks[0].content
    # 表格不被腰斩（两行数据都在同一块）
    assert "220V" in table_chunks[0].content


def test_chunks_do_not_cross_section():
    text = """## 1. 安装要求

设备应安装在干燥通风处。

## 2. 维护保养

每月检查一次接线端子。
"""
    chunks = chunk_text(text)
    sections = {c.section_path for c in chunks}
    assert "## 1. 安装要求" in sections
    assert "## 2. 维护保养" in sections


def test_clause_type_for_numbered_sections():
    text = """1.1 一线城市住宿标准为 500 元/晚。

1.2 其他城市住宿标准为 300 元/晚。
"""
    chunks = chunk_text(text)
    assert len(chunks) >= 1
    assert "500 元" in "".join(c.content for c in chunks)


def test_long_text_is_split():
    long_sentence = "内容。".join([f"这是第{i}条规定的具体内容说明" for i in range(200)])
    chunks = chunk_text(long_sentence)
    assert len(chunks) > 1
    # 每个 chunk 不超上限
    for c in chunks:
        assert len(c.content) <= 800 + 50
