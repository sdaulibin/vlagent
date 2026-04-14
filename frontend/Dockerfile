# 第一阶段：构建前端应用
FROM harbor.devops.qdb.com/devops/node:lts-bullseye as builder
WORKDIR /app
ARG NPM_REGISTRY

COPY . .

RUN npm config set fetch-timeout 600000 && \
    npm config set registry ${NPM_REGISTRY} && \
    npm install && \
    npm run build:docker

# 第二阶段：nginx 静态服务
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8001

CMD ["nginx", "-g", "daemon off;"]
