"""JD 管理 API"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..database import get_db
from ..schemas import JDCreate, JDResponse, JDDetailResponse
from ..models.job import JobDescription
from ..models.user import User
from ..core.rag_engine import rag_engine

router = APIRouter(prefix="/api/jds", tags=["jds"])


@router.post("", response_model=JDResponse)
async def create_jd(
    request: JDCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建 JD 并自动解析结构化需求"""
    # 创建 JD 记录
    jd = JobDescription(
        title=request.title,
        company=request.company,
        raw_text=request.raw_text,
        user_id=current_user.id,
    )
    db.add(jd)
    await db.flush()

    # 异步解析 JD (不阻塞响应)
    try:
        requirements = await rag_engine.parse_jd(request.raw_text)
        jd.structured_requirements = requirements
    except Exception:
        jd.structured_requirements = None

    await db.commit()

    return JDResponse(
        id=jd.id,
        title=jd.title,
        company=jd.company,
        created_at=jd.created_at,
    )


@router.get("", response_model=list[JDResponse])
async def list_jds(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """JD 列表"""
    result = await db.execute(
        select(JobDescription)
        .where(JobDescription.user_id == current_user.id)
        .order_by(JobDescription.created_at.desc())
    )
    jds = result.scalars().all()
    return [
        JDResponse(id=jd.id, title=jd.title, company=jd.company, created_at=jd.created_at)
        for jd in jds
    ]


@router.get("/{jd_id}", response_model=JDDetailResponse)
async def get_jd(
    jd_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """JD 详情"""
    result = await db.execute(
        select(JobDescription).where(JobDescription.id == jd_id)
    )
    jd = result.scalar_one_or_none()
    if not jd:
        raise HTTPException(status_code=404, detail="JD不存在")
    if jd.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    return JDDetailResponse(
        id=jd.id,
        title=jd.title,
        company=jd.company,
        raw_text=jd.raw_text,
        structured_requirements=jd.structured_requirements,
        created_at=jd.created_at,
    )


@router.delete("/{jd_id}")
async def delete_jd(
    jd_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 JD"""
    result = await db.execute(
        select(JobDescription).where(JobDescription.id == jd_id)
    )
    jd = result.scalar_one_or_none()
    if not jd:
        raise HTTPException(status_code=404, detail="JD不存在")
    if jd.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    await db.delete(jd)
    await db.commit()
    return {"status": "deleted", "id": jd_id}
