"""技能库管理 API — 用户手写技术栈/项目/实习"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..database import get_db
from ..models.skill_library import SkillLibraryEntry
from ..models.user import User
from ..core.embedder import vector_store
from ..core.retriever import retriever

logger = logging.getLogger("career-kb")

router = APIRouter(prefix="/api/skill-library", tags=["skill-library"])


# ============================================================
# 向量同步（技能库条目与 Chroma 必须始终一致）
# ============================================================

def _vector_payload(entry: SkillLibraryEntry) -> dict:
    """构造单条技能库条目的向量化载荷

    content 格式必须与 services/resume_service._auto_sync_to_skill_library 完全一致，
    否则「上传简历自动写入」与「手动新增/编辑」两条路径会产出不同向量。
    """
    return {
        "id": entry.id,
        "content": f"[{entry.entry_type}] {entry.title}\n{entry.content}\n标签: {entry.tags or ''}",
        "metadata": {
            "entry_type": entry.entry_type,
            "title": entry.title,
            "tags": entry.tags or "",
            "importance": str(entry.importance),
            "source": "skill_library",
            "user_id": str(entry.user_id),
        },
        "chunk_index": 0,
        "section_type": entry.entry_type,
        "section_title": entry.title,
        "token_count": len(entry.content or ""),
    }


def _invalidate_bm25(user_id: Optional[str]) -> None:
    """让该用户的 BM25 缓存失效，下次检索从 DB 重建（含本次改动）"""
    key = f"skill_library:{user_id}" if user_id else "skill_library"
    retriever.bm25_indexes.pop(key, None)


def _resync_entry_vector(entry: SkillLibraryEntry) -> bool:
    """重建单条向量：写入新内容，并回读校验确实覆盖成功

    Chroma 的写入语义随版本变化（现行 langchain-community 用 upsert 会覆盖，
    老版本 add 对已存在 id 可能只跳过不覆盖）。因此写入后必须回读比对；
    不一致时显式删除旧向量再重写，避免「编辑成功但检索仍是旧内容」。
    """
    payload = _vector_payload(entry)
    try:
        vector_store.add_skill_library_entry([payload])
        if vector_store.get_skill_library_entry_content(entry.id) != payload["content"]:
            logger.warning(f"技能库向量未覆盖，改为先删后写 [{entry.title}]")
            vector_store.delete_skill_library_entries([entry.id])
            vector_store.add_skill_library_entry([payload])
        _invalidate_bm25(entry.user_id)
        return True
    except Exception as e:
        logger.error(f"技能库向量同步失败 [{entry.title}]: {type(e).__name__}: {e}")
        return False


class SkillEntryCreate(BaseModel):
    entry_type: str = Field(..., description="类型: skill/project/internship/certificate/other")
    title: str = Field(..., description="标题")
    content: str = Field(..., description="详细内容")
    tags: Optional[str] = Field(None, description="技术标签")
    start_date: Optional[str] = Field(None)
    end_date: Optional[str] = Field(None)
    importance: int = Field(3, ge=1, le=5)


class SkillEntryUpdate(BaseModel):
    """更新请求体。

    条目内容动辄上千字，塞进 URL query 会撞 nginx 的请求行长度上限，
    因此新增 JSON body 形式；query 参数保留以兼容旧前端。
    """

    entry_type: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    importance: Optional[int] = Field(None, ge=1, le=5)


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
        vector_store.add_skill_library_entry([_vector_payload(entry)])
        # 使该用户的 BM25 缓存失效，下次检索从 DB 重建完整索引（含新条目）
        _invalidate_bm25(current_user.id)
    except Exception as e:
        logger.warning(f"技能库向量化失败 [{body.title}]: {type(e).__name__}: {e}")

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
    body: Optional[SkillEntryUpdate] = None,
    title: Optional[str] = Query(None),
    content: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    importance: Optional[int] = Query(None, ge=1, le=5),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新技能库条目（JSON body 优先，query 参数兼容旧调用）"""
    entry = await db.get(SkillLibraryEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权修改此条目")

    # 合并入参：body 优先，其次 query
    updates: dict = {}
    for key, value in (
        ("title", title), ("content", content), ("tags", tags),
        ("start_date", start_date), ("end_date", end_date), ("importance", importance),
    ):
        if value is not None:
            updates[key] = value
    if body is not None:
        updates.update(body.model_dump(exclude_unset=True, exclude_none=True))

    if "entry_type" in updates:
        valid_types = {"skill", "project", "internship", "work", "certificate", "education", "other"}
        if updates["entry_type"] not in valid_types:
            raise HTTPException(status_code=400, detail=f"无效类型。支持: {valid_types}")
    if "title" in updates and not str(updates["title"]).strip():
        raise HTTPException(status_code=400, detail="标题不能为空")

    # 参与向量化的字段是否变化（仅改起止时间不需要重新 embedding）
    vector_dirty = any(k in updates for k in ("entry_type", "title", "content", "tags", "importance"))

    for key, value in updates.items():
        setattr(entry, key, value)

    await db.flush()
    await db.commit()

    # 关键：编辑只改 DB 不会更新向量（原实现遗漏），检索拿到的仍是旧内容。
    # 顺序刻意放在 commit 之后：万一提交失败，宁可向量偏旧，也不要出现「向量比 DB 新」
    vector_synced = _resync_entry_vector(entry) if vector_dirty else None

    return {"status": "updated", "id": entry_id, "vector_synced": vector_synced}


@router.delete("/{entry_id}")
async def delete_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除技能库条目（同时清理向量与 BM25 缓存）"""
    entry = await db.get(SkillLibraryEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    if entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权删除此条目")

    # 先删向量再删 DB：向量删不掉就中止，避免留下无法管理的「幽灵向量」
    # （幽灵向量会被同用户的检索命中，把已删除内容写进简历）
    try:
        vector_store.delete_skill_library_entries([entry_id])
    except Exception as e:
        logger.error(f"技能库向量删除失败，已中止删除 [{entry.title}]: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="向量库删除失败，条目未删除，请重试")

    _invalidate_bm25(entry.user_id)

    await db.delete(entry)
    await db.commit()
    return {"status": "deleted", "id": entry_id, "vector_deleted": True}
