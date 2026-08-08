"""混合检索器 — Dense(BGE) + Sparse(BM25) + RRF 融合 (基于 LangChain)

检索策略:
1. Dense (稠密): BGE 向量语义检索 — 处理同义词和改写
2. Sparse (稀疏): jieba + BM25 关键词检索 — 精确匹配技术术语
3. RRF (Reciprocal Rank Fusion): 融合两种检索结果
4. 章节类型加权后处理
"""

import math
from collections import defaultdict
from typing import Optional, List

import jieba
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun

from .embedder import vector_store


# ============================================================
# BM25 稀疏检索器
# ============================================================

class BM25Scorer:
    """BM25 稀疏检索 (简易实现, 使用 jieba 中文分词)"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: list[dict] = []        # [{id, content, tokens}]
        self.doc_lengths: list[int] = []
        self.avg_doc_length: float = 0
        self.doc_freq: dict[str, int] = defaultdict(int)  # 文档频率
        self.total_docs: int = 0

    def index(self, documents: list[dict]):
        """构建索引

        Args:
            documents: [{id, content, ...}, ...]
        """
        self.documents = documents
        self.total_docs = len(documents)

        for doc in documents:
            tokens = list(jieba.cut(doc["content"]))
            doc["tokens"] = tokens
            self.doc_lengths.append(len(tokens))

            # 去重后统计文档频率
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freq[token] += 1

        self.avg_doc_length = sum(self.doc_lengths) / max(self.total_docs, 1)

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """BM25 检索"""
        query_tokens = list(jieba.cut(query))
        scores = []

        for i, doc in enumerate(self.documents):
            score = self._bm25_score(query_tokens, doc["tokens"], self.doc_lengths[i])
            if score > 0:
                scores.append({
                    "id": doc["id"],
                    "content": doc["content"],
                    "metadata": doc.get("metadata", {}),
                    "score": score,
                    "source": "sparse",
                })

        # 按分数降序
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]

    def _bm25_score(self, query_tokens: list[str], doc_tokens: list[str], doc_length: int) -> float:
        """计算单个文档的 BM25 分数"""
        score = 0.0
        doc_len = doc_length

        # 统计文档中的词频
        tf = defaultdict(int)
        for token in doc_tokens:
            tf[token] += 1

        for token in query_tokens:
            if token not in tf:
                continue

            # IDF
            df = self.doc_freq.get(token, 0)
            if df == 0:
                continue
            idf = math.log(1 + (self.total_docs - df + 0.5) / (df + 0.5))

            # TF with saturation
            term_freq = tf[token]
            numerator = term_freq * (self.k1 + 1)
            denominator = term_freq + self.k1 * (1 - self.b + self.b * doc_len / max(self.avg_doc_length, 1))
            score += idf * numerator / denominator

        return score


# ============================================================
# LangChain BaseRetriever 封装
# ============================================================

class JiebaBM25Retriever(BaseRetriever):
    """LangChain 兼容的 BM25 检索器 (jieba 分词)"""

    scorer: Optional[BM25Scorer] = None
    top_k: int = 10

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        if self.scorer is None:
            return []
        results = self.scorer.search(query, top_k=self.top_k)
        return [
            Document(
                page_content=r["content"],
                metadata={**r.get("metadata", {}), "id": r["id"], "score": r["score"], "source": "sparse"},
            )
            for r in results
        ]

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        return self._get_relevant_documents(query, run_manager=run_manager)


class ChromaRetriever(BaseRetriever):
    """LangChain 兼容的 Chroma 向量检索器 (Dense)"""

    collection_name: str = ""
    top_k: int = 15
    where_filter: Optional[dict] = None

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self, query: str, *, run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        results = vector_store.search(
            self.collection_name, query,
            top_k=self.top_k,
            where_filter=self.where_filter,
        )
        return [
            Document(
                page_content=r["content"],
                metadata={**r.get("metadata", {}), "id": r["id"], "score": r.get("score", 0), "source": "dense"},
            )
            for r in results
        ]

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: Optional[CallbackManagerForRetrieverRun] = None
    ) -> List[Document]:
        return self._get_relevant_documents(query, run_manager=run_manager)


# ============================================================
# RRF 融合
# ============================================================

def reciprocal_rank_fusion(
    dense_results: list[dict],
    sparse_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """RRF 融合: 合并稠密和稀疏检索结果

    RRF_score(d) = Σ(1 / (k + rank_i(d)))
    """
    scores = defaultdict(float)
    doc_map = {}  # id → document

    # Dense results
    for rank, doc in enumerate(dense_results):
        doc_id = doc["id"]
        scores[doc_id] += 1.0 / (k + rank + 1)
        doc_map[doc_id] = doc

    # Sparse results
    for rank, doc in enumerate(sparse_results):
        doc_id = doc["id"]
        scores[doc_id] += 1.0 / (k + rank + 1)
        if doc_id not in doc_map:
            doc_map[doc_id] = doc

    # 按 RRF 分数排序
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    results = []
    for doc_id in sorted_ids:
        doc = doc_map[doc_id]
        doc["rrf_score"] = scores[doc_id]
        results.append(doc)

    return results


def reciprocal_rank_fusion_docs(
    doc_lists: list[list[Document]],
    k: int = 60,
) -> list[Document]:
    """RRF 融合 (LangChain Document 版本)

    Args:
        doc_lists: 多个检索器返回的 Document 列表
        k: RRF 常数

    Returns:
        融合后的 Document 列表
    """
    scores = defaultdict(float)
    doc_map = {}  # hash_key → Document

    for doc_list in doc_lists:
        for rank, doc in enumerate(doc_list):
            # 使用 page_content + metadata 作为去重 key
            doc_key = doc.metadata.get("id", doc.page_content[:100])
            scores[doc_key] += 1.0 / (k + rank + 1)
            doc_map[doc_key] = doc

    sorted_keys = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    results = []
    for key in sorted_keys:
        doc = doc_map[key]
        doc.metadata["rrf_score"] = scores[key]
        results.append(doc)

    return results


# ============================================================
# 混合检索器 (保持旧接口兼容)
# ============================================================

class HybridRetriever:
    """混合检索器: Dense + Sparse + RRF + 章节加权

    对外接口保持与迁移前完全相同。
    """

    def __init__(self):
        self.bm25_indexes: dict[str, BM25Scorer] = {}  # 每个 collection 一个 BM25 索引
        self._dense_retrievers: dict[str, ChromaRetriever] = {}
        self._sparse_retrievers: dict[str, JiebaBM25Retriever] = {}

    async def retrieve(
        self,
        collection_name: str,
        queries: list[str],          # 多查询 (从JD需求生成的多个检索角度)
        top_k_dense: int = 15,
        top_k_sparse: int = 10,
        top_k_fusion: int = 20,
        section_weights: Optional[dict] = None,  # 章节类型加权
    ) -> list[dict]:
        """执行混合检索，返回候选 chunks

        返回格式与迁移前完全相同: [{id, content, metadata, score, source}, ...]
        """

        # 默认章节权重
        if section_weights is None:
            section_weights = {
                "work": 1.5,
                "project": 1.3,
                "skill": 1.2,
                "self_eval": 0.8,
                "education": 0.7,
                "basic_info": 0.6,
                "certificate": 0.5,
            }

        all_dense = []
        all_sparse = []

        for query in queries:
            # 1. Dense 检索
            dense = vector_store.search(collection_name, query, top_k=top_k_dense)
            all_dense.extend(dense)

            # 2. Sparse 检索 (如果有索引)
            if collection_name in self.bm25_indexes:
                sparse = self.bm25_indexes[collection_name].search(query, top_k=top_k_sparse)
                all_sparse.extend(sparse)

        # 去除 dense 中的重复 (按 id)
        seen_ids = set()
        dense_unique = []
        for d in all_dense:
            if d["id"] not in seen_ids:
                seen_ids.add(d["id"])
                dense_unique.append(d)

        # 3. RRF 融合
        if all_sparse:
            fused = reciprocal_rank_fusion(dense_unique, all_sparse)
        else:
            fused = dense_unique

        # 4. 章节类型加权（含内容推断回退，兼容旧 chunks 缺少 section_type 的问题）
        for doc in fused:
            section_type = doc.get("metadata", {}).get("section_type", "")
            if not section_type:
                section_type = self._infer_section_type(doc)
                doc["metadata"]["section_type"] = section_type  # 回填
            weight = section_weights.get(section_type, 1.0)
            current_score = doc.get("rrf_score", doc.get("score", 0))
            doc["weighted_score"] = current_score * weight

        # 按加权分数重排
        fused.sort(key=lambda x: x.get("weighted_score", 0), reverse=True)

        # 5. 内容领域关键词惩罚：跨领域 chunk 降权
        # 常见跨领域污染词对（检测到则降权 80%）
        OFF_DOMAIN_KEYWORDS = [
            # 机器人/自动驾驶
            "ROS", "ros", "机器人", "SLAM", "Gazebo", "自动驾驶",
            # 计算机视觉
            "YOLO", "yolo", "YOLOv", "目标检测", "图像分割", "图像分类",
            "OpenCV", "opencv", "点云", "激光雷达", "相机标定",
            # 嵌入式/硬件
            "嵌入式", "单片机", "STM32", "PCB", "电路", "FPGA",
            # 游戏
            "Unity", "Unreal", "游戏引擎",
            # 生物医药
            "医学影像", "CT影像", "MRI",
        ]
        for doc in fused:
            content = doc.get("content", "")
            if any(kw in content for kw in OFF_DOMAIN_KEYWORDS):
                # 检查是否与查询关键词匹配（如果查询中也包含这些词则不降权）
                query_match = any(
                    kw.lower() in q.lower()
                    for q in queries
                    for kw in OFF_DOMAIN_KEYWORDS
                )
                if not query_match:
                    doc["weighted_score"] = doc.get("weighted_score", 0) * 0.2

        # 6. 按加权分数重新排序
        fused.sort(key=lambda x: x.get("weighted_score", 0), reverse=True)

        # 7. 相关性阈值过滤（宽松策略：小集合不过度裁剪）
        if fused:
            max_score = max(d.get("weighted_score", 0) for d in fused)
            # 使用更宽松的阈值：max_score * 0.15（而非 0.5），
            # 避免在小集合（每collection 7-8 chunks）中过度裁剪
            MIN_RELEVANCE = max(0.005, max_score * 0.15)
            filtered = [d for d in fused if d.get("weighted_score", 0) >= MIN_RELEVANCE]
            # 确保至少返回 top_k_fusion 个结果（如果可用）
            if len(filtered) < top_k_fusion:
                # 从未通过阈值的结果中补充最高分的
                remaining = [d for d in fused if d not in filtered]
                remaining.sort(key=lambda x: x.get("weighted_score", 0), reverse=True)
                needed = min(top_k_fusion - len(filtered), len(remaining))
                filtered.extend(remaining[:needed])
        else:
            filtered = []

        return filtered[:top_k_fusion]

    @staticmethod
    def _infer_section_type(doc: dict) -> str:
        """从内容推断章节类型（兼容缺少 section_type metadata 的旧 chunks）"""
        content = doc.get("content", "")
        metadata = doc.get("metadata", {})

        # 优先用 metadata 中的 type 字段
        meta_type = metadata.get("type", "")
        if meta_type in ("basic_info", "self_eval", "skills", "certificate"):
            return meta_type

        # 检查 metadata 中是否有 project_name / company / school 等特征字段
        if metadata.get("project_name"):
            return "project"
        if metadata.get("company"):
            return "work"
        if metadata.get("school"):
            return "education"

        # 内容关键词匹配
        if content.startswith("姓名:") or content.startswith("姓名："):
            return "basic_info"
        if "求职意向" in content[:60] and "邮箱" in content[:80]:
            return "basic_info"
        if content.startswith("项目:") or content.startswith("项目："):
            return "project"
        if content.startswith("公司:") or content.startswith("公司："):
            return "work"
        if content.startswith("学校:") or content.startswith("学校："):
            return "education"
        if content.startswith("证书与荣誉"):
            return "certificate"
        if "programming_languages:" in content or "frameworks:" in content:
            return "skill"
        if metadata.get("skill_names"):
            return "skill"
        if metadata.get("degree"):
            return "education"

        return "other"

    async def retrieve_multi_collection(
        self,
        collection_names: list[str],
        queries: list[str],
        top_k_dense: int = 15,
        top_k_sparse: int = 10,
        top_k_fusion: int = 20,
        section_weights: Optional[dict] = None,
    ) -> list[dict]:
        """跨多个 collection 搜索（简历+技能库联合检索）"""
        if section_weights is None:
            section_weights = {
                "work": 1.5, "project": 1.3, "skill": 1.2,
                "internship": 1.4,  # 技能库实习条目加权
                "self_eval": 0.8, "education": 0.7,
                "basic_info": 0.6, "certificate": 0.5,
            }

        all_fused = []
        for collection_name in collection_names:
            # 对 skill_library 自动补建 BM25 索引（重启后丢失）
            if collection_name == "skill_library" and collection_name not in self.bm25_indexes:
                await self._build_skill_library_bm25()
            candidates = await self.retrieve(
                collection_name=collection_name,
                queries=queries,
                top_k_dense=top_k_dense,
                top_k_sparse=top_k_sparse,
                top_k_fusion=top_k_fusion,
                section_weights=section_weights,
            )
            # 标记来源
            for c in candidates:
                src = "skill_library" if collection_name == "skill_library" else "resume"
                c.setdefault("metadata", {})["source_collection"] = src
            all_fused.extend(candidates)

        # 按加权分数全局重排
        all_fused.sort(key=lambda x: x.get("weighted_score", 0), reverse=True)
        return all_fused[:top_k_fusion]

    async def _build_skill_library_bm25(self):
        """从 ChromaDB 读取技能库数据并构建 BM25 索引"""
        try:
            from ..models.skill_library import SkillLibraryEntry
            from ..database import async_session
            from sqlalchemy import select

            async with async_session() as session:
                result = await session.execute(
                    select(SkillLibraryEntry).where(SkillLibraryEntry.is_active == True)
                )
                entries = result.scalars().all()
                if entries:
                    docs = [{
                        "id": e.id,
                        "content": f"[{e.entry_type}] {e.title}\n{e.content}\n标签: {e.tags or ''}",
                        "metadata": {
                            "entry_type": e.entry_type,
                            "title": e.title,
                            "tags": e.tags or "",
                            "source_collection": "skill_library",
                            "section_type": e.entry_type,
                        },
                    } for e in entries]
                    self.build_bm25_index("skill_library", docs)
        except Exception:
            pass  # BM25 构建失败不影响 Dense 检索

    async def list_resume_collections(self) -> list[str]:
        """列出所有简历 collection（从 ChromaDB）"""
        try:
            all_collections = vector_store._client.list_collections()
            return [c.name for c in all_collections if c.name.startswith("resume_")]
        except Exception:
            return []

    def build_bm25_index(self, collection_name: str, documents: list[dict]):
        """为 collection 构建 BM25 索引"""
        scorer = BM25Scorer()
        scorer.index(documents)
        self.bm25_indexes[collection_name] = scorer
        # 同步创建 LangChain retriever
        retriever = JiebaBM25Retriever(scorer=scorer, top_k=10)
        self._sparse_retrievers[collection_name] = retriever

    def remove_bm25_index(self, collection_name: str):
        """删除 BM25 索引"""
        self.bm25_indexes.pop(collection_name, None)
        self._sparse_retrievers.pop(collection_name, None)

    def get_langchain_retrievers(
        self, collection_name: str,
    ) -> tuple[Optional[ChromaRetriever], Optional[JiebaBM25Retriever]]:
        """获取 LangChain 兼容的检索器 (供 LangGraph 使用)"""
        dense = ChromaRetriever(collection_name=collection_name, top_k=15)
        sparse = self._sparse_retrievers.get(collection_name)
        return dense, sparse


# 全局单例
retriever = HybridRetriever()
