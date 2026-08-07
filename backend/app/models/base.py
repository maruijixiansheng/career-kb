"""ORM 基类和通用混入"""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class TimestampMixin:
    """创建和更新时间戳

    使用 Python 端 datetime.now 而非 SQL func.now()，
    避免 server-generated 列在 flush 后被 SQLAlchemy expire，
    从而在事务内访问这些列时触发 greenlet lazy load 错误。
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )


class UUIDMixin:
    """UUID 主键"""
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
