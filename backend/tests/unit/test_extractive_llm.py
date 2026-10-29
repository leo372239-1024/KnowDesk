"""抽取式 LLM 测试：多行表格解析、引用、understand 不改写。"""
import asyncio

from app.core.llm import ExtractiveLLM


def _generate_prompt(entries: list[tuple[str, str]], query: str) -> str:
    context = "\n\n".join(f"[{cid}] {content}" for cid, content in entries)
    return (
        "基于以下资料回答用户问题。\n"
        f"<untrusted_document>\n{context}\n</untrusted_document>\n\n"
        f"用户问题：{query}\n"
    )


def test_extractive_parses_multiline_table():
    llm = ExtractiveLLM()
    prompt = _generate_prompt(
        [
            ("doc#0", "# XG-2000A 设备手册"),
            ("doc#3", "| 参数 | 数值 |\n|------|------|\n| 额定电流 | 10A |\n| 额定电压 | 220V |"),
        ],
        "XG-2000A 的额定电流是多少",
    )
    answer = asyncio.run(llm.agenerate([{"role": "user", "content": prompt}]))
    # 多行表格的后续行「额定电流 | 10A」应被保留并带引用
    assert "10A" in answer
    assert "额定电流" in answer
    assert "[doc#3]" in answer


def test_extractive_understand_returns_empty():
    llm = ExtractiveLLM()
    resp = asyncio.run(
        llm.agenerate(
            [
                {"role": "system", "content": "你是查询理解器。把用户问题改写为子问题。"},
                {"role": "user", "content": "XG-2000A 的额定电流是多少"},
            ]
        )
    )
    # 离线不改写，返回空让上层用原 query
    assert resp == ""


def test_extractive_no_match_returns_empty():
    llm = ExtractiveLLM()
    prompt = _generate_prompt([("doc#0", "完全无关的内容")], "XG-2000A 的额定电流是多少")
    answer = asyncio.run(llm.agenerate([{"role": "user", "content": prompt}]))
    assert answer == ""
