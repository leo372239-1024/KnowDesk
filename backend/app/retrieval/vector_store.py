"""向量存储抽象：统一 Milvus 与内存实现，便于替换与离线测试。"""
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChunkRecord:
    chunk_id: str
    document_id: str
    content: str
    section_path: str = ""
    chunk_type: str = "text"
    page_num: int | None = None
    bbox: dict[str, Any] | None = None
    tenant_id: str = "default"
    department: str = "general"
    acl_tags: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    chunk: ChunkRecord
    score: float


class BaseVectorStore(ABC):
    @abstractmethod
    def add(self, records: list[tuple[ChunkRecord, list[float]]]) -> None:
        """写入 (chunk, dense_vector) 列表。"""

    @abstractmethod
    def search(
        self,
        vector: list[float],
        tenant_id: str,
        department: str | None,
        acl_tags: list[str],
        top_k: int = 10,
    ) -> list[SearchResult]:
        """按向量检索，并在召回阶段做 ACL 前置过滤。"""

    @abstractmethod
    def delete(self, chunk_ids: list[str]) -> None:
        """删除指定 chunk 向量。"""

    def get(self, chunk_id: str) -> ChunkRecord | None:
        """按 id 取回完整 chunk 记录（作为多路召回的记录真源）。默认返回 None。"""
        return None


class InMemoryVectorStore(BaseVectorStore):
    """内存向量存储：余弦相似度 + ACL 过滤，用于单元测试与离线 demo。"""

    def __init__(self) -> None:
        self._records: dict[str, ChunkRecord] = {}
        self._vectors: dict[str, list[float]] = {}

    def get(self, chunk_id: str) -> ChunkRecord | None:
        return self._records.get(chunk_id)

    def add(self, records: list[tuple[ChunkRecord, list[float]]]) -> None:
        for record, vector in records:
            self._records[record.chunk_id] = record
            self._vectors[record.chunk_id] = vector

    def search(
        self,
        vector: list[float],
        tenant_id: str,
        department: str | None,
        acl_tags: list[str],
        top_k: int = 10,
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        for chunk_id, rec in self._records.items():
            # ACL 前置过滤（pre-filter）
            if rec.tenant_id != tenant_id:
                continue
            if department and rec.department != department:
                continue
            if rec.acl_tags and not any(t in acl_tags for t in rec.acl_tags):
                continue
            score = self._cosine(vector, self._vectors[chunk_id])
            results.append(SearchResult(chunk=rec, score=score))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def delete(self, chunk_ids: list[str]) -> None:
        for chunk_id in chunk_ids:
            self._records.pop(chunk_id, None)
            self._vectors.pop(chunk_id, None)

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(y * y for y in b)) or 1.0
        return dot / (na * nb)


class MilvusVectorStore(BaseVectorStore):
    """Milvus 实现（pymilvus）。连接失败抛 RetrievalError，由上层降级。"""

    def __init__(self, host: str, port: int, collection_name: str, dim: int) -> None:
        from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections

        self._collection_name = collection_name
        self._dim = dim
        connections.connect("default", host=host, port=port)
        self._ensure_collection()
        self._collection = Collection(collection_name)

    def _ensure_collection(self) -> None:
        from pymilvus import (
            Collection,
            CollectionSchema,
            DataType,
            FieldSchema,
            utility,
        )

        if utility.has_collection(self._collection_name):
            return
        fields = [
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema(name="dense", dtype=DataType.FLOAT_VECTOR, dim=self._dim),
            FieldSchema(name="tenant_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="department", dtype=DataType.VARCHAR, max_length=64),
        ]
        schema = CollectionSchema(fields, description="KnowDesk chunks")
        collection = Collection(self._collection_name, schema=schema)
        collection.create_index(
            field_name="dense",
            index_params={"metric_type": "IP", "index_type": "IVF_FLAT", "params": {"nlist": 128}},
        )
        collection.load()

    def add(self, records: list[tuple[ChunkRecord, list[float]]]) -> None:
        if not records:
            return
        self._collection.insert(
            [
                [r.chunk_id for r, _ in records],
                [v for _, v in records],
                [r.tenant_id for r, _ in records],
                [r.department for r, _ in records],
            ]
        )
        self._collection.flush()

    def search(
        self,
        vector: list[float],
        tenant_id: str,
        department: str | None,
        acl_tags: list[str],
        top_k: int = 10,
    ) -> list[SearchResult]:
        from pymilvus import Collection

        expr = f'tenant_id == "{tenant_id}"'
        if department:
            expr += f' and department == "{department}"'
        self._collection.load()
        res = self._collection.search(
            data=[vector],
            anns_field="dense",
            param={"metric_type": "IP", "params": {"nprobe": 16}},
            limit=top_k,
            expr=expr,
            output_fields=["chunk_id", "tenant_id", "department"],
        )
        # Milvus 不含 content，需回查（MVP 通过 PG 回填，这里返回占位由上层补齐）
        results: list[SearchResult] = []
        for hit in res[0]:
            rec = ChunkRecord(
                chunk_id=hit.entity.get("chunk_id"),
                document_id="",
                content="",
                tenant_id=hit.entity.get("tenant_id", "default"),
                department=hit.entity.get("department", "general"),
            )
            results.append(SearchResult(chunk=rec, score=float(hit.score)))
        return results

    def delete(self, chunk_ids: list[str]) -> None:
        if chunk_ids:
            self._collection.delete(f'chunk_id in {chunk_ids!r}')
