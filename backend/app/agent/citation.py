"""引用绑定与校验（亮点 3 核心）：无引用的断言裁掉，引用可回溯。"""
import re
from typing import Any

_CITE_PATTERN = re.compile(r"\[([^\]]+)\]")


def build_citations(retrieved: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """从检索结果构造引用列表，每条含定位信息（页码/bbox/snippet）。"""
    citations: list[dict[str, Any]] = []
    for item in retrieved:
        chunk = item.get("chunk", {})
        citations.append(
            {
                "chunk_id": chunk.get("chunk_id", ""),
                "document_id": chunk.get("document_id", ""),
                "section_path": chunk.get("section_path", ""),
                "page_num": chunk.get("page_num"),
                "bbox": chunk.get("bbox"),
                "snippet": (chunk.get("content", "") or "")[:200],
            }
        )
    return citations


def validate_citations(
    answer: str, valid_chunk_ids: set[str]
) -> tuple[str, list[dict[str, Any]], int]:
    """校验答案中的引用：返回 (清洗后答案, 有效引用id列表, 无效引用数)。

    规则：答案中出现的每个 [xxx] 必须命中 valid_chunk_ids；
    无效引用被移除。此函数是确定性的硬门禁，不依赖 LLM。
    """
    cited_ids: list[str] = []
    invalid_count = 0

    def _replace(match: re.Match[str]) -> str:
        nonlocal invalid_count
        token = match.group(1)
        if token in valid_chunk_ids:
            if token not in cited_ids:
                cited_ids.append(token)
            return match.group(0)
        invalid_count += 1
        return ""

    cleaned = _CITE_PATTERN.sub(_replace, answer)
    return cleaned, cited_ids, invalid_count
