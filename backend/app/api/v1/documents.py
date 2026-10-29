"""文档路由：上传、列表、详情。"""
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.container import get_retrieval
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.document import DocumentListResponse, DocumentResponse
from app.services.document_service import DocumentService

router = APIRouter()


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(""),
    department: str = Form("general"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentResponse:
    raw = await file.read()
    file_type = (file.filename or "").rsplit(".", 1)[-1] if "." in (file.filename or "") else "txt"
    title = title or (file.filename or "未命名文档")
    service = DocumentService(db, get_retrieval())
    doc = await service.upload(
        title=title,
        file_type=file_type,
        raw=raw,
        tenant_id=user.tenant_id,
        department=department,
        acl_tags=list(user.acl_tags or []),
    )
    return DocumentResponse.model_validate(doc)


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentListResponse:
    service = DocumentService(db, get_retrieval())
    docs, total = await service.list_documents(user.tenant_id)
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in docs], total=total
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentResponse:
    service = DocumentService(db, get_retrieval())
    doc = await service.get_document(document_id)
    if doc is None or doc.tenant_id != user.tenant_id:
        raise NotFoundError("文档不存在")
    return DocumentResponse.model_validate(doc)
