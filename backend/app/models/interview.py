"""面试模拟 ORM 模型"""

from typing import Optional
from datetime import datetime
from sqlalchemy import String, Text, JSON, Float, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, UUIDMixin, TimestampMixin


class InterviewSession(Base, UUIDMixin):
    """面试会话"""
    __tablename__ = "interview_sessions"

    jd_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("job_descriptions.id")
    )
    resume_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("resumes.id")
    )
    mode: Mapped[str] = mapped_column(
        String(20), default="technical",
        comment="technical/behavioral/mixed"
    )
    difficulty: Mapped[Optional[str]] = mapped_column(
        String(10), comment="easy/medium/hard"
    )
    interviewer_role: Mapped[Optional[str]] = mapped_column(
        String(100), comment="e.g. 技术面试官, HR"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="active/completed"
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True, comment="所属用户"
    )


class InterviewMessage(Base, UUIDMixin):
    """面试消息"""
    __tablename__ = "interview_messages"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="interviewer/candidate/system"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class InterviewReport(Base, UUIDMixin):
    """面试评估报告"""
    __tablename__ = "interview_reports"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False, unique=True
    )
    overall_score: Mapped[Optional[float]] = mapped_column(Float, comment="0-100")
    dimension_scores: Mapped[Optional[dict]] = mapped_column(JSON)
    strengths: Mapped[Optional[dict]] = mapped_column(JSON)
    weaknesses: Mapped[Optional[dict]] = mapped_column(JSON)
    suggestions: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
