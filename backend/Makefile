# =============================================================================
# 智能文档识别平台 Makefile
# =============================================================================
#
# 使用 `make help` 查看所有可用命令
#
# =============================================================================

# -----------------------------------------------------------------------------
# 变量定义
# -----------------------------------------------------------------------------

# Git 版本信息
HAS_TAG := $(shell git tag -l --points-at HEAD 2>/dev/null | wc -l)
ifeq ($(HAS_TAG), 0)
    BUILD_DATE := $(shell date +%Y%m%d-%H%M%S 2>/dev/null || echo "unknown")
    GIT_TAG := dev-$(BUILD_DATE)
else
    GIT_TAG := $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
endif
GIT_COMMIT := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# 镜像配置
IMAGE_NAME ?= vlagent
TAG ?= $(GIT_TAG)
REGISTRY ?=
FULL_IMAGE_NAME = $(if $(REGISTRY),$(REGISTRY)/$(IMAGE_NAME):$(TAG),$(IMAGE_NAME):$(TAG))

# Python 基础镜像
PYTHON_BUILDER_IMAGE ?= harbor.devops.qdb.com/star/python:3.13-bullseye-uv
PYTHON_RUNTIME_IMAGE ?= harbor.devops.qdb.com/star/vlagent-backend-runtime:1.0

# 应用端口
APP_PORT ?= 8000

# =============================================================================
# 开发环境
# =============================================================================

install:
	pip install uv
	uv sync

dev:
	@echo "🚀 Starting development server..."
	uv run uvicorn main:app --reload --port 8000

staging:
	@echo "🚀 Starting staging server..."
	. .venv/bin/activate && python -m uvicorn main:app --host 0.0.0.0 --port 8000

prod:
	@echo "🚀 Starting production server..."
	. .venv/bin/activate && python -m uvicorn main:app --host 0.0.0.0 --port 8000

# =============================================================================
# Docker 镜像构建 (本地开发用 docker)
# =============================================================================

docker-build:
	@echo "🐳 Building image: $(FULL_IMAGE_NAME)"
	docker build \
		--build-arg PYTHON_RUNTIME_IMAGE=$(PYTHON_RUNTIME_IMAGE) \
		--build-arg VERSION=$(GIT_TAG) \
		--build-arg COMMIT_ID=$(GIT_COMMIT) \
		-t $(FULL_IMAGE_NAME) \
		-f Dockerfile .
	@echo "✅ Image built: $(FULL_IMAGE_NAME)"

docker-run:
	@echo "🚀 Running container..."
	docker run -d --name $(IMAGE_NAME) -p $(APP_PORT):8000 $(FULL_IMAGE_NAME)
	@echo "✅ Container started at http://localhost:$(APP_PORT)"

docker-stop:
	@echo "🛑 Stopping container..."
	docker stop $(IMAGE_NAME) 2>/dev/null || true
	docker rm $(IMAGE_NAME) 2>/dev/null || true
	@echo "✅ Container stopped"

docker-logs:
	docker logs -f $(IMAGE_NAME)

docker-shell:
	docker exec -it $(IMAGE_NAME) /bin/bash

# =============================================================================
# CI/CD 构建 (K8s 环境用 nerdctl)
# =============================================================================

# PyPI 源配置 (内网 Nexus 代理)
# 使用 = 而非 ?=，允许命令行参数覆盖
PIP_INDEX_URL =
PIP_EXTRA_INDEX_URL =
PIP_TRUSTED_HOST =

# Jenkins CI 预构建 - 在 Jenkins Agent Pod 中执行 (拥有完整的 K8s 网络和 CoreDNS)
# 直接在 Agent 里完成依赖下载、编译、安装，生成可移植的 .venv
ci-prepare:
	@echo "📦 CI Prepare: 在 Jenkins Agent 中构建依赖..."
	@echo "📦 PyPI: $(PIP_INDEX_URL)"
	export PIP_INDEX_URL="$(PIP_INDEX_URL)" \
		PIP_EXTRA_INDEX_URL="$(PIP_EXTRA_INDEX_URL)" \
		PIP_TRUSTED_HOST="$(PIP_TRUSTED_HOST)" \
		UV_INDEX_URL="$(PIP_INDEX_URL)" \
		UV_EXTRA_INDEX_URL="$(PIP_EXTRA_INDEX_URL)" \
		UV_PYTHON_PREFERENCE="managed" && \
	rm -f uv.lock && \
	uv lock && \
	uv sync --no-dev
	@echo "🧹 清理 .venv 缓存以减小镜像体积..."
	@find .venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find .venv -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ CI Prepare 完成"

# Jenkins CI 构建镜像 - 纯打包，不需要网络，不需要 PyPI
# .venv 已经在 ci-prepare 阶段由 Jenkins Agent 准备好
ci-build:
	@echo "🐳 CI Build: $(RELEASE_IMAGE)-amd64"
	@echo "📋 Version: $(RELEASE_VERSION)"
	nerdctl build \
		--build-arg PYTHON_RUNTIME_IMAGE=$(PYTHON_RUNTIME_IMAGE) \
		--build-arg VERSION=$(RELEASE_VERSION) \
		--build-arg COMMIT_ID=$(RELEASE_VERSION) \
		-t $(RELEASE_IMAGE)-amd64 \
		-f Dockerfile .
	@echo "✅ Image built: $(RELEASE_IMAGE)-amd64"

# CI 推送镜像 (nerdctl 专用)
ci-push:
	@echo "📤 Pushing: $(RELEASE_IMAGE)-amd64"
	nerdctl --insecure-registry=true push $(RELEASE_IMAGE)-amd64
	@echo "✅ Image pushed"

# CI 导出镜像 (用于生产环境 FTP 传输)
ci-export:
	@echo "📦 Exporting: $(PROJECT_NAME)-$(RELEASE_VERSION).tar"
	nerdctl save -o $(PROJECT_NAME)-$(RELEASE_VERSION).tar $(PRODUCTION_IMAGE)-amd64
	@echo "✅ Image exported"

# CI 导出 Helm Chart
ci-chart:
	@echo "📦 Exporting chart: $(PROJECT_NAME)-$(RELEASE_VERSION)-chart.tar.gz"
	tar -czf $(PROJECT_NAME)-$(RELEASE_VERSION)-chart.tar.gz -C deploy charts/
	@echo "✅ Chart exported"

# =============================================================================
# 清理
# =============================================================================

clean:
	rm -rf .venv __pycache__ .pytest_cache .ruff_cache dist
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# =============================================================================
# 帮助
# =============================================================================

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "🚀 开发环境:"
	@echo "  install          安装依赖"
	@echo "  dev              开发环境启动 (热重载)"
	@echo "  staging          预发布环境启动"
	@echo "  prod             生产环境启动"
	@echo ""
	@echo "🐳 Docker (本地):"
	@echo "  docker-build     构建镜像"
	@echo "  docker-run       运行容器"
	@echo "  docker-stop      停止容器"
	@echo "  docker-logs      查看日志"
	@echo "  docker-shell     进入容器"
	@echo ""
	@echo "🔧 CI/CD (nerdctl):"
	@echo "  ci-prepare       CI 预构建 (在 Jenkins Agent 中构建依赖)"
	@echo "  ci-build         构建镜像 (需要 RELEASE_IMAGE, RELEASE_VERSION)"
	@echo "  ci-push          推送镜像 (需要 RELEASE_IMAGE)"
	@echo "  ci-export        导出镜像为 tar (需要 PROJECT_NAME, RELEASE_VERSION, PRODUCTION_IMAGE)"
	@echo "  ci-chart         导出 Helm Chart"
	@echo ""
	@echo "🧹 清理:"
	@echo "  clean            清理临时文件"

.DEFAULT_GOAL := help

.PHONY: install dev staging prod \
        docker-build docker-run docker-stop docker-logs docker-shell \
        ci-prepare ci-build ci-push ci-export ci-chart \
        clean help
