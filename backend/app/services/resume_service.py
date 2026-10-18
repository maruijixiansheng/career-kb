"""简历业务逻辑层"""

import os
import shutil
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.resume import Resume, ResumeChunk
from ..utils.parser import parse_resume, ResumeParseResult
from ..core.llm_client import llm_client
from ..core.prompts import RESUME_STRUCTURE_SYSTEM, RESUME_STRUCTURE_USER
from ..core.chunker import ResumeChunker, Chunk
from ..core.embedder import vector_store
from ..core.retriever import retriever
from ..config import settings


class ResumeService:
    """简历管理服务"""

    def __init__(self):
        self.chunker = ResumeChunker()

    @staticmethod
    def _normalize_title(title: str) -> str:
        """归一化标题用于去重：只保留字母/数字（含中文），去空格/标点/大小写"""
        import re
        return re.sub(r"[\W_]+", "", (title or "").lower())

    @staticmethod
    def _format_project_content(proj: dict) -> str:
        """把简历项目字段拼装成技能库 content（忠实原文，不编造）"""
        lines = []
        desc = (proj.get("description") or "").strip()
        role = (proj.get("role") or "").strip()
        if desc:
            lines.append(f"简介: {desc}")
        if role:
            lines.append(f"角色: {role}")
        resp = proj.get("responsibilities") or []
        if resp:
            lines.append("负责内容:")
            lines.extend(f"- {r}" for r in resp if r)
        ach = proj.get("achievements") or []
        if ach:
            lines.append("项目成果:")
            lines.extend(f"- {a}" for a in ach if a)
        techs = proj.get("technologies_used") or []
        if techs:
            lines.append(f"技术栈: {', '.join(techs)}")
        return "\n".join(lines)

    @staticmethod
    def _format_work_content(work: dict) -> str:
        """把简历工作/实习字段拼装成技能库 content（忠实原文，不编造）"""
        lines = []
        resp = work.get("responsibilities") or []
        if resp:
            lines.append("职责:")
            lines.extend(f"- {r}" for r in resp if r)
        ach = work.get("achievements") or []
        if ach:
            lines.append("成果:")
            lines.extend(f"- {a}" for a in ach if a)
        techs = work.get("technologies_used") or []
        if techs:
            lines.append(f"技术栈: {', '.join(techs)}")
        loc = (work.get("location") or "").strip()
        if loc:
            lines.append(f"地点: {loc}")
        return "\n".join(lines)

    # 技能分类中文名。soft_skills 故意不写入技能库：对检索排序与简历生成价值低，只会稀释结果
    _SKILL_CATEGORIES = {
        "programming_languages": "编程语言",
        "frameworks": "框架与库",
        "tools": "工具与平台",
    }

    def _build_pending_entries(self, structured_data: dict) -> list[dict]:
        """把结构化简历转成待写入技能库的条目（纯规则，便于单测）

        覆盖：项目 / 工作 / 实习 / 硬技能 / 证书获奖。
        标题归一化后在本批内先去重，跨批（与已有条目）去重在调用方完成。
        """
        if not structured_data or "raw" in structured_data:
            return []

        pending: list[dict] = []
        seen: set[str] = set()

        def add(entry: dict) -> None:
            norm = self._normalize_title(entry.get("title", ""))
            if not norm or norm in seen:
                return
            seen.add(norm)
            pending.append(entry)

        for proj in structured_data.get("projects") or []:
            name = (proj.get("name") or "").strip()
            if not name:
                continue
            add({
                "entry_type": "project",
                "title": name,
                "content": self._format_project_content(proj),
                "tags": ",".join(proj.get("technologies_used") or []),
                "start_date": proj.get("start_date") or None,
                "end_date": proj.get("end_date") or None,
            })

        for work in structured_data.get("work_experience") or []:
            position = (work.get("position") or "").strip()
            company = (work.get("company") or "").strip()
            title = " | ".join(x for x in (company, position) if x)
            if not title:
                continue
            # 实习判断：职位含「实习」或「intern」
            is_intern = "实习" in position or "intern" in position.lower()
            add({
                "entry_type": "internship" if is_intern else "work",
                "title": title,
                "content": self._format_work_content(work),
                "tags": ",".join(work.get("technologies_used") or []),
                "start_date": work.get("start_date") or None,
                "end_date": work.get("end_date") or None,
            })

        # 硬技能：按「单个技术名词」拆条，检索时能直接命中 Python / LangGraph 这类词
        skills = structured_data.get("skills") or {}
        if isinstance(skills, dict):
            for key, label in self._SKILL_CATEGORIES.items():
                for raw_name in skills.get(key) or []:
                    name = str(raw_name or "").strip()
                    if len(name) < 2:
                        continue
                    add({
                        "entry_type": "skill",
                        "title": name[:300],
                        "content": f"分类：{label}（来源：简历解析）",
                        "tags": label,
                        "start_date": None,
                        "end_date": None,
                    })

        # 证书 / 获奖
        for cert in structured_data.get("certificates") or []:
            text = str(cert or "").strip()
            if not text:
                continue
            add({
                "entry_type": "certificate",
                "title": text[:300],
                "content": f"证书/获奖：{text}",
                "tags": "证书",
                "start_date": None,
                "end_date": None,
            })

        return pending

    async def _auto_sync_to_skill_library(
        self, db: AsyncSession, structured_data: dict, user_id: str
    ) -> int:
        """上传简历后自动抽取项目/工作/实习/技能/证书写入技能库（纯规则，去重跳过，不覆盖已有条目）

        Returns:
            新增条目数
        """
        import logging
        logger = logging.getLogger("career-kb")
        from sqlalchemy import select
        from ..models.skill_library import SkillLibraryEntry

        # 结构化失败（回退成 raw）或没有可抽取内容时直接跳过
        pending = self._build_pending_entries(structured_data)
        if not pending:
            return 0

        # 2. 读取该用户已有技能库标题（归一化后做去重）
        existing = set()
        result = await db.execute(
            select(SkillLibraryEntry.title).where(SkillLibraryEntry.user_id == user_id)
        )
        for (t,) in result.fetchall():
            existing.add(self._normalize_title(t))

        # 3. 逐个写入（去重跳过，不覆盖手写/已有条目）
        created = 0
        for e in pending:
            norm = self._normalize_title(e["title"])
            if norm in existing:
                continue
            entry = SkillLibraryEntry(user_id=user_id, importance=3, **e)
            db.add(entry)
            await db.flush()  # 取 entry.id 供向量化
            # 向量化 + BM25 失效（与 skill_library.create_entry 一致）
            vector_store.add_skill_library_entry([{
                "id": entry.id,
                "content": f"[{entry.entry_type}] {entry.title}\n{entry.content}\n标签: {entry.tags or ''}",
                "metadata": {
                    "entry_type": entry.entry_type,
                    "title": entry.title,
                    "tags": entry.tags or "",
                    "importance": str(entry.importance),
                    "source": "skill_library",
                    "user_id": str(user_id),
                },
                "chunk_index": 0,
                "section_type": entry.entry_type,
                "section_title": entry.title,
                "token_count": len(entry.content),
            }])
            retriever.bm25_indexes.pop(f"skill_library:{user_id}", None)
            existing.add(norm)
            created += 1
            logger.info(f"技能库自动写入: [{entry.entry_type}] {entry.title}")

        return created

    async def upload_and_process(
        self,
        db: AsyncSession,
        file_path: str,
        name: str,
        photo_path: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Resume:
        """上传简历并完成全流程处理: 解析 → 结构化 → 分块 → 向量化"""
        # 1. 解析文件
        parse_result = parse_resume(file_path)

        # 2. 创建简历记录
        resume = Resume(
            name=name,
            source_filename=parse_result.source_filename,
            source_format=parse_result.source_format,
            raw_text=parse_result.raw_text,
            photo_path=photo_path,
            user_id=user_id,
        )
        db.add(resume)
        await db.flush()  # 获取 ID

        # 3. LLM 结构化解析 (允许失败，不阻塞流程)
        import logging
        logger = logging.getLogger("career-kb")
        try:
            structured = await llm_client.chat_json(
                system_prompt=RESUME_STRUCTURE_SYSTEM,
                user_message=RESUME_STRUCTURE_USER.format(raw_text=parse_result.raw_text[:3000]),
                temperature=0.1,
            )
            resume.structured_data = structured
            logger.info(f"简历结构化解析成功: {resume.id}")
        except Exception as e:
            logger.warning(f"简历结构化解析失败 (使用原始文本继续): {type(e).__name__}: {e}")
            resume.structured_data = {"raw": parse_result.raw_text}

        # 3.5 自动抽取项目/工作/实习写入技能库（去重跳过，失败不阻塞上传）
        if user_id:
            try:
                synced = await self._auto_sync_to_skill_library(db, resume.structured_data, user_id)
                if synced:
                    logger.info(f"技能库自动同步 {synced} 条")
            except Exception as e:
                logger.warning(f"技能库自动同步失败 (跳过): {type(e).__name__}: {e}")

        # 4. 智能分块
        try:
            chunks = self.chunker.chunk(resume.structured_data or {})
        except Exception as e:
            logger.error(f"分块失败: {e}")
            chunks = []
        resume.chunk_count = len(chunks)

        # 5. 向量化存储 (允许失败)
        collection_name = f"resume_{resume.id}"
        if chunks:
            try:
                # 注入 user_id 到 chunk metadata，供检索时按用户隔离
                if user_id:
                    for c in chunks:
                        c.metadata["user_id"] = user_id
                vector_store.add_chunks(collection_name, chunks)
                logger.info(f"向量化完成: {len(chunks)} chunks")
            except Exception as e:
                logger.warning(f"向量化失败 (跳过): {type(e).__name__}: {e}")

        # 6. 保存 chunk 记录到 SQLite
        for chunk in chunks:
            chunk_record = ResumeChunk(
                resume_id=resume.id,
                chroma_id=chunk.id,
                section_type=chunk.section_type,
                section_title=chunk.section_title,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                metadata_json=chunk.metadata,
                token_count=chunk.token_count,
            )
            db.add(chunk_record)

        # 7. 构建 BM25 索引
        bm25_docs = [
            {"id": c.id, "content": c.content, "metadata": c.metadata}
            for c in chunks
        ]
        retriever.build_bm25_index(collection_name, bm25_docs)

        await db.flush()
        return resume

    async def get_resume(self, db: AsyncSession, resume_id: str) -> Optional[Resume]:
        result = await db.execute(select(Resume).where(Resume.id == resume_id))
        return result.scalar_one_or_none()

    async def list_resumes(self, db: AsyncSession) -> list[Resume]:
        result = await db.execute(
            select(Resume).order_by(Resume.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_chunks(self, db: AsyncSession, resume_id: str) -> list[ResumeChunk]:
        result = await db.execute(
            select(ResumeChunk)
            .where(ResumeChunk.resume_id == resume_id)
            .order_by(ResumeChunk.chunk_index)
        )
        return list(result.scalars().all())

    async def save_generated_resume(
        self,
        db: AsyncSession,
        name: str,
        markdown_text: str,
        user_id: Optional[str] = None,
    ) -> Resume:
        """将生成的 Markdown 简历保存为新的简历记录（解析→分块→向量化）"""
        import logging
        logger = logging.getLogger("career-kb")

        # 1. 创建简历记录
        resume = Resume(
            name=name,
            source_filename=f"{name}.md",
            source_format="md",
            raw_text=markdown_text,
            user_id=user_id,
        )
        db.add(resume)
        await db.flush()

        # 2. LLM 结构化解析
        try:
            structured = await llm_client.chat_json(
                system_prompt=RESUME_STRUCTURE_SYSTEM,
                user_message=RESUME_STRUCTURE_USER.format(raw_text=markdown_text[:3000]),
                temperature=0.1,
            )
            resume.structured_data = structured
        except Exception as e:
            logger.warning(f"结构化解析失败: {e}")
            resume.structured_data = {"raw": markdown_text}

        # 3. 智能分块
        try:
            chunks = self.chunker.chunk(resume.structured_data or {})
        except Exception as e:
            logger.error(f"分块失败: {e}")
            chunks = []
        resume.chunk_count = len(chunks)

        # 4. 向量化存储
        collection_name = f"resume_{resume.id}"
        if chunks:
            try:
                # 注入 user_id 到 chunk metadata，供检索时按用户隔离
                if user_id:
                    for c in chunks:
                        c.metadata["user_id"] = user_id
                vector_store.add_chunks(collection_name, chunks)
            except Exception as e:
                logger.warning(f"向量化失败: {e}")

        # 5. 保存 chunk 记录
        for chunk in chunks:
            chunk_record = ResumeChunk(
                resume_id=resume.id,
                chroma_id=chunk.id,
                section_type=chunk.section_type,
                section_title=chunk.section_title,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                metadata_json=chunk.metadata,
                token_count=chunk.token_count,
            )
            db.add(chunk_record)

        # 6. 构建 BM25 索引
        bm25_docs = [
            {"id": c.id, "content": c.content, "metadata": c.metadata}
            for c in chunks
        ]
        retriever.build_bm25_index(collection_name, bm25_docs)

        await db.flush()
        logger.info(f"生成的简历已保存: {resume.id} ({name}), {len(chunks)} chunks")
        return resume

    async def delete_resume(self, db: AsyncSession, resume_id: str) -> bool:
        resume = await self.get_resume(db, resume_id)
        if not resume:
            return False

        # 删除 Chroma 向量
        collection_name = f"resume_{resume_id}"
        vector_store.delete_collection(collection_name)

        # 删除 BM25 索引
        retriever.remove_bm25_index(collection_name)

        # 删除关联照片
        if resume.photo_path:
            self.delete_photo(resume.photo_path)

        # 删除数据库记录 (级联删除 chunks)
        await db.delete(resume)
        return True

    @staticmethod
    def save_photo(resume_id: str, photo_file: UploadFile) -> str:
        """保存上传的证件照（从 UploadFile），缩放后返回存储路径"""
        photo_bytes = photo_file.file.read()
        return ResumeService._save_photo_bytes(resume_id, photo_bytes)

    @staticmethod
    def save_photo_from_bytes(resume_id: str, photo_bytes: bytes) -> str:
        """保存上传的证件照（从 bytes），缩放后返回存储路径"""
        return ResumeService._save_photo_bytes(resume_id, photo_bytes)

    @staticmethod
    def _save_photo_bytes(resume_id: str, photo_bytes: bytes) -> str:
        """内部: 保存照片 bytes"""
        from PIL import Image
        import io

        photos_dir = settings.PHOTOS_DIR
        os.makedirs(photos_dir, exist_ok=True)

        # 统一保存为 resume_id.jpg
        photo_path = os.path.join(photos_dir, f"{resume_id}.jpg")

        # 读取、缩放、保存
        image = Image.open(io.BytesIO(photo_bytes))
        # 转换为 RGB（处理 RGBA/PNG）
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        # 缩放到最大 300px 宽，保持比例
        if image.width > 300:
            ratio = 300 / image.width
            new_size = (300, int(image.height * ratio))
            image = image.resize(new_size, Image.LANCZOS)

        image.save(photo_path, "JPEG", quality=85)
        return photo_path

    @staticmethod
    def delete_photo(photo_path: str) -> None:
        """删除照片文件"""
        if photo_path and os.path.exists(photo_path):
            try:
                os.remove(photo_path)
            except OSError:
                pass


# 全局单例
resume_service = ResumeService()
