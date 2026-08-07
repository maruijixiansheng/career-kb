"""简历管理 ORM 模型"""

from typing import Optional
from sqlalchemy import String, Integer, Text, Boolean, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDMixin


class Resume(Base, UUIDMixin, TimestampMixin):
    """简历主表"""
    __tablename__ = "resumes"

    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="版本名称")
    source_filename: Mapped[Optional[str]] = mapped_column(String(500), comment="原始文件名")
    source_format: Mapped[Optional[str]] = mapped_column(String(10), comment="文件格式: pdf/docx/md")
    raw_text: Mapped[Optional[str]] = mapped_column(Text, comment="解析后的纯文本全文")
    structured_data: Mapped[Optional[dict]] = mapped_column(JSON, comment="结构化JSON数据")
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    photo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="证件照存储路径")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="所属用户"
    )

    # 关联
    chunks: Mapped[list["ResumeChunk"]] = relationship(
        "ResumeChunk", back_populates="resume", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Resume(id={self.id}, name={self.name})>"


class ResumeChunk(Base, UUIDMixin, TimestampMixin):
    """简历分块存储 (与 Chroma 向量 store 一一对应)"""
    __tablename__ = "resume_chunks"

    resume_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    chroma_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, comment="Chroma中的document id"
    )
    section_type: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="章节类型: basic_info/education/work/project/skill"
    )
    section_title: Mapped[Optional[str]] = mapped_column(String(200))
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, comment="在原简历中的位置序号")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="分块文本内容")
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, comment="元数据: company, position, skills等")
    token_count: Mapped[Optional[int]] = mapped_column(Integer)

    # 关联
    resume: Mapped["Resume"] = relationship("Resume", back_populates="chunks")

    def __repr__(self):
        return f"<ResumeChunk(id={self.id}, section={self.section_type}, index={self.chunk_index})>"
