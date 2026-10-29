# -*- coding: utf-8 -*-
"""通用评测：用当前 .env 配置的 LLM 跑 Golden Dataset，输出指标 + 失败明细。

用法：
    python scripts/run_eval.py [--limit N] [--verbose]
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from app.agent.graph import KnowDeskAgent
from app.core.llm import get_llm
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


def build_agent() -> tuple[KnowDeskAgent, RetrievalService]:
    retrieval = RetrievalService(vector_store=InMemoryVectorStore(), hybrid=True)
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
    return KnowDeskAgent(get_llm(), retrieval), retrieval


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 题（0=全量）")
    args = parser.parse_args()

    agent, retrieval = build_agent()
    report = await run_eval(
        str(DATASET), agent, retrieval, tenant_id="default", department="general",
        limit=args.limit,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
