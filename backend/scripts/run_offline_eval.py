# -*- coding: utf-8 -*-
"""离线评测对比：baseline（纯 dense 单路 + 无证据门控）vs 改进版（三路混合 + 门控）。

不依赖数据库/外网，直接跑 Golden Dataset，输出各亮点指标与改善幅度。
用法：
    python scripts/run_offline_eval.py
"""
import asyncio
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from app.agent.graph import KnowDeskAgent
from app.core.config import settings
from app.core.llm import ExtractiveLLM
from app.eval.known_docs import DOC_CONTRACT, DOC_EXPENSE, DOC_XG2000A
from app.eval.runner import run_eval
from app.ingestion.pipeline import IngestionPipeline
from app.retrieval.retriever import RetrievalService
from app.retrieval.vector_store import InMemoryVectorStore

SAMPLE_DIR = BASE / "data" / "sample_docs"
DATASET = BASE / "data" / "golden_dataset.jsonl"
DOC_FILES = {
    DOC_XG2000A: "XG-2000A设备手册.md",
    DOC_EXPENSE: "出差报销制度.md",
    DOC_CONTRACT: "合同盖章流程.md",
}


def build(hybrid: bool) -> tuple[KnowDeskAgent, RetrievalService]:
    retrieval = RetrievalService(vector_store=InMemoryVectorStore(), hybrid=hybrid)
    pipeline = IngestionPipeline(retrieval)
    for doc_id, filename in DOC_FILES.items():
        pipeline.process(
            raw=(SAMPLE_DIR / filename).read_bytes(),
            file_type="md",
            document_id=doc_id,
            tenant_id="default",
            department="general",
            acl_tags=[],
        )
    return KnowDeskAgent(ExtractiveLLM(), retrieval), retrieval


async def main() -> None:
    # 改进版
    improved_agent, improved_retr = build(hybrid=True)
    improved = await run_eval(str(DATASET), improved_agent, improved_retr,
                              tenant_id="default", department="general")

    # baseline：纯 dense + 无证据门控（阈值置 0 → 永不拒答）
    base_agent, base_retr = build(hybrid=False)
    original_threshold = settings.evidence_score_threshold
    settings.evidence_score_threshold = 0.0
    try:
        baseline = await run_eval(str(DATASET), base_agent, base_retr,
                                  tenant_id="default", department="general")
    finally:
        settings.evidence_score_threshold = original_threshold

    def delta(new: float, old: float) -> float:
        return round((new - old) / old * 100, 1) if old else 0.0

    out = {
        "baseline": baseline.to_dict(),
        "improved": improved.to_dict(),
        "improvement_pct": {
            "answer_accuracy": delta(improved.accuracy, baseline.accuracy),
            "refusal_correctness": delta(improved.refusal_correctness, baseline.refusal_correctness),
            "false_refusal_rate": delta(improved.false_refusal_rate, baseline.false_refusal_rate),
            "recall_at_10": delta(improved.recall_at_10, baseline.recall_at_10),
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
