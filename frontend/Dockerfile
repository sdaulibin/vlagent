# 第一阶段：构建前端应用
FROM harbor.devops.qdb.com/devops/node:lts-bullseye as builder
WORKDIR /app
ARG NPM_REGISTRY
ARG RELEASE_VERSION
ARG ENV_CONFIG
COPY . .
RUN npm config set fetch-timeout 600000 && \
    npm config set registry ${NPM_REGISTRY} && \
    npm install --loglevel verbose || (cat /root/.npm/_logs/*.log && exit 1)
RUN RELEASE_VERSION=${RELEASE_VERSION} npm run ${ENV_CONFIG}

# 第二阶段：配置OpenResty
FROM harbor.devops.qdb.com/devops/openresty:1.17.8.2-lua-4
# 复制前端构建产物
COPY --from=builder /app/dist /usr/local/openresty/nginx/html/

# 复制 Nginx 配置
# RUN mkdir -p /usr/local/openresty/nginx/conf/conf.d
# COPY nginx.conf /usr/local/openresty/nginx/conf/conf.d/default.conf

EXPOSE 8001

CMD ["/usr/local/openresty/bin/openresty", "-g", "daemon off;"]
