"""技能 Gap 分析 Agent — 基于 LangGraph StateGraph

流程:
1. extract_jd_skills — 从 JD 提取加权技术栈
2. format_resume_skills — 从简历结构化数据提取技能矩阵
3. analyze_gap — LLM 加权对比分析 + 生成学习路径
"""

import json
from typing import Optional, TypedDict, List

from langgraph.graph import StateGraph, END

from .llm_client import llm_client
from .prompts import (
    JD_SKILL_EXTRACT_SYSTEM,
    JD_SKILL_EXTRACT_USER,
    SKILL_GAP_SYSTEM,
    SKILL_GAP_USER,
)
from ..config import settings


# ============================================================
# State 定义
# ============================================================

class SkillGapState(TypedDict, total=False):
    """技能 Gap 分析状态"""

    # 输入
    jd_id: str
    resume_id: str
    jd_text: str
    jd_requirements: Optional[dict]
    structured_resume: Optional[dict]

    # 中间结果
    jd_tech_stack: Optional[list]
    resume_skills_text: str

    # 输出
    gap_analysis: Optional[dict]
    error: Optional[str]


# ============================================================
# 节点函数
# ============================================================

async def _extract_jd_skills_node(state: SkillGapState) -> dict:
    """节点1: 从 JD 提取加权技术栈"""
    jd_text = state.get("jd_text", "")
    jd_reqs = state.get("jd_requirements", {})

    try:
        result = await llm_client.chat_json(
            system_prompt=JD_SKILL_EXTRACT_SYSTEM,
            user_message=JD_SKILL_EXTRACT_USER.format(
                jd_text=jd_text,
                jd_requirements=json.dumps(jd_reqs, ensure_ascii=False, indent=2),
            ),
            model=settings.LLM_MODEL_SIMPLE,
            temperature=0.2,
        )
        return {"jd_tech_stack": result.get("tech_stack", [])}
    except Exception as e:
        return {"error": f"JD技能提取失败: {e}", "jd_tech_stack": []}


async def _format_resume_skills_node(state: SkillGapState) -> dict:
    """节点2: 从简历结构化数据提取技能文本"""
    structured = state.get("structured_resume") or {}

    parts = []
    basic = structured.get("basic_info", {})
    if basic.get("name"):
        parts.append(f"候选人: {basic['name']}")
    if basic.get("years_of_experience"):
        parts.append(f"工作年限: {basic['years_of_experience']}年")

    skills = structured.get("skills", {})
    if skills:
        parts.append("\n## 技能矩阵")
        for category, skill_list in skills.items():
            if isinstance(skill_list, list) and skill_list:
                parts.append(f"- {category}: {', '.join(skill_list)}")

    # 从工作经历中提取使用的技术
    work_experience = structured.get("work_experience", [])
    if work_experience:
        parts.append("\n## 工作经历技术栈")
        for w in work_experience[:5]:
            company = w.get("company", "")
            position = w.get("position", "")
            techs = w.get("technologies_used", [])
            if techs:
                parts.append(f"- {company}({position}): {', '.join(techs)}")

    projects = structured.get("projects", [])
    if projects:
        parts.append("\n## 项目技术栈")
        for p in projects[:3]:
            name = p.get("name", "")
            techs = p.get("technologies_used", [])
            if techs:
                parts.append(f"- {name}: {', '.join(techs)}")

    resume_text = "\n".join(parts) if parts else "暂无简历数据"

    return {"resume_skills_text": resume_text}


async def _analyze_gap_node(state: SkillGapState) -> dict:
    """节点3: LLM 加权 Gap 分析 + 学习路径"""
    jd_stack = state.get("jd_tech_stack", [])
    resume_text = state.get("resume_skills_text", "")

    try:
        result = await llm_client.chat_json(
            system_prompt=SKILL_GAP_SYSTEM,
            user_message=SKILL_GAP_USER.format(
                jd_tech_stack=json.dumps(jd_stack, ensure_ascii=False, indent=2),
                resume_skills=resume_text,
            ),
            model=settings.LLM_MODEL_POWERFUL,
            temperature=0.3,
        )
        return {"gap_analysis": result}
    except Exception as e:
        return {"error": f"Gap分析失败: {e}"}


# ============================================================
# 构建图
# ============================================================

def _build_skill_gap_graph() -> StateGraph:
    workflow = StateGraph(SkillGapState)
    workflow.add_node("extract_jd_skills", _extract_jd_skills_node)
    workflow.add_node("format_resume_skills", _format_resume_skills_node)
    workflow.add_node("analyze_gap", _analyze_gap_node)

    workflow.set_entry_point("extract_jd_skills")
    workflow.add_edge("extract_jd_skills", "format_resume_skills")
    workflow.add_edge("format_resume_skills", "analyze_gap")
    workflow.add_edge("analyze_gap", END)

    return workflow.compile()


_skill_gap_graph = _build_skill_gap_graph()


# ============================================================
# 对外接口
# ============================================================

class SkillGapAgent:
    """技能 Gap 分析 Agent"""

    def __init__(self):
        self.graph = _skill_gap_graph

    async def analyze(
        self,
        jd_id: str,
        resume_id: str,
        jd_text: str = "",
        jd_requirements: Optional[dict] = None,
        structured_resume: Optional[dict] = None,
    ) -> dict:
        """执行技能 Gap 分析"""
        initial_state: SkillGapState = {
            "jd_id": jd_id,
            "resume_id": resume_id,
            "jd_text": jd_text,
            "jd_requirements": jd_requirements,
            "structured_resume": structured_resume,
            "jd_tech_stack": None,
            "resume_skills_text": "",
            "gap_analysis": None,
            "error": None,
        }

        final_state = await self.graph.ainvoke(initial_state)

        return {
            "jd_tech_stack": final_state.get("jd_tech_stack", []),
            "gap_analysis": final_state.get("gap_analysis"),
            "error": final_state.get("error"),
        }

    async def extract_jd_skills(self, jd_text: str, jd_requirements: Optional[dict] = None) -> dict:
        """单独提取 JD 技术栈 (JD 上传时调用)"""
        try:
            result = await llm_client.chat_json(
                system_prompt=JD_SKILL_EXTRACT_SYSTEM,
                user_message=JD_SKILL_EXTRACT_USER.format(
                    jd_text=jd_text,
                    jd_requirements=json.dumps(jd_requirements or {}, ensure_ascii=False, indent=2),
                ),
                model=settings.LLM_MODEL_SIMPLE,
                temperature=0.2,
            )
            return result
        except Exception as e:
            return {"tech_stack": [], "error": str(e)}


# 全局单例
skill_gap_agent = SkillGapAgent()
