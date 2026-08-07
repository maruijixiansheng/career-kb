"""用户认证模型"""

from typing import Optional
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDMixin, TimestampMixin


class User(Base, UUIDMixin, TimestampMixin):
    """用户账户"""
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False, comment="登录邮箱"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="bcrypt 密码哈希"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="用户昵称"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否启用"
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"
