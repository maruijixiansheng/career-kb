"""面试模拟 Agent — 管理面试对话流程和评估

注意: 状态从数据库重建（非内存），避免多 worker 不同步问题。
"""

import json
from typing import Optional

from .llm_client import llm_client
from .prompts import (
    INTERVIEW_SYSTEM,
    INTERVIEW_FEEDBACK_SYSTEM,
    INTERVIEW_FEEDBACK_USER,
)
from ..config import settings


class InterviewAgent:
    """面试模拟 Agent（无状态：所有状态从 DB 重建）"""

    def __init__(self):
        # 内存缓存仅用于加速（非唯一状态源）
        self.sessions: dict[str, dict] = {}

    def get_state(self, session_id: str) -> Optional[dict]:
        """获取状态（内存缓存优先，回退到 DB 重建）"""
        if session_id in self.sessions:
            return self.sessions[session_id]
        return None  # 调用方应使用 load_state_from_db()

    async def load_state_from_db(self, session_id: str) -> Optional[dict]:
        """从数据库重建面试会话状态（解决多 worker 状态不同步）"""
        from ..models.interview import InterviewSession, InterviewMessage
        from ..models.job import JobDescription
        from ..models.resume import Resume
        from ..database import async_session
        from sqlalchemy import select

        async with async_session() as db:
            # 加载会话
            session_obj = (await db.execute(
                select(InterviewSession).where(InterviewSession.id == session_id)
            )).scalar_one_or_none()
            if not session_obj:
                return None

            # 加载消息
            messages_result = await db.execute(
                select(InterviewMessage)
                .where(InterviewMessage.session_id == session_id)
                .order_by(InterviewMessage.sequence)
            )
            db_messages = messages_result.scalars().all()

            # 加载 JD 和简历（用于 prompt）
            jd_text = ""
            resume_text = ""
            company = ""
            position = ""
            if session_obj.jd_id:
                jd_obj = (await db.execute(
                    select(JobDescription).where(JobDescription.id == session_obj.jd_id)
                )).scalar_one_or_none()
                if jd_obj:
                    jd_text = jd_obj.raw_text or ""
                    company = jd_obj.company or ""
                    position = jd_obj.title or ""
            if session_obj.resume_id:
                resume_obj = (await db.execute(
                    select(Resume).where(Resume.id == session_obj.resume_id)
                )).scalar_one_or_none()
                if resume_obj:
                    resume_text = resume_obj.raw_text or ""

            # 重建消息列表
            messages = [
                {"role": m.role, "content": m.content}
                for m in db_messages
            ]

        difficulty = session_obj.difficulty or "medium"
        stage_map = {
            "technical": "技术面试（侧重技术深度、系统设计、编码能力）",
            "behavioral": "行为面试（侧重沟通协作、领导力、问题解决）",
            "mixed": "综合面试（技术+行为混合，模拟真实面试流程）",
        }
        diff_map = {"easy": "偏基础，适合初级岗位", "medium": "中等难度", "hard": "高难度，适合高级岗位"}

        # 计算当前问题数（interviewer 角色的消息数量）
        question_count = sum(1 for m in messages if m["role"] == "interviewer")

        # 当前问题（最后一个 interviewer 消息）
        current_question = ""
        for m in reversed(messages):
            if m["role"] == "interviewer":
                current_question = m["content"]
                break

        state = {
            "session_id": session_id,
            "company": company,
            "position": position,
            "jd_text": jd_text,
            "resume_text": resume_text,
            "mode": session_obj.mode or "mixed",
            "difficulty": difficulty,
            "question_count": question_count,
            "max_questions": {"easy": 6, "medium": 10, "hard": 12}.get(difficulty, 10),
            "messages": messages,
            "current_question": current_question,
            "stage_description": stage_map.get(session_obj.mode, stage_map["mixed"]),
            "difficulty_description": diff_map.get(difficulty, diff_map["medium"]),
        }

        # 缓存到内存
        self.sessions[session_id] = state
        return state

    def init_session(
        self, session_id: str, jd_text: str, resume_text: str,
        mode: str = "mixed", difficulty: str = "medium",
        company: str = "", position: str = "",
    ) -> dict:
        """初始化面试会话"""
        stage_map = {
            "technical": "技术面试（侧重技术深度、系统设计、编码能力）",
            "behavioral": "行为面试（侧重沟通协作、领导力、问题解决）",
            "mixed": "综合面试（技术+行为混合，模拟真实面试流程）",
        }
        diff_map = {"easy": "偏基础，适合初级岗位", "medium": "中等难度", "hard": "高难度，适合高级岗位"}

        state = {
            "session_id": session_id,
            "company": company,
            "position": position,
            "jd_text": jd_text,
            "resume_text": resume_text,
            "mode": mode,
            "difficulty": difficulty,
            "question_count": 0,
            "max_questions": {"easy": 6, "medium": 10, "hard": 12}.get(difficulty, 10),
            "messages": [],
            "stage_description": stage_map.get(mode, stage_map["mixed"]),
            "difficulty_description": diff_map.get(difficulty, diff_map["medium"]),
        }
        self.sessions[session_id] = state
        return state

    async def generate_question(self, session_id: str, state: Optional[dict] = None) -> dict:
        """生成下一个面试问题（优先使用传入的 state，回退内存缓存）"""
        if state is None:
            state = self.sessions.get(session_id)
        if not state:
            return {"error": "会话不存在"}

        q_num = state["question_count"] + 1
        stage = f"第{q_num}/{state['max_questions']}题 - {state['difficulty_description']}"

        # 生成问题
        prompt = INTERVIEW_SYSTEM.format(
            company=state["company"] or "目标公司",
            position=state["position"] or "目标岗位",
            jd_text=state["jd_text"],
            resume_text=state["resume_text"],
            interview_stage=stage,
        )

        conversation = "\n".join([
            f"{'面试官' if m['role'] == 'interviewer' else '候选人'}: {m['content']}"
            for m in state["messages"]
        ])

        user_msg = f"{prompt}\n\n## 面试历史\n{conversation}\n\n请根据上述对话历史，提出第{q_num}个面试问题。只需返回问题文本，不要加任何前缀标签。"

        try:
            question = await llm_client.chat(
                system_prompt=prompt,
                user_message=user_msg,
                model=settings.LLM_MODEL_POWERFUL,
                temperature=0.7,
                max_tokens=500,
            )
        except Exception:
            question = "请简单介绍一下你自己和你的项目经历。"

        state["current_question"] = question.strip()
        state["question_count"] = q_num

        return {
            "session_id": session_id,
            "question": state["current_question"],
            "question_number": q_num,
            "total_questions": state["max_questions"],
            "is_last": q_num >= state["max_questions"],
        }

    async def process_answer(self, session_id: str, answer: str, state: Optional[dict] = None) -> dict:
        """处理候选人回答，返回反馈或下一个问题（优先使用传入的 state）"""
        if state is None:
            state = self.sessions.get(session_id)
        if not state:
            return {"error": "会话不存在"}

        # 记录候选人回答到内存状态
        # 注意：面试官问题已由 API 层在 generate_question 后存入 DB，
        # load_state_from_db 重建时 messages 已包含所有历史消息
        already_has_question = any(
            m["role"] == "interviewer" and m["content"] == state.get("current_question", "")
            for m in state["messages"]
        )
        if not already_has_question:
            state["messages"].append({"role": "interviewer", "content": state.get("current_question", "")})
        state["messages"].append({"role": "candidate", "content": answer})

        # 检查是否结束
        if state["question_count"] >= state["max_questions"]:
            return {"finished": True, "message": "面试环节结束，正在生成评估报告..."}

        # 给出简短反馈（不在这里生成下一题，由 API 层统一调用 generate_question）
        try:
            feedback_prompt = f"""基于候选人的回答，给出一句简短的鼓励或评价（10字以内），然后直接进入下一个问题。

候选人回答: {answer[:300]}

请返回JSON:
{{"feedback": "简短评价", "should_continue": true}}"""
            fb = await llm_client.chat_json(
                system_prompt="你是面试官，简短评价候选人的回答。",
                user_message=feedback_prompt,
                model=settings.LLM_MODEL_SIMPLE,
                temperature=0.5,
            )
            feedback = fb.get("feedback", "")
        except Exception:
            feedback = ""

        return {
            "finished": False,
            "feedback": feedback,
        }

    async def generate_report(self, session_id: str, state: Optional[dict] = None) -> dict:
        """生成面试评估报告（优先使用传入的 state）"""
        if state is None:
            state = self.sessions.get(session_id)
        if not state:
            return {"error": "会话不存在"}

        conversation = "\n".join([
            f"[{m['role']}] {m['content']}"
            for m in state["messages"]
        ])

        try:
            report = await llm_client.chat_json(
                system_prompt=INTERVIEW_FEEDBACK_SYSTEM,
                user_message=INTERVIEW_FEEDBACK_USER.format(
                    position=state["position"],
                    company=state["company"],
                    mode=state["mode"],
                    conversation=conversation,
                ),
                model=settings.LLM_MODEL_POWERFUL,
                temperature=0.3,
            )
        except Exception:
            report = {
                "overall_score": 70,
                "dimension_scores": {"technical": 70, "communication": 70, "project_experience": 70, "problem_solving": 70, "job_match": 70},
                "strengths": ["参与度良好"],
                "weaknesses": ["某些问题回答不够深入"],
                "suggestions": "建议针对JD要求做更充分的准备",
            }

        # 生成每个面试官问题的专业参考答案
        model_answers = await self._generate_model_answers(state)
        report["model_answers"] = model_answers

        state["status"] = "completed"
        state["messages"].append({"role": "system", "content": f"面试评估完成，综合得分: {report.get('overall_score', 0)}"})

        return report

    async def _generate_model_answers(self, state: dict) -> list[dict]:
        """为面试官提出的每个问题生成专业参考答案"""
        # 提取面试官的问题
        questions = []
        for m in state["messages"]:
            if m["role"] == "interviewer":
                questions.append(m["content"])

        if not questions:
            return []

        model_answers = []
        for i, q in enumerate(questions):
            try:
                prompt = f"""你是{state.get('position', '目标岗位')}的面试专家。请针对以下面试问题，给出一个专业的参考答案。

## 岗位信息
公司: {state.get('company', '未知')}
职位: {state.get('position', '未知')}
JD: {state.get('jd_text', '')[:500]}

## 面试问题
{q}

## 要求
1. 回答专业、有深度，展示对技术的深入理解
2. 如果是技术问题，给出具体的知识点、最佳实践或示例
3. 如果是行为问题，使用STAR法则组织回答
4. 如果是开放性问题，展示系统性的思考框架
5. 控制在200字以内

请直接给出参考答案，不要加前缀。"""
                answer = await llm_client.chat(
                    system_prompt=f"你是{state.get('position', '')}领域的资深专家，提供专业、有深度的面试参考答案。",
                    user_message=prompt,
                    model=settings.LLM_MODEL_POWERFUL,
                    temperature=0.5,
                    max_tokens=400,
                )
                model_answers.append({
                    "question_number": i + 1,
                    "question": q,
                    "model_answer": answer.strip(),
                })
            except Exception:
                model_answers.append({
                    "question_number": i + 1,
                    "question": q,
                    "model_answer": "（生成参考答案失败）",
                })

        return model_answers

    async def _get_next_question(self, session_id: str) -> str:
        """内部: 获取下一个问题"""
        try:
            return await self.generate_question(session_id)
        except Exception:
            return {"question": "请继续，下一个问题..."}


# 全局单例
interview_agent = InterviewAgent()
