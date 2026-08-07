"""ORM 模型注册 (确保所有模型被 Base.metadata 发现)"""

from .base import Base, TimestampMixin, UUIDMixin
from .resume import Resume, ResumeChunk
from .job import JobDescription, JDRequirement
from .application import Application, ApplicationStatusHistory
from .skill import Skill, ResumeSkill, JDSkill, SkillGapAnalysis
from .interview import InterviewSession, InterviewMessage, InterviewReport
from .evaluation import GenerationEval, EvalMetric
from .skill_library import SkillLibraryEntry
from .user_profile import UserProfile
from .user import User

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    "Resume",
    "ResumeChunk",
    "JobDescription",
    "JDRequirement",
    "Application",
    "ApplicationStatusHistory",
    "Skill",
    "ResumeSkill",
    "JDSkill",
    "SkillGapAnalysis",
    "InterviewSession",
    "InterviewMessage",
    "InterviewReport",
    "GenerationEval",
    "EvalMetric",
    "SkillLibraryEntry",
    "UserProfile",
    "User",
]
