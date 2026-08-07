"""求职追踪 API — 投递记录管理 + 无回应分析"""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..models.user import User
from ..database import get_db
from ..schemas import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
    ApplicationStats,
    NoResponseAnalysisRequest,
    NoResponseAnalysisResponse,
    StatusTransitionRequest,
    ApplicationTimelineEvent,
    InterviewFeedbackRequest,
    InterviewFeedbackResponse,
)
from ..models.application import Application, ApplicationStatusHistory
from ..models.job import JobDescription
from ..models.resume import Resume
from ..utils.state_machine import StateMachine
from ..core.no_response_agent import no_response_agent
from ..core.ai_assistant import ai_assistant

router = APIRouter(prefix="/api/applications", tags=["applications"])


# ============================================================
# CRUD
# ============================================================

@router.post("", response_model=ApplicationResponse, status_code=201)
async def create_application(
    request: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建投递记录"""
    # 验证状态合法性
    if request.status not in StateMachine.get_next_states("applied") and request.status != "applied":
        valid = StateMachine.get_all_states()
        valid_values = [s["value"] for s in valid]
        if request.status not in valid_values:
            raise HTTPException(status_code=400, detail=f"无效状态: {request.status}")

    app = Application(
        jd_id=request.jd_id,
        resume_id=request.resume_id,
        company=request.company,
        position=request.position,
        status=request.status,
        applied_at=request.applied_at or datetime.now(),
        notes=request.notes,
        user_id=current_user.id,
    )
    db.add(app)
    await db.flush()

    # 记录状态历史
    history = ApplicationStatusHistory(
        application_id=app.id,
        to_status=request.status,
        comment="创建投递记录",
    )
    db.add(history)

    await db.commit()

    return _to_response(app)


@router.get("", response_model=list[ApplicationResponse])
async def list_applications(
    status: Optional[str] = Query(None, description="按状态筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取投递列表（支持按状态筛选，看板视图用）"""
    query = select(Application).where(
        Application.user_id == current_user.id
    ).order_by(
        Application.applied_at.desc()
    )
    if status:
        if status == "active":
            # 活跃的投递 (非终态)
            query = query.where(
                Application.status.in_(["applied", "waiting", "no_response", "resume_screening", "written_test", "interview_1", "interview_2", "interview_3", "offer"])
            )
        else:
            query = query.where(Application.status == status)

    result = await db.execute(query)
    apps = result.scalars().all()

    return [_to_response(a) for a in apps]


@router.get("/stats", response_model=ApplicationStats)
async def get_application_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取投递统计数据"""
    result = await db.execute(
        select(Application.status, func.count(Application.id))
        .where(Application.user_id == current_user.id)
        .group_by(Application.status)
    )
    rows = result.all()

    by_status = {row[0]: row[1] for row in rows}
    total = sum(by_status.values())

    # 转化率计算
    conversion_rates = {}
    if total > 0:
        if by_status.get("resume_screening", 0) > 0:
            conversion_rates["applied_to_screening"] = round(by_status.get("resume_screening", 0) / max(by_status.get("applied", 1), 1) * 100, 1)
        if by_status.get("interview_1", 0) > 0:
            conversion_rates["screening_to_interview"] = round(by_status.get("interview_1", 0) / max(by_status.get("resume_screening", 1), 1) * 100, 1)
        if by_status.get("offer", 0) > 0:
            conversion_rates["interview_to_offer"] = round(by_status.get("offer", 0) / max(by_status.get("interview_1", 1), 1) * 100, 1)

    return ApplicationStats(
        total=total,
        by_status=by_status,
        conversion_rates=conversion_rates,
    )


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取投递详情"""
    app = await _get_app_or_404(db, application_id, current_user.id)
    return _to_response(app)


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: str,
    request: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新投递记录（状态、备注等）"""
    app = await _get_app_or_404(db, application_id, current_user.id)

    # 状态变更逻辑
    if request.status and request.status != app.status:
        if not StateMachine.can_transition(app.status, request.status):
            raise HTTPException(
                status_code=400,
                detail=f"无效状态转换: {StateMachine.get_label(app.status)} → {StateMachine.get_label(request.status)}",
            )
        # 记录历史
        history = ApplicationStatusHistory(
            application_id=app.id,
            from_status=app.status,
            to_status=request.status,
            comment="手动变更状态",
        )
        db.add(history)
        app.status = request.status

    # 更新其他字段
    for field, value in request.model_dump(exclude_unset=True, exclude={"status"}).items():
        setattr(app, field, value)

    await db.commit()
    return _to_response(app)


@router.delete("/{application_id}")
async def delete_application(
    application_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除投递记录"""
    app = await _get_app_or_404(db, application_id, current_user.id)
    await db.delete(app)
    await db.commit()
    return {"status": "deleted", "id": application_id}


# ============================================================
# 无回应分析
# ============================================================

@router.post("/{application_id}/no-response-analysis", response_model=NoResponseAnalysisResponse)
async def run_no_response_analysis(
    application_id: str,
    request: NoResponseAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发无回应分析 — 调用 LangGraph Agent 三路并行分析"""
    app = await _get_app_or_404(db, application_id, current_user.id)

    # 获取 JD 文本 (如有)
    jd_text = ""
    if app.jd_id:
        jd_result = await db.execute(select(JobDescription).where(JobDescription.id == app.jd_id))
        jd = jd_result.scalar_one_or_none()
        if jd:
            jd_text = jd.raw_text or ""

    # 获取简历摘要 (如有)
    resume_summary = ""
    if app.resume_id:
        resume_result = await db.execute(select(Resume).where(Resume.id == app.resume_id))
        resume = resume_result.scalar_one_or_none()
        if resume:
            structured = resume.structured_data or {}
            basic = structured.get("basic_info", {})
            skills = structured.get("skills", {})
            work_count = len(structured.get("work_experience", []))
            resume_summary = (
                f"姓名: {basic.get('name', '未知')}, "
                f"工作年限: {basic.get('years_of_experience', '未知')}年, "
                f"求职意向: {basic.get('target_position', '未知')}, "
                f"工作经历: {work_count}条, "
                f"技能: {json.dumps(skills, ensure_ascii=False) if skills else '未知'}"
            )

    # 调用 LangGraph Agent
    result = await no_response_agent.analyze(
        application_id=application_id,
        company=app.company,
        position=app.position,
        jd_text=jd_text,
        resume_summary=resume_summary,
        days_since_apply=request.days_since_apply,
    )

    return NoResponseAnalysisResponse(**result)


@router.post("/{application_id}/transition", response_model=ApplicationResponse)
async def transition_status(
    application_id: str,
    request: StatusTransitionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行状态转换 (带验证和历史记录)"""
    app = await _get_app_or_404(db, application_id, current_user.id)

    if not StateMachine.can_transition(app.status, request.to_status):
        raise HTTPException(
            status_code=400,
            detail=f"无效状态转换: {StateMachine.get_label(app.status)} → {StateMachine.get_label(request.to_status)}",
        )

    # 记录历史
    history = ApplicationStatusHistory(
        application_id=app.id,
        from_status=app.status,
        to_status=request.to_status,
        comment=request.comment or "状态变更",
    )
    db.add(history)

    app.status = request.to_status
    await db.commit()

    return _to_response(app)


@router.post("/{application_id}/interview-feedback", response_model=InterviewFeedbackResponse)
async def save_interview_feedback(
    application_id: str,
    request: InterviewFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存面试反馈 + AI 提取关键点"""
    app = await _get_app_or_404(db, application_id, current_user.id)

    app.interview_feedback = request.feedback

    # AI 提取关键点
    key_points = await ai_assistant.extract_interview_feedback(
        company=app.company,
        position=app.position,
        feedback=request.feedback,
    )
    app.interview_key_points = key_points

    await db.commit()

    return InterviewFeedbackResponse(
        interview_key_points=key_points,
        error=key_points.get("error") if isinstance(key_points, dict) else None,
    )


@router.get("/{application_id}/timeline", response_model=list[ApplicationTimelineEvent])
async def get_application_timeline(
    application_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取投递状态变更时间线"""
    app = await _get_app_or_404(db, application_id, current_user.id)

    result = await db.execute(
        select(ApplicationStatusHistory)
        .where(ApplicationStatusHistory.application_id == application_id)
        .order_by(ApplicationStatusHistory.changed_at.asc())
    )
    histories = result.scalars().all()

    return [
        ApplicationTimelineEvent(
            id=h.id,
            from_status=h.from_status,
            to_status=h.to_status,
            comment=h.comment,
            changed_at=h.changed_at,
        )
        for h in histories
    ]


# ============================================================
# 辅助函数
# ============================================================

async def _get_app_or_404(db: AsyncSession, app_id: str, user_id: str = None) -> Application:
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="投递记录不存在")
    if user_id is not None and app.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问")
    return app


def _to_response(app: Application) -> ApplicationResponse:
    return ApplicationResponse(
        id=app.id,
        company=app.company,
        position=app.position,
        status=app.status,
        resume_id=app.resume_id,
        jd_id=app.jd_id,
        channel=app.channel,
        applied_at=app.applied_at,
        next_action=app.next_action,
        next_due_date=app.next_due_date,
        salary_offer=app.salary_offer,
        notes=app.notes,
        follow_up_notes=app.follow_up_notes,
        interview_feedback=app.interview_feedback,
        interview_key_points=app.interview_key_points,
        created_at=app.created_at,
        updated_at=app.updated_at,
    )
