"""Golden Dataset 加载与校验。"""
import json
from pathlib import Path
from typing import Any

TASK_TYPES = {"参数查询", "制度判定", "多文档综合", "流程指引", "拒答判定"}


class DatasetError(ValueError):
    pass


def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    """加载评测集（JSON 数组或 JSONL），并校验结构。"""
    path = Path(path)
    if not path.exists():
        raise DatasetError(f"评测集不存在：{path}")

    items: list[dict[str, Any]] = []
    if path.suffix == ".jsonl":
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    items.append(json.loads(line))
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("questions", [])

    for item in items:
        _validate(item)
    return items


def _validate(item: dict[str, Any]) -> None:
    if "question" not in item:
        raise DatasetError("评测题缺少 question 字段")
    if "unanswerable" not in item:
        item["unanswerable"] = False
    if not item.get("unanswerable"):
        if not item.get("checkpoints"):
            raise DatasetError(f"可答题 {item.get('id', '?')} 缺少 checkpoints")
    item.setdefault("checkpoints", [])
    item.setdefault("must_cite_doc_ids", [])
