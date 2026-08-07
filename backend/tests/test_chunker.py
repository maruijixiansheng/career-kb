"""测试简历智能分块器 (ResumeChunker)"""

import pytest
from app.core.chunker import (
    ResumeChunker,
    detect_sections,
    Chunk,
    _match_section_title,
    SECTION_PATTERNS,
)


class TestChunk:
    """Chunk 数据结构测试"""

    def test_chunk_creation_defaults(self):
        chunk = Chunk()
        assert chunk.id  # 自动生成 UUID
        assert chunk.section_type == ""
        assert chunk.content == ""
        assert chunk.chunk_index == 0

    def test_chunk_creation_with_data(self):
        chunk = Chunk(
            id="test-001",
            section_type="work",
            section_title="工作经历",
            chunk_index=3,
            content="在字节跳动负责推荐系统开发",
            metadata={"company": "字节跳动"},
            token_count=15,
        )
        assert chunk.id == "test-001"
        assert chunk.section_type == "work"
        assert chunk.token_count == 15

    def test_to_dict(self):
        chunk = Chunk(
            id="test-001",
            section_type="work",
            content="内容",
            metadata={"company": "字节跳动"},
        )
        d = chunk.to_dict()
        assert d["id"] == "test-001"
        assert d["section_type"] == "work"
        assert d["content"] == "内容"
        assert d["metadata"]["company"] == "字节跳动"
        # parent_chunk_id 不在 to_dict 中
        assert "parent_chunk_id" not in d


class TestMatchSectionTitle:
    """章节标题匹配测试"""

    def test_match_work_experience(self):
        assert _match_section_title("工作经历") == "work"
        assert _match_section_title("工作经验") == "work"
        assert _match_section_title("实习经历") == "work"

    def test_match_education(self):
        assert _match_section_title("教育背景") == "education"
        assert _match_section_title("教育经历") == "education"
        assert _match_section_title("学历") == "education"

    def test_match_skills(self):
        assert _match_section_title("专业技能") == "skill"
        assert _match_section_title("技术栈") == "skill"

    def test_match_project(self):
        assert _match_section_title("项目经历") == "project"
        assert _match_section_title("项目经验") == "project"
        assert _match_section_title("主要项目") == "project"

    def test_match_basic_info(self):
        assert _match_section_title("基本信息") == "basic_info"
        assert _match_section_title("个人信息") == "basic_info"
        assert _match_section_title("求职意向") == "basic_info"

    def test_match_self_evaluation(self):
        assert _match_section_title("自我评价") == "self_evaluation"
        assert _match_section_title("个人总结") == "self_evaluation"

    def test_match_certificate(self):
        assert _match_section_title("证书") == "certificate"
        assert _match_section_title("资格证书") == "certificate"
        assert _match_section_title("获奖") == "certificate"

    def test_match_language(self):
        assert _match_section_title("语言能力") == "language"

    def test_no_match_for_normal_text(self):
        assert _match_section_title("负责推荐系统开发") is None
        assert _match_section_title("提升了30%的用户留存率") is None

    def test_long_text_not_treated_as_section(self):
        """超过15个字符的文本不当作章节标题"""
        assert _match_section_title("这是一段很长很长的工作经历描述文本") is None


class TestDetectSections:
    """章节边界检测测试"""

    def test_detect_basic_sections(self):
        text = """基本信息
姓名: 张三, 电话: 13800138000

工作经历
字节跳动 | 高级工程师 | 2020-01 - 至今
负责推荐系统开发

教育背景
清华大学 | 硕士 | 计算机科学"""
        sections = detect_sections(text)
        assert len(sections) >= 2
        section_types = [s.type for s in sections]
        assert "basic_info" in section_types
        assert "work" in section_types
        assert "education" in section_types

    def test_detect_sections_empty_text(self):
        sections = detect_sections("")
        assert len(sections) == 0

    def test_detect_sections_no_headers(self):
        text = "这是一段没有任何章节标题的纯文本内容。"
        sections = detect_sections(text)
        # 没有匹配的章节标题, 整段作为内容但不创建 section
        assert len(sections) == 0


class TestResumeChunker:
    """ResumeChunker 分块逻辑测试"""

    @pytest.fixture
    def chunker(self):
        return ResumeChunker(max_chars=800, target_chars=400)

    @pytest.fixture
    def sample_structured_data(self):
        return {
            "basic_info": {
                "name": "张三",
                "email": "zhangsan@example.com",
                "phone": "13800138000",
                "city": "北京",
                "target_position": "高级后端工程师",
                "years_of_experience": 5,
            },
            "self_evaluation": "拥有5年后端开发经验，擅长Python和Golang。",
            "work_experience": [
                {
                    "company": "字节跳动",
                    "position": "高级后端工程师",
                    "start_date": "2020-01",
                    "end_date": "至今",
                    "location": "北京",
                    "responsibilities": ["负责推荐系统后端开发", "优化API性能"],
                    "achievements": ["API响应时间降低50%", "日活用户增长30%"],
                    "technologies_used": ["Python", "Go", "Redis", "Kafka"],
                },
                {
                    "company": "阿里巴巴",
                    "position": "后端工程师",
                    "start_date": "2018-07",
                    "end_date": "2019-12",
                    "location": "杭州",
                    "responsibilities": ["参与电商平台订单系统开发"],
                    "achievements": ["系统吞吐量提升40%"],
                    "technologies_used": ["Java", "Spring", "MySQL"],
                },
            ],
            "projects": [
                {
                    "name": "实时推荐引擎",
                    "role": "核心开发",
                    "start_date": "2021-03",
                    "end_date": "2021-09",
                    "description": "基于用户行为的实时推荐系统",
                    "responsibilities": ["设计推荐算法", "搭建数据管道"],
                    "achievements": ["推荐点击率提升25%"],
                    "technologies_used": ["Python", "Spark", "Redis"],
                }
            ],
            "education": [
                {
                    "school": "清华大学",
                    "degree": "硕士",
                    "major": "计算机科学",
                    "start_date": "2016-09",
                    "end_date": "2018-07",
                }
            ],
            "skills": {
                "programming_languages": ["Python", "Go", "Java"],
                "frameworks": ["Django", "Spring", "Gin"],
                "tools": ["Docker", "Kubernetes", "Redis"],
                "soft_skills": ["团队协作", "技术管理"],
            },
            "certificates": ["AWS Solution Architect"],
        }

    def test_chunk_count(self, chunker, sample_structured_data):
        chunks = chunker.chunk(sample_structured_data)
        # basic_info(1) + self_eval(1) + work(2) + project(1) + education(1) + skill(1) + certificate(1)
        assert len(chunks) >= 5

    def test_basic_info_chunk(self, chunker, sample_structured_data):
        chunks = chunker.chunk(sample_structured_data)
        basic_chunks = [c for c in chunks if c.section_type == "basic_info"]
        assert len(basic_chunks) == 1
        chunk = basic_chunks[0]
        assert "张三" in chunk.content
        assert "zhangsan@example.com" in chunk.content
        assert "高级后端工程师" in chunk.content

    def test_work_experience_chunks(self, chunker, sample_structured_data):
        chunks = chunker.chunk(sample_structured_data)
        work_chunks = [c for c in chunks if c.section_type == "work"]
        assert len(work_chunks) >= 2  # 两条工作经历
        # 验证 metadata
        companies = [c.metadata.get("company") for c in work_chunks]
        assert "字节跳动" in companies
        assert "阿里巴巴" in companies

    def test_skill_chunk(self, chunker, sample_structured_data):
        chunks = chunker.chunk(sample_structured_data)
        skill_chunks = [c for c in chunks if c.section_type == "skill"]
        assert len(skill_chunks) == 1
        content = skill_chunks[0].content
        assert "Python" in content
        assert "Docker" in content

    def test_project_chunk(self, chunker, sample_structured_data):
        chunks = chunker.chunk(sample_structured_data)
        proj_chunks = [c for c in chunks if c.section_type == "project"]
        assert len(proj_chunks) == 1
        assert "实时推荐引擎" in proj_chunks[0].content

    def test_education_chunk(self, chunker, sample_structured_data):
        chunks = chunker.chunk(sample_structured_data)
        edu_chunks = [c for c in chunks if c.section_type == "education"]
        assert len(edu_chunks) == 1
        assert "清华大学" in edu_chunks[0].content

    def test_certificate_chunk(self, chunker, sample_structured_data):
        chunks = chunker.chunk(sample_structured_data)
        cert_chunks = [c for c in chunks if c.section_type == "certificate"]
        assert len(cert_chunks) == 1
        assert "AWS" in cert_chunks[0].content

    def test_chunk_index_ordering(self, chunker, sample_structured_data):
        chunks = chunker.chunk(sample_structured_data)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_empty_data(self, chunker):
        chunks = chunker.chunk({})
        assert len(chunks) == 0

    def test_none_skills(self, chunker):
        """测试 skills 为 None 的情况"""
        data = {
            "basic_info": {"name": "张三"},
            "skills": None,
        }
        chunks = chunker.chunk(data)
        skill_chunks = [c for c in chunks if c.section_type == "skill"]
        assert len(skill_chunks) == 0

    def test_str_skills(self, chunker):
        """测试 skills 为字符串的情况"""
        data = {
            "skills": "Python, Go, Docker",
        }
        chunks = chunker.chunk(data)
        skill_chunks = [c for c in chunks if c.section_type == "skill"]
        assert len(skill_chunks) == 1

    def test_self_evaluation_as_dict(self, chunker):
        """测试 self_evaluation 为 dict 的情况"""
        data = {
            "self_evaluation": {"summary": "一个有经验的工程师"},
        }
        chunks = chunker.chunk(data)
        eval_chunks = [c for c in chunks if c.section_type == "self_eval"]
        assert len(eval_chunks) == 1

    def test_long_work_experience_splitting(self, chunker):
        """测试超长工作经历被拆分为 L3 子chunk"""
        long_responsibilities = [f"职责描述{i}: 负责xxx系统的设计开发与维护优化工作，包含需求分析、架构设计、编码实现、测试部署等全流程" for i in range(20)]
        data = {
            "work_experience": [{
                "company": "测试公司",
                "position": "工程师",
                "start_date": "2020-01",
                "end_date": "2023-12",
                "responsibilities": long_responsibilities,
                "achievements": [],
                "technologies_used": ["Python"],
            }]
        }
        chunks = chunker.chunk(data)
        work_chunks = [c for c in chunks if c.section_type == "work"]
        # 应该有父chunk + 多个子chunk (因为超过 max_chars)
        assert len(work_chunks) >= 2
        # 检查是否有子chunk标记
        has_sub = any(c.metadata.get("is_partial") for c in work_chunks)
        assert has_sub

    def test_custom_max_chars(self):
        """测试自定义 max_chars 参数"""
        chunker_small = ResumeChunker(max_chars=100, target_chars=50)
        data = {
            "work_experience": [{
                "company": "测试公司",
                "position": "工程师",
                "start_date": "2020-01",
                "end_date": "2023-12",
                "responsibilities": ["职责A " * 30, "职责B " * 30],
                "achievements": [],
                "technologies_used": ["Python"],
            }]
        }
        chunks = chunker_small.chunk(data)
        work_chunks = [c for c in chunks if c.section_type == "work"]
        # 小 max_chars 应该触发拆分
        assert len(work_chunks) >= 2

    def test_empty_certificates(self, chunker):
        """测试证书为空列表"""
        data = {"certificates": []}
        chunks = chunker.chunk(data)
        cert_chunks = [c for c in chunks if c.section_type == "certificate"]
        assert len(cert_chunks) == 0

    def test_list_skills(self, chunker):
        """测试 skills 为列表格式"""
        data = {"skills": ["Python", "Go", "Docker"]}
        chunks = chunker.chunk(data)
        skill_chunks = [c for c in chunks if c.section_type == "skill"]
        assert len(skill_chunks) == 1
        assert "Python, Go, Docker" in skill_chunks[0].content
