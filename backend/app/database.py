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
    """初始化数据库表 + 自动追加缺失列"""
    import logging as _logging
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        mig_logger = _logging.getLogger("career-kb.migrate")

        async def columns_of(table: str) -> list[str]:
            if settings.DATABASE_TYPE == "sqlite":
                result = await conn.execute(text(f"PRAGMA table_info({table})"))
                return [row[1] for row in result.fetchall()]
            result = await conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = :table"
                ),
                {"table": table},
            )
            return [row[0] for row in result.fetchall()]

        # 需要补列的迁移：表名 -> [(列名, 类型)]
        tables_with_user_id = [
            "resumes", "job_descriptions", "applications", "skill_gap_analyses",
            "interview_sessions", "skill_library", "user_profile",
        ]
        migrations: dict[str, list[tuple[str, str]]] = {
            t: [("user_id", "VARCHAR(36)")] for t in tables_with_user_id
        }
        # v2.1 新增：专业课程（渲染在简历左侧栏）
        migrations["user_profile"].append(("courses", "TEXT"))

        for table, columns in migrations.items():
            try:
                existing = await columns_of(table)
                for name, ddl in columns:
                    if name not in existing:
                        await conn.execute(
                            text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                        )
                        mig_logger.info(f"迁移: {table} 表已添加 {name} 列")
            except Exception as e:
                mig_logger.warning(f"迁移 {table} 失败: {e}")

