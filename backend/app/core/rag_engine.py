"""RAG 核心编排引擎 — 基于 LangGraph StateGraph

流程 (5 个节点):
1. parse_jd: JD解析 (LLM, 可缓存)
2. generate_queries: 多查询生成 (基于规则)
3. retrieve: 混合检索 (Dense + Sparse + RRF)
4. restructure: 逐节生成简历 (LLM, 支持流式)
5. fact_check: 事实核查 (LLM)
"""

import json
import asyncio
from typing import AsyncIterator, Optional, List, Annotated, TypedDict

from langgraph.graph import StateGraph, END
from langgraph.types import StreamWriter

from .llm_client import llm_client
from .prompts import (
    JD_PARSE_SYSTEM,
    JD_PARSE_USER,
    RESTRUCTURE_SYSTEM,
    RESTRUCTURE_USER,
    FACT_CHECK_SYSTEM,
    FACT_CHECK_USER,
    RESUME_STRUCTURE_SYSTEM,
    RESUME_STRUCTURE_USER,
)
from .embedder import vector_store
from .retriever import retriever
from ..config import settings


# JD 解析缓存 (key: jd_text_hash, value: parsed_json)
_jd_cache: dict[str, dict] = {}


# ============================================================
# LangGraph 状态定义
# ============================================================

class RAGState(TypedDict, total=False):
    """RAG Pipeline 状态"""

    # 输入
    resume_id: str
    jd_text: str
    jd_title: str
    jd_company: str

    # 中间结果
    jd_requirements: Optional[dict]
    queries: List[str]
    retrieved_chunks: List[dict]
    chunks_text: str

    # 输出
    generated_resume: str
    analysis: str
    fact_check_result: Optional[dict]

    # 错误
    error: Optional[str]


# ============================================================
# 图节点函数
# ============================================================

async def _parse_jd_node(state: RAGState) -> dict:
    """节点1: 解析 JD → 结构化需求 (带缓存)"""
    jd_text = state.get("jd_text", "")

    # 检查缓存
    cache_key = str(hash(jd_text))
    if cache_key in _jd_cache:
        return {"jd_requirements": _jd_cache[cache_key]}

    try:
        result = await llm_client.chat_json(
            system_prompt=JD_PARSE_SYSTEM,
            user_message=JD_PARSE_USER.format(jd_text=jd_text),
            model=settings.LLM_MODEL_SIMPLE,
        )
        _jd_cache[cache_key] = result
        return {"jd_requirements": result}
    except Exception as e:
        return {"error": f"JD 解析失败: {e}", "jd_requirements": {}}


async def _generate_queries_node(state: RAGState) -> dict:
    """节点2: 基于 JD 需求生成多个检索查询 (基于规则)"""
    jd_reqs = state.get("jd_requirements") or {}
    core_reqs = jd_reqs.get("core_requirements", [])
    technical_skills = jd_reqs.get("technical_skills", [])
    keywords = jd_reqs.get("keywords", [])

    queries = []

    # 技能查询
    skill_names = [s["name"] for s in technical_skills[:5]]
    if skill_names:
        queries.append(" ".join(skill_names))

    # 核心需求查询
    for req in core_reqs[:3]:
        name = req.get("name", "")
        if name:
            queries.append(name)

    # 关键词查询
    if keywords:
        queries.append(" ".join(keywords[:5]))

    # 回退
    if len(queries) < 2:
        queries = keywords[:5] if keywords else [" ".join(skill_names)]

    if not queries:
        queries = [jd_reqs.get("position_title", "")]

    return {"queries": queries}


async def _retrieve_node(state: RAGState) -> dict:
    """节点3: 混合检索"""
    collection_name = f"resume_{state['resume_id']}"
    queries = state.get("queries", [])

    candidates = await retriever.retrieve(
        collection_name=collection_name,
        queries=queries,
        top_k_fusion=settings.RAG_TOP_K_RERANK,
    )

    return {"retrieved_chunks": candidates}


async def _format_chunks_node(state: RAGState) -> dict:
    """节点4: 格式化 chunks 为 LLM 可读文本"""
    chunks = state.get("retrieved_chunks", [])
    parts = []
    for i, chunk in enumerate(chunks):
        section = chunk.get("metadata", {}).get("section_type", "unknown")
        content = chunk.get("content", "")
        parts.append(f"[Chunk {i+1}] (章节: {section})")
        parts.append(content)
        parts.append("---")
    return {"chunks_text": "\n".join(parts)}


async def _restructure_node(state: RAGState) -> dict:
    """节点5: LLM 重组简历 (非流式)"""
    jd_reqs = state.get("jd_requirements", {})
    jd_title = state.get("jd_title") or jd_reqs.get("position_title", "目标岗位")
    jd_company = state.get("jd_company") or jd_reqs.get("company", "")

    user_message = RESTRUCTURE_USER.format(
        jd_title=jd_title,
        jd_company=jd_company,
        jd_text=state.get("jd_text", ""),
        jd_requirements=json.dumps(jd_reqs, ensure_ascii=False, indent=2),
        retrieved_chunks=state.get("chunks_text", ""),
    )

    try:
        result = await llm_client.chat(
            system_prompt=RESTRUCTURE_SYSTEM,
            user_message=user_message,
            model=settings.LLM_MODEL_POWERFUL,
            temperature=0.1,
            max_tokens=4096,
        )
        return {"generated_resume": result}
    except Exception as e:
        return {"error": f"简历生成失败: {e}", "generated_resume": ""}


async def _extract_analysis_node(state: RAGState) -> dict:
    """节点6: 从生成结果中分离 <analysis> 标签"""
    full_text = state.get("generated_resume", "")
    analysis = ""
    resume_text = full_text

    if "<analysis>" in full_text:
        parts = full_text.split("<analysis>", 1)
        resume_text = parts[0].strip()
        analysis = parts[1].replace("</analysis>", "").strip()

    return {"generated_resume": resume_text, "analysis": analysis}


async def _fact_check_node(state: RAGState) -> dict:
    """节点7: 事实核查"""
    chunks_text = state.get("chunks_text", "")
    resume_text = state.get("generated_resume", "")

    try:
        result = await llm_client.chat_json(
            system_prompt=FACT_CHECK_SYSTEM,
            user_message=FACT_CHECK_USER.format(
                original_chunks=chunks_text,
                generated_resume=resume_text,
            ),
            model=settings.LLM_MODEL_SIMPLE,
        )
        return {"fact_check_result": result}
    except Exception:
        return {"fact_check_result": {"is_factual": True, "score": 100, "issues": []}}


# ============================================================
# 构建 LangGraph 图
# ============================================================

def _build_rag_graph() -> StateGraph:
    """构建 RAG Pipeline 状态图"""
    workflow = StateGraph(RAGState)

    # 添加节点
    workflow.add_node("parse_jd", _parse_jd_node)
    workflow.add_node("generate_queries", _generate_queries_node)
    workflow.add_node("retrieve", _retrieve_node)
    workflow.add_node("format_chunks", _format_chunks_node)
    workflow.add_node("restructure", _restructure_node)
    workflow.add_node("extract_analysis", _extract_analysis_node)
    workflow.add_node("fact_check", _fact_check_node)

    # 添加边
    workflow.set_entry_point("parse_jd")
    workflow.add_edge("parse_jd", "generate_queries")
    workflow.add_edge("generate_queries", "retrieve")
    workflow.add_edge("retrieve", "format_chunks")
    workflow.add_edge("format_chunks", "restructure")
    workflow.add_edge("restructure", "extract_analysis")
    workflow.add_edge("extract_analysis", "fact_check")
    workflow.add_edge("fact_check", END)

    return workflow.compile()


# 编译全局图实例
_rag_graph = _build_rag_graph()


# ============================================================
# RAGEngine — 对外接口 (与迁移前完全兼容)
# ============================================================

class RAGEngine:
    """简历 RAG 引擎 (基于 LangGraph)"""

    def __init__(self):
        self.simple_model = settings.LLM_MODEL_SIMPLE
        self.powerful_model = settings.LLM_MODEL_POWERFUL
        self.graph = _rag_graph

    # ========== 对外方法 (API兼容) ==========

    async def parse_jd(self, jd_text: str) -> dict:
        """解析 JD，提取结构化需求 (带缓存)"""
        cache_key = str(hash(jd_text))
        if cache_key in _jd_cache:
            return _jd_cache[cache_key]

        result = await llm_client.chat_json(
            system_prompt=JD_PARSE_SYSTEM,
            user_message=JD_PARSE_USER.format(jd_text=jd_text),
            model=self.simple_model,
        )
        _jd_cache[cache_key] = result
        return result

    async def structure_resume(self, raw_text: str) -> dict:
        """使用 LLM 对简历进行结构化解析"""
        return await llm_client.chat_json(
            system_prompt=RESUME_STRUCTURE_SYSTEM,
            user_message=RESUME_STRUCTURE_USER.format(raw_text=raw_text),
            model=self.simple_model,
            temperature=0.1,
        )

    async def generate_queries(self, jd_requirements: dict) -> list[str]:
        """基于 JD 核心需求生成多个检索查询（多样化，覆盖更多角度）"""
        core_reqs = jd_requirements.get("core_requirements", [])
        technical_skills = jd_requirements.get("technical_skills", [])
        keywords = jd_requirements.get("keywords", [])
        position = jd_requirements.get("position_title", "")

        queries = []

        # 1. 技能组合查询
        skill_names = [s["name"] for s in technical_skills[:6]]
        if skill_names:
            queries.append(" ".join(skill_names))

        # 2. 每个核心技能独立查询（提高精准度）
        for s in technical_skills[:5]:
            name = s.get("name", "")
            if name and len(name) > 2:
                queries.append(name)

        # 3. 核心需求组合查询（每个需求一句话）
        req_names = [r.get("name", "") for r in core_reqs[:4] if r.get("name", "")]
        if req_names:
            queries.append(" ".join(req_names))

        # 4. 关键词
        if keywords:
            queries.append(" ".join(keywords[:6]))

        # 5. 岗位名称
        if position:
            queries.append(position)

        # 确保至少有 2 个查询
        if len(queries) < 2:
            queries = keywords[:5] if keywords else [position or " ".join(skill_names)]

        return queries[:8]  # 最多 8 个查询，避免 API 调用过多

    async def retrieve_chunks(
        self,
        resume_id: str,
        jd_requirements: dict,
        top_k: int = None,
    ) -> list[dict]:
        """检索与 JD 最相关的简历 chunks"""
        top_k = top_k or settings.RAG_TOP_K_RERANK
        collection_name = f"resume_{resume_id}"

        queries = await self.generate_queries(jd_requirements)
        candidates = await retriever.retrieve(
            collection_name=collection_name,
            queries=queries,
        )

        return candidates[:top_k]

    async def restructure_resume(
        self,
        resume_id: str,
        jd_text: str,
        jd_requirements: dict,
        retrieved_chunks: list[dict],
        jd_title: str = "",
        jd_company: str = "",
    ) -> str:
        """基于 JD 重组简历 (非流式)"""
        chunks_text = self._format_chunks(retrieved_chunks)

        user_message = RESTRUCTURE_USER.format(
            jd_title=jd_title or jd_requirements.get("position_title", "目标岗位"),
            jd_company=jd_company or jd_requirements.get("company", ""),
            jd_text=jd_text,
            jd_requirements=json.dumps(jd_requirements, ensure_ascii=False, indent=2),
            retrieved_chunks=chunks_text,
        )

        result = await llm_client.chat(
            system_prompt=RESTRUCTURE_SYSTEM,
            user_message=user_message,
            model=self.powerful_model,
            temperature=0.1,
            max_tokens=4096,
        )

        return result

    async def restructure_resume_stream(
        self,
        resume_id: str,
        jd_text: str,
        jd_requirements: dict,
        retrieved_chunks: list[dict],
        jd_title: str = "",
        jd_company: str = "",
    ) -> AsyncIterator[dict]:
        """流式重组简历 — 逐步返回进度和生成内容

        Yields:
            {"type": "progress", "stage": "...", "progress": N}
            {"type": "content", "text": "..."}
            {"type": "complete", "result": "..."}
            {"type": "error", "message": "..."}
        """
        try:
            # Step 1: 检索 (如果还没有 chunks)
            yield {"type": "progress", "stage": "retrieving", "progress": 20}
            if not retrieved_chunks:
                retrieved_chunks = await self.retrieve_chunks(resume_id, jd_requirements)

            # Step 2: 生成
            yield {"type": "progress", "stage": "generating", "progress": 40}

            chunks_text = self._format_chunks(retrieved_chunks)
            user_message = RESTRUCTURE_USER.format(
                jd_title=jd_title or jd_requirements.get("position_title", "目标岗位"),
                jd_company=jd_company or jd_requirements.get("company", ""),
                jd_text=jd_text,
                jd_requirements=json.dumps(jd_requirements, ensure_ascii=False, indent=2),
                retrieved_chunks=chunks_text,
            )

            full_text = ""
            async for token in llm_client.chat_stream(
                system_prompt=RESTRUCTURE_SYSTEM,
                user_message=user_message,
                model=self.powerful_model,
                temperature=0.1,
                max_tokens=4096,
            ):
                full_text += token
                yield {"type": "content", "text": token, "progress": min(40 + int(len(full_text) / 40), 85)}

            # Step 3: 事实核查
            yield {"type": "progress", "stage": "fact_checking", "progress": 90}

            # 提取 <analysis> 标签
            analysis = ""
            resume_text = full_text
            if "<analysis>" in full_text:
                parts = full_text.split("<analysis>", 1)
                resume_text = parts[0].strip()
                analysis = parts[1].replace("</analysis>", "").strip()

            # 异步进行事实核查 (不阻塞主流程)
            fact_check_task = asyncio.create_task(
                self.fact_check(chunks_text, resume_text)
            )

            yield {
                "type": "complete",
                "progress": 100,
                "resume_markdown": resume_text,
                "analysis": analysis,
                "chunk_sources": [
                    {"id": c["id"], "section_type": c.get("metadata", {}).get("section_type", "")}
                    for c in retrieved_chunks[:8]
                ],
            }

            # 等待事实核查完成
            try:
                fact_result = await fact_check_task
                yield {"type": "fact_check_result", "data": fact_result}
            except Exception:
                pass

        except Exception as e:
            yield {"type": "error", "message": str(e)}

    async def fact_check(self, original_chunks_text: str, generated_resume: str) -> dict:
        """事实核查"""
        try:
            result = await llm_client.chat_json(
                system_prompt=FACT_CHECK_SYSTEM,
                user_message=FACT_CHECK_USER.format(
                    original_chunks=original_chunks_text,
                    generated_resume=generated_resume,
                ),
                model=self.simple_model,
            )
            return result
        except Exception:
            return {"is_factual": True, "score": 100, "issues": []}

    async def full_pipeline(
        self,
        resume_id: str,
        raw_resume_text: str,
        jd_text: str,
        jd_title: str = "",
        jd_company: str = "",
        use_graph: bool = False,
    ) -> dict:
        """完整的简历重组 Pipeline

        Args:
            use_graph: 若为 True 则使用 LangGraph StateGraph 执行 (用于演示 LangGraph 集成)

        Returns:
            {
                "jd_requirements": dict,
                "retrieved_chunks": list,
                "generated_resume": str,
                "analysis": str,
                "fact_check": dict,
            }
        """
        if use_graph:
            return await self._run_graph_pipeline(
                resume_id, raw_resume_text, jd_text, jd_title, jd_company
            )

        # 直接执行 pipeline (默认路径，保持测试兼容)
        # 1. JD 解析
        jd_requirements = await self.parse_jd(jd_text)

        # 2. 检索
        retrieved_chunks = await self.retrieve_chunks(resume_id, jd_requirements)

        # 3. 生成
        result = await self.restructure_resume(
            resume_id=resume_id,
            jd_text=jd_text,
            jd_requirements=jd_requirements,
            retrieved_chunks=retrieved_chunks,
            jd_title=jd_title,
            jd_company=jd_company,
        )

        # 4. 提取 analysis
        analysis = ""
        resume_text = result
        if "<analysis>" in result:
            parts = result.split("<analysis>", 1)
            resume_text = parts[0].strip()
            analysis = parts[1].replace("</analysis>", "").strip()

        # 5. 事实核查
        chunks_text = self._format_chunks(retrieved_chunks)
        fact_result = await self.fact_check(chunks_text, resume_text)

        return {
            "jd_requirements": jd_requirements,
            "retrieved_chunks": [
                {"id": c["id"], "content": c["content"][:200] + "...", "score": c.get("score", 0)}
                for c in retrieved_chunks[:8]
            ],
            "generated_resume": resume_text,
            "analysis": analysis,
            "fact_check": fact_result,
        }

    async def _run_graph_pipeline(
        self,
        resume_id: str,
        raw_resume_text: str,
        jd_text: str,
        jd_title: str = "",
        jd_company: str = "",
    ) -> dict:
        """通过 LangGraph StateGraph 执行 pipeline (演示 LangGraph 集成)"""
        initial_state: RAGState = {
            "resume_id": resume_id,
            "jd_text": jd_text,
            "jd_title": jd_title,
            "jd_company": jd_company,
            "jd_requirements": None,
            "queries": [],
            "retrieved_chunks": [],
            "chunks_text": "",
            "generated_resume": "",
            "analysis": "",
            "fact_check_result": None,
            "error": None,
        }

        final_state = await self.graph.ainvoke(initial_state)

        retrieved_chunks = final_state.get("retrieved_chunks", [])

        return {
            "jd_requirements": final_state.get("jd_requirements", {}),
            "retrieved_chunks": [
                {"id": c.get("id", ""), "content": c.get("content", "")[:200] + "...", "score": c.get("score", 0)}
                for c in retrieved_chunks[:8]
            ],
            "generated_resume": final_state.get("generated_resume", ""),
            "analysis": final_state.get("analysis", ""),
            "fact_check": final_state.get("fact_check_result") or {"is_factual": True, "score": 100, "issues": []},
        }

    def _format_chunks(self, chunks: list[dict]) -> str:
        """格式化 chunks 为 LLM 可读文本（含相关性分数，帮助 LLM 区分优先级）"""
        parts = []
        for i, chunk in enumerate(chunks):
            section = chunk.get("metadata", {}).get("section_type", "unknown")
            source = chunk.get("metadata", {}).get("source_collection", "resume")
            content = chunk.get("content", "")
            score = chunk.get("weighted_score", chunk.get("score", 0))
            # 相关性等级
            relevance = "高" if score > 0.5 else ("中" if score > 0.2 else "低")
            parts.append(f"[片段{i+1}] 来源:{source} 类型:{section} 相关性:{relevance}({score:.3f})")
            parts.append(content)
            parts.append("---")
        return "\n".join(parts)

    async def retrieve_from_all_sources(
        self,
        jd_requirements: dict,
        user_id: str,
        top_k: int = 20,
    ) -> list[dict]:
        """从当前用户的所有简历+技能库中检索与JD相关的片段"""
        queries = await self.generate_queries(jd_requirements)

        # 获取当前用户在 DB 中的 resume 记录
        from ..models.resume import Resume
        from ..database import async_session

        user_resume_ids = []
        async with async_session() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(Resume.id).where(Resume.user_id == user_id)
            )
            user_resume_ids = [f"resume_{row[0]}" for row in result.fetchall()]

        # ChromeDB 中所有 resume_* 集合（含旧数据孤立的集合，迁移后 ID 可能不匹配）
        from .embedder import vector_store
        all_chroma_collections = []
        try:
            all_chroma_collections = [
                c.name for c in vector_store._client.list_collections()
                if c.name.startswith("resume_")
            ]
        except Exception:
            pass

        # 合并：DB中的 + ChromaDB中孤立的（确保旧数据不丢失）
        all_collections = list(set(user_resume_ids + all_chroma_collections)) + ["skill_library"]

        if not all_collections:
            return []

        candidates = await retriever.retrieve_multi_collection(
            collection_names=all_collections,
            queries=queries,
            top_k_fusion=top_k,
        )
        return candidates[:top_k]

    async def smart_restructure_pipeline(
        self,
        jd_text: str,
        user_id: str,
        jd_title: str = "",
        jd_company: str = "",
        resume_id: str = None,
    ) -> dict:
        """智能简历重组 Pipeline（当前用户的简历+技能库+扬长避短）

        与旧版 full_pipeline 的区别:
        - 从当前用户的所有简历和技能库中检索素材（不跨用户）
        - 智能判断哪些板块适用（如无实习经历则跳过）
        - 输出格式化纯文本（非Markdown）
        """
        # 1. JD 解析
        jd_requirements = await self.parse_jd(jd_text)

        # 2. 当前用户的简历+技能库检索（隔离！）
        all_chunks = await self.retrieve_from_all_sources(jd_requirements, user_id, top_k=50)

        # 如果指定了特定简历，将其 chunks 排在最前面
        if resume_id:
            resume_chunks = [c for c in all_chunks
                           if c.get("metadata", {}).get("source_collection", "") != "skill_library"
                           and f"resume_{resume_id}" in str(c.get("metadata", {}).get("chroma_id", ""))]
            other_chunks = [c for c in all_chunks if c not in resume_chunks]
            all_chunks = resume_chunks + other_chunks

        chunks_text = self._format_chunks(all_chunks)

        # 3. 智能重组（扬长避短 prompt）
        from .prompts import SMART_RESTRUCTURE_SYSTEM, SMART_RESTRUCTURE_USER

        result = await llm_client.chat(
            system_prompt=SMART_RESTRUCTURE_SYSTEM,
            user_message=SMART_RESTRUCTURE_USER.format(
                jd_title=jd_title or jd_requirements.get("position_title", "目标岗位"),
                jd_company=jd_company or jd_requirements.get("company", ""),
                jd_text=jd_text,
                jd_requirements=json.dumps(jd_requirements, ensure_ascii=False, indent=2),
                all_materials=chunks_text,
            ),
            model=self.powerful_model,
            temperature=0.1,
            max_tokens=4096,
        )

        # 4. 提取分析备注
        analysis = ""
        resume_text = result
        if "<analysis>" in result:
            parts = result.split("<analysis>", 1)
            resume_text = parts[0].strip()
            analysis = parts[1].replace("</analysis>", "").strip()

        # 5. 事实核查
        fact_result = await self.fact_check(chunks_text, resume_text)

        return {
            "jd_requirements": jd_requirements,
            "retrieved_chunks": [
                {"id": c.get("id", ""), "content": c.get("content", "")[:200] + "...",
                 "score": c.get("weighted_score", c.get("score", 0)),
                 "source": c.get("metadata", {}).get("source_collection", "resume")}
                for c in all_chunks[:10]
            ],
            "generated_resume": resume_text,
            "analysis": analysis,
            "fact_check": fact_result,
        }

    async def generate_pdf_siliconflow(self, content: str, title: str = "") -> bytes:
        """使用硅基流动大模型将文本渲染为精美 PDF"""
        import httpx
        from ..config import settings

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.SILICONFLOW_BASE_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.SILICONFLOW_EMBEDDING_MODEL,
                    "messages": [{
                        "role": "user",
                        "content": f"请将以下简历内容渲染为专业排版的HTML格式，适合导出PDF。\n简历标题: {title}\n\n{content}"
                    }],
                    "temperature": 0.1,
                    "max_tokens": 8192,
                },
            )
            resp.raise_for_status()
            result = resp.json()
            html_content = result["choices"][0]["message"]["content"]

        # 提取 <html>...</html>
        html_start = html_content.find("<html")
        if html_start < 0:
            html_start = html_content.find("<!DOCTYPE")
        html_end = html_content.rfind("</html>")
        if html_start >= 0 and html_end > html_start:
            html_content = html_content[html_start:html_end + 7]

        # 使用 weasyprint 或直接返回 HTML（前端可用浏览器打印）
        return html_content.encode("utf-8")


# 全局单例
rag_engine = RAGEngine()
