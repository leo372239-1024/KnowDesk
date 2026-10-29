"""BM25 关键词检索：内存倒排，支持可插拔分词器（词级 / 字符 n-gram）。

数据量小时用内存 BM25，避免维护 keyword table；大数据量时替换为 ES。
"""
from collections.abc import Callable, Iterable

from rank_bm25 import BM25Okapi

from app.retrieval.embedding import tokenize

Tokenizer = Callable[[str], list[str]]


class BM25Index:
    """轻量内存 BM25 索引，分词器可插拔（默认词级 jieba）。"""

    def __init__(self, tokenizer: Tokenizer | None = None) -> None:
        self._tokenizer: Tokenizer = tokenizer or tokenize
        self._corpus: list[str] = []
        self._tokenized: list[list[str]] = []
        self._bm25: BM25Okapi | None = None
        self._doc_ids: list[str] = []

    def add(self, doc_id: str, text: str) -> None:
        self._doc_ids.append(doc_id)
        self._corpus.append(text)
        self._tokenized.append(self._tokenizer(text))
        self._bm25 = BM25Okapi(self._tokenized)

    def remove(self, doc_id: str) -> None:
        if doc_id in self._doc_ids:
            idx = self._doc_ids.index(doc_id)
            self._doc_ids.pop(idx)
            self._corpus.pop(idx)
            self._tokenized.pop(idx)
            self._bm25 = BM25Okapi(self._tokenized) if self._tokenized else None

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """返回 [(doc_id, score)]，score 降序。"""
        if not self._bm25 or not self._doc_ids:
            return []
        scores = self._bm25.get_scores(self._tokenizer(query))
        ranked = sorted(
            zip(self._doc_ids, scores, strict=False), key=lambda x: x[1], reverse=True
        )
        return [(doc_id, float(score)) for doc_id, score in ranked[:top_k]]

    def __len__(self) -> int:
        return len(self._doc_ids)

    def ids(self) -> Iterable[str]:
        return list(self._doc_ids)
