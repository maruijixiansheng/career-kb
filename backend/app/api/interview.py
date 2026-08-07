"""面试模拟 API"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..database import get_db
from ..schemas import (
    InterviewStartRequest,
    InterviewRespondRequest,
    InterviewMessageResponse,
    InterviewFeedbackResponse,
)
from ..models.job import JobDescription
from ..models.resume import Resume
from ..models.interview import InterviewSession, InterviewMessage, InterviewReport
from ..models.user import User
from ..core.interview_agent import interview_agent

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.post("/start")
async def start_interview(
    request: InterviewStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """开始面试会话 → 返回第一个问题"""
    jd = None; resume = None
    if request.jd_id:
        jd = (await db.execute(select(JobDescription).where(JobDescription.id == request.jd_id))).scalar_one_or_none()
    if request.resume_id:
        resume = (await db.execute(select(Resume).where(Resume.id == request.resume_id))).scalar_one_or_none()

    # 创建数据库记录
    session = InterviewSession(
        jd_id=request.jd_id,
        resume_id=request.resume_id,
        mode=request.mode,
        difficulty="medium",
        user_id=current_user.id,
    )
    db.add(session)
    await db.flush()

    # 初始化 Agent
    jd_text = jd.raw_text if jd else ""
    resume_text = resume.raw_text if resume else ""
    interview_agent.init_session(
        session_id=session.id,
        jd_text=jd_text,
        resume_text=resume_text,
        mode=request.mode,
        company=jd.company if jd else "",
        position=jd.title if jd else "",
    )

    # 生成第一个问题
    result = await interview_agent.generate_question(session.id, state=interview_agent.get_state(session.id))

    # 保存消息
    msg = InterviewMessage(session_id=session.id, role="interviewer", content=result["question"], sequence=1)
    db.add(msg)
    await db.commit()

    return {"session_id": session.id, "question": result["question"], "question_number": 1, "total_questions": result["total_questions"]}


@router.post("/{session_id}/respond")
async def respond_interview(
    session_id: str,
    request: InterviewRespondRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """处理回答 → 返回下个问题或结束信号"""
    # 验证会话所有权
    session_check = await db.execute(
        select(InterviewSession).where(InterviewSession.id == session_id)
    )
    session_obj = session_check.scalar_one_or_none()
    if not session_obj:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session_obj.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")

    # 从数据库重建状态（解决多 worker 内存不同步问题）
    state = await interview_agent.load_state_from_db(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 用 DB 中已有消息数计算下一个序列号（避免 question_count 递增导致的冲突）
    msg_count_result = await db.execute(
        select(func.count()).select_from(InterviewMessage).where(InterviewMessage.session_id == session_id)
    )
    msg_count = msg_count_result.scalar() or 0
    answer_seq = msg_count + 1

    db.add(InterviewMessage(session_id=session_id, role="candidate", content=request.answer, sequence=answer_seq))
    await db.flush()

    # 处理回答
    result = await interview_agent.process_answer(session_id, request.answer, state=state)

    if result.get("finished"):
        # 生成报告
        report = await interview_agent.generate_report(session_id, state=state)
        db.add(InterviewReport(
            session_id=session_id,
            overall_score=report.get("overall_score"),
            dimension_scores=report.get("dimension_scores"),
            strengths=report.get("strengths"),
            weaknesses=report.get("weaknesses"),
            suggestions=report.get("suggestions"),
        ))
        # 更新会话状态
        s = (await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))).scalar_one()
        s.status = "completed"
        db.add(InterviewMessage(session_id=session_id, role="system", content=f"评估完成，得分: {report.get('overall_score')}", sequence=answer_seq + 1))
        await db.commit()
        return {"finished": True, "report": report}

    # 生成下一个问题
    next_q = await interview_agent.generate_question(session_id, state=state)
    db.add(InterviewMessage(session_id=session_id, role="interviewer", content=next_q["question"], sequence=answer_seq + 1))
    await db.commit()

    return {
        "finished": False,
        "feedback": result.get("feedback", ""),
        "question": next_q["question"],
        "question_number": next_q["question_number"],
        "total_questions": next_q["total_questions"],
    }


@router.get("/{session_id}/report", response_model=InterviewFeedbackResponse)
async def get_interview_report(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取面试评估报告"""
    # 验证会话所有权
    session_check = await db.execute(
        select(InterviewSession).where(InterviewSession.id == session_id)
    )
    session_obj = session_check.scalar_one_or_none()
    if not session_obj:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session_obj.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")

    r = (await db.execute(select(InterviewReport).where(InterviewReport.session_id == session_id))).scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="报告不存在")
    return InterviewFeedbackResponse(
        overall_score=r.overall_score,
        dimension_scores=r.dimension_scores,
        strengths=r.strengths,
        weaknesses=r.weaknesses,
        suggestions=r.suggestions,
    )


@router.get("/sessions", response_model=list[dict])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取面试会话历史"""
    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == current_user.id)
        .order_by(InterviewSession.started_at.desc())
        .limit(20)
    )
    sessions = result.scalars().all()
    return [{"id": s.id, "mode": s.mode, "status": s.status, "started_at": s.started_at, "ended_at": s.ended_at} for s in sessions]
