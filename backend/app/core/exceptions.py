"""KnowDesk 统一异常体系。异常的唯一定义点，禁止在业务代码中 raise 裸异常。"""


class AppError(Exception):
    """业务异常基类：携带稳定错误码供前端/评测脚本判定。"""

    code: str = "internal_error"
    message: str = "服务内部错误"
    status_code: int = 500

    def __init__(self, message: str | None = None, detail: dict | None = None) -> None:
        super().__init__(message or self.message)
        self.message = message or self.message
        self.detail = detail

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "detail": self.detail}


class NotFoundError(AppError):
    code = "not_found"
    message = "资源不存在"
    status_code = 404


class PermissionDeniedError(AppError):
    code = "permission_denied"
    message = "无权限访问该资源"
    status_code = 403


class UnauthorizedError(AppError):
    code = "unauthorized"
    message = "未认证或凭证已失效"
    status_code = 401


class ValidationError(AppError):
    code = "validation_error"
    message = "请求参数不合法"
    status_code = 422


class DocumentParseError(AppError):
    code = "parse_failed"
    message = "文档解析失败"
    status_code = 422


class EvidenceInsufficientError(AppError):
    code = "evidence_insufficient"
    message = "资料未覆盖该问题"
    status_code = 200  # 拒答不是 HTTP 错误，业务层正常返回拒答结果


class ModelTimeoutError(AppError):
    code = "model_timeout"
    message = "模型调用超时"
    status_code = 504


class ModelDegradedError(AppError):
    code = "model_degraded"
    message = "主模型不可用，已降级到备用模型"
    status_code = 200


class RetrievalError(AppError):
    code = "retrieval_error"
    message = "检索服务异常"
    status_code = 503
