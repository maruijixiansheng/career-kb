"""企业级日志系统 — 结构化日志 + 请求追踪 + 文件轮转"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

from ..config import settings


def setup_logging() -> None:
    """配置全局日志系统"""

    # 日志目录
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # 根 logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # 格式
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台输出 (开发环境)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if settings.DEBUG else logging.WARNING)
    console.setFormatter(fmt)
    root.addHandler(console)

    # 文件输出 — 所有日志 (10MB × 5 轮转)
    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # 错误日志单独文件
    error_handler = RotatingFileHandler(
        log_dir / "error.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(fmt)
    root.addHandler(error_handler)

    # LLM 审计日志单独文件
    audit_handler = RotatingFileHandler(
        log_dir / "llm_audit.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    audit_handler.setLevel(logging.INFO)
    audit_handler.setFormatter(fmt)
    audit_logger = logging.getLogger("career-kb.llm-audit")
    audit_logger.addHandler(audit_handler)
    audit_logger.propagate = False  # 不重复输出到根 logger

    # 抑制第三方库的冗余日志
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

    root.info(f"日志系统初始化完成 | 级别: {'DEBUG' if settings.DEBUG else 'INFO'}")
    return root


# 模块级 logger
logger = logging.getLogger("career-kb")
