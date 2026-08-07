"""测试 RAG 引擎 (使用 Mock 模拟 LLM)"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.rag_engine import RAGEngine, _jd_cache


class TestRAGEngineJDParse:
    """JD 解析测试"""

    @pytest.fixture
    def engine(self):
        return RAGEngine()

    @pytest.fixture
    def sample_jd(self):
        return """高级Python后端工程师

岗位职责:
1. 负责公司核心业务系统的架构设计和开发
2. 优化系统性能，提升API响应速度
3. 参与技术方案评审和代码review

任职要求:
1. 5年以上Python开发经验
2. 熟悉Django/FastAPI等主流框架
3. 熟悉MySQL、Redis、Kafka等中间件
4. 有大规模分布式系统经验者优先
"""

    @pytest.fixture
    def mock_jd_result(self):
        return {
            "position_title": "高级Python后端工程师",
            "company": "",
            "core_requirements": [
                {"name": "Python开发经验", "category": "experience", "importance": "required", "description": "5年以上Python开发经验"},
                {"name": "分布式系统经验", "category": "experience", "importance": "preferred", "description": "大规模分布式系统经验"},
            ],
            "technical_skills": [
                {"name": "Python", "level": "expert", "is_required": True},
                {"name": "Django", "level": "advanced", "is_required": True},
                {"name": "FastAPI", "level": "advanced", "is_required": True},
                {"name": "MySQL", "level": "intermediate", "is_required": True},
                {"name": "Redis", "level": "intermediate", "is_required": True},
                {"name": "Kafka", "level": "intermediate", "is_required": True},
            ],
            "soft_skills": ["团队协作", "代码审查"],
            "responsibilities": ["系统架构设计", "性能优化"],
            "qualifications": ["5年以上Python经验"],
            "keywords": ["Python", "后端", "分布式", "FastAPI", "Redis"],
            "company_culture_hints": "",
        }

    @pytest.mark.asyncio
    async def test_parse_jd_with_mock(self, engine, sample_jd, mock_jd_result):
        """测试 JD 解析 (Mock LLM)"""
        with patch.object(engine, 'simple_model', 'deepseek-chat'):
            with patch('app.core.rag_engine.llm_client.chat_json', new_callable=AsyncMock) as mock_chat:
                mock_chat.return_value = mock_jd_result

                result = await engine.parse_jd(sample_jd)

                assert result["position_title"] == "高级Python后端工程师"
                assert len(result["technical_skills"]) == 6
                mock_chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_jd_caching(self, engine, sample_jd, mock_jd_result):
        """测试 JD 解析缓存"""
        _jd_cache.clear()

        with patch('app.core.rag_engine.llm_client.chat_json', new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_jd_result

            # 第一次调用: 调用 LLM
            result1 = await engine.parse_jd(sample_jd)
            # 第二次调用: 从缓存获取
            result2 = await engine.parse_jd(sample_jd)

            assert result1 == result2
            # LLM 只被调用一次
            assert mock_chat.call_count == 1

        _jd_cache.clear()

    @pytest.mark.asyncio
    async def test_parse_jd_empty_text(self, engine):
        """空 JD 文本"""
        with patch('app.core.rag_engine.llm_client.chat_json', new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = {"position_title": "", "core_requirements": []}

            result = await engine.parse_jd("")
            assert isinstance(result, dict)


class TestQueryGeneration:
    """检索查询生成测试"""

    @pytest.fixture
    def engine(self):
        return RAGEngine()

    @pytest.mark.asyncio
    async def test_generate_queries_from_skills(self, engine):
        jd = {
            "technical_skills": [
                {"name": "Python"},
                {"name": "Django"},
                {"name": "Redis"},
                {"name": "Kafka"},
                {"name": "Docker"},
            ],
            "core_requirements": [],
            "keywords": [],
        }
        queries = await engine.generate_queries(jd)
        assert len(queries) > 0
        # 应该包含前5个技能名
        assert "Python" in queries[0]

    @pytest.mark.asyncio
    async def test_generate_queries_from_core_reqs(self, engine):
        jd = {
            "technical_skills": [],
            "core_requirements": [
                {"name": "系统架构设计"},
                {"name": "性能优化"},
            ],
            "keywords": [],
        }
        queries = await engine.generate_queries(jd)
        assert len(queries) > 0

    @pytest.mark.asyncio
    async def test_generate_queries_from_keywords_fallback(self, engine):
        jd = {
            "technical_skills": [],
            "core_requirements": [],
            "keywords": ["Python", "后端", "分布式"],
        }
        queries = await engine.generate_queries(jd)
        assert len(queries) > 0

    @pytest.mark.asyncio
    async def test_generate_queries_empty(self, engine):
        """所有字段为空时，回退到 position_title"""
        jd = {
            "technical_skills": [],
            "core_requirements": [],
            "keywords": [],
            "position_title": "软件工程师",
        }
        queries = await engine.generate_queries(jd)
        assert len(queries) >= 1

    @pytest.mark.asyncio
    async def test_generate_queries_empty_skills_list(self, engine):
        """技能列表为空时不应报错"""
        jd = {
            "technical_skills": [{"name": ""}],
            "core_requirements": [],
            "keywords": [],
        }
        queries = await engine.generate_queries(jd)
        assert isinstance(queries, list)


class TestFormatChunks:
    """Chunks 格式化测试"""

    def test_format_chunks(self):
        engine = RAGEngine()
        chunks = [
            {"id": "1", "content": "内容1", "metadata": {"section_type": "work"}, "score": 0.9},
            {"id": "2", "content": "内容2", "metadata": {"section_type": "skill"}, "score": 0.8},
        ]
        result = engine._format_chunks(chunks)
        assert "[片段1]" in result
        assert "类型:work" in result
        assert "内容1" in result
        assert "[片段2]" in result
        assert "类型:skill" in result

    def test_format_chunks_empty(self):
        engine = RAGEngine()
        result = engine._format_chunks([])
        assert result == ""


class TestStructureResume:
    """简历结构化解析测试"""

    @pytest.fixture
    def engine(self):
        return RAGEngine()

    @pytest.mark.asyncio
    async def test_structure_resume(self, engine):
        with patch('app.core.rag_engine.llm_client.chat_json', new_callable=AsyncMock) as mock:
            mock.return_value = {
                "basic_info": {"name": "张三", "email": "test@test.com"},
                "work_experience": [],
                "education": [],
                "skills": {},
            }
            result = await engine.structure_resume("姓名: 张三")
            assert result["basic_info"]["name"] == "张三"

    @pytest.mark.asyncio
    async def test_restructure_resume(self, engine):
        with patch('app.core.rag_engine.llm_client.chat', new_callable=AsyncMock) as mock:
            mock.return_value = "# 张三\n\n## 个人总结\n\n测试简历内容\n\n<analysis>\n匹配度分析内容\n</analysis>"

            result = await engine.restructure_resume(
                resume_id="test",
                jd_text="Python工程师",
                jd_requirements={"position_title": "Python工程师"},
                retrieved_chunks=[
                    {"id": "1", "content": "Python开发", "metadata": {"section_type": "work"}, "score": 0.9}
                ],
            )
            assert "张三" in result
            assert "测试简历内容" in result

    @pytest.mark.asyncio
    async def test_fact_check(self, engine):
        with patch('app.core.rag_engine.llm_client.chat_json', new_callable=AsyncMock) as mock:
            mock.return_value = {"is_factual": True, "score": 100, "issues": []}
            result = await engine.fact_check("原始内容", "生成内容")
            assert result["is_factual"] is True
            assert result["score"] == 100

    @pytest.mark.asyncio
    async def test_fact_check_error_fallback(self, engine):
        """事实核查出错时返回默认值"""
        with patch('app.core.rag_engine.llm_client.chat_json', new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("API error")
            result = await engine.fact_check("原始内容", "生成内容")
            assert result["is_factual"] is True  # 默认值
            assert result["issues"] == []

    @pytest.mark.asyncio
    async def test_full_pipeline(self, engine):
        """测试完整 Pipeline"""
        with patch('app.core.rag_engine.llm_client.chat_json', new_callable=AsyncMock) as mock_json:
            with patch('app.core.rag_engine.llm_client.chat', new_callable=AsyncMock) as mock_chat:
                mock_json.return_value = {
                    "position_title": "工程师",
                    "company": "",
                    "core_requirements": [],
                    "technical_skills": [],
                    "soft_skills": [],
                    "responsibilities": [],
                    "qualifications": [],
                    "keywords": ["测试"],
                    "company_culture_hints": "",
                }
                mock_chat.return_value = "# 生成的简历\n\n<analysis>\n分析内容\n</analysis>"

                with patch.object(engine, 'retrieve_chunks', new_callable=AsyncMock) as mock_retrieve:
                    mock_retrieve.return_value = [
                        {"id": "1", "content": "测试内容", "metadata": {"section_type": "work"}, "score": 0.9}
                    ]

                    result = await engine.full_pipeline(
                        resume_id="test",
                        raw_resume_text="测试简历",
                        jd_text="测试JD",
                    )

                    assert "jd_requirements" in result
                    assert "retrieved_chunks" in result
                    assert "generated_resume" in result
                    assert "analysis" in result
                    assert "fact_check" in result


class TestRestructureResumeStream:
    """流式重组简历测试"""

    @pytest.fixture
    def engine(self):
        return RAGEngine()

    @pytest.mark.asyncio
    async def test_stream_basic(self, engine):
        """测试流式输出的完整流程"""

        async def mock_stream(*args, **kwargs):
            yield "生"
            yield "成"
            yield "内容"

        with patch.object(engine, 'simple_model', 'deepseek-chat'), \
             patch.object(engine, 'powerful_model', 'deepseek-chat'), \
             patch('app.core.rag_engine.llm_client.chat_stream', side_effect=mock_stream):

            events = []
            async for event in engine.restructure_resume_stream(
                resume_id="test",
                jd_text="JD内容",
                jd_requirements={"position_title": "工程师"},
                retrieved_chunks=[
                    {"id": "1", "content": "测试内容", "metadata": {"section_type": "work"}}
                ],
            ):
                events.append(event)

            # 应该有 progress → content → complete → fact_check_result
            event_types = [e["type"] for e in events]
            assert "progress" in event_types
            assert "content" in event_types
            assert "complete" in event_types

            # 检查 complete 事件
            complete_events = [e for e in events if e["type"] == "complete"]
            assert len(complete_events) >= 1
            assert "resume_markdown" in complete_events[0]

    @pytest.mark.asyncio
    async def test_stream_with_analysis_tag(self, engine):
        """测试包含 analysis 标签的流式输出"""

        async def mock_stream(*args, **kwargs):
            yield "# 简历\n\n正文\n<analysis>\n分析\n</analysis>"
            # empty yield to finish

        with patch('app.core.rag_engine.llm_client.chat_stream', side_effect=mock_stream):

            events = []
            async for event in engine.restructure_resume_stream(
                resume_id="test",
                jd_text="JD",
                jd_requirements={"position_title": "工程师"},
                retrieved_chunks=[
                    {"id": "1", "content": "测试", "metadata": {"section_type": "work"}}
                ],
            ):
                events.append(event)

            complete_events = [e for e in events if e["type"] == "complete"]
            assert len(complete_events) >= 1
            # analysis 应该被分离
            resume = complete_events[0].get("resume_markdown", "")
            assert "<analysis>" not in resume

    @pytest.mark.asyncio
    async def test_stream_error_handling(self, engine):
        """测试流式输出异常处理"""

        async def raise_error(*args, **kwargs):
            raise Exception("API connection failed")
            yield  # 永远不会执行，但使函数成为 async generator

        with patch('app.core.rag_engine.llm_client.chat_stream', side_effect=raise_error):

            events = []
            async for event in engine.restructure_resume_stream(
                resume_id="test",
                jd_text="JD",
                jd_requirements={"position_title": "工程师"},
                retrieved_chunks=[{"id": "1", "content": "测试", "metadata": {"section_type": "work"}}],
            ):
                events.append(event)

            error_events = [e for e in events if e["type"] == "error"]
            assert len(error_events) >= 1
            assert "API connection failed" in error_events[0]["message"]

    @pytest.mark.asyncio
    async def test_stream_auto_retrieve(self, engine):
        """当未提供 chunks 时，自动检索"""

        async def mock_stream(*args, **kwargs):
            yield "生成内容"

        with patch('app.core.rag_engine.llm_client.chat_stream', side_effect=mock_stream), \
             patch.object(engine, 'retrieve_chunks', new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.return_value = [{"id": "1", "content": "测试", "metadata": {}, "score": 0.9}]

            events = []
            async for event in engine.restructure_resume_stream(
                resume_id="test",
                jd_text="JD",
                jd_requirements={"position_title": "工程师"},
                retrieved_chunks=[],  # 空列表
            ):
                events.append(event)

            # 由于传入了空列表，应该调用 retrieve_chunks
            mock_retrieve.assert_called_once()
