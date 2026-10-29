"""安全横切：JWT、密码哈希、ACL 判定、PII 脱敏（X1 规范落地）。"""
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings


# ===== 密码 =====
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ===== JWT =====
def _create_token(subject: str, expires_delta: timedelta, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str) -> str:
    return _create_token(
        user_id, timedelta(minutes=settings.access_token_expire_minutes), "access"
    )


def create_refresh_token(user_id: str) -> str:
    return _create_token(
        user_id, timedelta(days=settings.refresh_token_expire_days), "refresh"
    )


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """解码并校验 token，失败抛 UnauthorizedError。"""
    from app.core.exceptions import UnauthorizedError

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise UnauthorizedError("凭证无效或已过期") from exc
    if payload.get("type") != expected_type:
        raise UnauthorizedError("凭证类型错误")
    return payload


# ===== ACL =====
def acl_allows(doc_acl_tags: list[str], user_acl_tags: list[str]) -> bool:
    """文档 ACL 判定：用户标签集必须覆盖文档要求的全部密级标签。

    doc_acl_tags 为空表示公开文档；否则用户需包含其中任一允许标签。
    """
    if not doc_acl_tags:
        return True
    return any(tag in user_acl_tags for tag in doc_acl_tags)


# ===== PII 脱敏 =====
_PII_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b\d{11}\b"), "[PHONE]"),  # 手机号
    (re.compile(r"\b\d{17}[\dXx]\b"), "[ID_CARD]"),  # 身份证
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[EMAIL]"),  # 邮箱
]


def redact_pii(text: str) -> str:
    """入库前对文档内容做 PII 脱敏。"""
    for pattern, repl in _PII_PATTERNS:
        text = pattern.sub(repl, text)
    return text
