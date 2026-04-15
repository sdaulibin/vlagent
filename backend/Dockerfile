ARG PYTHON_RUNTIME_IMAGE=harbor.devops.qdb.com/star/python:3.13-bullseye-slim-runtime

# 构建时版本参数（通过 Makefile 传入）
ARG VERSION=0.0.0
ARG COMMIT_ID=unknown

# -----------------------------------------------------------------------------
# 单阶段：运行阶段 (Runtime Stage)
# 构建工作已在 Jenkins Agent 中完成，这里只负责打包
# -----------------------------------------------------------------------------
FROM ${PYTHON_RUNTIME_IMAGE}

# 继承构建时的版本参数
ARG VERSION
ARG COMMIT_ID

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/app/.venv/bin:$PATH" \
    # 版本信息（运行时可访问）
    APP_VERSION=${VERSION} \
    APP_COMMIT_ID=${COMMIT_ID}

WORKDIR /app

# 安装 PDF 处理所需的系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    ghostscript \
    libgl1 \
    libglib2.0-0 \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户运行应用（安全最佳实践）
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# 从 Jenkins Agent 构建好的产物中复制虚拟环境（已在 ci-prepare 阶段生成并清理）
COPY .venv /app/.venv

# 修复 .venv 内的 Python 软链接（Jenkins Agent 里的路径在 Runtime 镜像中不存在）
RUN REAL_PYTHON=$(which python3) && \
    ln -sf "$REAL_PYTHON" /app/.venv/bin/python && \
    ln -sf "$REAL_PYTHON" /app/.venv/bin/python3 && \
    ln -sf "$REAL_PYTHON" /app/.venv/bin/python3.13

# 创建上传、日志、下载目录并设置权限
RUN mkdir -p /app/upload /app/download /app/logs && chown -R appuser:appgroup /app

# 切换到非 root 用户
USER appuser

EXPOSE 8000

# 健康检查配置
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 使用 tini 作为 init 进程
ENTRYPOINT ["/usr/bin/tini", "--"]

# 默认启动命令 (Server: FastAPI)
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
