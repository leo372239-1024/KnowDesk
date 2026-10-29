"""FastAPI 应用入口：装配日志、异常处理器、CORS、路由。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.core.logging import get_logger, setup_logging
from app.core.config import settings

setup_logging(debug=False)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时从 PG 回填 chunk 到检索服务（内存向量库不持久化）。"""
    from app.container import get_retrieval
    from app.services.backfill import backfill_retrieval

    try:
        count = await backfill_retrieval(get_retrieval())
        logger.info("backfill_chunks", count=count)
    except Exception:  # noqa: BLE001  数据库未就绪时降级启动，稍后入库仍可用
        logger.exception("backfill_failed")
    yield


app = FastAPI(title="KnowDesk API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    from app.core.logging import get_trace_id

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "trace_id": get_trace_id(),
                "detail": exc.detail,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    from app.core.logging import get_trace_id

    logger.error("unhandled_error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "服务内部错误",
                "trace_id": get_trace_id(),
            }
        },
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# 路由在 S6 阶段挂载
from app.api import router  # noqa: E402

app.include_router(router, prefix="/api/v1")
