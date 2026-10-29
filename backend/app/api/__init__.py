"""API 路由汇总。"""
from fastapi import APIRouter

from app.api.v1 import auth, chat, documents, eval as eval_api, observability

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])
router.include_router(eval_api.router, prefix="/eval", tags=["eval"])
router.include_router(observability.router, prefix="/observability", tags=["observability"])
