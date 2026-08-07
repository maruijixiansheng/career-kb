"""向量化服务 — 支持本地模型和云端 API 两种模式

模式切换: 在 .env 中设置 EMBEDDING_PROVIDER=local 或 EMBEDDING_PROVIDER=api

本地模式 (local):
  - 模型: BAAI/bge-small-zh-v1.5 (24M 参数, ~95MB)
  - 优点: 离线可用, 无 API 费用
  - 缺点: 需加载模型, 占用内存, 精度略低

API 模式 (api, 默认):
  - 平台: 硅基流动 SiliconFlow
  - 模型: BAAI/bge-m3 (1024 维, 多语言, 高质量)
  - 优点: 零加载时间, 大模型精度高, 节省本地资源
  - 缺点: 需要网络, 按 token 计费
"""

import os
import uuid
from abc import ABC, abstractmethod
from typing import Optional, List

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_core.embeddings import Embeddings

from .chunker import Chunk
from ..config import settings


# ============================================================
# 抽象嵌入服务
# ============================================================

class BaseEmbeddingService(ABC):
    """嵌入服务抽象基类"""

    @property
    @abstractmethod
    def embeddings(self) -> Embeddings:
        """返回 LangChain 兼容的 Embeddings 对象"""
        ...

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """批量生成文档向量"""
        ...

    @abstractmethod
    def embed_query(self, query: str) -> List[float]:
        """生成查询向量"""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """向量维度"""
        ...


# ============================================================
# 本地嵌入服务 (BGE 模型)
# ============================================================

class LocalEmbeddingService(BaseEmbeddingService):
    """本地 BGE 嵌入模型 (通过 HuggingFaceEmbeddings)"""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._embeddings = None
        self._dimension = None

    @property
    def embeddings(self) -> Embeddings:
        """延迟加载模型"""
        if self._embeddings is None:
            from langchain_huggingface import HuggingFaceEmbeddings
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            self._embeddings = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs={"device": device},
                encode_kwargs={"normalize_embeddings": True},
            )
            self._dimension = 1024
        return self._embeddings

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            _ = self.embeddings  # 触发加载
        return self._dimension or 1024

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return self.embeddings.embed_documents(texts)

    def embed_query(self, query: str) -> List[float]:
        return self.embeddings.embed_query(query)


# ============================================================
# API 嵌入服务 (硅基流动 SiliconFlow)
# ============================================================

class APIEmbeddingService(BaseEmbeddingService):
    """硅基流动云端嵌入服务 (通过 OpenAIEmbeddings 兼容接口)

    支持的模型:
    - BAAI/bge-m3 (1024维, 推荐)
    - BAAI/bge-large-zh-v1.5 (1024维)
    - netease-youdao/bce-embedding-base_v1 (768维)
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model_name = model or settings.SILICONFLOW_EMBEDDING_MODEL
        self.api_key = api_key or settings.SILICONFLOW_API_KEY
        self.base_url = base_url or settings.SILICONFLOW_BASE_URL
        self._embeddings = None
        self._dimension = None

    @property
    def embeddings(self) -> Embeddings:
        """创建 OpenAIEmbeddings 实例 (指向硅基流动)"""
        if self._embeddings is None:
            from langchain_openai import OpenAIEmbeddings
            self._embeddings = OpenAIEmbeddings(
                model=self.model_name,
                api_key=self.api_key,
                base_url=self.base_url,
            )
            # BGE-m3 和 BGE-large-zh 的输出是 1024 维
            if "bce-embedding" in self.model_name.lower():
                self._dimension = 768
            else:
                self._dimension = 1024
        return self._embeddings

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            _ = self.embeddings
        return self._dimension or 1024

    def embed(self, texts: List[str]) -> List[List[float]]:
        """批量生成嵌入向量 (调用硅基流动 API)"""
        if not texts:
            return []
        return self.embeddings.embed_documents(texts)

    def embed_query(self, query: str) -> List[float]:
        """生成查询向量"""
        return self.embeddings.embed_query(query)


# ============================================================
# 工厂函数
# ============================================================

def create_embedding_service() -> BaseEmbeddingService:
    """根据配置创建嵌入服务实例"""
    provider = settings.EMBEDDING_PROVIDER.lower()

    if provider == "api":
        if not settings.SILICONFLOW_API_KEY:
            print("[警告] SILICONFLOW_API_KEY 未设置，回退到本地嵌入模型")
            return LocalEmbeddingService()
        print(f"[嵌入] 使用硅基流动 API: {settings.SILICONFLOW_EMBEDDING_MODEL}")
        return APIEmbeddingService()

    # 默认使用本地模型
    print(f"[嵌入] 使用本地模型: {settings.EMBEDDING_MODEL}")
    return LocalEmbeddingService()


# ============================================================
# 向量存储 (ChromaDB, 与嵌入服务解耦)
# ============================================================

class VectorStore:
    """Chroma 向量存储封装 (基于 LangChain Chroma wrapper)"""

    def __init__(self, persist_dir: Optional[str] = None, embedding_service: Optional[BaseEmbeddingService] = None):
        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self._embedding_service = embedding_service
        # 底层 chromadb 客户端 (用于 collection_exists 等操作)
        self._client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        # 缓存 LangChain Chroma 实例，避免重复创建导致冲突
        self._chroma_instances: dict[str, object] = {}

    @property
    def embedding_service(self) -> BaseEmbeddingService:
        """延迟获取嵌入服务单例"""
        if self._embedding_service is None:
            self._embedding_service = embedding_service
        return self._embedding_service

    def _get_chroma(self, collection_name: str):
        """获取 LangChain Chroma 实例（复用已有 collection，避免设置冲突）"""
        if collection_name not in self._chroma_instances:
            from langchain_community.vectorstores import Chroma
            import logging
            logger = logging.getLogger("career-kb")

            # 检查 collection 是否已存在
            existing = self._client.list_collections()
            already_exists = any(c.name == collection_name for c in existing)

            if already_exists:
                # 已存在的 collection，不传 collection_metadata 避免冲突
                logger.info(f"Chroma collection 已存在，直接复用: {collection_name}")
                self._chroma_instances[collection_name] = Chroma(
                    client=self._client,
                    collection_name=collection_name,
                    embedding_function=self.embedding_service.embeddings,
                )
            else:
                # 新建 collection
                logger.info(f"Chroma collection 新建: {collection_name}")
                try:
                    self._chroma_instances[collection_name] = Chroma(
                        client=self._client,
                        collection_name=collection_name,
                        embedding_function=self.embedding_service.embeddings,
                        collection_metadata={"hnsw:space": "cosine"},
                    )
                except ValueError as e:
                    # 并发创建可能导致冲突，重试
                    logger.warning(f"Chroma collection 创建冲突，重试: {e}")
                    try:
                        self._client.delete_collection(collection_name)
                    except Exception:
                        pass
                    self._chroma_instances[collection_name] = Chroma(
                        client=self._client,
                        collection_name=collection_name,
                        embedding_function=self.embedding_service.embeddings,
                        collection_metadata={"hnsw:space": "cosine"},
                    )
        return self._chroma_instances[collection_name]

    def get_or_create_collection(self, collection_name: str):
        """获取或创建 collection (兼容旧接口)"""
        return self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, collection_name: str, chunks: list[Chunk]) -> int:
        """批量添加分块到 Chroma

        Returns:
            添加的 chunk 数量
        """
        if not chunks:
            return 0

        chroma = self._get_chroma(collection_name)

        texts = [chunk.content for chunk in chunks]
        metadatas = [
            {
                **{k: str(v) if not isinstance(v, (str, int, float, bool)) else v
                   for k, v in chunk.metadata.items()},
                # 将 Chunk 核心字段也序列化到 metadata
                # （修复 section_type 丢失 + id 去重失效的根因）
                "id": chunk.id,
                "section_type": chunk.section_type,
                "section_title": chunk.section_title,
                "chunk_index": chunk.chunk_index,
            }
            for chunk in chunks
        ]
        ids = [chunk.id for chunk in chunks]

        chroma.add_texts(texts=texts, metadatas=metadatas, ids=ids)

        return len(chunks)

    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 15,
        where_filter: Optional[dict] = None,
    ) -> list[dict]:
        """向量相似度搜索

        Returns:
            [{id, content, metadata, score, source}, ...]
        """
        chroma = self._get_chroma(collection_name)

        results = chroma.similarity_search_with_score(
            query,
            k=top_k,
            filter=where_filter,
        )

        # 格式化结果 — Chroma 返回距离 (lower is better), 转换为相似度
        formatted = []
        for doc, distance in results:
            formatted.append({
                "id": doc.metadata.get("id", ""),
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": 1.0 - distance,  # 距离 → 相似度
                "source": "dense",
            })

        return formatted

    def add_skill_library_entry(self, entries: list[dict]) -> int:
        """添加技能库条目到向量存储（专用方法，不依赖 Chunk dataclass）"""
        if not entries:
            return 0

        collection_name = "skill_library"
        chroma = self._get_chroma(collection_name)

        texts = [e["content"] for e in entries]
        metadatas = [
            {k: str(v) if not isinstance(v, (str, int, float, bool)) else v
             for k, v in e.get("metadata", {}).items()}
            for e in entries
        ]
        ids = [e["id"] for e in entries]

        chroma.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        return len(entries)

    def delete_collection(self, collection_name: str):
        """删除 collection"""
        self._chroma_instances.pop(collection_name, None)
        try:
            self._client.delete_collection(collection_name)
        except Exception:
            pass

    def collection_exists(self, collection_name: str) -> bool:
        """检查 collection 是否存在"""
        collections = self._client.list_collections()
        return any(c.name == collection_name for c in collections)


# ============================================================
# 全局单例
# ============================================================

embedding_service = create_embedding_service()
vector_store = VectorStore(embedding_service=embedding_service)
