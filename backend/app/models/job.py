"""JD管理 ORM 模型"""

from typing import Optional
from sqlalchemy import String, Text, JSON, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDMixin, TimestampMixin


class JobDescription(Base, UUIDMixin, TimestampMixin):
    """JD 主表"""
    __tablename__ = "job_descriptions"

    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="职位名称")
    company: Mapped[Optional[str]] = mapped_column(String(200), comment="公司名称")
    raw_text: Mapped[str] = mapped_column(Text, nullable=False, comment="JD原始全文")
    structured_requirements: Mapped[Optional[dict]] = mapped_column(
        JSON, comment="LLM提取的结构化需求: {skills, responsibilities, qualifications, keywords}"
    )
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True, comment="所属用户"
    )

    def __repr__(self):
        return f"<JD(id={self.id}, title={self.title}, company={self.company})>"


class JDRequirement(Base, UUIDMixin):
    """JD 中的每条具体需求"""
    __tablename__ = "jd_requirements"

    jd_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_descriptions.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(30), comment="类别: skill/experience/education/certificate/language/other"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="需求名称")
    level: Mapped[Optional[str]] = mapped_column(String(30), comment="熟练程度")
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0, comment="重要性权重")
