"""评测相关 schema。"""
import uuid
from typing import Any

from pydantic import BaseModel


class EvalDatasetCreate(BaseModel):
    name: str
    questions: list[dict[str, Any]]


class EvalRunResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    metrics: dict[str, Any]
    report: str
    created_at: str

    model_config = {"from_attributes": True}
