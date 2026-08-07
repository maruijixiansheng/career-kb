"""Pydantic 请求/响应模型"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


# ===== 认证 =====

class UserRegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255, description="登录邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="登录密码")
    name: str = Field(..., min_length=1, max_length=100, description="用户昵称")


class UserLoginRequest(BaseModel):
    email: str = Field(..., description="登录邮箱")
    password: str = Field(..., description="登录密码")


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    is_active: bool = True
    created_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ===== 简历 =====

class ResumeCreate(BaseModel):
    """上传简历 (文件通过 FormData 处理)"""
    name: str = Field(..., description="版本名称")

class ResumeResponse(BaseModel):
    id: str
    name: str
    source_filename: Optional[str] = None
    source_format: Optional[str] = None
    chunk_count: int = 0
    photo_url: Optional[str] = None
    has_photo: bool = False
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ResumeDetailResponse(ResumeResponse):
    raw_text: Optional[str] = None
    structured_data: Optional[dict] = None

class ChunkResponse(BaseModel):
    id: str
    section_type: str
    section_title: Optional[str] = None
    chunk_index: int
    content: str
    metadata: Optional[dict] = None
    token_count: Optional[int] = None


# ===== JD =====

class JDCreate(BaseModel):
    """上传/创建 JD"""
    title: str = Field(..., description="职位名称")
    company: Optional[str] = None
    raw_text: str = Field(..., description="JD 原文")

class JDResponse(BaseModel):
    id: str
    title: str
    company: Optional[str] = None
    created_at: Optional[datetime] = None

class JDDetailResponse(JDResponse):
    raw_text: str
    structured_requirements: Optional[dict] = None


# ===== 简历重组 =====

class RestructureRequest(BaseModel):
    """简历重组请求"""
    jd_id: Optional[str] = None         # 使用已有 JD
    jd_text: Optional[str] = None       # 或者直接粘贴 JD 文本
    jd_title: Optional[str] = None
    jd_company: Optional[str] = None

class RestructureResponse(BaseModel):
    restructured_markdown: str
    changes_summary: Optional[str] = None
    match_score: Optional[float] = None
    fact_check: Optional[dict] = None


class GeneratePdfRequest(BaseModel):
    """PDF 生成请求 — 接收已生成的 Markdown 文本"""
    markdown: str = Field(..., description="LLM 生成的 Markdown 简历")
    title: Optional[str] = Field(None, description="岗位名称，用于文件命名")


# ===== 求职追踪 =====

class ApplicationCreate(BaseModel):
    jd_id: Optional[str] = None
    resume_id: Optional[str] = None
    company: str
    position: str
    status: str = "applied"
    channel: str = "other"  # boss/website/referral/liepin/other
    applied_at: Optional[datetime] = None
    notes: Optional[str] = None

class ApplicationUpdate(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    status: Optional[str] = None
    channel: Optional[str] = None
    next_action: Optional[str] = None
    next_due_date: Optional[datetime] = None
    salary_offer: Optional[str] = None
    notes: Optional[str] = None
    follow_up_notes: Optional[str] = None

class ApplicationResponse(BaseModel):
    id: str
    company: str
    position: str
    status: str
    channel: Optional[str] = "other"
    resume_id: Optional[str] = None
    jd_id: Optional[str] = None
    applied_at: Optional[datetime] = None
    next_action: Optional[str] = None
    next_due_date: Optional[datetime] = None
    salary_offer: Optional[str] = None
    notes: Optional[str] = None
    follow_up_notes: Optional[str] = None
    interview_feedback: Optional[str] = None
    interview_key_points: Optional[dict] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ApplicationStats(BaseModel):
    total: int
    by_status: dict
    conversion_rates: dict


# ===== 面试模拟 =====

class InterviewStartRequest(BaseModel):
    resume_id: str
    jd_id: Optional[str] = None
    mode: str = "technical"  # technical/behavioral/mixed

class InterviewRespondRequest(BaseModel):
    answer: str

class InterviewMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sequence: int

class InterviewFeedbackResponse(BaseModel):
    overall_score: Optional[float] = None
    dimension_scores: Optional[dict] = None
    strengths: Optional[list] = None
    weaknesses: Optional[list] = None
    suggestions: Optional[str] = None


# ===== 无回应分析 (Phase 2) =====

class NoResponseAnalysisRequest(BaseModel):
    """无回应分析请求"""
    days_since_apply: int = Field(default=7, ge=1, description="投递距今多少天")

class NoResponseAnalysisResponse(BaseModel):
    analysis_result: Optional[dict] = None
    follow_up_result: Optional[dict] = None
    suggest_result: Optional[dict] = None
    merged_summary: Optional[str] = None
    error: Optional[str] = None

class StatusTransitionRequest(BaseModel):
    """状态变更请求"""
    to_status: str = Field(..., description="目标状态")
    comment: Optional[str] = Field(None, description="变更备注")

class ApplicationTimelineEvent(BaseModel):
    """时间线事件"""
    id: str
    from_status: Optional[str] = None
    to_status: str
    comment: Optional[str] = None
    changed_at: Optional[datetime] = None


# ===== AI 辅助录入 (Phase 2 增强) =====

class CompanyAutocompleteRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=100)

class CompanyAutocompleteResponse(BaseModel):
    company_name: str = ""
    industry: Optional[str] = None
    company_size: Optional[str] = None
    headquarters: Optional[str] = None
    is_listed: Optional[bool] = None
    brief: Optional[str] = None
    confidence: str = "low"

class PositionAutocompleteRequest(BaseModel):
    position_name: str = Field(..., min_length=1, max_length=100)
    industry: str = ""

class PositionAutocompleteResponse(BaseModel):
    position_name: str = ""
    typical_requirements: Optional[dict] = None
    typical_responsibilities: Optional[list] = None
    salary_range: Optional[str] = None
    career_path: Optional[str] = None

class InterviewFeedbackRequest(BaseModel):
    feedback: str = Field(..., min_length=1, description="面试反馈描述")

class InterviewFeedbackResponse(BaseModel):
    interview_key_points: Optional[dict] = None
    error: Optional[str] = None

class OCRRequest(BaseModel):
    image_base64: str = Field(..., description="图片的 base64 编码")

class OCRResponse(BaseModel):
    text: str = ""
    success: bool = False
    error: Optional[str] = None

class STTRequest(BaseModel):
    audio_base64: str = Field(..., description="音频的 base64 编码")

class STTResponse(BaseModel):
    text: str = ""
    success: bool = False
    error: Optional[str] = None


# ===== 技能 Gap 分析 (Phase 3) =====

class GapAnalysisRequest(BaseModel):
    jd_id: str = Field(..., description="JD ID")
    resume_id: str = Field(..., description="简历 ID")

class JDTechStackResponse(BaseModel):
    tech_stack: list = []
    total_weight: float = 100.0
    primary_stack: list = []
    nice_to_have: list = []
    industry_context: Optional[str] = None

class GapAnalysisResponse(BaseModel):
    jd_tech_stack: list = []
    gap_analysis: Optional[dict] = None
    error: Optional[str] = None


# ===== 用户基本信息 =====

class UserProfileResponse(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    current_role: Optional[str] = None
    years_of_experience: Optional[int] = None
    education: Optional[str] = None
    school: Optional[str] = None
    major: Optional[str] = None
    summary: Optional[str] = None
    expected_role: Optional[str] = None
    expected_salary: Optional[str] = None
    job_status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class UserProfileUpdate(BaseModel):
    """更新用户基本信息（所有字段可选，允许部分更新）"""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    current_role: Optional[str] = None
    years_of_experience: Optional[int] = None
    education: Optional[str] = None
    school: Optional[str] = None
    major: Optional[str] = None
    summary: Optional[str] = None
    expected_role: Optional[str] = None
    expected_salary: Optional[str] = None
    job_status: Optional[str] = None


# ===== 通用 =====

class ErrorResponse(BaseModel):
    detail: str
