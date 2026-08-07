"""中文简历智能分块器 — 系统差异化能力的根基

分块策略:
- L1 (粗粒度/章节级): 整章保留作为后备上下文，不参与向量检索
- L2 (中粒度/条目级): 单条工作经历/项目/教育经历，检索主力
- L3 (细粒度/职责级): L2超过800字时拆分，通过parent_id关联可回溯还原

核心原则:
1. 章节为天然边界，绝不跨越章节分块
2. 工作条目为原子单元，单条≤800字不拆分
3. 中文目标chunk_size: 300-500字 (中文信息密度远高于英文)
"""

import re
import uuid
from typing import Optional
from dataclasses import dataclass, field

from ..config import settings


# 常见简历章节标题关键词
SECTION_PATTERNS = {
    "basic_info": ["基本信息", "个人信息", "个人资料", "联系方式", "求职意向", "期望职位", "期望城市"],
    "self_evaluation": ["自我评价", "个人评价", "自我介绍", "关于我", "个人总结", "职业目标"],
    "education": ["教育背景", "教育经历", "学历", "教育", "学习经历", "学术背景"],
    "work": ["工作经历", "工作经验", "工作", "实习经历", "实习经验", "职业经历"],
    "project": ["项目经历", "项目经验", "项目", "所做项目", "主要项目"],
    "skill": ["技能", "专业技能", "技术栈", "掌握技能", "个人技能", "技术能力"],
    "certificate": ["证书", "资格证书", "获奖", "荣誉", "奖项"],
    "language": ["语言能力", "外语水平", "语言"],
}


@dataclass
class Chunk:
    """分块数据结构"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    section_type: str = ""              # basic_info/education/work/project/skill/self_eval/certificate
    section_title: str = ""             # 原始章节标题
    chunk_index: int = 0                # 在原简历中的位置序号
    content: str = ""                   # 分块文本
    metadata: dict = field(default_factory=dict)  # 元数据
    token_count: int = 0                # 字符数
    parent_chunk_id: Optional[str] = None  # L3 → L2 的父chunk关联

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "section_type": self.section_type,
            "section_title": self.section_title,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "metadata": self.metadata,
            "token_count": self.token_count,
        }

    def to_langchain_document(self):
        """转换为 LangChain Document 格式 (供 LangChain Retriever 使用)"""
        from langchain_core.documents import Document
        return Document(
            page_content=self.content,
            metadata={
                **self.metadata,
                "chunk_id": self.id,
                "section_type": self.section_type,
                "section_title": self.section_title,
                "chunk_index": self.chunk_index,
                "token_count": self.token_count,
            },
        )


@dataclass
class Section:
    """简历章节"""
    type: str
    title: str
    content: str
    entries: list[dict] = field(default_factory=list)


class ResumeChunker:
    """中文简历智能分块器"""

    def __init__(
        self,
        max_chars: int = None,
        target_chars: int = None,
    ):
        self.max_chars = max_chars or settings.CHUNK_MAX_CHARS
        self.target_chars = target_chars or settings.CHUNK_TARGET_CHARS

    def chunk(self, structured_data: dict) -> list[Chunk]:
        """对结构化简历进行分块

        Args:
            structured_data: LLM解析后的结构化JSON简历数据

        Returns:
            分块列表
        """
        chunks = []
        chunk_index = 0

        # 1. Basic Info: 整体保留，不拆分
        basic = structured_data.get("basic_info")
        if basic:
            text = self._format_basic_info(basic)
            chunks.append(Chunk(
                section_type="basic_info",
                section_title="基本信息",
                chunk_index=chunk_index,
                content=text,
                metadata={"type": "basic_info", "name": basic.get("name", "")},
                token_count=len(text),
            ))
            chunk_index += 1

        # 2. Self Evaluation: 整体保留
        self_eval = structured_data.get("self_evaluation")
        if self_eval:
            chunks.append(Chunk(
                section_type="self_eval",
                section_title="个人总结",
                chunk_index=chunk_index,
                content=self_eval if isinstance(self_eval, str) else str(self_eval),
                metadata={"type": "self_eval"},
                token_count=len(self_eval) if isinstance(self_eval, str) else 0,
            ))
            chunk_index += 1

        # 3. Work Experience: 每条经历独立分块 (最关键的分块逻辑)
        for i, work in enumerate(structured_data.get("work_experience", [])):
            entry_text = self._format_work_entry(work)
            techs = work.get("technologies_used", [])

            if len(entry_text) <= self.max_chars:
                # 整条经历作为一个chunk (L2)
                chunks.append(Chunk(
                    section_type="work",
                    section_title="工作经历",
                    chunk_index=chunk_index,
                    content=entry_text,
                    metadata={
                        "company": work.get("company", ""),
                        "position": work.get("position", ""),
                        "start_date": work.get("start_date", ""),
                        "end_date": work.get("end_date", ""),
                        "technologies": techs,
                        "is_partial": False,
                    },
                    token_count=len(entry_text),
                ))
                chunk_index += 1
            else:
                # 超长经历: 按职责点拆分 (L3)
                parent_chunk_id = str(uuid.uuid4())
                header = f"{work.get('company', '')} | {work.get('position', '')}"
                if work.get("start_date"):
                    header += f" | {work.get('start_date')} - {work.get('end_date', '至今')}"

                # 先创建父 chunk (L2, 包含header+概述)
                chunks.append(Chunk(
                    id=parent_chunk_id,
                    section_type="work",
                    section_title="工作经历",
                    chunk_index=chunk_index,
                    content=header,
                    metadata={
                        "company": work.get("company", ""),
                        "position": work.get("position", ""),
                        "start_date": work.get("start_date", ""),
                        "end_date": work.get("end_date", ""),
                        "technologies": techs,
                        "is_partial": False,
                        "has_sub_chunks": True,
                    },
                    token_count=len(header),
                ))
                chunk_index += 1

                # 拆分职责为子chunk (L3)
                responsibilities = work.get("responsibilities", [])
                for j, resp in enumerate(responsibilities):
                    sub_content = f"{header}\n{resp}"
                    chunks.append(Chunk(
                        section_type="work",
                        section_title="工作经历",
                        chunk_index=chunk_index,
                        content=sub_content,
                        metadata={
                            "company": work.get("company", ""),
                            "position": work.get("position", ""),
                            "is_partial": True,
                            "parent_chunk_id": parent_chunk_id,
                            "part_index": j,
                        },
                        token_count=len(sub_content),
                        parent_chunk_id=parent_chunk_id,
                    ))
                    chunk_index += 1

        # 4. Projects: 每个项目一个chunk
        for proj in structured_data.get("projects", []):
            text = self._format_project(proj)
            chunks.append(Chunk(
                section_type="project",
                section_title="项目经历",
                chunk_index=chunk_index,
                content=text,
                metadata={
                    "project_name": proj.get("name", ""),
                    "role": proj.get("role", ""),
                    "technologies": proj.get("technologies_used", []),
                },
                token_count=len(text),
            ))
            chunk_index += 1

        # 5. Education: 每条独立chunk
        for edu in structured_data.get("education", []):
            text = self._format_education(edu)
            chunks.append(Chunk(
                section_type="education",
                section_title="教育背景",
                chunk_index=chunk_index,
                content=text,
                metadata={
                    "school": edu.get("school", ""),
                    "degree": edu.get("degree", ""),
                    "major": edu.get("major", ""),
                },
                token_count=len(text),
            ))
            chunk_index += 1

        # 6. Skills: 整体保留 (便于技能匹配)
        skills = structured_data.get("skills")
        if skills:
            text = self._format_skills(skills)
            chunks.append(Chunk(
                section_type="skill",
                section_title="专业技能",
                chunk_index=chunk_index,
                content=text,
                metadata={
                    "skill_names": self._extract_skill_names(skills),
                    "type": "skills",
                },
                token_count=len(text),
            ))
            chunk_index += 1

        # 7. Certificates: 整体保留
        certs = structured_data.get("certificates", [])
        if certs:
            text = "证书与荣誉:\n" + "\n".join(f"- {c}" for c in certs)
            chunks.append(Chunk(
                section_type="certificate",
                section_title="证书与荣誉",
                chunk_index=chunk_index,
                content=text,
                metadata={"type": "certificate"},
                token_count=len(text),
            ))
            chunk_index += 1

        return chunks

    def _format_basic_info(self, info: dict) -> str:
        """格式化基本信息"""
        parts = []
        if info.get("name"):
            parts.append(f"姓名: {info['name']}")
        if info.get("email"):
            parts.append(f"邮箱: {info['email']}")
        if info.get("phone"):
            parts.append(f"电话: {info['phone']}")
        if info.get("city"):
            parts.append(f"城市: {info['city']}")
        if info.get("target_position"):
            parts.append(f"求职意向: {info['target_position']}")
        if info.get("years_of_experience"):
            parts.append(f"工作年限: {info['years_of_experience']}年")
        return "\n".join(parts)

    def _format_work_entry(self, work: dict) -> str:
        """格式化单条工作经历"""
        parts = [f"公司: {work.get('company', '')}"]
        parts.append(f"职位: {work.get('position', '')}")
        if work.get("start_date"):
            parts.append(f"时间: {work['start_date']} - {work.get('end_date', '至今')}")
        if work.get("location"):
            parts.append(f"地点: {work['location']}")
        if work.get("responsibilities"):
            parts.append("职责:")
            for r in work["responsibilities"]:
                parts.append(f"  - {r}")
        if work.get("achievements"):
            parts.append("成果:")
            for a in work["achievements"]:
                parts.append(f"  - {a}")
        if work.get("technologies_used"):
            parts.append(f"技术栈: {', '.join(work['technologies_used'])}")
        return "\n".join(parts)

    def _format_project(self, proj: dict) -> str:
        """格式化单条项目经历"""
        parts = [f"项目: {proj.get('name', '')}"]
        if proj.get("role"):
            parts.append(f"角色: {proj['role']}")
        if proj.get("start_date"):
            parts.append(f"时间: {proj['start_date']} - {proj.get('end_date', '')}")
        if proj.get("description"):
            parts.append(f"简介: {proj['description']}")
        if proj.get("responsibilities"):
            parts.append("职责:")
            for r in proj["responsibilities"]:
                parts.append(f"  - {r}")
        if proj.get("achievements"):
            parts.append("成果:")
            for a in proj["achievements"]:
                parts.append(f"  - {a}")
        if proj.get("technologies_used"):
            parts.append(f"技术栈: {', '.join(proj['technologies_used'])}")
        return "\n".join(parts)

    def _format_education(self, edu: dict) -> str:
        """格式化单条教育经历"""
        parts = [f"学校: {edu.get('school', '')}"]
        parts.append(f"学历: {edu.get('degree', '')}")
        if edu.get("major"):
            parts.append(f"专业: {edu['major']}")
        if edu.get("start_date"):
            parts.append(f"时间: {edu['start_date']} - {edu.get('end_date', '')}")
        return "\n".join(parts)

    def _format_skills(self, skills: dict) -> str:
        """格式化技能部分"""
        parts = []
        if isinstance(skills, dict):
            for category, skill_list in skills.items():
                if skill_list:
                    parts.append(f"{category}: {', '.join(skill_list)}")
        elif isinstance(skills, list):
            parts.append("技能: " + ", ".join(skills))
        return "\n".join(parts)

    def _extract_skill_names(self, skills: dict) -> list[str]:
        """从技能dict中提取所有技能名称"""
        names = []
        if isinstance(skills, dict):
            for skill_list in skills.values():
                if isinstance(skill_list, list):
                    names.extend(skill_list)
        elif isinstance(skills, list):
            names = skills
        return names


def detect_sections(raw_text: str) -> list[Section]:
    """基于规则检测简历章节边界 (用于LLM解析前的预分段)

    通过识别章节标题关键词(如"工作经历"、"教育背景"等)来切分简历，
    每段送入LLM进行结构化提取。
    """
    lines = raw_text.split("\n")
    sections = []
    current_section = None
    current_content = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_content.append("")
            continue

        # 检测是否为章节标题
        section_type = _match_section_title(stripped)
        if section_type:
            # 保存上一章节
            if current_section:
                sections.append(Section(
                    type=current_section["type"],
                    title=current_section["title"],
                    content="\n".join(current_content).strip(),
                ))

            current_section = {"type": section_type, "title": stripped}
            current_content = []
        else:
            current_content.append(stripped)

    # 保存最后一节
    if current_section:
        sections.append(Section(
            type=current_section["type"],
            title=current_section["title"],
            content="\n".join(current_content).strip(),
        ))

    return sections


def _match_section_title(text: str) -> Optional[str]:
    """匹配章节标题，返回章节类型"""
    text_clean = text.strip().lstrip("#").strip()
    for section_type, patterns in SECTION_PATTERNS.items():
        for pattern in patterns:
            if pattern in text_clean and len(text_clean) <= 15:
                return section_type
    return None
