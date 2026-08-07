"""技能 Gap 分析 API"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..database import get_db
from ..schemas import GapAnalysisRequest, GapAnalysisResponse, JDTechStackResponse
from ..models.job import JobDescription
from ..models.resume import Resume
from ..models.skill import SkillGapAnalysis
from ..models.user import User
from ..core.skill_gap_agent import skill_gap_agent

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("/jd/{jd_id}/tech-stack", response_model=JDTechStackResponse)
async def get_jd_tech_stack(
    jd_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 JD 的技术栈 + 重要度分布"""
    result = await db.execute(select(JobDescription).where(JobDescription.id == jd_id))
    jd = result.scalar_one_or_none()
    if not jd:
        raise HTTPException(status_code=404, detail="JD 不存在")
    if jd.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")

    # 提取加权技术栈
    tech = await skill_gap_agent.extract_jd_skills(
        jd_text=jd.raw_text or "",
        jd_requirements=jd.structured_requirements,
    )
    return JDTechStackResponse(**tech)


@router.post("/gap-analysis", response_model=GapAnalysisResponse)
async def run_gap_analysis(
    request: GapAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行技能 Gap 分析"""
    # 获取 JD
    jd_result = await db.execute(select(JobDescription).where(JobDescription.id == request.jd_id))
    jd = jd_result.scalar_one_or_none()
    if not jd:
        raise HTTPException(status_code=404, detail="JD 不存在")
    if jd.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该JD")

    # 获取简历
    resume_result = await db.execute(select(Resume).where(Resume.id == request.resume_id))
    resume = resume_result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    if resume.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该简历")

    # 执行分析
    result = await skill_gap_agent.analyze(
        jd_id=jd.id,
        resume_id=resume.id,
        jd_text=jd.raw_text or "",
        jd_requirements=jd.structured_requirements,
        structured_resume=resume.structured_data,
    )

    # 保存分析记录
    analysis_record = SkillGapAnalysis(
        resume_id=resume.id,
        jd_id=jd.id,
        gap_result_json=result.get("gap_analysis"),
        gap_score=result.get("gap_analysis", {}).get("weighted_score") if result.get("gap_analysis") else None,
        user_id=current_user.id,
    )
    db.add(analysis_record)
    await db.commit()

    return GapAnalysisResponse(**result)


@router.get("/gap-analysis", response_model=list[dict])
async def list_gap_analyses(
    resume_id: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询历史 Gap 分析记录"""
    query = select(SkillGapAnalysis).where(
        SkillGapAnalysis.user_id == current_user.id
    ).order_by(SkillGapAnalysis.analyzed_at.desc()).limit(20)
    if resume_id:
        query = query.where(SkillGapAnalysis.resume_id == resume_id)

    result = await db.execute(query)
    records = result.scalars().all()

    return [
        {
            "id": r.id,
            "resume_id": r.resume_id,
            "jd_id": r.jd_id,
            "gap_score": r.gap_score,
            "gap_result_json": r.gap_result_json,
            "analyzed_at": r.analyzed_at,
        }
        for r in records
    ]
