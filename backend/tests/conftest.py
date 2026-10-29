"""测试全局 fixture：强制离线（fake embedding），保证测试可离线、可重复。

真实 embedding（openai_compat / sentence_transformer）依赖外部服务/模型，
测试中一律降级为确定性 FakeEmbedding，避免网络依赖与不可重复。
"""
import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _force_offline_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """把 embedding/rerank 提供者强制为 fake，隔离外部依赖。"""
    monkeypatch.setattr(settings, "embedding_provider", "fake")
    monkeypatch.setattr(settings, "rerank_provider", "fake")
    yield
