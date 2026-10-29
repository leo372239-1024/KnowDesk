# Error Handling

> KnowDesk 后端如何定义、传播、降级、返回错误。异常的唯一定义点是 `app/core/exceptions.py`。

## 异常体系

统一继承一个业务基类，携带稳定错误码供前端/评测脚本判定：

```python
# app/core/exceptions.py
class AppError(Exception):
    code: str          # 稳定机器码，如 "evidence_insufficient"
    message: str       # 面向用户的说明
    status_code: int   # HTTP 状态码
    detail: dict | None = None  # 结构化补充（可含 doc_id、retryable 等）
```

按层派生，禁止到处 `raise Exception("...")`：

| 异常 | code | 场景 |
|---|---|---|
| `NotFoundError` | `not_found` | 文档/会话不存在 |
| `PermissionDeniedError` | `permission_denied` | ACL 校验失败 |
| `DocumentParseError` | `parse_failed` | 解析失败（触发解析门禁，见 quality） |
| `EvidenceInsufficientError` | `evidence_insufficient` | 检索证据不足，触发拒答分支 |
| `ModelTimeoutError` | `model_timeout` | 主模型超时，可降级 |
| `ModelDegradedError` | `model_degraded` | 主模型 5xx/不可用，已降级到备用 |
| `RetrievalError` | `retrieval_error` | 向量库/ES 异常，可重试 |

## 传播与兜底

- **路由层不 try/except 业务逻辑**。业务函数直接 `raise AppError` 子类，由全局异常处理器统一转响应。
- **全局异常处理器**（`main.py` 注册）负责：把 `AppError` 转标准错误响应；把未捕获异常记为 `internal_error` 并落日志（带 trace_id）；对外只暴露 code/message，不回传堆栈。

## 降级与重试（Agent 特有，必做）

P1 的可用性依赖三段降级，每段都要写进 trace：

1. **模型降级**：主模型超时/5xx → 重试 1 次（指数退避）→ 仍失败降级备用模型，`degraded=true` 写 trace。
2. **rerank 降级**：reranker 超时 → 降级为纯 RRF 排序结果，不阻断问答。
3. **检索重试**：向量库连接异常重试 1 次；仍失败转 `RetrievalError`。

**禁止**：把降级后的结果伪装成正常结果；必须在响应/trace 中可区分。

## API 错误响应格式

统一为结构化 JSON（近似 RFC 7807）：

```json
{
  "error": {
    "code": "evidence_insufficient",
    "message": "资料未覆盖该问题，建议咨询 XX",
    "trace_id": "0193-...",
    "detail": { "suggested_owner": "财务部" }
  }
}
```

- `trace_id` 必填，用于与日志/审计关联。
- 前端根据 `code` 而非 `message` 做分支逻辑（如 `evidence_insufficient` 显示拒答话术）。

## 反模式

- ❌ `except Exception: pass` 或裸 `except:`。
- ❌ 在路由里 `return {"error": "..."}` 硬编码错误结构。
- ❌ 把未捕获异常堆栈直接返回给客户端。
- ❌ 用字符串 `raise "..."`；必须用类型化异常。
- ❌ 静默降级（降级了却不标记 `degraded`），会让评测指标失真。
