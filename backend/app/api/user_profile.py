"""用户基本信息 API — 单例 CRUD"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..database import get_db
from ..schemas import UserProfileResponse, UserProfileUpdate
from ..models.user import User
from ..models.user_profile import UserProfile

router = APIRouter(prefix="/api/user-profile", tags=["user-profile"])


@router.get("", response_model=UserProfileResponse)
async def get_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户基本信息（如不存在则自动创建空记录）"""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalars().first()

    if profile is None:
        profile = UserProfile(user_id=current_user.id)
        db.add(profile)
        await db.flush()
        await db.commit()
        await db.refresh(profile)

    return _profile_to_dict(profile)


@router.put("", response_model=UserProfileResponse)
async def update_profile(
    body: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新用户基本信息"""
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    profile = result.scalars().first()

    if profile is None:
        raise HTTPException(status_code=404, detail="用户资料不存在，请先调用 GET 创建")

    # 仅更新传入的非空字段
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.flush()
    await db.commit()
    await db.refresh(profile)

    return _profile_to_dict(profile)


def _profile_to_dict(profile: UserProfile) -> dict:
    """模型转字典"""
    return {
        "id": profile.id,
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
        "city": profile.city,
        "current_role": profile.current_role,
        "years_of_experience": profile.years_of_experience,
        "education": profile.education,
        "school": profile.school,
        "major": profile.major,
        "summary": profile.summary,
        "expected_role": profile.expected_role,
        "expected_salary": profile.expected_salary,
        "job_status": profile.job_status,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }
