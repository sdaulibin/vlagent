# 构建阶段
FROM node:20-alpine AS builder

WORKDIR /app

# 只复制 package.json（不复制 lock 文件）
COPY package.json ./

# 安装依赖（让 npm 重新解析）
RUN npm install

# 调试：检查 vite 是否安装
RUN echo "=== 检查 vite ===" && ls node_modules/vite/bin/ && echo "vite 已安装"

# 复制源码
COPY . .

# 构建
RUN npm run build:docker

# 生产阶段
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
