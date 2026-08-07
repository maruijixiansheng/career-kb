"""测试混合检索器 (Retriever)"""

import pytest
from app.core.retriever import (
    BM25Scorer,
    reciprocal_rank_fusion,
    HybridRetriever,
)


class TestBM25Scorer:
    """BM25 稀疏检索测试"""

    @pytest.fixture
    def scorer(self):
        return BM25Scorer()

    @pytest.fixture
    def sample_docs(self):
        return [
            {"id": "1", "content": "Python后端开发工程师，负责API设计和数据库优化"},
            {"id": "2", "content": "前端React开发，负责用户界面和交互体验"},
            {"id": "3", "content": "全栈工程师，精通Python和JavaScript，有丰富的后端和前端经验"},
            {"id": "4", "content": "数据分析师，使用Python进行数据挖掘和机器学习"},
        ]

    def test_index(self, scorer, sample_docs):
        scorer.index(sample_docs)
        assert scorer.total_docs == 4
        assert len(scorer.documents) == 4
        assert scorer.avg_doc_length > 0
        # 每个文档都有 tokens
        for doc in scorer.documents:
            assert "tokens" in doc
            assert len(doc["tokens"]) > 0

    def test_search_returns_results(self, scorer, sample_docs):
        scorer.index(sample_docs)
        results = scorer.search("Python后端", top_k=2)
        assert len(results) == 2
        # 最相关的结果应该包含Python相关内容
        for r in results:
            assert r["source"] == "sparse"
            assert "score" in r
            assert r["score"] > 0

    def test_search_relevance(self, scorer, sample_docs):
        """Python后端查询应该优先返回后端相关文档"""
        scorer.index(sample_docs)
        results = scorer.search("Python后端开发")
        assert len(results) > 0
        # 第一个结果应该最相关
        top_id = results[0]["id"]
        # doc 1 或 doc 3 最匹配 "Python后端开发"
        assert top_id in ["1", "3"]

    def test_search_empty_query(self, scorer, sample_docs):
        scorer.index(sample_docs)
        results = scorer.search("")
        assert len(results) == 0  # 空查询无结果

    def test_search_no_match(self, scorer, sample_docs):
        scorer.index(sample_docs)
        results = scorer.search("区块链比特币")
        # 可能返回空或低分结果
        assert isinstance(results, list)

    def test_search_top_k(self, scorer, sample_docs):
        scorer.index(sample_docs)
        results = scorer.search("Python", top_k=1)
        assert len(results) == 1

    def test_empty_index(self, scorer):
        scorer.index([])
        assert scorer.total_docs == 0
        results = scorer.search("Python")
        assert len(results) == 0

    def test_bm25_params(self):
        """测试自定义 BM25 参数"""
        scorer = BM25Scorer(k1=2.0, b=0.5)
        assert scorer.k1 == 2.0
        assert scorer.b == 0.5


class TestReciprocalRankFusion:
    """RRF 融合测试"""

    def test_basic_fusion(self):
        dense = [
            {"id": "A", "content": "doc A", "score": 0.9},
            {"id": "B", "content": "doc B", "score": 0.7},
            {"id": "C", "content": "doc C", "score": 0.5},
        ]
        sparse = [
            {"id": "B", "content": "doc B", "score": 0.8},
            {"id": "C", "content": "doc C", "score": 0.6},
            {"id": "D", "content": "doc D", "score": 0.4},
        ]
        fused = reciprocal_rank_fusion(dense, sparse)
        assert len(fused) == 4  # A, B, C, D
        assert "rrf_score" in fused[0]

    def test_fusion_same_ranks(self):
        """两边排名相同的情况"""
        dense = [
            {"id": "A", "content": "doc A", "score": 0.9},
        ]
        sparse = [
            {"id": "A", "content": "doc A", "score": 0.8},
        ]
        fused = reciprocal_rank_fusion(dense, sparse)
        assert len(fused) == 1
        # RRF 分数应该是 1/(60+1) + 1/(60+1)
        expected = 1.0 / 61 + 1.0 / 61
        assert abs(fused[0]["rrf_score"] - expected) < 0.001

    def test_fusion_empty_dense(self):
        dense = []
        sparse = [{"id": "A", "content": "doc A", "score": 0.5}]
        fused = reciprocal_rank_fusion(dense, sparse)
        assert len(fused) == 1

    def test_fusion_empty_sparse(self):
        dense = [{"id": "A", "content": "doc A", "score": 0.5}]
        sparse = []
        fused = reciprocal_rank_fusion(dense, sparse)
        assert len(fused) == 1

    def test_fusion_both_empty(self):
        fused = reciprocal_rank_fusion([], [])
        assert len(fused) == 0

    def test_fusion_ordering(self):
        """排名靠前的文档应该在融合后有更高的分数"""
        dense = [
            {"id": "top", "content": "top", "score": 0.99},
            {"id": "mid", "content": "mid", "score": 0.5},
        ]
        sparse = [
            {"id": "top", "content": "top", "score": 0.99},
            {"id": "mid", "content": "mid", "score": 0.5},
        ]
        fused = reciprocal_rank_fusion(dense, sparse)
        assert fused[0]["id"] == "top"


class TestHybridRetriever:
    """混合检索器测试"""

    def test_build_and_remove_bm25_index(self):
        retriever = HybridRetriever()
        docs = [{"id": "1", "content": "测试文档"}]
        retriever.build_bm25_index("test_collection", docs)
        assert "test_collection" in retriever.bm25_indexes

        retriever.remove_bm25_index("test_collection")
        assert "test_collection" not in retriever.bm25_indexes

    def test_remove_nonexistent_index(self):
        retriever = HybridRetriever()
        # 不存在的索引，删除不应报错
        retriever.remove_bm25_index("nonexistent")
        assert "nonexistent" not in retriever.bm25_indexes
