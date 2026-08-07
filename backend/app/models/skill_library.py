"""技能库 ORM 模型 — 用户手写技术栈/项目/实习经历"""

from typing import Optional
from sqlalchemy import String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, UUIDMixin


class SkillLibraryEntry(Base, UUIDMixin, TimestampMixin):
    """技能库条目 — 用户手动录入的技术栈、项目、实习等"""

    __tablename__ = "skill_library"

    # 类型: skill / project / internship / certificate / other
    entry_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True,
        comment="条目类型: skill/project/internship/certificate/other"
    )

    # 标题（技能名/项目名/公司名等）
    title: Mapped[str] = mapped_column(
        String(300), nullable=False, comment="标题"
    )

    # 详细内容（技能描述/项目详情/实习职责等）
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="详细内容"
    )

    # 技术标签（逗号分隔，便于检索匹配）
    tags: Mapped[Optional[str]] = mapped_column(
        String(1000), nullable=True, comment="技术标签，逗号分隔"
    )

    # 时间范围（项目/实习适用）
    start_date: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, comment="开始时间 YYYY-MM"
    )
    end_date: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, comment="结束时间 YYYY-MM"
    )

    # 重要程度 1-5（影响检索权重）
    importance: Mapped[int] = mapped_column(
        Integer, default=3, comment="重要程度 1-5"
    )

    # 是否公开（某些敏感信息可隐藏）
    is_active: Mapped[bool] = mapped_column(default=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True, comment="所属用户"
    )

    def __repr__(self):
        return f"<SkillLibrary(id={self.id}, type={self.entry_type}, title={self.title})>"
