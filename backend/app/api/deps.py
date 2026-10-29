"""FastAPI 依赖注入：当前用户、DB session。"""
import uuid

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_token
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise UnauthorizedError("缺少认证凭证")
    payload = decode_token(credentials.credentials, "access")
    user_id = payload.get("sub")
    user = await db.get(User, uuid.UUID(user_id))
    if user is None:
        raise UnauthorizedError("用户不存在")
    return user
