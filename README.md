# 个人职业知识管家 (Career KB)

基于 AI 的全流程求职助手 — 简历优化、求职追踪、技能分析、面试模拟。

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | FastAPI + LangChain + LangGraph + SQLAlchemy (async) |
| 前端 | React 18 + TypeScript + Tailwind CSS + Vite |
| 向量库 | ChromaDB + BGE-M3 (硅基流动 API) |
| LLM | DeepSeek (对话) + 硅基流动 (嵌入/OCR/语音) |
| 数据库 | PostgreSQL 16 (生产) / SQLite (本地) |
| 部署 | Docker + Docker Compose + Nginx + ngrok |

## 快速开始

### 1. 环境配置

```bash
# 后端环境变量
cp backend/.env.example backend/.env
# 编辑 backend/.env 填入 DEEPSEEK_API_KEY 和 SILICONFLOW_API_KEY
# SECRET_KEY 必须设置固定值（多 worker JWT 签名需要一致）

# Docker 环境变量（ngrok 内网穿透用）
cp .env.example .env
# 编辑 .env 填入 NGROK_AUTHTOKEN 和 NGROK_DOMAIN（可选）
```

### 2. 本地开发

```bash
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
- 前端页面: http://localhost:5173

### 3. Docker 部署（推荐）

```bash
cd D:/lenging/个人职业助手

# 基础启动
docker compose -p career-kb up -d --build

# 含 ngrok 内网穿透
docker compose -p career-kb --profile tunnel up -d
```

启动后访问:
- 前端: http://localhost
- API: http://localhost/api/health
- 外网: https://你的域名.ngrok-free.dev (需 --profile tunnel)

### 4. 内网穿透（ngrok）

```bash
# 1. 注册 ngrok 账号: https://ngrok.com
# 2. 获取 authtoken 和静态域名
# 3. 写入 .env
NGROK_AUTHTOKEN=你的token
NGROK_DOMAIN=你的域名.ngrok-free.dev

# 4. 启动
docker compose -p career-kb --profile tunnel up -d
```

ngrok 免费版提供 1 个静态域名，URL 固定不变。

## 功能模块

### Phase 1: 简历 RAG 库
- 上传简历 (PDF/DOCX/MD) → 智能解析 → 三层分块 → 向量化
- JD 匹配 → 混合检索 (Dense BM25 RRF) → LLM 智能重组 → 事实核查
- 流式 SSE 生成 + 专业 HTML 模板 + WeasyPrint PDF 导出
- 证件照嵌入、技能标签云、两栏布局

### Phase 2: 求职追踪
- Kanban 看板管理投递状态 (12 种状态 + 合法转换验证)
- 7 天无回应 → LangGraph Agent 三路并行分析
- AI 辅助录入 (公司/岗位补全 + JD OCR + 语音转文字)
- 面试反馈 AI 结构化提取

### Phase 3: 技能 Gap 分析
- JD 技术栈权重提取 (重要度百分比)
- 加权 Gap 计分 → 6 维雷达图
- AI 生成分阶段学习路径 (含资源推荐)

### Phase 4: 面试模拟
- 技术/行为/综合三种模式
- LLM 驱动自适应问答 (10 轮)
- 5 维评估报告 (技术/沟通/项目/解决/匹配)
- 多 worker 安全：状态从数据库重建

## 项目结构

```
个人职业助手/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI 路由 (auth, resumes, jds, applications, ai, skills, interview)
│   │   ├── core/         # 核心引擎 (RAG, Agent, LLM, Prompts, Embedder, Retriever, Interview)
│   │   ├── models/       # SQLAlchemy ORM
│   │   ├── services/     # 业务逻辑层
│   │   ├── utils/        # 工具 (状态机, 文件解析)
│   │   └── templates/    # 简历 HTML 模板
│   ├── tests/            # pytest
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/        # 页面组件 (Dashboard, Resume, Restructure, Tracker, Skills, Interview, etc.)
│   │   ├── components/   # 可复用组件 (auth, layout, ui, resume, skills, tracker)
│   │   ├── services/     # API 封装 (axios + SSE 流式)
│   │   └── types/        # TypeScript 类型定义
│   └── package.json
├── docs/
│   └── 问题追溯与技术方案.md
├── docker-compose.yml
├── Dockerfile            # Nginx + 前端构建
├── nginx.conf
├── .env                  # Docker 环境变量 (ngrok)
└── README.md
```

## 环境变量

| 变量 | 位置 | 说明 |
|------|------|------|
| `DEEPSEEK_API_KEY` | `backend/.env` | LLM 对话 (必须) |
| `SILICONFLOW_API_KEY` | `backend/.env` | 向量嵌入/OCR/语音 (必须) |
| `SECRET_KEY` | `backend/.env` | JWT 签名密钥 (必须设固定值) |
| `NGROK_AUTHTOKEN` | `.env` | ngrok 认证 (可选) |
| `NGROK_DOMAIN` | `.env` | ngrok 静态域名 (可选) |

## 测试

```bash
# 后端
cd backend && pytest tests/ -v

# 前端
cd frontend && npx tsc --noEmit
```
