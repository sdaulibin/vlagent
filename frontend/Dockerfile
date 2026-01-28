# ====================================================
# VL Flow Frontend - 离线部署 Dockerfile
# 前置步骤：在联网机器上先运行 npm run build:docker
# ====================================================

# 生产阶段 - 只需要 nginx 和构建产物
FROM nginx:alpine

# 复制本地构建好的静态文件
COPY dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
