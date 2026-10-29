"""评测指标计算（checklist 要点法，非 BLEU/ROUGE）。"""
import re


def answer_accuracy(checkpoints: list[str], answer: str) -> float:
    """要点覆盖率：答案文本命中 checkpoints 的比例。"""
    if not checkpoints:
        return 1.0
    hits = sum(1 for cp in checkpoints if _hit(cp, answer))
    return hits / len(checkpoints)


def _hit(checkpoint: str, answer: str) -> bool:
    """要点命中：拆关键词，全部命中视为该要点覆盖。

    对「数值+单位」类 checkpoint（如 "12.5kg"）容忍答案中的空格（"12.5 kg"），
    避免 LLM 输出自然带空格导致的假阴性。
    """
    keywords = [k for k in checkpoint.split() if len(k) >= 2]
    if not keywords:
        return checkpoint in answer
    compact_answer = re.sub(r"\s+", "", answer)
    for k in keywords:
        if k in answer:
            continue
        if re.sub(r"\s+", "", k) in compact_answer:
            continue
        return False
    return True


def faithfulness(valid_citations: int, total_citations: int) -> float:
    """引用支持率：有效引用 / 总引用。无引用时视为不忠实（返回 0）。"""
    if total_citations == 0:
        return 0.0
    return valid_citations / total_citations


def refusal_correctness(predicted_refused: bool, unanswerable: bool) -> float:
    """不可答题被正确拒答。"""
    return 1.0 if (unanswerable and predicted_refused) else 0.0


def false_refusal(predicted_refused: bool, unanswerable: bool) -> float:
    """可答题被误拒。"""
    return 1.0 if (not unanswerable and predicted_refused) else 0.0


def recall_at_k(retrieved_doc_ids: list[str], must_cite: list[str], k: int = 10) -> float:
    """Recall@k：标准答案所需文档进入 Top-k 的比例。"""
    if not must_cite:
        return 1.0
    top_k = retrieved_doc_ids[:k]
    hits = sum(1 for d in must_cite if d in top_k)
    return hits / len(must_cite)
