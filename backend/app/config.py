"""应用配置管理"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置"""

    # 应用
    APP_NAME: str = "个人职业知识管家"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # 认证
    SECRET_KEY: str = ""  # 生产环境必须设置（留空则自动生成随机密钥）
    ACCESS_TOKEN_EXPIRE_HOURS: int = 24

    # 数据库
    DATABASE_TYPE: str = "sqlite"  # "sqlite" | "postgres"
    DATABASE_URL: str = ""  # 留空则根据 DATABASE_TYPE 自动构建

    # PostgreSQL 连接参数 (DATABASE_TYPE=postgres 时使用)
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "career"
    POSTGRES_PASSWORD: str = "career"
    POSTGRES_DB: str = "career_kb"

    # Chroma 向量存储
    CHROMA_PERSIST_DIR: str = str(Path(__file__).parent.parent.parent / "data" / "chroma")

    # 文件上传
    UPLOAD_DIR: str = str(Path(__file__).parent.parent.parent / "data" / "uploads")
    MAX_UPLOAD_SIZE_MB: int = 10

    # LLM — DeepSeek API
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL_SIMPLE: str = "deepseek-chat"    # 简单任务: JD解析、分块、核查
    LLM_MODEL_POWERFUL: str = "deepseek-chat"  # 复杂任务: 简历生成、面试模拟

    # 嵌入模型 — 支持本地模型和云端 API 两种模式
    # 模式: "local" (本地 BGE 模型) 或 "api" (硅基流动云端大模型)
    EMBEDDING_PROVIDER: str = "api"  # local | api

    # 本地嵌入模型 (EMBEDDING_PROVIDER=local 时使用)
    EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"

    # 硅基流动 API 嵌入 (EMBEDDING_PROVIDER=api 时使用)
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_EMBEDDING_MODEL: str = "BAAI/bge-m3"  # 1024维，多语言，质��最高

    RERANKER_MODEL: str = "BAAI/bge-reranker-large"

    # 照片上传
    PHOTOS_DIR: str = str(Path(__file__).parent.parent.parent / "data" / "photos")
    FONTS_DIR: str = str(Path(__file__).parent / "static" / "fonts")
    MAX_PHOTO_SIZE_MB: int = 2

    # RAG 参数
    RAG_TOP_K_RETRIEVAL: int = 15
    RAG_TOP_K_RERANK: int = 8
    CHUNK_MAX_CHARS: int = 800
    CHUNK_TARGET_CHARS: int = 400

    # LangChain / LangGraph (可选)
    LANGCHAIN_PROJECT: str = "career-kb"

    def model_post_init(self, __context):
        """动态构建 DATABASE_URL（兼容 SQLite 和 PostgreSQL）"""
        if not self.DATABASE_URL:
            if self.DATABASE_TYPE == "postgres":
                self.DATABASE_URL = (
                    f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                    f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
                )
            else:
                self.DATABASE_URL = (
                    f"sqlite+aiosqlite:///{Path(__file__).parent.parent.parent / 'data' / 'career.db'}"
                )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
