"""评测跑分入口：检索评测 + 问答评测，输出指标表。"""
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.agent.graph import KnowDeskAgent
from app.eval.dataset import load_dataset
from app.eval.metrics import (
    answer_accuracy,
    faithfulness,
    false_refusal,
    recall_at_k,
    refusal_correctness,
)
from app.retrieval.retriever import RetrievalService


@dataclass
class EvalReport:
    total: int = 0
    accuracy: float = 0.0
    faithfulness: float = 0.0
    refusal_correctness: float = 0.0
    false_refusal_rate: float = 0.0
    recall_at_10: float = 0.0
    failures: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "answer_accuracy": round(self.accuracy, 4),
            "faithfulness": round(self.faithfulness, 4),
            "refusal_correctness": round(self.refusal_correctness, 4),
            "false_refusal_rate": round(self.false_refusal_rate, 4),
            "recall_at_10": round(self.recall_at_10, 4),
            "failures": self.failures,
        }


async def run_eval(
    dataset_path: str,
    agent: KnowDeskAgent,
    retrieval: RetrievalService,
    tenant_id: str = "default",
    department: str | None = None,
    limit: int = 0,
) -> EvalReport:
    items = load_dataset(dataset_path)
    if limit:
        items = items[:limit]
    report = EvalReport(total=len(items))

    acc_sum = 0.0
    faith_sum = 0.0
    n_answerable = 0
    n_unanswerable = 0
    refused_correct = 0
    false_refused = 0
    recall_sum = 0.0
    recall_count = 0
    answered_with_cite = 0
    answered_count = 0

    for item in items:
        question = item["question"]
        unanswerable = item.get("unanswerable", False)
        checkpoints = item.get("checkpoints", [])
        must_cite = item.get("must_cite_doc_ids", [])

        # 1. 检索评测（Recall@10）
        if must_cite:
            results = retrieval.retrieve(question, tenant_id=tenant_id, department=department)
            doc_ids = [r.chunk.document_id for r in results]
            recall_sum += recall_at_k(doc_ids, must_cite, k=10)
            recall_count += 1

        # 2. 问答评测（单题容错：LLM 网络抖动等异常不中断整体评测）
        try:
            result = await agent.arun(question, tenant_id=tenant_id, department=department)
        except Exception as exc:  # noqa: BLE001  单题失败记录后继续，避免整场评测崩溃
            report.failures.append(
                {
                    "id": item.get("id"),
                    "type": "RUN_ERROR",
                    "question": question,
                    "error": str(exc)[:200],
                }
            )
            continue
        answer = result.get("answer", "")
        predicted_refused = result.get("refused", False)
        citations = result.get("citations", [])

        if unanswerable:
            n_unanswerable += 1
            if predicted_refused:
                refused_correct += 1
            else:
                report.failures.append(
                    {
                        "id": item.get("id"),
                        "type": "EVIDENCE_WEAK",
                        "question": question,
                        "answer": answer[:200],
                    }
                )
        else:
            n_answerable += 1
            acc = answer_accuracy(checkpoints, answer)
            acc_sum += acc
            if predicted_refused:
                false_refused += 1
                report.failures.append(
                    {"id": item.get("id"), "type": "OVER_REFUSE", "question": question}
                )
            else:
                answered_count += 1
                faith_sum += faithfulness(len(citations), len(citations))
                if citations:
                    answered_with_cite += 1
                if acc < 1.0:
                    report.failures.append(
                        {
                            "id": item.get("id"),
                            "type": "LOW_ACCURACY",
                            "question": question,
                            "accuracy": round(acc, 2),
                            "checkpoints": checkpoints,
                            "answer": answer[:200],
                        }
                    )

    n = max(1, report.total)
    report.accuracy = acc_sum / max(1, n_answerable)
    # faithfulness 只对「已作答」的可答题计（拒答题不计入分母）
    report.faithfulness = faith_sum / max(1, answered_count)
    report.refusal_correctness = refused_correct / max(1, n_unanswerable)
    report.false_refusal_rate = false_refused / max(1, n_answerable)
    if recall_count:
        report.recall_at_10 = recall_sum / recall_count
    return report


def run_eval_cli(dataset_path: str, agent: KnowDeskAgent, retrieval: RetrievalService) -> None:
    report = asyncio.run(run_eval(dataset_path, agent, retrieval))
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
