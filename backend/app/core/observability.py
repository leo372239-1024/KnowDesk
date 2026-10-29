"""可观测性：全链路 trace/span 采集。

一次问答对应一个 trace_id，LangGraph 每个节点/每次 LLM/检索调用是一个 span。
span 记录阶段名、耗时、token、top-k、拒答原因，支持离线重放与归因。
"""
import contextvars
import time
from contextlib import contextmanager
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_trace_spans_var: contextvars.ContextVar[list[dict[str, Any]]] = contextvars.ContextVar(
    "trace_spans", default=[]
)


def start_trace() -> None:
    _trace_spans_var.set([])


def get_spans() -> list[dict[str, Any]]:
    return _trace_spans_var.get()


@contextmanager
def trace_span(name: str, **metadata: Any):
    """记录一个 span 的耗时与元数据。用法：

    with trace_span("retrieve", top_k=8):
        result = do_retrieve(...)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        span = {"name": name, "elapsed_ms": elapsed_ms, **metadata}
        _trace_spans_var.get().append(span)
        logger.info("span.closed", span=name, elapsed_ms=elapsed_ms, **metadata)


def trace_snapshot() -> dict[str, Any]:
    """导出当前 trace 的全部 span 快照。"""
    return {"spans": list(_trace_spans_var.get())}
