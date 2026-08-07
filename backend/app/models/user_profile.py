"""用户基本信息 ORM 模型 — 单例"""

from typing import Optional
from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class UserProfile(Base, UUIDMixin, TimestampMixin):
    """用户基本信息（单例）"""

    __tablename__ = "user_profile"

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, default="未命名", comment="姓名"
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="邮箱"
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="手机号"
    )
    city: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="所在城市"
    )
    current_role: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="当前职位"
    )
    years_of_experience: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="工作年限"
    )
    education: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="最高学历: 高中/大专/本科/硕士/博士"
    )
    school: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="毕业院校"
    )
    major: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="专业"
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="个人简介"
    )
    expected_role: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="期望职位"
    )
    expected_salary: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="期望薪资"
    )
    job_status: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="求职状态: 在职看机会/已离职/应届生"
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True, unique=True, index=True, comment="所属用户"
    )

    def __repr__(self):
        return f"<UserProfile(id={self.id}, name={self.name})>"
