"""用户与租户模型（RBAC）。"""
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)  # admin/user
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    department: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    acl_tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # 权限标签
