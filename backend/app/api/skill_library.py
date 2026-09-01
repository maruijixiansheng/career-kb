"""技能库管理 API — 用户手写技术栈/项目/实习"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..database import get_db
from ..models.skill_library import SkillLibraryEntry
from ..models.user import User
from ..core.embedder import vector_store
from ..core.retriever import retriever

router = APIRouter(prefix="/api/skill-library", tags=["skill-library"])


class SkillEntryCreate(BaseModel):
    entry_type: str = Field(..., description="类型: skill/project/internship/certificate/other")
    title: str = Field(..., description="标题")
    content: str = Field(..., description="详细内容")
    tags: Optional[str] = Field(None, description="技术标签")
    start_date: Optional[str] = Field(None)
    end_date: Optional[str] = Field(None)
    importance: int = Field(3, ge=1, le=5)


@router.post("")
async def create_entry(
    body: SkillEntryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动添加技能库条目"""
    valid_types = {"skill", "project", "internship", "certificate", "other"}
    if body.entry_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"无效类型。支持: {valid_types}")

    entry = SkillLibraryEntry(
        user_id=current_user.id,
        entry_type=body.entry_type,
        title=body.title,
        content=body.content,
        tags=body.tags,
        start_date=body.start_date,
        end_date=body.end_date,
        importance=body.importance,
    )
    db.add(entry)
    await db.flush()

    # 向量化到技能库专用 collection
    try:
        chunks = [{
            "id": entry.id,
            "content": f"[{entry_type}] {title}\n{content}\n标签: {tags or ''}",
            "metadata": {
                "entry_type": entry_type,
                "title": title,
                "tags": tags or "",
                "importance": str(importance),
                "source": "skill_library",
                "user_id": str(current_user.id),
            },
            "chunk_index": 0,
            "section_type": entry_type,
            "section_title": title,
            "token_count": len(content),
        }]
        vector_store.add_skill_library_entry(chunks)
        # 使该用户的 BM25 缓存失效，下次检索从 DB 重建完整索引（含新条目）
        retriever.bm25_indexes.pop(f"skill_library:{current_user.id}", None)
    except Exception as e:
        import logging; logging.getLogger("career_kb").warning(f"技能库向量化失败 [{title}]: {e}")

    await db.commit()

    return {
        "id": entry.id,
        "entry_type": entry.entry_type,
        "title": entry.title,
        "content": entry.content,
        "tags": entry.tags,
        "start_date": entry.start_date,
        "end_date": entry.end_date,
        "importance": entry.importance,
        "is_active": entry.is_active,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


@router.get("")
async def list_entries(
    entry_type: Optional[str] = Query(None, description="筛选类型"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取技能库列表"""
    stmt = select(SkillLibraryEntry).where(
        SkillLibraryEntry.is_active == True,
        SkillLibraryEntry.user_id == current_user.id,
    )
    if entry_type:
        stmt = stmt.where(SkillLibraryEntry.entry_type == entry_type)
    stmt = stmt.order_by(SkillLibraryEntry.importance.desc(), SkillLibraryEntry.updated_at.desc())

    result = await db.execute(stmt)
    entries = result.scalars().all()

    return [
        {
            "id": e.id,
            "entry_type": e.entry_type,
            "title": e.title,
            "content": e.content,
            "tags": e.tags,
            "start_date": e.start_date,
            "end_date": e.end_date,
            "importance": e.importance,
            "is_active": e.is_active,
            "created_at": e.created_at,
            "updated_at": e.updated_at,
        }
        for e in entries
    ]


@router.get("/{entry_id}")
async def get_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取技能库条目详情"""
    entry = await db.get(SkillLibraryEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问此条目")
    return {
        "id": entry.id,
        "entry_type": entry.entry_type,
        "title": entry.title,
        "content": entry.content,
        "tags": entry.tags,
        "start_date": entry.start_date,
        "end_date": entry.end_date,
        "importance": entry.importance,
        "is_active": entry.is_active,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


@router.put("/{entry_id}")
async def update_entry(
    entry_id: str,
    title: Optional[str] = Query(None),
    content: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    importance: Optional[int] = Query(None, ge=1, le=5),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新技能库条目"""
    entry = await db.get(SkillLibraryEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权修改此条目")

    if title is not None:
        entry.title = title
    if content is not None:
        entry.content = content
    if tags is not None:
        entry.tags = tags
    if start_date is not None:
        entry.start_date = start_date
    if end_date is not None:
        entry.end_date = end_date
    if importance is not None:
        entry.importance = importance

    await db.flush()
    await db.commit()

    return {"status": "updated", "id": entry_id}


@router.delete("/{entry_id}")
async def delete_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除技能库条目"""
    entry = await db.get(SkillLibraryEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除此条目")
    await db.delete(entry)
    await db.commit()
    return {"status": "deleted", "id": entry_id}
