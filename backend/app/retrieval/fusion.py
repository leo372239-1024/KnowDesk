"""RRF 融合：多路召回结果合并，免调权重，对专有名词/编号类 query 更友好。"""


def rrf_fuse(
    rankings: list[list[tuple[str, float]]], k: int = 60
) -> dict[str, float]:
    """多路排名列表 → {doc_id: rrf_score}。

    RRF 分数 = Σ 1/(k + rank)，rank 从 1 开始。
    """
    fused: dict[str, float] = {}
    for ranking in rankings:
        for rank, (doc_id, _score) in enumerate(ranking, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    return fused
