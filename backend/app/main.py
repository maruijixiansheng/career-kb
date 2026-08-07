"""FastAPI 应用入口 — 企业级配置"""

import os
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from .config import settings
from .database import init_db, engine
from .api import resumes, jobs, applications, ai, skills, interview, skill_library, user_profile, auth
from .core.logging_config import setup_logging

# 初始化日志系统
logger = setup_logging()

# ===== 简易内存限流器 =====

class SimpleRateLimiter:
    """基于内存的简单限流器（替代 slowapi，避免 Windows 中文 .env 编码问题）"""

    def __init__(self, requests: int = 100, window: int = 60):
        self.requests = requests   # 窗口内允许的请求数
        self.window = window       # 时间窗口（秒）
        self._store: dict[str, list[float]] = defaultdict(list)

    def _clean(self, key: str, now: float):
        self._store[key] = [t for t in self._store[key] if now - t < self.window]

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        self._clean(key, now)
        return len(self._store[key]) < self.requests

    def hit(self, key: str):
        self._store[key].append(time.time())


rate_limiter = SimpleRateLimiter(requests=100, window=60)
llm_rate_limiter = SimpleRateLimiter(requests=5, window=60)  # LLM 端点专用严格限流


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info(f"启动 {settings.APP_NAME} v{settings.APP_VERSION}")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    os.makedirs(settings.PHOTOS_DIR, exist_ok=True)
    await init_db()
    logger.info("数据库初始化完成")

    # 预热嵌入模型
    if settings.EMBEDDING_PROVIDER == "local":
        import threading
        def warmup():
            from .core.embedder import embedding_service
            _ = embedding_service.embeddings
        threading.Thread(target=warmup, daemon=True).start()

    yield
    logger.info("应用关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== 全局中间件 =====

# LLM 端点路径前缀（需严格限流）
LLM_PATH_PREFIXES = ("/api/resumes/", "/api/skills/gap-analysis", "/api/interview/start", "/api/ai/")


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """全局限流 + LLM 端点严格限流"""
    client_ip = request.client.host if request.client else "unknown"

    # LLM 端点: 5 req/min
    if any(request.url.path.startswith(p) for p in LLM_PATH_PREFIXES):
        key = f"llm:{client_ip}"
        if not llm_rate_limiter.is_allowed(key):
            return JSONResponse(
                status_code=429,
                content={"detail": "AI 请求过于频繁，请稍后再试"},
                headers={"Retry-After": "60"},
            )
        llm_rate_limiter.hit(key)

    # 全局: 100 req/min
    if not rate_limiter.is_allowed(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "请求过于频繁，请稍后再试"},
            headers={"Retry-After": "60"},
        )
    rate_limiter.hit(client_ip)

    return await call_next(request)


@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    """为每个请求注入 trace_id 用于全链路追踪"""
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    request.state.trace_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """请求日志 + 耗时追踪"""
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000
    trace_id = getattr(request.state, "trace_id", "-")
    logger.info(f"[{trace_id}] {request.method} {request.url.path} → {response.status_code} ({elapsed:.0f}ms)")
    return response


# ===== Prometheus 指标 =====
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=True)


# ===== 全局异常处理 =====

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未捕获异常: {request.method} {request.url.path} | {type(exc).__name__}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误", "error_type": type(exc).__name__},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    logger.warning(f"参数错误: {request.method} {request.url.path} | {exc}")
    return JSONResponse(status_code=400, content={"detail": str(exc)})


# ===== 注册路由 =====

app.include_router(resumes.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(ai.router)
app.include_router(skills.router)
app.include_router(interview.router)
app.include_router(skill_library.router)
app.include_router(user_profile.router)
app.include_router(auth.router)


@app.get("/api/health")
async def health_check():
    """健康检查（含数据库连接验证）"""
    db_status = "connected"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "provider": settings.EMBEDDING_PROVIDER,
    }
