"""结构化分块（亮点 1 核心）。

策略：结构优先 + 语义补充。
1. 按标题层级（# / 数字编号 / 第X章）切大块，保证语义完整。
2. 表格独立成块，且全量保留表头。
3. 大块超过阈值时按句子断点二次切。
4. 每个 chunk 携带 section_path（章节路径）与 chunk_type。
"""
import re
from dataclasses import dataclass, field
from typing import Any

MAX_CHUNK_CHARS = 800  # 约 500 token（中文）
_TITLE_PATTERNS = [
    re.compile(r"^(#{1,6})\s+(.+)$"),  # markdown 标题
    re.compile(r"^第[一二三四五六七八九十百\d]+[章节条款]\s*.*$"),  # 第X章/节/条/款
    re.compile(r"^(\d+(\.\d+)*)[、.．]\s*.+$"),  # 数字编号 1. / 1.1
]
# 章节级标题：只有这些才更新 section_path（数字编号「子条款」继承父章节）
_SECTION_TITLE_RE = re.compile(r"^(#{1,6})\s+(.+)$")
_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百\d]+[章节]\s*.*$")
_TABLE_ROW = re.compile(r"^\s*\|.+\|\s*$")


@dataclass
class ParsedChunk:
    content: str
    section_path: str
    chunk_type: str = "text"  # text / table / clause
    page_num: int | None = None
    bbox: dict[str, Any] | None = None
    token_count: int = field(default=0)

    def __post_init__(self) -> None:
        self.token_count = len(self.content)


def _detect_title(line: str) -> str | None:
    """识别标题行，返回标题文本；非标题返回 None。"""
    for pattern in _TITLE_PATTERNS:
        m = pattern.match(line.strip())
        if m:
            return line.strip()
    return None


def _is_table_row(line: str) -> bool:
    return bool(_TABLE_ROW.match(line.strip()))


def chunk_text(text: str, page_num: int | None = None) -> list[ParsedChunk]:
    """对纯文本做结构化分块，返回有序 chunk 列表。"""
    lines = text.splitlines()
    chunks: list[ParsedChunk] = []
    current: list[str] = []
    section_path = ""
    pending_table: list[str] = []
    table_header: list[str] = []

    def flush_text() -> None:
        nonlocal current
        if not current:
            return
        body = "\n".join(current).strip()
        current = []
        if not body:
            return
        for piece in _split_long(body):
            chunks.append(
                ParsedChunk(
                    content=piece,
                    section_path=section_path,
                    chunk_type="clause" if _is_clause(piece) else "text",
                    page_num=page_num,
                )
            )

    def flush_table() -> None:
        nonlocal pending_table, table_header
        if not pending_table:
            return
        # 表格独立成块：全量保留表头（关键细节）
        header = table_header[0] if table_header else ""
        body_rows = [r for r in pending_table if r not in table_header]
        content = "\n".join([header] + body_rows) if header else "\n".join(pending_table)
        if content.strip():
            chunks.append(
                ParsedChunk(
                    content=content.strip(),
                    section_path=section_path,
                    chunk_type="table",
                    page_num=page_num,
                )
            )
        pending_table = []
        table_header = []

    for line in lines:
        stripped = line.strip()
        # 标题：先 flush 现有内容与表格，标题本身也作为 chunk 内容保留
        title = _detect_title(stripped)
        if title and not _is_table_row(stripped):
            flush_table()
            flush_text()
            # 只有章节级标题才更新 section_path；数字编号「子条款」继承父章节，
            # 使同章节的条款 chunk 拥有相同的 section_path（供章节上下文扩展/追溯）。
            if _SECTION_TITLE_RE.match(stripped) or _CHAPTER_RE.match(stripped):
                section_path = stripped
            current.append(line.rstrip())
            continue
        # 表格行
        if _is_table_row(stripped):
            flush_text()
            if not pending_table:
                table_header = [line.rstrip()]
            pending_table.append(line.rstrip())
            continue
        # 空行
        if not stripped:
            flush_table()
            continue
        # 普通行
        flush_table()
        current.append(line.rstrip())

    flush_table()
    flush_text()
    return chunks


def _is_clause(text: str) -> bool:
    """条款类 chunk：内容以「第X条/款」或数字编号（1.1 / 4.1）开头。"""
    return bool(re.search(r"第[一二三四五六七八九十百\d]+[条款]", text)) or bool(
        re.match(r"^\d+(\.\d+)+[、.．]", text)
    )


def _split_long(body: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """超长段落按句子断点二次切分。"""
    if len(body) <= max_chars:
        return [body]
    sentences = re.split(r"(?<=[。！？；\n])", body)
    pieces: list[str] = []
    buf = ""
    for sentence in sentences:
        if len(buf) + len(sentence) > max_chars and buf:
            pieces.append(buf.strip())
            buf = sentence
        else:
            buf += sentence
    if buf.strip():
        pieces.append(buf.strip())
    return pieces or [body]
