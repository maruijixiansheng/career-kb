"""求职追踪 ORM 模型"""

from typing import Optional
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDMixin, TimestampMixin


class Application(Base, UUIDMixin, TimestampMixin):
    """投递记录"""
    __tablename__ = "applications"

    jd_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("job_descriptions.id"), nullable=True
    )
    resume_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("resumes.id"), nullable=True
    )
    generated_resume_id: Mapped[Optional[str]] = mapped_column(String(36))
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="applied",
        comment="applied/screening/written_test/interview_1/interview_2/interview_3/offer/accepted/rejected/withdrawn"
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    next_action: Mapped[Optional[str]] = mapped_column(String(500))
    next_due_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    channel: Mapped[str] = mapped_column(
        String(20), default="other",
        comment="投递渠道: boss/website/referral/liepin/other"
    )
    salary_offer: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    follow_up_notes: Mapped[Optional[str]] = mapped_column(Text, comment="跟进记录")
    interview_feedback: Mapped[Optional[str]] = mapped_column(Text, comment="面试反馈原始文本")
    interview_key_points: Mapped[Optional[dict]] = mapped_column(JSON, comment="AI提取的面试关键点")
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True, comment="所属用户"
    )


class ApplicationStatusHistory(Base, UUIDMixin):
    """状态变更历史"""
    __tablename__ = "application_status_history"

    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
