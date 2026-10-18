"""相关性把关回归测试：工作/实习必须始终保留（P0：生成简历丢实习经历）"""

import asyncio

from app.core import rag_engine as re_mod


def chunk(kind: str, title: str) -> dict:
    return {
        "id": title,
        "content": f"{title} 的内容描述",
        "metadata": {"section_type": kind, "title": title},
    }


class FakeLLM:
    def __init__(self, result):
        self.result = result
        self.calls: list[dict] = []

    async def chat_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def test_internship_kept_even_when_projects_filtered(monkeypatch):
    fake = FakeLLM([{"id": "0", "relevant": False, "reason": "跨领域"},
                    {"id": "1", "relevant": False, "reason": "跨领域"}])
    monkeypatch.setattr(re_mod, "llm_client", fake)

    candidates = [
        chunk("project", "CV 项目"),
        chunk("project", "RAG 项目"),
        chunk("internship", "实在智能实习"),
    ]
    out = asyncio.run(re_mod.rag_engine.filter_by_relevance({"position_title": "AI应用开发"}, candidates))
    titles = [c["metadata"]["title"] for c in out]

    assert "实在智能实习" in titles          # 实习始终保留
    assert "CV 项目" not in titles
    assert "RAG 项目" not in titles
    # 送给 LLM 的候选里不应出现实习（它不参与判断）
    assert "实在智能实习" not in fake.calls[0]["user_message"]


def test_work_kept_and_projects_partially_kept(monkeypatch):
    fake = FakeLLM([{"id": "0", "relevant": True, "reason": "方向一致"},
                    {"id": "1", "relevant": False, "reason": "跨领域"}])
    monkeypatch.setattr(re_mod, "llm_client", fake)

    candidates = [
        chunk("project", "RAG 项目"),
        chunk("project", "CV 项目"),
        chunk("work", "某公司后端"),
    ]
    out = asyncio.run(re_mod.rag_engine.filter_by_relevance({"position_title": "AI应用开发"}, candidates))
    titles = [c["metadata"]["title"] for c in out]

    assert "某公司后端" in titles
    assert "RAG 项目" in titles
    assert "CV 项目" not in titles


def test_single_project_skips_filter(monkeypatch):
    fake = FakeLLM([{"id": "0", "relevant": False}])
    monkeypatch.setattr(re_mod, "llm_client", fake)

    candidates = [chunk("project", "唯一项目"), chunk("internship", "实习")]
    out = asyncio.run(re_mod.rag_engine.filter_by_relevance({"position_title": "AI应用开发"}, candidates))

    assert out == candidates
    assert fake.calls == []  # 项目太少，不调用 LLM


def test_llm_failure_keeps_all(monkeypatch):
    class Boom:
        async def chat_json(self, **kwargs):
            raise RuntimeError("timeout")

    monkeypatch.setattr(re_mod, "llm_client", Boom())
    candidates = [chunk("project", "A"), chunk("project", "B"), chunk("internship", "实习")]
    out = asyncio.run(re_mod.rag_engine.filter_by_relevance({"position_title": "x"}, candidates))
    assert len(out) == 3
