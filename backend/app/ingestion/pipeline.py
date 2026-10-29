"""入库 Pipeline 编排：解析 → 门禁 → 脱敏 → 分块 → embedding → 索引 → 写库。"""
from dataclasses import dataclass

from app.core.security import redact_pii
from app.ingestion.chunker import chunk_text
from app.ingestion.parser import parse_document
from app.retrieval.embedding import get_embedding
from app.retrieval.retriever import RetrievalService
from app.retrieval.vector_store import ChunkRecord


@dataclass
class IngestionResult:
    chunk_count: int
    chunk_records: list[tuple[ChunkRecord, list[float]]]


class IngestionPipeline:
    def __init__(self, retrieval: RetrievalService) -> None:
        self.retrieval = retrieval
        self.embedding = get_embedding()

    def process(
        self,
        raw: bytes,
        file_type: str,
        document_id: str,
        tenant_id: str,
        department: str,
        acl_tags: list[str],
    ) -> IngestionResult:
        """完整入库流程，返回生成的 chunk 记录（供上层写 PG）。"""
        # 1. 解析（含质量门禁）
        text = parse_document(raw, file_type)
        # 2. PII 脱敏
        text = redact_pii(text)
        # 3. 结构化分块
        parsed_chunks = chunk_text(text)
        if not parsed_chunks:
            from app.core.exceptions import DocumentParseError

            raise DocumentParseError("分块结果为空")
        # 4. embedding + 构建 ChunkRecord
        contents = [c.content for c in parsed_chunks]
        vectors = self.embedding.embed_documents(contents)
        records: list[tuple[ChunkRecord, list[float]]] = []
        for i, (parsed, vector) in enumerate(zip(parsed_chunks, vectors)):
            record = ChunkRecord(
                chunk_id=f"{document_id}#{i}",
                document_id=document_id,
                content=parsed.content,
                section_path=parsed.section_path,
                chunk_type=parsed.chunk_type,
                page_num=parsed.page_num,
                bbox=parsed.bbox,
                tenant_id=tenant_id,
                department=department,
                acl_tags=acl_tags,
            )
            records.append((record, vector))
        # 5. 写向量库 + BM25
        self.retrieval.index_chunks(records)
        return IngestionResult(chunk_count=len(records), chunk_records=records)
