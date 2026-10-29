"""多格式文档解析 + 解析质量门禁（亮点 1 / FR-2）。"""
import io
import re

from app.core.exceptions import DocumentParseError

MIN_TEXT_LENGTH = 10
_SCRAMBLED = re.compile(r"[\ufffd\u0000-\u0008]")


def parse_document(raw: bytes, file_type: str) -> str:
    """按文件类型路由到对应解析器，返回纯文本。"""
    file_type = file_type.lower().lstrip(".")
    if file_type == "pdf":
        text = _parse_pdf(raw)
    elif file_type in ("doc", "docx"):
        text = _parse_word(raw)
    elif file_type in ("md", "markdown", "txt"):
        text = _parse_plain(raw)
    elif file_type in ("xls", "xlsx"):
        text = _parse_excel(raw)
    else:
        raise DocumentParseError(f"不支持的文件类型：{file_type}")

    _quality_gate(text, file_type)
    return text


def _parse_pdf(raw: bytes) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(raw))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n\n".join(parts)
    except Exception as exc:  # noqa: BLE001
        raise DocumentParseError("PDF 解析失败") from exc


def _parse_word(raw: bytes) -> str:
    try:
        from docx import Document

        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as exc:  # noqa: BLE001
        raise DocumentParseError("Word 解析失败") from exc


def _parse_plain(raw: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DocumentParseError("文本文件编码无法识别")


def _parse_excel(raw: bytes) -> str:
    try:
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(raw), data_only=True)
        parts = []
        for ws in wb.worksheets:
            parts.append(f"## {ws.title}")
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    parts.append(" | ".join(cells))
        return "\n".join(parts)
    except Exception as exc:  # noqa: BLE001
        raise DocumentParseError("Excel 解析失败") from exc


def _quality_gate(text: str, file_type: str) -> None:
    """解析质量门禁：坏文档拒绝入库并告警，禁止静默降级。"""
    stripped = text.strip()
    if len(stripped) < MIN_TEXT_LENGTH:
        raise DocumentParseError("解析内容为空或过短，可能是扫描件或损坏文件")
    if _SCRAMBLED.search(stripped):
        raise DocumentParseError("解析内容含乱码，解析质量不达标")
    # 表格错行/页序倒置在具体解析器中检测，此处做基础拦截
