# ============================================================
# Career KB — Nginx + 前端静态文件
# 多阶段构建: 前端打包 → Nginx 镜像
# ============================================================

# ===== 阶段 1: 前端构建 =====
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json* ./
# 只加 --registry 不够：package-lock.json 里的 resolved 地址仍指向 registry.npmjs.org，
# 在境内会长时间卡住。replace-registry-host=always 会把 lockfile 里的 host 一起替换掉。
RUN npm config set registry https://registry.npmmirror.com \
 && npm config set replace-registry-host always \
 && npm config set fetch-retries 3 \
 && npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ===== 阶段 2: Nginx =====
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
