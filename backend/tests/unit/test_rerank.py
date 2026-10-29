"""混合重排测试：长 chunk + 短 query 场景下的相关/不相关分离度。"""
from app.retrieval.rerank import DenseReranker, HybridReranker, get_reranker


def test_hybrid_rerank_separates_related_from_unrelated():
    q = "XG-2000A 的额定电流是多少"
    related = "XG-2000A 设备额定电流为 10A，额定电压 220V，额定功率 2.2kW，工作频率 50Hz。"
    unrelated = "明年 Q3 的销售目标是多少，市场部预算如何分配。"

    hybrid = HybridReranker()
    rel, unrel = hybrid.rerank(q, [related, unrelated])

    # 相关分明显高于无关分，且跨越证据门控阈值（0.35）
    assert rel > unrel
    assert rel > 0.35
    assert unrel < 0.35


def test_hybrid_beats_dense_separation():
    q = "XG-2000A 的额定电流是多少"
    related = "XG-2000A 设备额定电流为 10A，额定电压 220V。"
    unrelated = "明年 Q3 的销售目标是多少。"

    dense = DenseReranker()
    hybrid = HybridReranker()
    d_rel, d_unrel = dense.rerank(q, [related, unrelated])
    h_rel, h_unrel = hybrid.rerank(q, [related, unrelated])

    dense_gap = d_rel - d_unrel
    hybrid_gap = h_rel - h_unrel
    # 混合重排的分离度应显著大于纯余弦
    assert hybrid_gap > dense_gap


def test_get_reranker_default_hybrid():
    assert isinstance(get_reranker(), HybridReranker)
