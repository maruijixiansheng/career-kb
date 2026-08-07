# ============================================================
# Career KB — Nginx + 前端静态文件
# 多阶段构建: 前端打包 → Nginx 镜像
# ============================================================

# ===== 阶段 1: 前端构建 =====
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --registry=https://registry.npmmirror.com
COPY frontend/ ./
RUN npm run build

# ===== 阶段 2: Nginx =====
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
