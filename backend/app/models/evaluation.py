"""评估体系 ORM 模型"""

from typing import Optional
from sqlalchemy import String, Text, JSON, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from .base import Base, UUIDMixin


class GenerationEval(Base, UUIDMixin):
    """简历生成评估记录 (核心效果度量)"""
    __tablename__ = "generation_evals"

    resume_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("resumes.id"), nullable=False
    )
    jd_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_descriptions.id"), nullable=False
    )
    generated_text: Mapped[str] = mapped_column(Text, nullable=False)
    human_review: Mapped[Optional[str]] = mapped_column(
        String(20), comment="approved/needs_revision/rejected"
    )
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text)
    pass_through: Mapped[Optional[bool]] = mapped_column(
        Boolean, comment="是否真实通过初筛 (实际反馈)"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class EvalMetric(Base, UUIDMixin):
    """自动评估指标详情"""
    __tablename__ = "eval_metrics"

    eval_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generation_evals.id", ondelete="CASCADE"), nullable=False
    )
    metric_name: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="keyword_coverage/factual_consistency/jd_match_score/structure_score/readability"
    )
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    details_json: Mapped[Optional[dict]] = mapped_column(JSON)
