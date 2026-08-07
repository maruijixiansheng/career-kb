FROM python:3.12-slim

WORKDIR /app

# 系统依赖 (Pango/Cairo 用于 WeasyPrint, 中文字体用于 PDF, curl 用于健康检查)
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    libpango-1.0-0 libpangocairo-1.0-0 libffi-dev \
    libcairo2 libpangoft2-1.0-0 libgdk-pixbuf-xlib-2.0-0 \
    fonts-noto-cjk \
    && fc-cache -fv

# Python 依赖
ARG EMBEDDING_MODE=api
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 本地嵌入模式: 额外安装 PyTorch + sentence-transformers (~4GB)
# 默认跳过 (API 模式用硅基流动)
RUN if [ "$EMBEDDING_MODE" = "local" ]; then \
    pip install --no-cache-dir \
        torch --index-url https://download.pytorch.org/whl/cpu \
        sentence-transformers==3.* \
        -i https://pypi.tuna.tsinghua.edu.cn/simple ; \
    fi

# 清理编译工具 (节省 ~800MB)
RUN apt-get purge -y build-essential && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# 应用代码
COPY . .
RUN mkdir -p /app/data /app/logs

# Worker 数: 默认 4 (生产多用户), 可通过环境变量覆盖
ENV UVICORN_WORKERS=4

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://127.0.0.1:8000/api/health || exit 1

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS}"]
