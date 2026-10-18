"""技能库向量同步回归测试（P0：编辑/删除必须同步 Chroma）

不依赖真实 Chroma / 网络：用 FakeStore 替换 vector_store，验证调用顺序与回读校验。
"""

from types import SimpleNamespace

import pytest

from app.api import skill_library as sl


def _entry(**kw):
    base = dict(
        id="entry-1",
        user_id="user-a",
        entry_type="project",
        title="掌柜智库",
        content="基于 RAG 的企业知识库",
        tags="RAG,LangGraph",
        importance=5,
    )
    base.update(kw)
    return SimpleNamespace(**base)


class FakeStore:
    """记录调用；readback 模拟写入后可读到的内容"""

    def __init__(self):
        self.added: list[dict] = []
        self.deleted: list[list[str]] = []
        self.current: str | None = None
        self.fail_on_add = False

    def add_skill_library_entry(self, entries):
        if self.fail_on_add:
            raise RuntimeError("embedding api down")
        self.added.extend(entries)
        self.current = entries[-1]["content"]
        return len(entries)

    def delete_skill_library_entries(self, ids):
        self.deleted.append(list(ids))
        self.current = None
        return len(ids)

    def get_skill_library_entry_content(self, entry_id):
        return self.current


def test_vector_payload_keeps_expected_shape():
    payload = sl._vector_payload(_entry())

    assert payload["id"] == "entry-1"
    assert payload["content"].startswith("[project] 掌柜智库\n基于 RAG 的企业知识库")
    assert "标签: RAG,LangGraph" in payload["content"]
    # metadata 必须带 id / section_type / user_id，否则检索侧去重与用户隔离都会失效
    assert payload["metadata"]["user_id"] == "user-a"
    assert payload["section_type"] == "project"
    assert payload["metadata"]["importance"] == "5"


def test_resync_writes_and_verifies(monkeypatch):
    store = FakeStore()
    monkeypatch.setattr(sl, "vector_store", store)
    monkeypatch.setitem(sl.retriever.bm25_indexes, "skill_library:user-a", object())

    assert sl._resync_entry_vector(_entry()) is True
    assert len(store.added) == 1
    # 回读一致 → 不应触发删除
    assert store.deleted == []
    # BM25 缓存必须失效
    assert "skill_library:user-a" not in sl.retriever.bm25_indexes


def test_resync_falls_back_to_delete_when_not_overwritten(monkeypatch):
    """某些 Chroma 版本 add 对已存在 id 只跳过不覆盖 → 必须删旧重写"""

    class SkipStore(FakeStore):
        def add_skill_library_entry(self, entries):
            self.added.extend(entries)
            return len(entries)  # 不更新 current，模拟"没写进去"

    store = SkipStore()
    store.current = "[project] 旧内容"
    monkeypatch.setattr(sl, "vector_store", store)

    assert sl._resync_entry_vector(_entry()) is True
    assert store.deleted == [["entry-1"]]
    assert len(store.added) == 2


def test_resync_returns_false_on_failure(monkeypatch):
    store = FakeStore()
    store.fail_on_add = True
    monkeypatch.setattr(sl, "vector_store", store)

    assert sl._resync_entry_vector(_entry()) is False
