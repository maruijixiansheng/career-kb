"""数据库连接和会话管理 — SQLite / PostgreSQL 双模式"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from .config import settings

# SQLite 和 PostgreSQL 连接参数不同
_connect_args = {}
if settings.DATABASE_TYPE == "sqlite":
    _connect_args["check_same_thread"] = False

engine_kwargs = {"echo": False}
if _connect_args:
    engine_kwargs["connect_args"] = _connect_args

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

# expire_on_commit=False: 提交后不使属性过期。
# 配合 Python 端时间戳（非 server-generated），
# 避免 commit 后访问 ORM 属性时触发 greenlet lazy load。
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """ORM 基类"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI 依赖: 获取数据库会话"""
    session = async_session()
    try:
        yield session
    finally:
        await session.close()


async def init_db():
    """初始化数据库表 + 自动迁移缺失列"""
    import logging as _logging
    from sqlalchemy import text, inspect

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    _migrate_logger = _logging.getLogger("career-kb.migrate")
    tables_with_user_id = [
        "resumes", "job_descriptions", "applications", "skill_gap_analyses",
        "interview_sessions", "skill_library", "user_profile",
    ]

    for table in tables_with_user_id:
        try:
            if settings.DATABASE_TYPE == "sqlite":
                result = await conn.execute(text(f"PRAGMA table_info({table})"))
                columns = [row[1] for row in result.fetchall()]
            else:
                # PostgreSQL: 查询 information_schema
                result = await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = :table"
                    ),
                    {"table": table},
                )
                columns = [row[0] for row in result.fetchall()]

            if "user_id" not in columns:
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN user_id VARCHAR(36)")
                )
                _migrate_logger.info(f"迁移: {table} 表已添加 user_id 列")
            await conn.commit()
        except Exception as e:
            _migrate_logger.warning(f"迁移 {table} 失败: {e}")
            await conn.rollback()
