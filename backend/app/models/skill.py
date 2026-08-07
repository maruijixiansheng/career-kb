"""技能与Gap分析 ORM 模型"""

from typing import Optional
from sqlalchemy import String, Text, JSON, Float, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDMixin, TimestampMixin


class Skill(Base, UUIDMixin):
    """技能库"""
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(
        String(30), comment="programming/framework/tool/soft_skill/language/domain"
    )
    description: Mapped[Optional[str]] = mapped_column(Text)


class ResumeSkill(Base):
    """简历-技能关联"""
    __tablename__ = "resume_skills"

    resume_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("resumes.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )
    proficiency: Mapped[Optional[str]] = mapped_column(
        String(30), comment="beginner/intermediate/advanced/expert"
    )
    years: Mapped[Optional[float]] = mapped_column(Float)


class JDSkill(Base):
    """JD-技能关联 (含权重)"""
    __tablename__ = "jd_skills"

    jd_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_descriptions.id", ondelete="CASCADE"), primary_key=True
    )
    skill_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True
    )
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class SkillGapAnalysis(Base, UUIDMixin):
    """技能Gap分析记录"""
    __tablename__ = "skill_gap_analyses"

    resume_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("resumes.id"), nullable=False
    )
    jd_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_descriptions.id"), nullable=False
    )
    gap_result_json: Mapped[Optional[dict]] = mapped_column(JSON)
    learning_path_json: Mapped[Optional[dict]] = mapped_column(JSON)
    gap_score: Mapped[Optional[float]] = mapped_column(Float, comment="0-100 综合匹配度")
    analyzed_at: Mapped[str] = mapped_column(String(30), default="datetime('now')")
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True, comment="所属用户"
    )
