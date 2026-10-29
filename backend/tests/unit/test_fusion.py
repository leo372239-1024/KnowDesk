"""RRF 融合测试。"""
from app.retrieval.fusion import rrf_fuse


def test_rrf_fuse_merges_and_scores():
    rankings = [
        [("a", 0.9), ("b", 0.8)],
        [("b", 0.9), ("c", 0.7)],
    ]
    fused = rrf_fuse(rankings)
    # b 出现在两路，分数最高
    assert fused["b"] > fused["a"]
    assert fused["b"] > fused["c"]
    # 所有文档都在结果里
    assert set(fused) == {"a", "b", "c"}


def test_rrf_fuse_empty():
    assert rrf_fuse([]) == {}


def test_rrf_fuse_higher_rank_higher_score():
    rankings = [[("a", 0.5), ("b", 0.5)]]
    fused = rrf_fuse(rankings)
    assert fused["a"] > fused["b"]
