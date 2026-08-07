"""无回应分析 Agent — 基于 LangGraph StateGraph

当投递超过 7 天未收到回应时，触发三路并行分析:
1. 原因分析 (analyze) — 分析为什么没有回应
2. 跟进建议 (follow_up) — 生成跟进沟通方案
3. 策略建议 (suggest) — 提供求职策略调整建议

三路 LLM 调用使用 asyncio.gather 并行执行，然后合并结果。
"""

import asyncio
import json
from typing import Optional, TypedDict, List

from langgraph.graph import StateGraph, END

from .llm_client import llm_client
from .prompts import (
    NO_RESPONSE_ANALYZE_SYSTEM,
    NO_RESPONSE_ANALYZE_USER,
    NO_RESPONSE_FOLLOWUP_SYSTEM,
    NO_RESPONSE_FOLLOWUP_USER,
    NO_RESPONSE_SUGGEST_SYSTEM,
    NO_RESPONSE_SUGGEST_USER,
)
from ..config import settings


# ============================================================
# State 定义
# ============================================================

class NoResponseState(TypedDict, total=False):
    """无回应分析 Agent 状态"""

    # 输入
    application_id: str
    company: str
    position: str
    jd_text: str
    resume_summary: str
    days_since_apply: int

    # 三路并行输出
    analysis_result: Optional[dict]
    follow_up_result: Optional[dict]
    suggest_result: Optional[dict]

    # 合并结果
    merged_summary: Optional[str]
    error: Optional[str]


# ============================================================
# 节点函数
# ============================================================

async def _load_context_node(state: NoResponseState) -> dict:
    """节点1: 加载应用上下文 (验证输入)"""
    company = state.get("company", "")
    position = state.get("position", "")
    days = state.get("days_since_apply", 0)

    if not company or not position:
        return {"error": "缺少公司和职位信息"}

    return {
        "company": company,
        "position": position,
        "days_since_apply": max(days, 1),
    }


async def _parallel_analyze_node(state: NoResponseState) -> dict:
    """节点2: 并行执行三路 LLM 分析 (asyncio.gather)"""
    company = state["company"]
    position = state["position"]
    jd_text = state.get("jd_text", "暂无 JD 信息")
    resume_summary = state.get("resume_summary", "暂无简历摘要")
    days = state.get("days_since_apply", 7)

    # 并行调用三个 LLM (独立调用，无依赖关系)
    try:
        results = await asyncio.gather(
            llm_client.chat_json(
                system_prompt=NO_RESPONSE_ANALYZE_SYSTEM,
                user_message=NO_RESPONSE_ANALYZE_USER.format(
                    company=company,
                    position=position,
                    jd_text=jd_text,
                    resume_summary=resume_summary,
                    days_since_apply=days,
                ),
                model=settings.LLM_MODEL_SIMPLE,
                temperature=0.3,
            ),
            llm_client.chat_json(
                system_prompt=NO_RESPONSE_FOLLOWUP_SYSTEM,
                user_message=NO_RESPONSE_FOLLOWUP_USER.format(
                    company=company,
                    position=position,
                    resume_summary=resume_summary,
                    days_since_apply=days,
                ),
                model=settings.LLM_MODEL_SIMPLE,
                temperature=0.5,
            ),
            llm_client.chat_json(
                system_prompt=NO_RESPONSE_SUGGEST_SYSTEM,
                user_message=NO_RESPONSE_SUGGEST_USER.format(
                    company=company,
                    position=position,
                    jd_text=jd_text,
                    resume_summary=resume_summary,
                    days_since_apply=days,
                    analysis_result="待分析完成后填入",
                ),
                model=settings.LLM_MODEL_SIMPLE,
                temperature=0.5,
            ),
            return_exceptions=True,
        )

        analysis_result = results[0] if not isinstance(results[0], Exception) else None
        follow_up_result = results[1] if not isinstance(results[1], Exception) else None
        suggest_result = results[2] if not isinstance(results[2], Exception) else None

        return {
            "analysis_result": analysis_result,
            "follow_up_result": follow_up_result,
            "suggest_result": suggest_result,
        }
    except Exception as e:
        return {"error": f"并行分析失败: {e}"}


async def _merge_node(state: NoResponseState) -> dict:
    """节点3: 合并三路分析结果，生成综合摘要"""
    analysis = state.get("analysis_result") or {}
    follow_up = state.get("follow_up_result") or {}
    suggest = state.get("suggest_result") or {}
    company = state.get("company", "")
    position = state.get("position", "")

    # 构建综合摘要
    summary_parts = []

    # 分析结果摘要
    if analysis:
        primary = analysis.get("primary_reason", "未知")
        summary_parts.append(f"【原因分析】{primary}")
        dims = analysis.get("dimensions", {})
        for dim_name, dim_data in dims.items():
            if isinstance(dim_data, dict) and dim_data.get("score", 0) < 50:
                summary_parts.append(f"  - 薄弱项: {dim_data.get('analysis', '')}")

    # 跟进方案摘要
    if follow_up:
        channel = follow_up.get("recommended_channel", "")
        summary_parts.append(f"【推荐跟进渠道】{channel}")

    # 策略建议摘要
    if suggest:
        action = suggest.get("recommended_action", "")
        strategies = suggest.get("strategies", [])
        high_priority = [s for s in strategies if isinstance(s, dict) and s.get("priority") == "high"]
        summary_parts.append(f"【推荐行动】{action}")
        if high_priority:
            summary_parts.append(f"  高优先级策略: {len(high_priority)} 项")

    merged = "\n".join(summary_parts) if summary_parts else "分析完成"

    return {"merged_summary": merged}


# ============================================================
# 构建和编译图
# ============================================================

def _build_no_response_graph() -> StateGraph:
    """构建无回应分析状态图"""
    workflow = StateGraph(NoResponseState)

    workflow.add_node("load_context", _load_context_node)
    workflow.add_node("parallel_analyze", _parallel_analyze_node)
    workflow.add_node("merge", _merge_node)

    workflow.set_entry_point("load_context")
    workflow.add_edge("load_context", "parallel_analyze")
    workflow.add_edge("parallel_analyze", "merge")
    workflow.add_edge("merge", END)

    return workflow.compile()


# 全局图实例
_no_response_graph = _build_no_response_graph()


# ============================================================
# 对外接口
# ============================================================

class NoResponseAgent:
    """无回应分析 Agent"""

    def __init__(self):
        self.graph = _no_response_graph

    async def analyze(
        self,
        application_id: str,
        company: str,
        position: str,
        jd_text: str = "",
        resume_summary: str = "",
        days_since_apply: int = 7,
    ) -> dict:
        """执行无回应分析

        Returns:
            {
                "analysis_result": dict,      # 原因分析
                "follow_up_result": dict,     # 跟进方案
                "suggest_result": dict,       # 策略建议
                "merged_summary": str,        # 综合摘要
                "error": str or None
            }
        """
        initial_state: NoResponseState = {
            "application_id": application_id,
            "company": company,
            "position": position,
            "jd_text": jd_text,
            "resume_summary": resume_summary,
            "days_since_apply": days_since_apply,
            "analysis_result": None,
            "follow_up_result": None,
            "suggest_result": None,
            "merged_summary": None,
            "error": None,
        }

        final_state = await self.graph.ainvoke(initial_state)

        return {
            "analysis_result": final_state.get("analysis_result"),
            "follow_up_result": final_state.get("follow_up_result"),
            "suggest_result": final_state.get("suggest_result"),
            "merged_summary": final_state.get("merged_summary", ""),
            "error": final_state.get("error"),
        }


# 全局单例
no_response_agent = NoResponseAgent()
