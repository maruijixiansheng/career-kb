"""章节感知的 Markdown 解析器 — 将 LLM 生成的简历 Markdown 解析为结构化数据

LLM 输出格式约定:
# 姓名
## 求职意向 → 一行描述
## 个人总结 → 多行文本
## 工作经历
### 公司 | 职位 | 时间  (或 **公司** | 职位)
- 职责/成果...
## 项目经历 (同上结构)
## 教育背景
## 专业技能
## 证书与荣誉
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExperienceEntry:
    """工作/项目经历的单个条目"""
    header: str = ""                        # 第一行: "公司 | 职位 | 时间" 或 "项目名 | 角色"
    details: list[str] = field(default_factory=list)  # 职责/成果列表


@dataclass
class ParsedResumeSections:
    """解析后的简历各章节"""
    name: str = ""
    target_position: str = ""
    personal_summary: str = ""
    work_experience: list[ExperienceEntry] = field(default_factory=list)
    project_experience: list[ExperienceEntry] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    certificates: list[str] = field(default_factory=list)


# 章节标题 → 字段映射
SECTION_MAP = {
    "求职意向": "target_position",
    "个人总结": "personal_summary",
    "自我评价": "personal_summary",
    "自我介绍": "personal_summary",
    "工作经历": "work_experience",
    "工作经验": "work_experience",
    "实习经历": "work_experience",
    "项目经历": "project_experience",
    "项目经验": "project_experience",
    "教育背景": "education",
    "教育经历": "education",
    "学历": "education",
    "专业技能": "skills",
    "技术栈": "skills",
    "掌握技能": "skills",
    "技能": "skills",
    "证书与荣誉": "certificates",
    "证书": "certificates",
    "获奖": "certificates",
    "荣誉": "certificates",
    "奖项": "certificates",
    "语言能力": "language",  # 归入技能
}


def parse_resume_markdown(markdown: str) -> ParsedResumeSections:
    """解析 LLM 生成的简历 Markdown 为结构化数据

    Args:
        markdown: 去除了 <analysis> 标签的纯 Markdown 简历

    Returns:
        ParsedResumeSections 结构化数据
    """
    result = ParsedResumeSections()
    lines = markdown.strip().split("\n")

    # 1. 提取姓名（第一个 # 标题）
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            result.name = stripped[2:].strip()
            break

    # 2. 按 ## 拆分为章节
    sections = _split_by_h2(lines)

    for section_title, section_lines in sections.items():
        # 匹配章节类型
        section_key = _match_section(section_title)
        content = "\n".join(section_lines).strip()

        if section_key == "target_position":
            # 求职意向: 通常是单行
            result.target_position = _clean_line(section_lines[0]) if section_lines else ""

        elif section_key == "personal_summary":
            # 个人总结: 一段或多行文本
            result.personal_summary = _clean_text(content)

        elif section_key == "work_experience":
            result.work_experience = _parse_experience_entries(section_lines)

        elif section_key == "project_experience":
            result.project_experience = _parse_experience_entries(section_lines)

        elif section_key == "education":
            result.education = _parse_list_items(section_lines)

        elif section_key == "skills":
            result.skills = _parse_skills(section_lines)

        elif section_key == "certificates":
            result.certificates = _parse_list_items(section_lines)

    return result


def _split_by_h2(lines: list[str]) -> dict[str, list[str]]:
    """按 ## 二级标题拆分，返回 {章节标题: [行列表]}"""
    sections = {}
    current_title = None
    current_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            # 保存上一章节
            if current_title is not None:
                sections[current_title] = current_lines
            current_title = stripped[3:].strip()
            current_lines = []
        elif current_title is not None:
            current_lines.append(stripped)

    # 最后一个章节
    if current_title is not None:
        sections[current_title] = current_lines

    return sections


def _match_section(title: str) -> str:
    """匹配章节标题到类型 key"""
    for pattern, key in SECTION_MAP.items():
        if pattern in title:
            return key
    return ""


def _parse_experience_entries(lines: list[str]) -> list[ExperienceEntry]:
    """解析工作/项目经历条目

    支持格式:
    1. ### 公司 | 职位 | 时间  → 条目分隔
    2. **公司** | 职位 | 时间  → 条目分隔
    3. 公司 | 职位 | 时间 (纯文本加粗检测)
    """
    entries = []
    current_entry = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 检测新条目开始
        is_new_entry = False
        header = ""

        # ### 标题
        if stripped.startswith("### "):
            header = stripped[4:].strip()
            is_new_entry = True
        # **加粗** 标题
        elif stripped.startswith("**") and "**" in stripped[2:]:
            header = stripped.strip("*").strip()
            is_new_entry = True
        # "公司 | " 格式
        elif " | " in stripped and current_entry is None:
            header = stripped
            is_new_entry = True
        # 纯文本行，以公司/项目名开头（第一次遇到）
        elif current_entry is None and not stripped.startswith("-") and not stripped.startswith("*"):
            header = stripped
            is_new_entry = True

        if is_new_entry and header:
            if current_entry is not None:
                entries.append(current_entry)
            current_entry = ExperienceEntry(header=header)
        elif current_entry is not None:
            # 职责/成果行
            detail = stripped.lstrip("-*• ").strip()
            if detail:
                current_entry.details.append(detail)

    if current_entry is not None:
        entries.append(current_entry)

    return entries


def _parse_list_items(lines: list[str]) -> list[str]:
    """解析列表条目（教育背景、证书等）"""
    items = []
    for line in lines:
        stripped = line.strip().lstrip("-*• ").strip()
        if stripped:
            items.append(stripped)
    return items


def _parse_skills(lines: list[str]) -> list[str]:
    """解析技能部分，保留原始文本行"""
    skills = []
    for line in lines:
        stripped = line.strip().lstrip("-*• ").strip()
        if stripped:
            skills.append(stripped)
    return skills


def _clean_line(line: str) -> str:
    """清洗单行文本"""
    return line.strip().lstrip("-*• ").strip()


def _clean_text(text: str) -> str:
    """清洗多行文本，合并为一段"""
    lines = [l.strip().lstrip("-*• ").strip() for l in text.split("\n")]
    return " ".join(l for l in lines if l)
