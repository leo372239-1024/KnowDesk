"""Rerank 抽象：精排召回候选。

- HybridReranker（默认，离线可用）：融合 dense 余弦 + query 内容覆盖度 + 字符
  n-gram 精确匹配，解决「长 chunk + 短 query」在纯余弦下被长度稀释的问题。
- DenseReranker：纯 dense 余弦（评测 baseline，用于量化混合重排的增益）。
- SentenceTransformerReranker：真实 bge-reranker cross-encoder（需 [ml] 依赖）。
"""
import math
from abc import ABC, abstractmethod

from app.core.config import settings
from app.retrieval.embedding import char_ngrams, get_embedding, meaningful_tokens


class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        """返回与 candidates 等长的相关性分数（越高越相关）。"""


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _query_coverage(query: str, chunk: str) -> tuple[float, float]:
    """计算 query 内容被 chunk 覆盖的程度。

    返回 (word_coverage, char_gram_coverage) 两个 [0,1] 信号：
    - word_coverage：有意义词元命中比例（语义/术语匹配，主信号）。
    - char_gram_coverage：字符 bigram 命中比例（型号/编号精确匹配，辅信号）。
    """
    q_tokens = meaningful_tokens(query)
    c_tokens = set(meaningful_tokens(chunk))
    word_cov = (sum(1 for t in q_tokens if t in c_tokens) / len(q_tokens)) if q_tokens else 0.0

    q_grams = char_ngrams(query, 2)
    c_grams = set(char_ngrams(chunk, 2))
    gram_cov = (sum(1 for g in q_grams if g in c_grams) / len(q_grams)) if q_grams else 0.0
    return word_cov, gram_cov


class HybridReranker(BaseReranker):
    """离线混合重排：dense 余弦 + query 覆盖度 + 字符 n-gram 精确匹配。

    权重设计（对长/短不对称鲁棒）：覆盖度是主信号——相关 chunk 往往完整包含
    query 的内容词元，而不受 chunk 长度稀释；dense 余弦作为语义补充。
    """

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        emb = get_embedding()
        # batch 向量化（query + 全部候选一次请求），避免逐个 HTTP 调用
        vectors = emb.embed_documents([query, *candidates])
        qv, cand_vecs = vectors[0], vectors[1:]
        scores: list[float] = []
        for cand, cv in zip(candidates, cand_vecs):
            dense = _cosine(qv, cv)
            word_cov, gram_cov = _query_coverage(query, cand)
            score = 0.35 * dense + 0.45 * word_cov + 0.20 * gram_cov
            scores.append(round(score, 6))
        return scores


class DenseReranker(BaseReranker):
    """纯 dense 余弦重排（评测 baseline：对比混合重排的增益）。"""

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        emb = get_embedding()
        vectors = emb.embed_documents([query, *candidates])
        qv, cand_vecs = vectors[0], vectors[1:]
        return [round(_cosine(qv, cv), 6) for cv in cand_vecs]


class SentenceTransformerReranker(BaseReranker):
    def __init__(self, model_name: str | None = None) -> None:
        from sentence_transformers import CrossEncoder

        self.model_name = model_name or settings.rerank_model
        self.model = CrossEncoder(self.model_name)

    def rerank(self, query: str, candidates: list[str]) -> list[float]:
        if not candidates:
            return []
        pairs = [[query, c] for c in candidates]
        scores = self.model.predict(pairs)
        return [float(s) for s in scores]


def get_reranker() -> BaseReranker:
    if settings.rerank_provider == "sentence_transformer":
        return SentenceTransformerReranker()
    return HybridReranker()
