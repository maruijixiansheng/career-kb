"""简历上传 → 技能库自动同步（纯规则部分）回归测试"""

from app.services.resume_service import ResumeService


def _structured():
    return {
        "basic_info": {"name": "张三"},
        "projects": [
            {
                "name": "Career KB",
                "start_date": "2026-08",
                "end_date": "至今",
                "description": "AI 求职助手",
                "responsibilities": ["设计检索链路"],
                "achievements": ["召回从 5 提到 38"],
                "technologies_used": ["Python", "LangGraph"],
            }
        ],
        "work_experience": [
            {
                "company": "某公司",
                "position": "算法实习生",
                "start_date": "2025-07",
                "end_date": "2025-09",
                "responsibilities": ["数据清洗"],
                "technologies_used": ["Python"],
            },
            {
                "company": "另一公司",
                "position": "后端开发",
                "start_date": "2025-01",
                "end_date": "2025-03",
                "responsibilities": ["接口开发"],
                "technologies_used": ["FastAPI"],
            },
        ],
        "skills": {
            "programming_languages": ["Python", "C++"],
            "frameworks": ["LangGraph", "Docker"],
            "tools": ["Docker", "Linux"],
            "soft_skills": ["沟通能力强"],
        },
        "certificates": ["CET-6", "蓝桥杯省二"],
    }


def test_builds_projects_work_internship_skills_certs():
    pending = ResumeService()._build_pending_entries(_structured())
    types = [e["entry_type"] for e in pending]
    titles = [e["title"] for e in pending]

    assert "project" in types
    assert "internship" in types          # 职位含「实习」
    assert "work" in types                # 不含实习 → 正式工作
    assert "skill" in types
    assert "certificate" in types
    assert "Career KB" in titles
    assert "某公司 | 算法实习生" in titles  # 公司 | 职位
    assert "CET-6" in titles
    # 软技能不写入技能库
    assert "沟通能力强" not in titles
    # 同一技术出现在两个分类只保留一条
    assert titles.count("Docker") == 1


def test_skill_entry_content_carries_category():
    pending = ResumeService()._build_pending_entries(_structured())
    linux = next(e for e in pending if e["title"] == "Linux")
    assert linux["entry_type"] == "skill"
    assert "工具与平台" in linux["content"]
    assert linux["tags"] == "工具与平台"


def test_dedupes_against_project_titles():
    data = {"projects": [{"name": "Python"}], "skills": {"programming_languages": ["Python"]}}
    pending = ResumeService()._build_pending_entries(data)
    assert [e["title"] for e in pending] == ["Python"]
    assert pending[0]["entry_type"] == "project"


def test_raw_fallback_returns_empty():
    assert ResumeService()._build_pending_entries({"raw": "随便一段文本"}) == []
    assert ResumeService()._build_pending_entries({}) == []
