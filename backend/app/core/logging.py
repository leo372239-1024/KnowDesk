"""structlog 装配与 trace_id 上下文传播。

日志同时服务排障、可观测性（trace）、审计三件事。
trace_id 通过 contextvar 隔离，避免多并发串号。
"""
import contextvars
import sys
import uuid

import structlog

_trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


def new_trace_id() -> str:
    return str(uuid.uuid4())


def set_trace_id(trace_id: str) -> None:
    _trace_id_var.set(trace_id)


def get_trace_id() -> str:
    return _trace_id_var.get()


def _trace_id_processor(logger, method_name, event_dict):  # noqa: ANN001
    if not event_dict.get("trace_id"):
        event_dict["trace_id"] = _trace_id_var.get()
    return event_dict


def setup_logging(debug: bool = False) -> None:
    """在应用启动时调用一次，装配 structlog。"""
    processors = [
        structlog.contextvars.merge_contextvars,
        _trace_id_processor,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if debug:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            __import__("logging").DEBUG if debug else __import__("logging").INFO
        ),
        cache_logger_on_first_use=True,
    )
    # 标准库日志兜底重定向到 stdout
    logging = __import__("logging")
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def get_logger(name: str = "knowdesk"):
    return structlog.get_logger(name)
