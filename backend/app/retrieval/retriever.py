"""检索编排服务：三路召回 → RRF 融合 → 重排 → ACL 前置过滤。

亮点 2 的载体：dense + 词级 BM25 + 字符级 BM25 三路召回，RRF 免调权融合，
hybrid 重排精排，证据充分度门控。
"""
from app.core.config import settings
from app.retrieval.bm25 import BM25Index
from app.retrieval.embedding import char_ngrams, get_embedding
from app.retrieval.fusion import rrf_fuse
from app.retrieval.rerank import get_reranker
from app.retrieval.vector_store import (
    BaseVectorStore,
    ChunkRecord,
    InMemoryVectorStore,
    SearchResult,
)


def compute_evidence_score(scores: list[float]) -> float:
    """证据充分度评分（单一实现，judge 与 retriever 共用）。

    以 rerank top1 分数为主信号，top1/top3 分数差作为「置信度加成」——
    仅当 top1 显著高于 top3 时小幅加分，不对多跳场景（top1≈top3）做惩罚，
    避免把「需要多 chunk 综合」的可答题误判为证据不足。
    """
    if not scores:
        return 0.0
    top1 = scores[0]
    if len(scores) >= 3:
        top3 = scores[2]
        return round(min(1.0, top1 + max(0.0, top1 - top3) * 0.2), 4)
    return round(top1, 4)


class RetrievalService:
    def __init__(
        self,
        vector_store: BaseVectorStore | None = None,
        bm25: BM25Index | None = None,
        bm25_char: BM25Index | None = None,
        hybrid: bool = True,
    ) -> None:
        self.vector_store = vector_store or InMemoryVectorStore()
        # 词级 BM25（jieba 分词，语义/术语）
        self.bm25 = bm25 or BM25Index()
        # 字符级 BM25（bigram，型号/编号精确匹配）
        self.bm25_char = bm25_char or BM25Index(tokenizer=lambda t: char_ngrams(t, 2))
        self.embedding = get_embedding()
        self.reranker = get_reranker()
        # hybrid=False 时退回纯 dense 单路（评测 baseline）
        self.hybrid = hybrid
        # chunk_id -> 完整记录缓存（多路召回的记录真源，独立于向量库实现，
        # 使 Milvus 等「不含 content」的向量库也能取回完整 chunk）
        self._records: dict[str, ChunkRecord] = {}

    def index_chunks(self, records: list[tuple[ChunkRecord, list[float]]]) -> None:
        """入库：写向量库 + 两路 BM25 + 记录缓存。"""
        self.vector_store.add(records)
        for record, _vector in records:
            self._records[record.chunk_id] = record
            self.bm25.add(record.chunk_id, record.content)
            self.bm25_char.add(record.chunk_id, record.content)

    def retrieve(
        self,
        query: str,
        tenant_id: str = "default",
        department: str | None = None,
        acl_tags: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """混合检索：三路召回 → RRF → ACL 过滤 → 重排 → TopK。"""
        if not self.hybrid:
            return self.retrieve_dense_only(query, tenant_id, department, acl_tags, top_k)
        top_k = top_k or settings.retrieve_top_k
        acl_tags = acl_tags or []

        # 1. dense 召回（向量库内已做 ACL pre-filter）
        query_vec = self.embedding.embed_query(query)
        dense_hits = self.vector_store.search(
            query_vec, tenant_id, department, acl_tags, top_k=top_k * 2
        )
        dense_ranking = [(h.chunk.chunk_id, h.score) for h in dense_hits]

        # 2. 词级 BM25 召回
        bm25_ranking = self.bm25.search(query, top_k=top_k * 3)
        # 3. 字符级 BM25 召回
        char_ranking = self.bm25_char.search(query, top_k=top_k * 3)

        # 4. RRF 融合
        fused = rrf_fuse([dense_ranking, bm25_ranking, char_ranking])
        fused_sorted = sorted(fused.items(), key=lambda x: x[1], reverse=True)

        # 5. 取融合分候选，以记录缓存为真源 + ACL 前置过滤
        candidates: list[ChunkRecord] = []
        for chunk_id, _score in fused_sorted[: top_k * 2]:
            record = self._records.get(chunk_id)
            if record is None:
                continue
            if not self._acl_allows(record, tenant_id, department, acl_tags):
                continue
            candidates.append(record)

        # 6. 重排精排
        rerank_scores = self.reranker.rerank(query, [r.content for r in candidates])
        scored: list[SearchResult] = [
            SearchResult(chunk=rec, score=s) for rec, s in zip(candidates, rerank_scores)
        ]
        scored.sort(key=lambda s: s.score, reverse=True)
        return scored[:top_k]

    def retrieve_dense_only(
        self,
        query: str,
        tenant_id: str = "default",
        department: str | None = None,
        acl_tags: list[str] | None = None,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """Baseline：纯 dense 单路召回（无 BM25、无重排），用于量化混合检索增益。"""
        top_k = top_k or settings.retrieve_top_k
        acl_tags = acl_tags or []
        query_vec = self.embedding.embed_query(query)
        return self.vector_store.search(
            query_vec, tenant_id, department, acl_tags, top_k=top_k
        )

    def evidence_score(self, results: list[SearchResult]) -> float:
        """证据充分度评分（委托给单一实现 compute_evidence_score）。"""
        return compute_evidence_score([r.score for r in results])

    def expand_siblings(
        self, results: list[SearchResult], max_total: int = 16
    ) -> list[SearchResult]:
        """章节上下文扩展：补齐命中 chunk 的同章节兄弟 chunk（生成用召回）。

        解决「流程/清单类」query 需覆盖同章节全部环节、但部分环节字面匹配弱、
        召回不足的问题（如「报销完整流程」漏召「出纳打款」环节）。
        兄弟 chunk 分数 = 源 chunk 分数 × 0.9，排在命中 chunk 之后、纯噪声之前。
        """
        if not results:
            return results
        seen: dict[str, SearchResult] = {r.chunk.chunk_id: r for r in results}
        for r in list(results):
            section = r.chunk.section_path
            if not section:
                continue
            for rec in self._records.values():
                if rec.document_id == r.chunk.document_id and rec.section_path == section:
                    if rec.chunk_id not in seen:
                        seen[rec.chunk_id] = SearchResult(chunk=rec, score=r.score * 0.9)
        return sorted(seen.values(), key=lambda x: x.score, reverse=True)[:max_total]

    @staticmethod
    def _acl_allows(
        record: ChunkRecord,
        tenant_id: str,
        department: str | None,
        acl_tags: list[str],
    ) -> bool:
        if record.tenant_id != tenant_id:
            return False
        if department and record.department != department:
            return False
        if record.acl_tags and not any(t in acl_tags for t in record.acl_tags):
            return False
        return True
