"""评测 API：评测集管理 + 触发跑分。"""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.container import get_agent, get_retrieval
from app.core.database import get_db
from app.eval.runner import run_eval
from app.models.eval import EvalDataset, EvalRun
from app.models.user import User
from app.schemas.eval import EvalDatasetCreate, EvalRunResponse

router = APIRouter()


@router.post("/datasets", response_model=dict)
async def create_dataset(
    payload: EvalDatasetCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    ds = EvalDataset(name=payload.name, questions=payload.questions)
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return {"id": str(ds.id), "name": ds.name, "count": len(ds.questions)}


@router.get("/datasets", response_model=list[dict])
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    result = await db.execute(select(EvalDataset).order_by(EvalDataset.created_at.desc()))
    datasets = result.scalars().all()
    return [{"id": str(d.id), "name": d.name, "count": len(d.questions)} for d in datasets]


@router.post("/run/{dataset_id}", response_model=EvalRunResponse)
async def run_evaluation(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EvalRunResponse:
    ds = await db.get(EvalDataset, uuid.UUID(dataset_id))
    if ds is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("评测集不存在")

    # 临时把评测集写入本地文件供 runner 读取
    import json
    import tempfile

    agent = get_agent()
    retrieval = get_retrieval()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(ds.questions, f, ensure_ascii=False)
        tmp_path = f.name
    report = await run_eval(
        tmp_path, agent, retrieval, tenant_id=user.tenant_id, department=user.department
    )

    run = EvalRun(dataset_id=ds.id, metrics=report.to_dict(), report=json.dumps(report.to_dict(), ensure_ascii=False))
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return EvalRunResponse(
        id=str(run.id),
        dataset_id=str(run.dataset_id),
        metrics=run.metrics,
        report=run.report,
        created_at=str(run.created_at),
    )
