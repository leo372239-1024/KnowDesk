"""种子脚本：创建测试用户与样例文档元数据。

用法：uv run python -m scripts.seed
"""
import asyncio

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.core.security import hash_password
from app.models.user import User


async def seed() -> None:
    async with async_session_factory() as db:
        existing = await db.execute(select(User).where(User.username == "admin"))
        if existing.scalar_one_or_none() is None:
            db.add(
                User(
                    username="admin",
                    hashed_password=hash_password("admin123"),
                    role="admin",
                    tenant_id="default",
                    department="admin",
                    acl_tags=["public", "confidential"],
                )
            )
        existing = await db.execute(select(User).where(User.username == "user"))
        if existing.scalar_one_or_none() is None:
            db.add(
                User(
                    username="user",
                    hashed_password=hash_password("user123"),
                    role="user",
                    tenant_id="default",
                    department="general",
                    acl_tags=["public"],
                )
            )
        await db.commit()
    await engine.dispose()
    print("种子数据完成：admin/admin123, user/user123")


if __name__ == "__main__":
    asyncio.run(seed())
