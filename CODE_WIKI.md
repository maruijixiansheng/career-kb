# Career KB · Code Wiki

> 个人职业知识管家 — 基于 AI 的全流程求职助手
> 本文档为项目代码 Wiki，涵盖整体架构、模块职责、关键类与函数、依赖关系与运行方式。

---

## 目录

1. [项目概览](#1-项目概览)
2. [整体架构](#2-整体架构)
3. [技术栈](#3-技术栈)
4. [项目目录结构](#4-项目目录结构)
5. [后端模块详解](#5-后端模块详解)
6. [前端模块详解](#6-前端模块详解)
7. [关键类与函数](#7-关键类与函数)
8. [核心业务流程](#8-核心业务流程)
9. [依赖关系](#9-依赖关系)
10. [部署与运行方式](#10-部署与运行方式)
11. [测试与 CI](#11-测试与-ci)
12. [环境变量与配置](#12-环境变量与配置)

---

## 1. 项目概览

**Career KB（个人职业知识管家）** 是一套面向求职者的 AI 全流程求职助手，将"简历优化 — 求职追踪 — 技能分析 — 面试模拟"四个核心环节串联起来。

项目按阶段划分为四个 Phase：

| Phase | 名称 | 核心能力 |
|-------|------|----------|
| Phase 1 | 简历 RAG 库 | 上传简历(PDF/DOCX/MD) → 解析 → 三层分块 → 向量化 → JD 匹配 → LLM 智能重组 → 事实核查 → PDF 导出 |
| Phase 2 | 求职追踪 | Kanban 看板（12 种状态 + 合法转换）、7 天无回应 LangGraph 三路并行分析、AI 辅助录入(OCR/语音)、面试反馈结构化提取 |
| Phase 3 | 技能 Gap 分析 | JD 技术栈权重提取、加权 Gap 计分、6 维雷达图、AI 学习路径生成 |
| Phase 4 | 面试模拟 | 技术/行为/综合三种模式、LLM 自适应问答（10 轮）、5 维评估报告、多 worker 安全（状态从 DB 重建） |

---

## 2. 整体架构

### 2.1 部署架构（Docker 模式）

```
浏览器 ──> Nginx (:80) ──> Backend (FastAPI :8000, 多 worker) ──> PostgreSQL (:5432)
              │                       │
              │                       ├──> ChromaDB (向量存储, 持久化文件)
              │                       ├──> DeepSeek API (LLM 对话)
              │                       └──> 硅基流动 API (Embedding / OCR / 语音)
              │
              └──> 前端静态文件 (Vite 构建产物)
              
可选: ngrok → Nginx (内网穿透, --profile tunnel)
```

### 2.2 后端分层架构

```
┌──────────────────────────────────────────────────────────┐
│  HTTP 层 (FastAPI Routers)  app/api/*.py                │
│  - auth / resumes / jobs / applications / ai /          │
│    skills / interview / skill_library / user_profile    │
├──────────────────────────────────────────────────────────┤
│  中间件层  app/main.py                                   │
│  - CORS / 限流 / trace_id / 请求日志 / 全局异常          │
│  - Prometheus 指标  /metrics                           │
├──────────────────────────────────────────────────────────┤
│  业务服务层  app/services/resume_service.py             │
│  - 简历全流程编排: 解析→结构化→分块→向量化             │
├──────────────────────────────────────────────────────────┤
│  核心引擎层 (AI)  app/core/                              │
│  - rag_engine      LangGraph 简历重组编排                │
│  - llm_client      DeepSeek API 封装                    │
│  - embedder        向量化服务 + ChromaDB 封装           │
│  - retriever       Dense+Sparse+RRF 混合检索             │
│  - chunker         中文简历三层分块                      │
│  - interview_agent 面试模拟 Agent                       │
│  - no_response_agent 无回应三路并行分析 Agent            │
│  - skill_gap_agent 技能 Gap 分析 Agent                  │
│  - ai_assistant    公司/岗位补全、OCR、STT              │
│  - pdf_generator   WeasyPrint PDF 渲染                  │
│  - resume_template 专业 HTML 简历模板                    │
│  - prompts         Prompt 模板集中管理                  │
│  - auth (JWT) / deps (依赖注入) / logging_config         │
├──────────────────────────────────────────────────────────┤
│  数据访问层 (ORM)  app/models/                           │
│  - User / Resume / ResumeChunk / JobDescription /       │
│    Application / InterviewSession / Skill / SkillLibrary │
│  base.py: TimestampMixin / UUIDMixin                   │
├──────────────────────────────────────────────────────────┤
│  工具层  app/utils/                                      │
│  - parser (PDF/DOCX/MD) / state_machine / markdown_parser│
├──────────────────────────────────────────────────────────┤
│  基础设施  app/config.py + app/database.py               │
│  - Settings (pydantic-settings)                        │
│  - async engine + async_sessionmaker + Base            │
└──────────────────────────────────────────────────────────┘
```

### 2.3 前端架构

```
main.tsx → BrowserRouter + AuthProvider → App.tsx (路由表)
                                              │
        ┌─────────────────────────────────────┴────────────────────────────────────┐
        │ ProtectedRoute → Layout (Sidebar + Outlet)                            │
        │   /Dashboard /ResumePage /RestructurePage /SkillLibraryPage           │
        │   /TrackerPage /SkillsPage /InterviewPage /UserProfilePage            │
        │   /JDRestructurePage                                                  │
        │                                                                       │
        │ 公开路由: /login /register                                            │
        └────────────────────────────────────────────────────────────────────────┘
                            │
        services/api.ts (axios + SSE 流式 fetch)  ←→  后端 /api/*
        contexts/AuthContext.tsx (用户态、token、登录注册登出)
        types/index.ts (TS 接口定义)
        components/ (auth/layout/skills/tracker/ErrorBoundary)
```

---

## 3. 技术栈

| 层 | 技术 | 说明 |
|---|------|------|
| 后端框架 | FastAPI 0.115 + Uvicorn | 异步、自动 OpenAPI 文档 |
| ORM | SQLAlchemy 2.0 (async) + aiosqlite / asyncpg | 双数据库支持 |
| 迁移 | Alembic 1.14 | 异步迁移 env |
| 向量库 | ChromaDB 0.5 + BGE-M3 | 持久化到本地目录 |
| LLM 框架 | LangChain ≥0.3 + LangGraph ≥0.2 | 状态图编排 |
| LLM 服务 | DeepSeek (deepseek-chat) | 对话 / 结构化解析 / 生成 |
| 嵌入服务 | 硅基流动 SiliconFlow (BGE-M3 1024 维) | 默认 API 模式，可选本地 BGE |
| 中文 NLP | jieba 0.42 | BM25 分词 |
| 文档解析 | PyMuPDF 1.24 / python-docx 1.1 | PDF/DOCX 解析 |
| PDF 渲染 | WeasyPrint ≥65 + Pillow 11 + Jinja2 | HTML→PDF |
| 认证 | python-jose (JWT) + bcrypt | HS256 签名 |
| 监控 | prometheus-fastapi-instrumentator 7 | /metrics 指标 |
| 测试 | pytest 8 + pytest-asyncio + httpx | 异步测试 |
| 前端框架 | React 18 + TypeScript 5.5 + Vite 5 | SPA |
| 前端路由 | react-router-dom 6 | 嵌套路由 + 受保护路由 |
| 前端状态 | zustand 4 + AuthContext | 轻量全局状态 |
| 前端 UI | Tailwind CSS 3.4 + lucide-react | 图标 + 工具类 |
| 前端可视化 | recharts 2.12 + @uiw/react-md-editor | 雷达图 / Markdown 编辑 |
| HTTP 客户端 | axios 1.7 + fetch (SSE) | 流式与非流式分开 |
| 部署 | Docker + Docker Compose + Nginx + ngrok | 多容器编排 |
| 数据库 | PostgreSQL 16 (生产) / SQLite (本地) | 双模式自动切换 |

---

## 4. 项目目录结构

```
个人职业助手/
├── backend/
│   ├── alembic/                      # 数据库迁移
│   │   ├── env.py                    # 异步迁移环境
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 55003edece2d_initial.py
│   ├── alembic.ini
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI 入口 + 中间件 + 路由注册
│   │   ├── config.py                 # Settings (pydantic-settings)
│   │   ├── database.py               # 异步引擎 + 会话 + init_db
│   │   ├── schemas.py                # Pydantic 请求/响应模型
│   │   ├── api/                      # FastAPI 路由
│   │   │   ├── __init__.py
│   │   │   ├── auth.py               # 注册/登录/me/改密
│   │   │   ├── resumes.py            # 简历 CRUD + 重组 + PDF
│   │   │   ├── jobs.py               # JD CRUD + 自动解析
│   │   │   ├── applications.py       # 投递 + 状态机 + 无回应分析
│   │   │   ├── ai.py                 # 公司/岗位补全 + OCR + STT
│   │   │   ├── skills.py             # 技能 Gap 分析
│   │   │   ├── interview.py          # 面试模拟会话
│   │   │   ├── skill_library.py      # 技能库 CRUD
│   │   │   └── user_profile.py       # 用户基本信息 CRUD
│   │   ├── core/                     # 核心引擎
│   │   │   ├── __init__.py
│   │   │   ├── rag_engine.py         # LangGraph 简历重组编排
│   │   │   ├── llm_client.py         # DeepSeek (LangChain ChatOpenAI)
│   │   │   ├── embedder.py           # 嵌入服务 + Chroma VectorStore
│   │   │   ├── retriever.py          # Dense + Sparse + RRF 混合检索
│   │   │   ├── chunker.py            # 中文简历三层分块
│   │   │   ├── interview_agent.py    # 面试模拟 Agent
│   │   │   ├── no_response_agent.py  # 无回应三路并行分析 (LangGraph)
│   │   │   ├── skill_gap_agent.py    # 技能 Gap 分析 (LangGraph)
│   │   │   ├── ai_assistant.py       # 公司/岗位补全 + OCR + STT
│   │   │   ├── pdf_generator.py      # WeasyPrint PDF 渲染 + 单页回缩
│   │   │   ├── resume_template.py    # 专业 HTML 简历模板
│   │   │   ├── prompts.py            # Prompt 模板集中管理
│   │   │   ├── auth.py               # JWT + bcrypt
│   │   │   ├── deps.py               # get_current_user / get_optional_user
│   │   │   └── logging_config.py     # 结构化日志 + 文件轮转
│   │   ├── models/                   # SQLAlchemy ORM
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # Base / TimestampMixin / UUIDMixin
│   │   │   ├── user.py
│   │   │   ├── resume.py             # Resume + ResumeChunk
│   │   │   ├── job.py                # JobDescription + JDRequirement
│   │   │   ├── application.py        # Application + ApplicationStatusHistory
│   │   │   ├── interview.py          # InterviewSession/Message/Report
│   │   │   ├── skill.py              # Skill/ResumeSkill/JDSkill/SkillGapAnalysis
│   │   │   ├── skill_library.py      # SkillLibraryEntry
│   │   │   ├── user_profile.py       # UserProfile (单例)
│   │   │   └── evaluation.py         # GenerationEval + EvalMetric
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── resume_service.py     # 简历全流程业务逻辑
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── parser.py             # PDF/DOCX/MD/TXT 解析
│   │   │   ├── markdown_parser.py    # 章节 Markdown 解析
│   │   │   └── state_machine.py      # 求职状态机
│   │   └── templates/
│   │       └── resume_template.html  # (已迁移到 resume_template.py)
│   ├── tests/                        # pytest 测试套件
│   │   ├── test_api.py
│   │   ├── test_chunker.py
│   │   ├── test_llm_client.py
│   │   ├── test_parser.py
│   │   ├── test_rag_engine.py
│   │   ├── test_retriever.py
│   │   └── test_state_machine.py
│   ├── .env.example
│   ├── .dockerignore
│   ├── Dockerfile                    # Python 3.12 + WeasyPrint 依赖
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.tsx                  # 入口 (AuthProvider + BrowserRouter)
│   │   ├── App.tsx                   # 路由表
│   │   ├── index.css                 # Tailwind 入口
│   │   ├── pages/                    # 页面组件
│   │   │   ├── Dashboard.tsx
│   │   │   ├── LoginPage.tsx / RegisterPage.tsx
│   │   │   ├── ResumePage.tsx
│   │   │   ├── RestructurePage.tsx / JDRestructurePage.tsx
│   │   │   ├── SkillLibraryPage.tsx
│   │   │   ├── TrackerPage.tsx
│   │   │   ├── SkillsPage.tsx
│   │   │   ├── InterviewPage.tsx
│   │   │   └── UserProfilePage.tsx
│   │   ├── components/
│   │   │   ├── ErrorBoundary.tsx
│   │   │   ├── auth/ProtectedRoute.tsx
│   │   │   ├── layout/{Layout.tsx, Sidebar.tsx}
│   │   │   ├── skills/{GapRadarChart, LearningPath, TechStackChart}.tsx
│   │   │   └── tracker/{ApplicationCard, EnhancedCreateForm,
│   │   │                InterviewFeedback, KanbanColumn,
│   │   │                NoResponseModal, VoiceInput}.tsx
│   │   ├── contexts/AuthContext.tsx   # 全局认证上下文
│   │   ├── services/api.ts            # axios + SSE 封装
│   │   └── types/index.ts             # TypeScript 接口
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts                 # 端口 5173 + /api 代理
│   ├── tailwind.config.js
│   └── postcss.config.js
├── docs/
│   ├── 技术栈文档.md
│   └── 问题追溯与技术方案.md
├── .github/workflows/ci.yml          # CI: 后端测试 + 前端 tsc + docker build
├── Dockerfile                        # 多阶段: 前端构建 → Nginx
├── nginx.conf                        # 反向代理 + 静态文件
├── docker-compose.yml                # postgres + backend + nginx + ngrok(profile)
├── .env.example                      # ngrok 配置
├── .gitignore
└── README.md
```

---

## 5. 后端模块详解

### 5.1 应用入口 [main.py](file:///workspace/backend/app/main.py)

FastAPI 应用入口，承担**应用生命周期、中间件、限流、监控、异常处理、路由注册**等职责。

**关键组件**：
- `SimpleRateLimiter`：自实现的内存限流器（替代 slowapi，规避 Windows 中文 .env 编码问题）。维护两个实例：
  - `rate_limiter`：全局 100 req/min
  - `llm_rate_limiter`：LLM 端点专用 5 req/min
- `lifespan(app)`：异步生命周期管理器。启动时创建 `UPLOAD_DIR`/`CHROMA_PERSIST_DIR`/`PHOTOS_DIR`，调用 `init_db()`，本地嵌入模式下异步预热嵌入模型。
- 三层中间件：
  - `rate_limit_middleware`：LLM 端点（`/api/resumes/`、`/api/skills/gap-analysis`、`/api/interview/start`、`/api/ai/`）严格限流；全局 100 req/min；超限返回 429 + `Retry-After`。
  - `add_trace_id`：注入 `X-Request-ID`（取请求头或生成 12 位 hex），写入 `request.state.trace_id` 与响应头。
  - `log_requests`：记录方法、路径、状态码、耗时。
- `Instrumentator`：暴露 Prometheus 指标于 `/metrics`。
- 全局异常处理：`Exception → 500`、`ValueError → 400`。
- 路由注册：`resumes`、`jobs`、`applications`、`ai`、`skills`、`interview`、`skill_library`、`user_profile`、`auth`。
- `GET /api/health`：健康检查，验证 DB 连接（`SELECT 1`）。

### 5.2 配置管理 [config.py](file:///workspace/backend/app/config.py)

`Settings(BaseSettings)` 全局配置类，从 `.env` 读取，关键参数：

| 分组 | 字段 | 默认值 |
|------|------|--------|
| 应用 | `APP_NAME` / `APP_VERSION` / `DEBUG` | 个人职业知识管家 / 0.1.0 / True |
| 认证 | `SECRET_KEY` / `ACCESS_TOKEN_EXPIRE_HOURS` | 空（自动生成随机）/ 24 |
| 数据库 | `DATABASE_TYPE` (sqlite\|postgres) + PG 连接参数 | sqlite |
| 向量 | `CHROMA_PERSIST_DIR` | ../data/chroma |
| 上传 | `UPLOAD_DIR` / `MAX_UPLOAD_SIZE_MB` / `PHOTOS_DIR` / `MAX_PHOTO_SIZE_MB` | ../data/uploads / 10 / ../data/photos / 2 |
| LLM | `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `LLM_MODEL_SIMPLE` / `LLM_MODEL_POWERFUL` | deepseek-chat / deepseek-chat |
| 嵌入 | `EMBEDDING_PROVIDER` (local\|api) / `EMBEDDING_MODEL` / `SILICONFLOW_*` / `RERANKER_MODEL` | api / BAAI/bge-small-zh-v1.5 / BAAI/bge-m3 |
| RAG | `RAG_TOP_K_RETRIEVAL` / `RAG_TOP_K_RERANK` / `CHUNK_MAX_CHARS` / `CHUNK_TARGET_CHARS` | 15 / 8 / 800 / 400 |
| LangChain | `LANGCHAIN_PROJECT` | career-kb |

`model_post_init`：根据 `DATABASE_TYPE` 动态构建 `DATABASE_URL`（postgres 用 `postgresql+asyncpg://`，sqlite 用 `sqlite+aiosqlite://`）。

### 5.3 数据库 [database.py](file:///workspace/backend/app/database.py)

- `engine = create_async_engine(...)`：异步引擎，sqlite 关闭 `check_same_thread`。
- `async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)`：**关键** `expire_on_commit=False`，配合 Python 端时间戳，避免 commit 后访问 ORM 属性触发 greenlet lazy load。
- `Base(DeclarativeBase)`：ORM 基类。
- `get_db()`：FastAPI 依赖，yield session 后关闭。
- `init_db()`：`create_all` + 自动迁移缺失的 `user_id` 列（兼容历史表结构，sqlite 用 `PRAGMA table_info`、postgres 用 `information_schema.columns`）。

### 5.4 API 路由层 [app/api/](file:///workspace/backend/app/api)

所有路由均以 `/api` 前缀挂载，依赖注入 `get_current_user`（强制认证）或 `get_optional_user`（兼容旧版）。

#### 5.4.1 [auth.py](file:///workspace/backend/app/api/auth.py) — 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册，bcrypt 哈希密码，签发 JWT |
| POST | `/api/auth/login` | 登录，验证密码后签发 JWT |
| GET | `/api/auth/me` | 获取当前登录用户（需 Bearer） |
| POST | `/api/auth/change-password` | 修改密码（验证旧密码） |

#### 5.4.2 [resumes.py](file:///workspace/backend/app/api/resumes.py) — 简历管理
- `POST /api/resumes/upload`：上传 PDF/DOCX/MD/TXT + 可选证件照，调用 `resume_service.upload_and_process` 完成全流程。
- `GET /api/resumes`：列表（按 `user_id` 过滤）。
- `GET /api/resumes/{id}` / `/{id}/chunks`：详情与分块。
- `DELETE /api/resumes/{id}`：删除（含向量与索引）。
- `POST /api/resumes/save-generated`：保存 LLM 生成的简历。
- `GET /api/resumes/{id}/photo`：获取证件照。
- `GET|POST /api/resumes/{id}/styled`：生成专业排版 HTML（GET 用 query 传内容，POST 用 body）。
- `POST /api/resumes/{id}/generate-pdf`：渲染 PDF 下载，文件名 `姓名-岗位简历.pdf`，UTF-8 编码。
- `POST /api/resumes/smart-restructure`：**智能重组**（跨所有简历+技能库检索，扬长避短）。
- `POST /api/resumes/{id}/restructure`：基于单简历重组（非流式）。
- `POST /api/resumes/{id}/restructure/stream`：**SSE 流式重组**。

辅助函数：`_get_profile_header`（从 UserProfile 构建简历头部）、`_strip_static_sections`（剥离 LLM 重复输出的静态章节）、`_move_summary_to_end`（强制个人总结置末）。

#### 5.4.3 [jobs.py](file:///workspace/backend/app/api/jobs.py) — JD 管理
CRUD + 创建时异步调用 `rag_engine.parse_jd` 提取结构化需求。

#### 5.4.4 [applications.py](file:///workspace/backend/app/api/applications.py) — 求职追踪
- 投递 CRUD + `/stats` 统计（按状态分组 + 转化率）。
- `POST /{id}/transition`：执行状态转换（带 `StateMachine` 验证 + 历史记录）。
- `POST /{id}/no-response-analysis`：触发 LangGraph Agent 三路并行分析。
- `POST /{id}/interview-feedback`：保存面试反馈 + AI 提取关键点。
- `GET /{id}/timeline`：状态变更时间线。

#### 5.4.5 [ai.py](file:///workspace/backend/app/api/ai.py) — AI 辅助录入
公司补全、岗位补全、JD OCR（硅基流动 PaddleOCR-VL-1.5）、语音转文字。

#### 5.4.6 [skills.py](file:///workspace/backend/app/api/skills.py) — 技能 Gap 分析
- `GET /skills/jd/{jd_id}/tech-stack`：获取 JD 加权技术栈。
- `POST /skills/gap-analysis`：执行 Gap 分析（调用 `skill_gap_agent`）+ 保存记录。
- `GET /skills/gap-analysis`：历史记录列表。

#### 5.4.7 [interview.py](file:///workspace/backend/app/api/interview.py) — 面试模拟
- `POST /api/interview/start`：开始会话，初始化 Agent，生成第一题。
- `POST /api/interview/{id}/respond`：处理回答，**从 DB 重建状态**（多 worker 安全），返回下一题或最终报告。
- `GET /api/interview/{id}/report`：获取报告。
- `GET /api/interview/sessions`：会话历史。

#### 5.4.8 [skill_library.py](file:///workspace/backend/app/api/skill_library.py) — 技能库 CRUD
手动添加技术栈/项目/实习条目，写入 DB + 向量化到 `skill_library` collection（按 `user_id` 隔离），并失效 BM25 缓存。

#### 5.4.9 [user_profile.py](file:///workspace/backend/app/api/user_profile.py) — 用户基本信息
单例 CRUD：`GET` 不存在则自动创建空记录；`PUT` 仅更新传入字段。

### 5.5 核心引擎层 [app/core/](file:///workspace/backend/app/core)

#### 5.5.1 [rag_engine.py](file:///workspace/backend/app/core/rag_engine.py) — RAG 编排引擎

基于 **LangGraph StateGraph** 的简历重组编排，是项目核心差异化能力。

**LangGraph 状态图（`RAGState` TypedDict）节点**：

| 节点 | 函数 | 职责 |
|------|------|------|
| `parse_jd` | `_parse_jd_node` | LLM 解析 JD 为结构化需求（带缓存 `_jd_cache`） |
| `generate_queries` | `_generate_queries_node` | 基于 JD 需求生成多查询（岗位/领域/技能/关键词锚点） |
| `retrieve` | `_retrieve_node` | 调 `retriever.retrieve` 混合检索 |
| `format_chunks` | `_format_chunks_node` | 格式化为 LLM 可读文本 |
| `restructure` | `_restructure_node` | LLM 重组简历（非流式） |
| `extract_analysis` | `_extract_analysis_node` | 分离 `<analysis>` 标签 |
| `fact_check` | `_fact_check_node` | LLM 事实核查 |

边：`parse_jd → generate_queries → retrieve → format_chunks → restructure → extract_analysis → fact_check → END`。

**`RAGEngine` 对外接口**（保持迁移前兼容）：
- `parse_jd(jd_text)` → dict（带缓存）
- `structure_resume(raw_text)` → dict
- `generate_queries(jd_requirements)` → list[str]（含领域锚点，避免跨领域误匹配）
- `retrieve_chunks(resume_id, jd_requirements, top_k)` → list[dict]
- `restructure_resume(...)` → str（非流式）
- `restructure_resume_stream(...)` → AsyncIterator[dict]（**流式**，yield `progress`/`content`/`complete`/`fact_check_result`/`error`）
- `fact_check(original_chunks_text, generated_resume)` → dict
- `full_pipeline(...)` → dict（默认直接执行；`use_graph=True` 走 LangGraph）
- `filter_by_relevance(jd_requirements, candidates)` → list[dict]：**LLM 相关性把关**，分离经历类（project/work/internship）与非经历类，LLM 判断经历是否与 JD 方向一致。
- `retrieve_from_all_sources(jd_requirements, user_id, top_k)`：跨用户所有简历+技能库检索（**用户隔离**，只扫 DB 中该用户的 collection）。
- `smart_restructure_pipeline(...)`：**智能重组**，扬长避短，输出格式化纯文本。
- `generate_pdf_siliconflow(content, title)`：调硅基流动大模型生成 HTML。

#### 5.5.2 [llm_client.py](file:///workspace/backend/app/core/llm_client.py) — LLM 客户端

`LLMClient` 封装 **DeepSeek API**（基于 LangChain `ChatOpenAI` 兼容接口）。

- 双 LLM 实例：`_simple_llm`（简单任务）/ `_powerful_llm`（复杂任务）。
- `chat(system_prompt, user_message, model, temperature, max_tokens)` → str：同步聊天，**写入审计日志**（估算 token + 成本，输出到 `career-kb.llm-audit` logger）。
- `chat_json(...)` → dict：在 `chat` 基础上强制 JSON 输出，**多模式提取**（剥离 markdown 代码块、正则匹配对象/数组、嵌套容错）。
- `chat_stream(...)` → AsyncIterator[str]：流式逐 token 返回。

全局单例 `llm_client = LLMClient()`。

#### 5.5.3 [embedder.py](file:///workspace/backend/app/core/embedder.py) — 嵌入与向量存储

**双模式嵌入服务**（抽象基类 `BaseEmbeddingService`）：
- `LocalEmbeddingService`：本地 BGE（`HuggingFaceEmbeddings`），延迟加载，GPU/CPU 自动选择。
- `APIEmbeddingService`：硅基流动 `OpenAIEmbeddings`，默认 BGE-M3（1024 维）。
- `create_embedding_service()`：工厂函数，按 `EMBEDDING_PROVIDER` 创建实例，API key 缺失自动回退本地。

**`VectorStore`**（ChromaDB 封装）：
- `_get_chroma(collection_name)`：缓存 LangChain Chroma 实例，避免重复创建冲突；已存在则不传 `collection_metadata`，新建用 `cosine` 距离。
- `add_chunks(collection_name, chunks)`：批量添加分块（**核心字段序列化到 metadata**：`id`/`section_type`/`section_title`/`chunk_index`）。
- `search(collection_name, query, top_k, where_filter)`：相似度搜索，距离 → 相似度转换。
- `add_skill_library_entry(entries)`：技能库专用方法（不依赖 Chunk dataclass）。
- `delete_collection` / `collection_exists`。

全局单例 `embedding_service` + `vector_store`。

#### 5.5.4 [retriever.py](file:///workspace/backend/app/core/retriever.py) — 混合检索器

**Dense + Sparse + RRF 融合 + 章节加权**。

- `BM25Scorer`：自实现 BM25（jieba 分词），参数 `k1=1.5, b=0.75`。
- `JiebaBM25Retriever` / `ChromaRetriever`：LangChain `BaseRetriever` 兼容封装。
- `reciprocal_rank_fusion(dense, sparse, k=60)`：RRF 融合，`RRF_score(d) = Σ 1/(k + rank_i(d))`。
- `reciprocal_rank_fusion_docs(doc_lists, k=60)`：LangChain Document 版本。

**`HybridRetriever`**（核心）：
- `retrieve(collection_name, queries, ...)`：
  1. BM25 索引按需重建（重启后丢失，从 DB 重建；技能库按 `user_id` 分 key）。
  2. 章节加权（默认 work=1.5/project=1.3/skill=1.2，basic_info=0.6 等）。
  3. 用户隔离：dense 用 `where_filter={"user_id": user_id}`，BM25 按 `skill_library:{user_id}` 分 key。
  4. 多查询并行检索 → RRF 融合 → 章节加权重排。
  5. **跨领域惩罚**：JD 提供的 `irrelevant_keywords` 或静态黑名单（YOLO/ROS/STM32 等机器人/嵌入式/医学影像方向），命中且 query 不含该词时 `*0.2` 惩罚。
  6. 宽松相关性阈值（`max_score * 0.15`，小集合不过度裁剪）。
- `retrieve_multi_collection(...)`：跨多 collection（简历+技能库）联合检索。
- `_infer_section_type(doc)`：从 metadata/内容推断章节类型（兼容旧 chunks）。
- `list_resume_collections()`：从 ChromaDB 列出所有简历 collection。

全局单例 `retriever = HybridRetriever()`。

#### 5.5.5 [chunker.py](file:///workspace/backend/app/core/chunker.py) — 简历分块器

**三层分块策略**：
- L1（粗粒度/章节级）：整章保留作为后备上下文，不参与向量检索。
- L2（中粒度/条目级）：单条工作/项目/教育经历，**检索主力**。
- L3（细粒度/职责级）：L2 超 800 字时按职责点拆分，通过 `parent_chunk_id` 关联回溯。

**核心原则**：章节为天然边界、工作条目为原子单元（≤800 字不拆）、中文目标 300-500 字。

`SECTION_PATTERNS`：8 类章节关键词识别（basic_info/education/work/project/skill/certificate/self_evaluation/language）。

**`Chunk` dataclass**：`id`/`section_type`/`section_title`/`chunk_index`/`content`/`metadata`/`token_count`/`parent_chunk_id`。

**`ResumeChunker.chunk(structured_data)`**：对 LLM 结构化 JSON 分块，逐章节处理（基本信息/自评/工作经历/项目/教育/技能/证书），超长工作经历拆 L3 子 chunk。

`detect_sections(raw_text)` + `_match_section_title(text)`：基于规则的章节边界检测（LLM 解析前预分段）。

#### 5.5.6 [interview_agent.py](file:///workspace/backend/app/core/interview_agent.py) — 面试 Agent

`InterviewAgent` **无状态**设计（所有状态从 DB 重建，解决多 worker 不同步）。

- `init_session(...)`：初始化会话（公司/职位/JD/简历/模式/难度），模式映射：technical/behavioral/mixed；难度映射题数（easy=6/medium=10/hard=12）。
- `load_state_from_db(session_id)`：**从 DB 重建状态**（InterviewSession + InterviewMessage + JobDescription + Resume）。
- `generate_question(session_id, state)`：LLM 生成下一题（`temperature=0.7`），失败回退"请简单介绍你自己"。
- `process_answer(session_id, answer, state)`：记录候选人回答，达到 `max_questions` 返回 `finished`，否则 LLM 生成简短反馈。
- `generate_report(session_id, state)`：LLM 生成 5 维评估报告 + `_generate_model_answers` 为每个面试官问题生成专业参考答案。

全局单例 `interview_agent = InterviewAgent()`。

#### 5.5.7 [no_response_agent.py](file:///workspace/backend/app/core/no_response_agent.py) — 无回应分析 Agent

基于 **LangGraph StateGraph**，三节点：
1. `load_context`：验证公司/职位/天数。
2. `parallel_analyze`：**`asyncio.gather` 三路并行 LLM 调用**（`return_exceptions=True` 容错）：
   - 原因分析（`NO_RESPONSE_ANALYZE_*`）
   - 跟进建议（`NO_RESPONSE_FOLLOWUP_*`）
   - 策略建议（`NO_RESPONSE_SUGGEST_*`）
3. `merge`：合并三路结果为综合摘要。

对外 `NoResponseAgent.analyze(application_id, company, position, jd_text, resume_summary, days_since_apply)` → dict。

#### 5.5.8 [skill_gap_agent.py](file:///workspace/backend/app/core/skill_gap_agent.py) — 技能 Gap Agent

基于 **LangGraph StateGraph**，三节点：
1. `extract_jd_skills`：LLM 从 JD 提取加权技术栈。
2. `format_resume_skills`：从结构化简历提取技能矩阵（基本信息/技能/工作技术栈/项目技术栈）。
3. `analyze_gap`：LLM 加权对比 + 生成学习路径。

`SkillGapAgent.analyze(...)` + `extract_jd_skills(jd_text, jd_requirements)`（JD 上传时单独调用）。

#### 5.5.9 [ai_assistant.py](file:///workspace/backend/app/core/ai_assistant.py) — AI 辅助

- `autocomplete_company(company_name)`：公司 → 行业/规模/简介。
- `autocomplete_position(position_name, industry)`：岗位 → 技能/职责/薪资。
- `extract_interview_feedback(company, position, feedback)`：面试反馈结构化提取。
- `ocr_jd(image_base64)`：JD 截图 OCR（PaddlePaddle/PaddleOCR-VL-1.5），**自动压缩超 2MB 图片**（PIL 缩放到 1920px 宽 + JPEG quality=75）。
- `speech_to_text(audio_base64)`：语音转文字（FunAudioLLM/SenseVoiceSmall）。

#### 5.5.10 [pdf_generator.py](file:///workspace/backend/app/core/pdf_generator.py) — PDF 生成

`PDFGenerator.generate(markdown, photo_path, structured_data)`：
1. **渲染-测量-回缩循环**：内容溢出且第二页不足半页时，逐级降字号回缩到一页（步长 -2%，下限 -25%）。
2. 使用与预览相同的 HTML 模板（`resume_template.generate_resume_html`）。
3. WeasyPrint 渲染 HTML → PDF。

辅助：`_resolve_scale`（测量溢出）、`_strip_min_height`（剥离 `min-height: 297mm` 测量自然高度）、`_page_content_height`（页内容高度）。

#### 5.5.11 [resume_template.py](file:///workspace/backend/app/core/resume_template.py) — HTML 模板

`generate_resume_html(content, photo_path, structured_data, scale)`：生成专业排版 HTML（含证件照 base64 嵌入、侧边栏、两栏布局）。`_parse_sections(content)` 解析简历文本为结构化板块（兼容 `##` 和 `【】` 格式）。

#### 5.5.12 [prompts.py](file:///workspace/backend/app/core/prompts.py) — Prompt 模板

集中管理所有 Prompt 常量（双接口：原始字符串 + LangChain `ChatPromptTemplate`），是系统差异化能力的核心：
- `RESUME_STRUCTURE_*`：简历结构化解析（JSON Schema 强约束）。
- `JD_PARSE_*`：JD 解析。
- `RESTRUCTURE_*` / `SMART_RESTRUCTURE_*`：简历重组 / 智能重组（扬长避短）。
- `FACT_CHECK_*`：事实核查。
- `RELEVANCE_FILTER_*`：相关性把关。
- `JD_SKILL_EXTRACT_*` / `SKILL_GAP_*`：技能提取与 Gap 分析。
- `INTERVIEW_*` / `INTERVIEW_FEEDBACK_*`：面试问答与评估。
- `NO_RESPONSE_*`：无回应三路分析。
- `COMPANY_AUTOCOMPLETE_*` / `POSITION_AUTOCOMPLETE_*`：补全。

#### 5.5.13 [auth.py](file:///workspace/backend/app/core/auth.py) — JWT 工具

`create_access_token(user_id)` / `verify_token(token)` / `get_password_hash(password)` / `verify_password(plain, hashed)`。算法 HS256，密钥取 `settings.SECRET_KEY` 或随机生成。

#### 5.5.14 [deps.py](file:///workspace/backend/app/core/deps.py) — 依赖注入

- `get_current_user(credentials, db)`：**强制认证**，Bearer token 解析 → DB 查 User → 不存在/未激活返回 401。
- `get_optional_user(credentials, db)`：**可选认证**，未登录返回 None。

#### 5.5.15 [logging_config.py](file:///workspace/backend/app/core/logging_config.py) — 日志

`setup_logging()` 配置：控制台 + 全量文件（`app.log` 10MB×5 轮转）+ 错误文件（`error.log`）+ LLM 审计文件（`llm_audit.log` 5MB×3）。抑制 chromadb/httpx/openai/sentence_transformers 冗余日志。

### 5.6 ORM 模型层 [app/models/](file:///workspace/backend/app/models)

**[base.py](file:///workspace/backend/app/models/base.py)**：
- `TimestampMixin`：`created_at` / `updated_at`（**Python 端 `datetime.now`**，非 SQL `func.now()`，避免 server-generated 列在 flush 后触发 greenlet lazy load）。
- `UUIDMixin`：`id` String(36) UUID 主键。

| 模型 | 表 | 说明 |
|------|----|----|
| [User](file:///workspace/backend/app/models/user.py) | users | 邮箱+bcrypt 哈希+昵称+is_active |
| [Resume](file:///workspace/backend/app/models/resume.py) | resumes | 简历主表：name/source_*/raw_text/structured_data(JSON)/chunk_count/photo_path/user_id，关联 ResumeChunk（cascade delete-orphan） |
| ResumeChunk | resume_chunks | chroma_id/section_type/chunk_index/content/metadata_json/token_count |
| [JobDescription](file:///workspace/backend/app/models/job.py) | job_descriptions | title/company/raw_text/structured_requirements(JSON)/source_url/user_id |
| JDRequirement | jd_requirements | jd_id/category/name/level/is_required/weight |
| [Application](file:///workspace/backend/app/models/application.py) | applications | jd_id/resume_id/company/position/status(12种)/applied_at/channel/salary_offer/notes/follow_up_notes/interview_feedback/interview_key_points(JSON)/user_id |
| ApplicationStatusHistory | application_status_history | from_status/to_status/comment/changed_at |
| [InterviewSession](file:///workspace/backend/app/models/interview.py) | interview_sessions | jd_id/resume_id/mode/difficulty/interviewer_role/status/started_at/ended_at/user_id |
| InterviewMessage | interview_messages | session_id/role(interviewer\|candidate\|system)/content/sequence |
| InterviewReport | interview_reports | session_id/overall_score/dimension_scores(JSON)/strengths/weaknesses/suggestions |
| [Skill](file:///workspace/backend/app/models/skill.py) | skills | name/category/description |
| ResumeSkill | resume_skills | 关联表：resume_id/skill_id/proficiency/years |
| JDSkill | jd_skills | 关联表：jd_id/skill_id/is_required/weight |
| SkillGapAnalysis | skill_gap_analyses | resume_id/jd_id/gap_result_json/learning_path_json/gap_score/user_id |
| [SkillLibraryEntry](file:///workspace/backend/app/models/skill_library.py) | skill_library | entry_type(skill\|project\|internship\|certificate\|other)/title/content/tags/start_date/end_date/importance(1-5)/is_active/user_id |
| [UserProfile](file:///workspace/backend/app/models/user_profile.py) | user_profile | 单例：name/email/phone/city/current_role/years_of_experience/education/school/major/summary/expected_role/expected_salary/job_status/user_id(unique) |
| [GenerationEval](file:///workspace/backend/app/models/evaluation.py) | generation_evals | resume_id/jd_id/generated_text/human_review/reviewer_notes/pass_through（核心效果度量） |
| EvalMetric | eval_metrics | eval_id/metric_name/metric_value/details_json（自动评估指标） |

### 5.7 业务服务层 [app/services/resume_service.py](file:///workspace/backend/app/services/resume_service.py)

`ResumeService` 简历全流程业务逻辑：

- `upload_and_process(db, file_path, name, photo_path, user_id)` → Resume：
  1. `parse_resume(file_path)` 解析文件。
  2. 创建 Resume 记录。
  3. **LLM 结构化解析**（允许失败，不阻塞流程，失败回退 `{"raw": raw_text}`）。
  4. `chunker.chunk(structured_data)` 智能分块。
  5. **向量化存储**（注入 `user_id` 到 chunk metadata 供检索隔离）。
  6. 保存 ResumeChunk 到 DB。
  7. `retriever.build_bm25_index` 构建 BM25 索引。
- `save_generated_resume(...)`：保存 LLM 生成的 Markdown 简历（同样走全流程）。
- `delete_resume(...)`：删除向量 + BM25 索引 + 照片 + DB 记录。
- `save_photo_from_bytes` / `_save_photo_bytes`：PIL 缩放到 300px 宽 + JPEG quality=85。
- `delete_photo`：删除照片文件。

全局单例 `resume_service = ResumeService()`。

### 5.8 工具层 [app/utils/](file:///workspace/backend/app/utils)

#### [parser.py](file:///workspace/backend/app/utils/parser.py) — 简历解析
- `parse_resume(file_path)`：按扩展名分发（`.pdf`/`.docx`/`.md`/`.markdown`/`.txt`）。
- `parse_pdf`：PyMuPDF 提取文本 + 坐标（x0/y0/x1/y1/font_size/is_bold/page）。
- `parse_docx`：python-docx 提取段落 + 字体/粗体信息。
- `parse_markdown` / `parse_text`。
- `reconstruct_reading_order(paragraphs)`：基于坐标的阅读顺序重建（PDF 双栏布局修复）。

#### [state_machine.py](file:///workspace/backend/app/utils/state_machine.py) — 求职状态机
12 种状态（`applied`/`waiting`/`no_response`/`resume_screening`/`written_test`/`interview_1..3`/`offer`/`accepted`/`rejected`/`withdrawn`）+ `TRANSITIONS` 合法转换映射 + `STATE_LABELS`/`STATE_COLORS`。`StateMachine` 静态方法：`can_transition`/`get_next_states`/`get_label`/`is_terminal`/`transition`/`get_all_states`。

#### [markdown_parser.py](file:///workspace/backend/app/utils/markdown_parser.py) — Markdown 解析
章节感知的 Markdown 解析器，将 LLM 生成的简历 Markdown 解析为 `ParsedResumeSections`（name/target_position/personal_summary/work_experience/project_experience/education/skills/certificates）。

### 5.9 Pydantic 模型 [schemas.py](file:///workspace/backend/app/schemas.py)

请求/响应模型，包括：认证（UserRegisterRequest/UserLoginRequest/ChangePasswordRequest/UserResponse/TokenResponse）、简历（ResumeCreate/ResumeResponse/ResumeDetailResponse/ChunkResponse）、JD（JDCreate/JDResponse/JDDetailResponse）、重组（RestructureRequest/RestructureResponse/GeneratePdfRequest）、投递（ApplicationCreate/Update/Response/Stats/StatusTransitionRequest/ApplicationTimelineEvent/NoResponseAnalysis*）、AI 补全（Company/Position Autocomplete*）、OCR/STT、技能 Gap（GapAnalysis*/JDTechStackResponse）、面试（InterviewStartRequest/RespondRequest/MessageResponse/FeedbackResponse）、用户资料（UserProfileResponse/Update）。

### 5.10 数据库迁移 [alembic/](file:///workspace/backend/alembic)

- [env.py](file:///workspace/backend/alembic/env.py)：异步迁移环境，自动发现所有模型（`from app.models import *`），`target_metadata = Base.metadata`。
- `versions/55003edece2d_initial.py`：初始迁移（applications 表追加 channel/follow_up_notes/interview_feedback/interview_key_points 列）。
- 实际生产中 `init_db()` 的 `create_all` + 自动 `user_id` 列迁移是主要建表路径，Alembic 用于增量结构变更。

---

## 6. 前端模块详解

### 6.1 入口与路由

- [main.tsx](file:///workspace/frontend/src/main.tsx)：`React.StrictMode` + `AuthProvider` + `BrowserRouter` 包裹 `App`。
- [App.tsx](file:///workspace/frontend/src/App.tsx)：路由表。
  - 公开路由：`/login`、`/register`。
  - 受保护路由（`ProtectedRoute` 包 `Layout`）：`/`(Dashboard)、`/profile`、`/resumes`、`/resumes/:id/restructure`、`/skill-library`、`/tracker`、`/skills`、`/interview`、`/jd-restructure/:jdId`。

### 6.2 全局上下文 [contexts/AuthContext.tsx](file:///workspace/frontend/src/contexts/AuthContext.tsx)

`AuthProvider` 管理 `user`/`token`/`isLoading`/`isAuthenticated`。
- 初始化 `useEffect`：从 `localStorage` 取 `access_token`，调 `/api/auth/me` 验证；失败清除。
- `login(email, password)` / `register(...)`：fetch 调 `/api/auth/login|register`，存 token + 设置 user。
- `logout()`：清除 token + user。
- `useAuth()` hook：消费 context。

### 6.3 受保护路由 [components/auth/ProtectedRoute.tsx](file:///workspace/frontend/src/components/auth/ProtectedRoute.tsx)

`isLoading` 显示 spinner；未认证 `<Navigate to="/login" replace />`；已认证渲染 children。

### 6.4 布局 [components/layout/](file:///workspace/frontend/src/components/layout)

- [Layout.tsx](file:///workspace/frontend/src/components/layout/Layout.tsx)：`flex h-screen` + `Sidebar` + `<Outlet/>`。
- [Sidebar.tsx](file:///workspace/frontend/src/components/layout/Sidebar.tsx)：7 项导航（仪表盘/个人信息/简历RAG库/技能库/求职追踪/技能Gap分析/面试模拟）+ 用户信息卡 + 退出登录。版本标识 `v0.2.0 · Phase 2`。

### 6.5 页面 [pages/](file:///workspace/frontend/src/pages)

| 页面 | 对应模块 |
|------|----------|
| Dashboard | 仪表盘（汇总） |
| LoginPage / RegisterPage | 认证 |
| ResumePage | 简历 RAG 库（上传/列表/详情） |
| RestructurePage / JDRestructurePage | 简历重组（流式 SSE + PDF 下载） |
| SkillLibraryPage | 技能库 CRUD |
| TrackerPage | 求职追踪 Kanban + 无回应分析 |
| SkillsPage | 技能 Gap 分析 + 雷达图 + 学习路径 |
| InterviewPage | 面试模拟会话 |
| UserProfilePage | 用户基本信息 |

### 6.6 组件 [components/](file:///workspace/frontend/src/components)

- `ErrorBoundary.tsx`：全局错误边界。
- `skills/GapRadarChart.tsx` / `LearningPath.tsx` / `TechStackChart.tsx`：技能可视化（recharts）。
- `tracker/ApplicationCard.tsx` / `EnhancedCreateForm.tsx` / `InterviewFeedback.tsx` / `KanbanColumn.tsx` / `NoResponseModal.tsx` / `VoiceInput.tsx`：求职追踪组件（Kanban 列、AI 录入表单、无回应分析弹窗、语音输入）。

### 6.7 API 服务 [services/api.ts](file:///workspace/frontend/src/services/api.ts)

axios 实例（`baseURL: '/api'`, `timeout: 60000`）+ 请求拦截器自动附加 JWT + 响应拦截器 401 跳登录。

**两类调用**：
- 普通：axios（简历/JD/投递/AI/技能/面试/技能库/用户资料/改密）。
- **流式**：`restructureResumeStream` 用 `fetch` + `ReadableStream` + `TextDecoder` 手动解析 SSE（`data: ` 行），返回 `AbortController` 支持取消。
- **PDF 下载**：`downloadPdfResume` 用 `fetch` + `blob` + `<a download>`，从 `Content-Disposition` 头解析 UTF-8 文件名。

### 6.8 类型定义 [types/index.ts](file:///workspace/frontend/src/types/index.ts)

TypeScript 接口：Resume/ResumeDetail/ResumeChunk/JobDescription/JDDetail/RestructureRequest/Response/FactCheckResult/Application/ApplicationStats/ApplicationCreate/Update/NoResponseAnalysis*/ApplicationTimelineEvent/Company/PositionAutocompleteResponse/InterviewFeedbackResponse/JDTechStack/GapAnalysisResult/UserProfile/UserProfileUpdate/SkillLibraryEntry。

### 6.9 构建配置

- [vite.config.ts](file:///workspace/frontend/vite.config.ts)：端口 5173，`/api` 代理到 `http://localhost:8000`。
- `tsconfig.json`：严格 TS。
- `tailwind.config.js` + `postcss.config.js`：Tailwind CSS。

---

## 7. 关键类与函数

### 7.1 后端关键类

| 类 | 文件 | 职责 |
|----|------|------|
| `Settings` | config.py | 全局配置 |
| `SimpleRateLimiter` | main.py | 内存限流器 |
| `RAGEngine` | rag_engine.py | 简历 RAG 编排（含 LangGraph） |
| `LLMClient` | llm_client.py | DeepSeek 客户端 |
| `BaseEmbeddingService` / `LocalEmbeddingService` / `APIEmbeddingService` | embedder.py | 嵌入服务抽象与实现 |
| `VectorStore` | embedder.py | ChromaDB 封装 |
| `BM25Scorer` / `JiebaBM25Retriever` / `ChromaRetriever` | retriever.py | 检索组件 |
| `HybridRetriever` | retriever.py | 混合检索器 |
| `Chunk` / `Section` / `ResumeChunker` | chunker.py | 分块数据结构与分块器 |
| `InterviewAgent` | interview_agent.py | 面试模拟 |
| `NoResponseAgent` | no_response_agent.py | 无回应分析 |
| `SkillGapAgent` | skill_gap_agent.py | 技能 Gap 分析 |
| `AIAssistant` | ai_assistant.py | AI 辅助录入 |
| `PDFGenerator` | pdf_generator.py | PDF 生成 |
| `ResumeService` | resume_service.py | 简历业务编排 |
| `StateMachine` | state_machine.py | 求职状态机 |
| `Base` / `TimestampMixin` / `UUIDMixin` | base.py | ORM 基类 |

### 7.2 关键函数

| 函数 | 文件 | 职责 |
|------|------|------|
| `lifespan(app)` | main.py | 应用生命周期 |
| `rate_limit_middleware` | main.py | 限流中间件 |
| `add_trace_id` / `log_requests` | main.py | 中间件 |
| `reciprocal_rank_fusion` / `reciprocal_rank_fusion_docs` | retriever.py | RRF 融合 |
| `detect_sections` / `_match_section_title` | chunker.py | 章节检测 |
| `parse_resume` / `parse_pdf` / `parse_docx` | parser.py | 文件解析 |
| `reconstruct_reading_order` | parser.py | PDF 阅读顺序重建 |
| `create_access_token` / `verify_token` / `get_password_hash` / `verify_password` | auth.py | JWT/密码工具 |
| `get_current_user` / `get_optional_user` | deps.py | 依赖注入 |
| `init_db` / `get_db` | database.py | DB 初始化与会话 |
| `generate_resume_html` | resume_template.py | HTML 模板生成 |
| `setup_logging` | logging_config.py | 日志配置 |
| `create_embedding_service` | embedder.py | 嵌入服务工厂 |

### 7.3 全局单例

`settings`、`engine`、`async_session`、`Base`、`logger`、`rate_limiter`、`llm_rate_limiter`、`app`、`rag_engine`、`llm_client`、`embedding_service`、`vector_store`、`retriever`、`interview_agent`、`no_response_agent`、`skill_gap_agent`、`ai_assistant`、`pdf_generator`、`resume_service`、`_rag_graph`、`_no_response_graph`、`_skill_gap_graph`。

### 7.4 前端关键函数

| 函数 | 文件 | 职责 |
|------|------|------|
| `AuthProvider` / `useAuth` | AuthContext.tsx | 认证上下文 |
| `uploadResume` / `restructureResume` / `restructureResumeStream` / `downloadPdfResume` | api.ts | 简历相关 API |
| `createApplication` / `runNoResponseAnalysis` / `getApplicationTimeline` | api.ts | 投递追踪 |
| `runGapAnalysis` / `getJDTechStack` | api.ts | 技能 Gap |
| `startInterview` / `respondInterview` / `getInterviewReport` | api.ts | 面试模拟 |

---

## 8. 核心业务流程

### 8.1 Phase 1: 简历 RAG 重组流程

```
用户上传简历 (PDF/DOCX/MD)
  ↓ resume_service.upload_and_process
  ├─ parse_resume (parser.py): 文件解析为 raw_text
  ├─ llm_client.chat_json (RESUME_STRUCTURE_*): 结构化为 JSON
  ├─ ResumeChunker.chunk: 三层分块
  ├─ vector_store.add_chunks: Chroma 向量化（注入 user_id）
  ├─ 保存 ResumeChunk 到 DB
  └─ retriever.build_bm25_index: 构建 BM25 索引

用户提交 JD + 选择简历 → 重组
  ↓ rag_engine.smart_restructure_pipeline / full_pipeline
  ├─ parse_jd: LLM 解析 JD（带缓存）
  ├─ retrieve_from_all_sources: 跨用户简历+技能库检索（用户隔离）
  │   └─ retriever.retrieve: Dense + Sparse + RRF + 章节加权 + 跨领域惩罚
  ├─ filter_by_relevance: LLM 相关性把关（过滤跨领域误匹配）
  ├─ llm_client.chat (SMART_RESTRUCTURE_*): 重组简历（扬长避短）
  ├─ 提取 <analysis> 标签
  └─ fact_check: 事实核查

API 层: _get_profile_header + _strip_static_sections + _move_summary_to_end → 最终 Markdown
  ↓
前端: 流式 SSE 预览 → PDF 下载 (pdf_generator + WeasyPrint)
```

### 8.2 Phase 2: 无回应分析流程

```
投递记录 > 7 天无回应
  ↓ POST /api/applications/{id}/no-response-analysis
  ├─ 加载 Application + 关联 JD + Resume 摘要
  └─ no_response_agent.analyze (LangGraph)
      ├─ load_context: 验证输入
      ├─ parallel_analyze: asyncio.gather 三路并行 LLM
      │   ├─ 原因分析 (NO_RESPONSE_ANALYZE_*)
      │   ├─ 跟进建议 (NO_RESPONSE_FOLLOWUP_*)
      │   └─ 策略建议 (NO_RESPONSE_SUGGEST_*)
      └─ merge: 合并综合摘要
```

### 8.3 Phase 3: 技能 Gap 分析流程

```
用户选择 JD + 简历
  ↓ POST /api/skills/gap-analysis
  └─ skill_gap_agent.analyze (LangGraph)
      ├─ extract_jd_skills: LLM 提取 JD 加权技术栈
      ├─ format_resume_skills: 从结构化简历提取技能矩阵
      └─ analyze_gap: LLM 加权对比 + 学习路径
  ↓ 保存 SkillGapAnalysis 记录
前端: 雷达图 + 技术栈分布 + 学习路径展示
```

### 8.4 Phase 4: 面试模拟流程

```
用户开始面试 (JD + 简历 + 模式)
  ↓ POST /api/interview/start
  ├─ 创建 InterviewSession
  ├─ interview_agent.init_session
  ├─ interview_agent.generate_question: LLM 生成第一题
  └─ 保存 InterviewMessage (role=interviewer, sequence=1)

用户回答
  ↓ POST /api/interview/{id}/respond
  ├─ interview_agent.load_state_from_db: 从 DB 重建状态（多 worker 安全）
  ├─ 保存 candidate 消息
  ├─ interview_agent.process_answer: 反馈 / 判断是否结束
  ├─ 未结束: generate_question → 保存 interviewer 消息
  └─ 结束: generate_report (5 维评估 + 参考答案) → 保存 InterviewReport
```

### 8.5 认证流程

```
注册/登录 → bcrypt 哈希/验证 → create_access_token (JWT HS256, 24h)
  ↓ 前端 localStorage 存 access_token
axios 拦截器: 自动附加 Authorization: Bearer <token>
  ↓ 后端 deps.get_current_user: 解析 token → DB 查 User → 401 if 无效
```

---

## 9. 依赖关系

### 9.1 后端内部依赖

```
main.py
  ├─ config.Settings
  ├─ database.init_db / engine
  ├─ api.* (9 个路由)
  │   ├─ core.deps.get_current_user
  │   │   └─ core.auth.verify_token
  │   ├─ services.resume_service
  │   │   ├─ utils.parser.parse_resume
  │   │   ├─ core.llm_client.llm_client
  │   │   ├─ core.chunker.ResumeChunker
  │   │   ├─ core.embedder.vector_store
  │   │   └─ core.retriever.retriever
  │   ├─ core.rag_engine.rag_engine
  │   │   ├─ core.llm_client.llm_client
  │   │   ├─ core.embedder.vector_store
  │   │   ├─ core.retriever.retriever
  │   │   └─ core.prompts.*
  │   ├─ core.pdf_generator.pdf_generator
  │   │   └─ core.resume_template.generate_resume_html
  │   ├─ core.no_response_agent.no_response_agent (LangGraph)
  │   ├─ core.skill_gap_agent.skill_gap_agent (LangGraph)
  │   ├─ core.interview_agent.interview_agent
  │   ├─ core.ai_assistant.ai_assistant
  │   └─ utils.state_machine.StateMachine
  ├─ core.logging_config.setup_logging
  └─ prometheus_fastapi_instrumentator
```

### 9.2 外部服务依赖

| 服务 | 用途 | 必需 |
|------|------|------|
| DeepSeek API | LLM 对话/结构化/生成/面试 | 是（`DEEPSEEK_API_KEY`） |
| 硅基流动 SiliconFlow | Embedding（BGE-M3）/OCR（PaddleOCR-VL-1.5）/语音（SenseVoiceSmall） | 是（`SILICONFLOW_API_KEY`，API 模式） |
| PostgreSQL 16 / SQLite | 关系型数据存储 | 任选其一 |
| ChromaDB（本地文件） | 向量存储 | 是（嵌入式，无需独立服务） |
| ngrok | 内网穿透（可选） | 否（`--profile tunnel`） |

### 9.3 前端依赖（package.json）

- **运行时**：react 18、react-dom、react-router-dom 6、zustand 4、axios、lucide-react、@uiw/react-md-editor、recharts。
- **开发时**：@types/react、@types/react-dom、@vitejs/plugin-react、autoprefixer、postcss、tailwindcss、typescript 5.5、vite 5。

### 9.4 LangGraph 状态图

| 图 | 节点 | 触发 |
|----|------|------|
| `_rag_graph` | parse_jd → generate_queries → retrieve → format_chunks → restructure → extract_analysis → fact_check | `full_pipeline(use_graph=True)` |
| `_no_response_graph` | load_context → parallel_analyze → merge | 无回应分析 |
| `_skill_gap_graph` | extract_jd_skills → format_resume_skills → analyze_gap | 技能 Gap 分析 |

---

## 10. 部署与运行方式

### 10.1 本地开发

```bash
# 后端环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env 填入 DEEPSEEK_API_KEY 和 SILICONFLOW_API_KEY
# SECRET_KEY 必须设置固定值（多 worker JWT 签名需要一致）

# 后端
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# 前端（新开终端）
cd frontend
npm install
npm run dev
```

- API 文档: http://localhost:8000/docs
- 前端页面: http://localhost:5173（Vite 代理 `/api` → 8000）

### 10.2 Docker 部署（推荐）

```bash
# 基础启动
docker compose -p career-kb up -d --build

# 含 ngrok 内网穿透
docker compose -p career-kb --profile tunnel up -d
```

[docker-compose.yml](file:///workspace/docker-compose.yml) 编排 4 个服务：

| 服务 | 镜像/构建 | 端口 | 健康检查 |
|------|----------|------|----------|
| `postgres` | postgres:16-alpine | 内部 5432 | `pg_isready -U career -d career_kb` |
| `backend` | ./backend/Dockerfile (python:3.12-slim + WeasyPrint 依赖) | 内部 8000 | `curl /api/health` |
| `nginx` | ./Dockerfile (node:20-alpine 构建 → nginx:alpine) | 80:80 | `curl /` |
| `ngrok` | ngrok/ngrok:latest（profile: tunnel） | - | `wget /api/tunnels` |

**[backend/Dockerfile](file:///workspace/backend/Dockerfile)** 关键点：
- 系统依赖：Pango/Cairo（WeasyPrint）、fonts-noto-cjk（中文 PDF）、curl（健康检查）。
- `EMBEDDING_MODE=api`（默认）跳过 PyTorch；`local` 模式额外安装 torch + sentence-transformers（~4GB）。
- `UVICORN_WORKERS=4`（生产多用户），可环境变量覆盖。
- 使用清华源加速 pip。

**[Dockerfile](file:///Dockerfile)**（前端）：多阶段 `node:20-alpine` 构建 → `nginx:alpine`。

**[nginx.conf](file:///workspace/nginx.conf)**：
- `/` 静态文件（`try_files` SPA 回退）。
- `/api/` 代理到 `backend:8000`，`proxy_read_timeout 300s`（SSE 长超时）。
- `/docs`、`/redoc`、`/openapi.json` 代理。

启动后访问：
- 前端: http://localhost
- API: http://localhost/api/health
- 外网: https://你的域名.ngrok-free.dev（需 `--profile tunnel`）

### 10.3 内网穿透（ngrok）

```bash
# .env
NGROK_AUTHTOKEN=你的token
NGROK_DOMAIN=你的域名.ngrok-free.dev

docker compose -p career-kb --profile tunnel up -d
```

ngrok 免费版提供 1 个静态域名，URL 固定不变。

---

## 11. 测试与 CI

### 11.1 后端测试 [backend/tests/](file:///workspace/backend/tests)

```bash
cd backend && pytest tests/ -v
```

| 测试文件 | 覆盖 |
|----------|------|
| test_api.py | API 端点集成测试 |
| test_chunker.py | 分块器单元测试 |
| test_llm_client.py | LLM 客户端（JSON 提取等） |
| test_parser.py | 文件解析器 |
| test_rag_engine.py | RAG 引擎 |
| test_retriever.py | 混合检索 + RRF |
| test_state_machine.py | 状态机 |

测试框架：pytest 8 + pytest-asyncio 0.24 + httpx 0.28。

### 11.2 前端类型检查

```bash
cd frontend && npx tsc --noEmit
```

### 11.3 CI [.github/workflows/ci.yml](file:///workspace/.github/workflows/ci.yml)

3 个 Job（`on: push/PR to main`）：
1. `backend-test`：ubuntu-latest + postgres:16-alpine service + Python 3.12 + `pytest tests/ -v`（`DATABASE_TYPE=postgres`，`DEEPSEEK_API_KEY` 来自 secrets）。
2. `frontend-check`：ubuntu-latest + Node 20 + `npm ci` + `npx tsc --noEmit`。
3. `docker-build`：依赖前两者通过，`docker compose build`。

---

## 12. 环境变量与配置

### 12.1 后端 [backend/.env](file:///workspace/backend/.env.example)

| 变量 | 说明 | 必需 |
|------|------|------|
| `DEEPSEEK_API_KEY` | LLM 对话（DeepSeek） | 是 |
| `SILICONFLOW_API_KEY` | 向量嵌入/OCR/语音（硅基流动） | 是（API 模式） |
| `SECRET_KEY` | JWT 签名密钥（**必须设固定值**，多 worker 一致） | 是 |
| `DATABASE_TYPE` | sqlite \| postgres | 否（默认 sqlite） |
| `POSTGRES_*` | PostgreSQL 连接参数 | postgres 模式必需 |
| `EMBEDDING_PROVIDER` | local \| api | 否（默认 api） |
| `EMBEDDING_MODEL` | 本地嵌入模型名 | 否 |
| `SILICONFLOW_EMBEDDING_MODEL` | API 嵌入模型名 | 否（默认 BAAI/bge-m3） |
| `LLM_MODEL_SIMPLE` / `LLM_MODEL_POWERFUL` | LLM 模型名 | 否（默认 deepseek-chat） |
| `RAG_TOP_K_*` / `CHUNK_*` | RAG 与分块参数 | 否 |
| `MAX_UPLOAD_SIZE_MB` / `MAX_PHOTO_SIZE_MB` | 上传大小限制 | 否 |

### 12.2 Docker [.env](file:///workspace/.env.example)

| 变量 | 说明 | 必需 |
|------|------|------|
| `NGROK_AUTHTOKEN` | ngrok 认证 token | 否（仅 `--profile tunnel`） |
| `NGROK_DOMAIN` | ngrok 静态域名 | 否 |

### 12.3 关键设计决策

1. **多 worker 安全**：`SECRET_KEY` 必须固定值；面试 Agent 状态从 DB 重建（非内存）。
2. **用户隔离**：所有检索（dense 用 metadata `where_filter`，BM25 按 `skill_library:{user_id}` 分 key）严格按 user_id 隔离，`retrieve_from_all_sources` 只扫 DB 中该用户的 collection。
3. **异步一致性**：`expire_on_commit=False` + Python 端 `datetime.now`，避免 commit 后访问 ORM 属性触发 greenlet lazy load。
4. **限流**：LLM 端点专用严格限流（5 req/min），全局 100 req/min。
5. **可观测性**：trace_id 全链路追踪 + Prometheus 指标 + LLM 审计日志（含成本估算）。
6. **降级容错**：LLM 结构化解析失败不阻塞流程；BM25 构建失败不影响 Dense 检索；事实核查失败返回默认通过。
7. **PDF 单页优化**：渲染-测量-回缩循环，第二页不足半页时逐级降字号回缩到一页。
8. **跨领域防误匹配**：JD 提取的 `irrelevant_keywords` + 静态黑名单 + LLM 相关性把关三重过滤。

---

## 附录：关键文件索引

### 后端
- 应用入口：[main.py](file:///workspace/backend/app/main.py)
- 配置：[config.py](file:///workspace/backend/app/config.py)
- 数据库：[database.py](file:///workspace/backend/app/database.py)
- RAG 引擎：[rag_engine.py](file:///workspace/backend/app/core/rag_engine.py)
- LLM 客户端：[llm_client.py](file:///workspace/backend/app/core/llm_client.py)
- 嵌入/向量：[embedder.py](file:///workspace/backend/app/core/embedder.py)
- 检索器：[retriever.py](file:///workspace/backend/app/core/retriever.py)
- 分块器：[chunker.py](file:///workspace/backend/app/core/chunker.py)
- 面试 Agent：[interview_agent.py](file:///workspace/backend/app/core/interview_agent.py)
- 无回应 Agent：[no_response_agent.py](file:///workspace/backend/app/core/no_response_agent.py)
- 技能 Gap Agent：[skill_gap_agent.py](file:///workspace/backend/app/core/skill_gap_agent.py)
- AI 辅助：[ai_assistant.py](file:///workspace/backend/app/core/ai_assistant.py)
- PDF 生成：[pdf_generator.py](file:///workspace/backend/app/core/pdf_generator.py)
- 简历模板：[resume_template.py](file:///workspace/backend/app/core/resume_template.py)
- Prompt 模板：[prompts.py](file:///workspace/backend/app/core/prompts.py)
- JWT 工具：[auth.py](file:///workspace/backend/app/core/auth.py)
- 依赖注入：[deps.py](file:///workspace/backend/app/core/deps.py)
- 日志：[logging_config.py](file:///workspace/backend/app/core/logging_config.py)
- 简历服务：[resume_service.py](file:///workspace/backend/app/services/resume_service.py)
- 文件解析：[parser.py](file:///workspace/backend/app/utils/parser.py)
- 状态机：[state_machine.py](file:///workspace/backend/app/utils/state_machine.py)
- ORM 基类：[base.py](file:///workspace/backend/app/models/base.py)
- Pydantic 模型：[schemas.py](file:///workspace/backend/app/schemas.py)

### 前端
- 入口：[main.tsx](file:///workspace/frontend/src/main.tsx)
- 路由：[App.tsx](file:///workspace/frontend/src/App.tsx)
- 认证上下文：[AuthContext.tsx](file:///workspace/frontend/src/contexts/AuthContext.tsx)
- 受保护路由：[ProtectedRoute.tsx](file:///workspace/frontend/src/components/auth/ProtectedRoute.tsx)
- 布局：[Layout.tsx](file:///workspace/frontend/src/components/layout/Layout.tsx) / [Sidebar.tsx](file:///workspace/frontend/src/components/layout/Sidebar.tsx)
- API 服务：[api.ts](file:///workspace/frontend/src/services/api.ts)
- 类型：[index.ts](file:///workspace/frontend/src/types/index.ts)
- Vite 配置：[vite.config.ts](file:///workspace/frontend/vite.config.ts)

### 部署
- Compose：[docker-compose.yml](file:///workspace/docker-compose.yml)
- 后端镜像：[backend/Dockerfile](file:///workspace/backend/Dockerfile)
- 前端镜像：[Dockerfile](file:///workspace/Dockerfile)
- Nginx：[nginx.conf](file:///workspace/nginx.conf)
- CI：[ci.yml](file:///workspace/.github/workflows/ci.yml)
- README：[README.md](file:///workspace/README.md)
