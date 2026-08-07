"""简历管理 API"""

import os
import uuid
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models.user_profile import UserProfile
from ..core.deps import get_current_user
from ..models.user import User
from ..schemas import (
    ResumeResponse,
    ResumeDetailResponse,
    ChunkResponse,
    RestructureRequest,
    RestructureResponse,
    GeneratePdfRequest,
    ErrorResponse,
)
from ..services.resume_service import resume_service
from ..core.rag_engine import rag_engine
from ..core.pdf_generator import pdf_generator
from ..core.embedder import vector_store
from ..models.job import JobDescription
from ..config import settings

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


@router.post("/upload", response_model=ResumeResponse)
async def upload_resume(
    file: UploadFile = File(...),
    name: str = Form(...),
    photo: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传简历文件 → 解析 → 结构化 → 分块 → 向量化"""
    # 验证文件格式
    allowed_extensions = {".pdf", ".docx", ".md", ".markdown", ".txt"}
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}。支持: PDF, DOCX, Markdown, TXT",
        )

    # 保存临时文件
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    temp_filename = f"{uuid.uuid4()}{file_ext}"
    temp_path = os.path.join(upload_dir, temp_filename)

    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        # 处理简历（包含解析→结构化→分块→向量化）
        resume = await resume_service.upload_and_process(
            db=db, file_path=temp_path, name=name
        )
        resume.user_id = current_user.id

        # 处理证件照（需要 resume.id 作为文件名）
        photo_path = None
        if photo and photo.filename:
            allowed_photo = {".jpg", ".jpeg", ".png"}
            photo_ext = os.path.splitext(photo.filename)[1].lower()
            if photo_ext not in allowed_photo:
                raise HTTPException(
                    status_code=400,
                    detail=f"不支持的照片格式: {photo_ext}。仅支持: JPG, PNG",
                )
            # 检查大小
            photo_content = await photo.read()
            if len(photo_content) > settings.MAX_PHOTO_SIZE_MB * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=f"照片大小不能超过 {settings.MAX_PHOTO_SIZE_MB}MB",
                )
            photo_path = resume_service.save_photo_from_bytes(resume.id, photo_content)
            resume.photo_path = photo_path
            await db.flush()

        # ⚠️ 关键: 在 commit 之前提取所有 ORM 属性为普通 Python 值
        # TimestampMixin 使用 Python 端 datetime.now，配合 expire_on_commit=False
        # 可避免 commit 后访问 ORM 属性时触发 greenlet lazy load
        resp_id = resume.id
        resp_name = resume.name
        resp_source_filename = resume.source_filename
        resp_source_format = resume.source_format
        resp_chunk_count = resume.chunk_count
        resp_is_active = resume.is_active
        resp_created_at = resume.created_at
        resp_updated_at = resume.updated_at

        await db.commit()

        return ResumeResponse(
            id=resp_id,
            name=resp_name,
            source_filename=resp_source_filename,
            source_format=resp_source_format,
            chunk_count=resp_chunk_count,
            photo_url=f"/api/resumes/{resp_id}/photo" if photo_path else None,
            has_photo=bool(photo_path),
            is_active=resp_is_active,
            created_at=resp_created_at,
            updated_at=resp_updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger("career-kb")
        logger.error(f"简历上传失败: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"处理失败: {str(e)}")
    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("", response_model=list[ResumeResponse])
async def list_resumes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取简历列表"""
    resumes = await resume_service.list_resumes(db)
    return [
        ResumeResponse(
            id=r.id,
            name=r.name,
            source_filename=r.source_filename,
            source_format=r.source_format,
            chunk_count=r.chunk_count,
            photo_url=f"/api/resumes/{r.id}/photo" if r.photo_path else None,
            has_photo=bool(r.photo_path),
            is_active=r.is_active,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )
        for r in resumes
        if r.user_id == current_user.id
    ]


@router.get("/{resume_id}", response_model=ResumeDetailResponse)
async def get_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取简历详情"""
    resume = await resume_service.get_resume(db, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="简历不存在")
    return ResumeDetailResponse(
        id=resume.id,
        name=resume.name,
        source_filename=resume.source_filename,
        source_format=resume.source_format,
        raw_text=resume.raw_text,
        structured_data=resume.structured_data,
        chunk_count=resume.chunk_count,
        photo_url=f"/api/resumes/{resume.id}/photo" if resume.photo_path else None,
        has_photo=bool(resume.photo_path),
        is_active=resume.is_active,
        created_at=resume.created_at,
        updated_at=resume.updated_at,
    )


@router.get("/{resume_id}/chunks", response_model=list[ChunkResponse])
async def get_resume_chunks(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取简历分块列表"""
    resume = await resume_service.get_resume(db, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="简历不存在")

    chunks = await resume_service.get_chunks(db, resume_id)
    return [
        ChunkResponse(
            id=c.id,
            section_type=c.section_type,
            section_title=c.section_title,
            chunk_index=c.chunk_index,
            content=c.content,
            metadata=c.metadata_json,
            token_count=c.token_count,
        )
        for c in chunks
    ]


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除简历 (含向量数据和索引)"""
    # 先检查所有权
    resume = await resume_service.get_resume(db, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="简历不存在")
    success = await resume_service.delete_resume(db, resume_id)
    if not success:
        raise HTTPException(status_code=404, detail="简历不存在")
    await db.commit()
    return {"status": "deleted", "id": resume_id}


@router.post("/save-generated")
async def save_generated_resume(
    name: str = Form(..., description="简历名称"),
    markdown: str = Form(..., description="生成的Markdown内容"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将生成的简历保存到简历库"""
    import logging
    logger = logging.getLogger("career-kb")
    try:
        resume = await resume_service.save_generated_resume(
            db=db,
            name=name,
            markdown_text=markdown,
        )
        resume.user_id = current_user.id
        await db.commit()
        return {
            "status": "saved",
            "id": resume.id,
            "name": resume.name,
            "chunk_count": resume.chunk_count,
        }
    except Exception as e:
        logger.error(f"保存生成简历失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/{resume_id}/photo")
async def get_resume_photo(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取简历证件照"""
    resume = await resume_service.get_resume(db, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="简历不存在")
    if not resume.photo_path or not os.path.exists(resume.photo_path):
        raise HTTPException(status_code=404, detail="未上传证件照")

    return FileResponse(
        resume.photo_path,
        media_type="image/jpeg",
        filename=f"photo_{resume_id}.jpg",
    )


@router.get("/{resume_id}/styled")
async def get_styled_resume(
    resume_id: str,
    content: str = Query(..., description="重组后的简历文本"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成含证件照的专业排版简历 HTML（浏览器打印即可导出PDF）"""
    resume = await resume_service.get_resume(db, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="简历不存在")

    from ..core.resume_template import generate_resume_html
    html = generate_resume_html(
        content=content,
        photo_path=resume.photo_path,
        structured_data=resume.structured_data,
    )
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.post("/{resume_id}/styled")
async def post_styled_resume(
    resume_id: str,
    request: GeneratePdfRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """POST 版本的样式化简历 HTML（避免 URL 长度限制，用于长内容预览）"""
    resume = await resume_service.get_resume(db, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="简历不存在")

    if not request.markdown:
        raise HTTPException(status_code=400, detail="内容不能为空")

    from ..core.resume_template import generate_resume_html
    html = generate_resume_html(
        content=request.markdown,
        photo_path=resume.photo_path,
        structured_data=resume.structured_data,
    )
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.post("/{resume_id}/generate-pdf")
async def generate_pdf_resume(
    resume_id: str,
    request: GeneratePdfRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将已生成的 Markdown 简历渲染为 PDF 下载"""
    resume = await resume_service.get_resume(db, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="简历不存在")

    if not request.markdown:
        raise HTTPException(status_code=400, detail="Markdown 内容不能为空")

    try:
        pdf_bytes = pdf_generator.generate(
            markdown=request.markdown,
            photo_path=resume.photo_path,
            structured_data=resume.structured_data,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 生成失败: {str(e)}")

    # 构建文件名: 姓名-岗位-简历.pdf
    profile_name = ""
    try:
        from sqlalchemy import select
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == current_user.id)
        )
        profile = result.scalars().first()
        if profile and profile.name and profile.name != "未命名":
            profile_name = profile.name
    except Exception:
        pass

    position = request.title or ""
    if profile_name and position:
        filename = f"{profile_name}-{position}简历.pdf"
    elif profile_name:
        filename = f"{profile_name}简历.pdf"
    elif position:
        filename = f"{position}简历.pdf"
    else:
        filename = "定制简历.pdf"

    # URL 编码中文文件名
    from urllib.parse import quote
    encoded_filename = quote(filename)

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Content-Length": str(len(pdf_bytes)),
        },
    )


async def _get_profile_header(db: AsyncSession, user_id: str, jd_title: str = "") -> str:
    """从用户基本信息构建简历头部（Markdown格式）"""
    from sqlalchemy import select
    result = await db.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalars().first()

    if not profile:
        return ""

    lines = []

    # 姓名
    name = profile.name if profile.name and profile.name != "未命名" else ""
    if name:
        lines.append(f"# {name}")
    else:
        lines.append("# 姓名")
    lines.append("")

    # 联系方式行
    contact_parts = []
    if profile.email:
        contact_parts.append(profile.email)
    if profile.phone:
        contact_parts.append(profile.phone)
    if profile.city:
        contact_parts.append(profile.city)
    if contact_parts:
        lines.append(" | ".join(contact_parts))
        lines.append("")

    # 求职意向
    target_role = jd_title or profile.expected_role or ""
    if target_role:
        lines.append(f"## 求职意向")
        lines.append(target_role)
        lines.append("")

    # 教育背景
    edu_parts = []
    if profile.education:
        edu_parts.append(profile.education)
    if profile.school:
        edu_parts.append(profile.school)
    if profile.major:
        edu_parts.append(profile.major)
    if edu_parts:
        lines.append("## 教育背景")
        lines.append(" | ".join(edu_parts))
        if profile.years_of_experience is not None:
            lines.append(f"工作年限: {profile.years_of_experience}年")
        lines.append("")

    return "\n".join(lines)


def _strip_static_sections(text: str) -> str:
    """从 LLM 生成的简历内容中移除静态信息章节（这些由系统预填充）

    兼容 Markdown (##) 和纯文本格式
    移除: # 姓名行, 联系方式, 求职意向, 教育背景
    """
    import re

    # 移除 # 姓名行（Markdown H1，可能出现在任意位置）
    text = re.sub(r'^#\s+.+?\n\n?', '', text, flags=re.MULTILINE)

    # 移除联系方式行（各种格式）
    text = re.sub(r'^📧\s*.+?\n\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^📱\s*.+?\n\n?', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\w\.\-]+@[\w\-]+.*?\n\n?', '', text, flags=re.MULTILINE)

    # 移除独立的"联系方式"小节（智能模式输出）
    text = re.sub(r'\n联系方式\s*\n(?:📧.*?\n)?(?:📱.*?\n)?', '\n', text)

    # 移除 ## 求职意向 或 【求职意向】 或 求职意向 章节（含内容，直到下一个章节标题）
    for header in [r'##\s*求职意向', r'【求职意向】', r'^求职意向\s*$']:
        text = re.sub(
            rf'{header}\s*\n.*?(?=\n(?:##|【|(?:\S+)\s*\n---)|<analysis>|\Z)',
            '', text, flags=re.DOTALL | re.MULTILINE
        )

    # 移除 ## 教育背景 或 【教育背景】 或 教育背景 章节（含内容）
    for header in [r'##\s*教育背景', r'【教育背景】', r'^教育背景\s*$']:
        text = re.sub(
            rf'{header}\s*\n.*?(?=\n(?:##|【|(?:\S+)\s*\n---)|<analysis>|\Z)',
            '', text, flags=re.DOTALL | re.MULTILINE
        )

    return text.strip()


def _move_summary_to_end(text: str) -> str:
    """强制将 个人总结 章节移到简历末尾（项目经历和工作经历之后）

    兼容 Markdown (## 个人总结)、纯文本 (个人总结)、括号 (【个人总结】) 三种格式
    """
    import re

    # 匹配多种格式的个人总结章节
    # 格式1: ## 个人总结 (Markdown)
    # 格式2: 个人总结 (纯文本独立行)
    # 格式3: 【个人总结】 (括号格式)
    patterns = [
        r'\n##\s*个人总结\s*\n.*?(?=\n(?:##\s|\【|<\w+>)|<analysis>|\Z)',
        r'\n【个人总结】\s*\n.*?(?=\n(?:##\s|\【\S+\】\s*\n|<\w+>)|<analysis>|\Z)',
        r'\n个人总结\s*\n(?:(?!\n(?:项目经历|工作经历|专业技能|证书))[\s\S])*?(?=\n(?:项目经历|工作经历|专业技能|证书|【|<analysis>)|\Z)',
    ]

    summary_section = None
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.DOTALL)
        if match:
            summary_section = match.group(0)
            text = text[:match.start()] + text[match.end():]
            break

    if summary_section is None:
        return text  # 没有个人总结章节，无需处理

    # 在 <analysis> 之前插入（如果有），否则追加到末尾
    analysis_match = re.search(r'\n<analysis>', text)
    if analysis_match:
        text = text[:analysis_match.start()] + summary_section + "\n" + text[analysis_match.start():]
    else:
        text = text.rstrip() + "\n" + summary_section + "\n"

    return text


@router.post("/smart-restructure")
async def smart_restructure(
    request: RestructureRequest,
    resume_id: str = Query(None, description="可选：指定主简历ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """智能简历重组（新版）: 跨所有简历+技能库检索，扬长避短，非Markdown输出"""
    # 如果指定了简历ID，检查所有权
    if resume_id:
        resume = await resume_service.get_resume(db, resume_id)
        if not resume or resume.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="简历不存在")

    # 获取 JD 文本
    jd_text = request.jd_text
    jd_title = request.jd_title or ""
    jd_company = request.jd_company or ""

    if request.jd_id:
        from sqlalchemy import select
        from ..models.job import JobDescription
        result = await db.execute(
            select(JobDescription).where(JobDescription.id == request.jd_id)
        )
        jd = result.scalar_one_or_none()
        if jd:
            jd_text = jd.raw_text
            jd_title = jd.title
            jd_company = jd.company or ""

    if not jd_text:
        raise HTTPException(status_code=400, detail="请提供 JD 文本或 JD ID")

    # 执行智能重组 pipeline
    result = await rag_engine.smart_restructure_pipeline(
        jd_text=jd_text,
        user_id=current_user.id,
        jd_title=jd_title,
        jd_company=jd_company,
        resume_id=resume_id,
    )

    # 预填充用户个人信息，剥离 LLM 输出的静态章节，确保个人总结在末尾
    profile_header = await _get_profile_header(db, current_user.id, jd_title)
    body = _strip_static_sections(result["generated_resume"])
    body = _move_summary_to_end(body)
    final_resume = profile_header + "\n" + body if profile_header else body

    match_score = 0
    if result["retrieved_chunks"]:
        scores = [c.get("weighted_score", c.get("score", 0)) for c in result["retrieved_chunks"]]
        if scores:
            max_s = max(scores)
            avg_s = sum(scores) / len(scores)
            match_score = min(100, (max_s * 0.6 + avg_s * 0.4) * 500)

    return RestructureResponse(
        restructured_markdown=final_resume,
        changes_summary=result["analysis"],
        match_score=round(match_score, 1),
        fact_check=result["fact_check"],
    )


@router.post("/{resume_id}/restructure")
async def restructure_resume(
    resume_id: str,
    request: RestructureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """基于 JD 重组简历 (核心功能 — 非流式)"""
    # 验证简历存在及所有权
    resume = await resume_service.get_resume(db, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="简历不存在")

    # 获取 JD 文本
    jd_text = request.jd_text
    jd_title = request.jd_title or ""
    jd_company = request.jd_company or ""

    if request.jd_id:
        from sqlalchemy import select
        result = await db.execute(
            select(JobDescription).where(JobDescription.id == request.jd_id)
        )
        jd = result.scalar_one_or_none()
        if jd:
            jd_text = jd.raw_text
            jd_title = jd.title
            jd_company = jd.company or ""
        else:
            raise HTTPException(status_code=404, detail="JD不存在")

    if not jd_text:
        raise HTTPException(status_code=400, detail="请提供 JD 文本或 JD ID")

    # 执行重组 pipeline
    result = await rag_engine.full_pipeline(
        resume_id=resume_id,
        raw_resume_text=resume.raw_text or "",
        jd_text=jd_text,
        jd_title=jd_title,
        jd_company=jd_company,
    )

    # 预填充用户个人信息，剥离 LLM 输出的静态章节，确保个人总结在末尾
    profile_header = await _get_profile_header(db, current_user.id, jd_title)
    body = _strip_static_sections(result["generated_resume"])
    body = _move_summary_to_end(body)
    final_resume = profile_header + "\n" + body if profile_header else body

    # 计算匹配度 (简化版: 基于 JD 需求与检索chunks的匹配)
    match_score = 0
    if result["retrieved_chunks"]:
        scores = [c.get("weighted_score", c.get("score", 0)) for c in result["retrieved_chunks"]]
        if scores:
            max_s = max(scores)
            avg_s = sum(scores) / len(scores)
            match_score = min(100, (max_s * 0.6 + avg_s * 0.4) * 500)

    return RestructureResponse(
        restructured_markdown=final_resume,
        changes_summary=result["analysis"],
        match_score=round(match_score, 1),
        fact_check=result["fact_check"],
    )


@router.post("/{resume_id}/restructure/stream")
async def restructure_resume_stream(
    resume_id: str,
    request: RestructureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """基于 JD 重组简历 (流式 SSE)"""
    # 验证简历存在及所有权
    resume = await resume_service.get_resume(db, resume_id)
    if not resume or resume.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="简历不存在")

    # 获取 JD 文本
    jd_text = request.jd_text
    jd_title = request.jd_title or ""
    jd_company = request.jd_company or ""

    if request.jd_id:
        from sqlalchemy import select
        result = await db.execute(
            select(JobDescription).where(JobDescription.id == request.jd_id)
        )
        jd = result.scalar_one_or_none()
        if jd:
            jd_text = jd.raw_text
            jd_title = jd.title
            jd_company = jd.company or ""

    if not jd_text:
        raise HTTPException(status_code=400, detail="请提供 JD 文本或 JD ID")

    # 先解析 JD 并检索
    jd_requirements = await rag_engine.parse_jd(jd_text)
    retrieved_chunks = await rag_engine.retrieve_chunks(resume_id, jd_requirements)

    # 预构建个人信息头部
    profile_header = await _get_profile_header(db, current_user.id, jd_title)

    async def event_stream():
        import json
        body_chunks = []  # 累积 LLM 输出的 body 内容

        # 先发送个人信息头部（流式预览）
        if profile_header:
            yield f"event: content\ndata: {json.dumps({'type': 'content', 'text': profile_header + '\n', 'stage': 'profile_header'}, ensure_ascii=False)}\n\n"

        async for event in rag_engine.restructure_resume_stream(
            resume_id=resume_id,
            jd_text=jd_text,
            jd_requirements=jd_requirements,
            retrieved_chunks=retrieved_chunks,
            jd_title=jd_title,
            jd_company=jd_company,
        ):
            event_type = event.get("type", "message")

            # 收集 content 事件用于最终修正
            if event_type == "content":
                body_chunks.append(event.get("text", ""))

            # 修正 complete 事件：确保个人总结在末尾
            if event_type == "complete":
                body = "".join(body_chunks)
                body = _strip_static_sections(body)
                body = _move_summary_to_end(body)
                final_md = (profile_header + "\n" + body) if profile_header else body
                event = {**event, "resume_markdown": final_md}

            yield f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
