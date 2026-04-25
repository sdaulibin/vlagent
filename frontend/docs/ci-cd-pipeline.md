# VLAgent CI/CD 构建流水线文档

## 1. 整体架构概览

VLAgent 项目采用前后端分离架构，通过共享同一个 Ingress 网关对外提供服务。

```
用户浏览器
    |
    v
Ingress (vlagent.sit.qdb.com)
    |
    +-- /       --> vlagent-frontend Service:8001 (OpenResty 静态服务)
    +-- /api/   --> vlagent-backend Service:8000  (FastAPI 后端)
```

### 环境流转

```
  SIT 环境                    UAT 环境                    生产环境
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ GitLab sit   │         │ GitLab       │         │ FTP 服务器    │
│ 分支         │         │ release/*    │         │ (离线传输)    │
│              │         │ 分支         │         │              │
│ nerdctl build│         │ nerdctl build│         │ nerdctl load │
│      |       │         │      |       │         │      |       │
│ Harbor(内网) │         │ Harbor(内网) │  FTP    │ Harbor(生产) │
│      |       │         │      |       │  ---->  │      |       │
│ helm deploy  │         │ helm deploy  │         │ helm deploy │
│      |       │         │      |       │         │      |       │
│ namespace:   │         │ namespace:   │         │ namespace:   │
│ star-sit     │         │ vl-flow-uat  │         │ vl-flow      │
└──────────────┘         └──────────────┘         └──────────────┘
```

---

## 2. 前端项目构建流水线

### 2.1 项目目录结构

```
vlagent-frontend/
├── Dockerfile                  # 多阶段构建（Node.js 编译 + OpenResty 运行）
├── Dockerfile.20260414         # 离线部署用（预构建 + nginx）
├── Makefile                    # 构建编排
├── Jenkinsfile-k8s-cd-sit     # SIT 流水线
├── Jenkinsfile-k8s-cd-uat     # UAT/生产镜像构建流水线
├── Jenkinsfile-k8s-cd-prd     # 生产部署流水线（无构建）
├── .dockerignore               # Docker 构建排除文件
├── package.json                # 依赖和构建脚本
├── .env.development            # 本地开发环境变量
├── .env.sit                    # SIT 环境变量
├── .env.uat                    # UAT 环境变量
├── .env.production             # 生产环境变量
├── nginx.conf                  # 本地开发用 nginx 配置（未用于生产）
└── deploy/charts/              # Helm Chart
    ├── Chart.yaml
    ├── values.yaml
    └── templates/
        ├── _helpers.tpl
        ├── deployment.yaml
        ├── configmap.yaml
        ├── ingress.yaml
        └── timezone-cm.yaml
```

### 2.2 Dockerfile 分析

**文件：** `Dockerfile`

采用两阶段构建：

```dockerfile
# 第一阶段：构建前端应用
FROM harbor.devops.qdb.com/devops/node:lts-bullseye as builder
WORKDIR /app
ARG NPM_REGISTRY          # npm 私有仓库地址
ARG RELEASE_VERSION       # Git commit ID
ARG ENV_CONFIG            # 构建模式：sit / uat / production
COPY . .
RUN npm config set fetch-timeout 600000 && \
    npm config set registry ${NPM_REGISTRY} && \
    npm install --loglevel verbose || (cat /root/.npm/_logs/*.log && exit 1)
RUN RELEASE_VERSION=${RELEASE_VERSION} npm run ${ENV_CONFIG}

# 第二阶段：配置 OpenResty
FROM harbor.devops.qdb.com/devops/openresty:1.17.8.2-lua-4
COPY --from=builder /app/dist /usr/local/openresty/nginx/html/
EXPOSE 8001
CMD ["/usr/local/openresty/bin/openresty", "-g", "daemon off;"]
```

**构建参数：**

| 参数 | 说明 | 示例值 |
|------|------|--------|
| `NPM_REGISTRY` | npm 私有仓库地址 | `http://10.238.145.145:4873/` |
| `RELEASE_VERSION` | 版本标识 | `a54f898` |
| `ENV_CONFIG` | Vite 构建模式 | `sit` / `uat` / `production` |

**构建流程：**

```
Stage 1 (builder)                    Stage 2 (runtime)
┌─────────────────────┐              ┌─────────────────────┐
│ node:lts-bullseye   │              │ openresty:1.17.8.2   │
│                     │              │                     │
│ 1. COPY 源码        │   dist/      │ 1. COPY dist/ 到    │
│ 2. 设置 npm 仓库    │  ──────>     │    nginx/html/      │
│ 3. npm install      │              │ 2. EXPOSE 8001      │
│ 4. npm run sit      │              │ 3. 启动 openresty   │
│    (vite build)     │              │                     │
└─────────────────────┘              └─────────────────────┘
```

**关键设计决策：**

- **排除 `package-lock.json`**：`.dockerignore` 中排除了 lock 文件，因为 lock 中可能包含外部镜像源（如 `registry.npmmirror.com`）的 resolved URL，在 Docker 容器内无法访问。每次从私有仓库全新解析依赖。
- **`--loglevel verbose`**：详细日志输出，便于定位 npm install 失败的具体包。
- **失败时打印日志**：`|| (cat /root/.npm/_logs/*.log && exit 1)` 在 npm 崩溃时输出完整日志。

### 2.3 Makefile 分析

**文件：** `Makefile`

```makefile
RELEASE_REGISTRY?=harbor.devops.qdb.com/star
RELEASE_VERSION?=$(shell git rev-parse --short HEAD)
RELEASE_IMAGE:=$(RELEASE_REGISTRY)/vlagent-frontend:$(RELEASE_VERSION)

.PHONY: all
all: install build

.PHONY: install
install:
	npm install

.PHONY: install-deps
install-deps:
	npm install

.PHONY: build
build: build-app

.PHONY: build-app
build-app: install-deps
	RELEASE_VERSION=$(RELEASE_VERSION) ENV_CONFIG=$(ENV_CONFIG) npm run $(ENV_CONFIG)

.PHONY: build-vlagent-frontend
build-vlagent-frontend: build-app

.PHONY: clean
clean:
	rm -rf ./dist ./node_modules

.PHONY: release-image.amd64
release-image.amd64: clean
	nerdctl build --build-arg RELEASE_VERSION="$(RELEASE_VERSION)" \
	  --build-arg NPM_REGISTRY="$(NPM_REGISTRY)" \
	  --build-arg ENV_CONFIG="$(ENV_CONFIG)" \
	  -t $(RELEASE_IMAGE)-amd64 .

.PHONY: release-image.arm64
release-image.arm64: clean
	nerdctl build ... # 同上，arm64 架构
```

**核心目标：**

| 目标 | 用途 |
|------|------|
| `all` | 本地开发：install + build |
| `build-vlagent-frontend` | Makefile 内部构建链（被 CI 调用） |
| `release-image.amd64` | CI 使用：clean → nerdctl build |
| `release-image.arm64` | 同上，arm64 架构 |

**变量传递链：**

```
Jenkins 参数 → env vars → make -e → Dockerfile ARG → 构建脚本
```

### 2.4 Jenkinsfile 分析

#### SIT 流水线

**文件：** `Jenkinsfile-k8s-cd-sit`

```
Stage 1: Init
    └── builds.InitSteps()   # 初始化构建环境

Stage 2: Get sit Branches
    └── checkout master → checkout sit   # 获取代码

Stage 3: Get Gitlab Info
    └── 获取 sit 分支的 commit ID

Stage 4: Build Docker Image with nerdctl
    ├── 设置环境变量 (RELEASE_REGISTRY, RELEASE_VERSION, RELEASE_IMAGE)
    ├── make -e release-image.amd64       # 构建 amd64 镜像
    └── nerdctl push ${RELEASE_IMAGE}     # 推送到 Harbor

Stage 5: Helm Deploy Application
    ├── kubectl delete configmap (清理旧 ConfigMap)
    └── helm upgrade --install vlagent-front deploy/charts \
          --namespace star-sit \
          --set image.tag=${COMMIT_ID}-amd64 \
          --set ingress.hosts[0].host=vlagent.devops.qdb.com \
          --set replicaCount=1
```

**关键参数默认值：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `srcUrl` | `http://gitlab.qdccb.cn/star/vlagent-frontend.git` | Git 仓库 |
| `HELM_NS` | `vlagent-frontend-sit` | K8s 命名空间 |
| `ingress` | `nginx-vlagent-frontend-sit` | Ingress 类名 |
| `ingressHost` | `vlagent.devops.qdb.com` | 域名 |
| `NPM_REGISTRY` | `http://10.238.145.145:4873/` | npm 私有仓库 |

#### UAT 流水线

**文件：** `Jenkinsfile-k8s-cd-uat`

与 SIT 的主要区别：

1. **分支选择**：从 `release/*` 分支列表中选择，非自动拉取
2. **双模式运行**（`purpose` 参数）：
   - `uat`：构建 → 推送 Harbor → Helm 部署
   - `production`：构建 → 推送 Harbor → 导出镜像 tar + Chart tar.gz → 上传 FTP
3. **版本号**：`{branchName}-{COMMIT_ID}`（而非纯 commit ID）

```
purpose=uat:                        purpose=production:
  build → push → helm deploy          build → push → tag →
  namespace: vl-flow-uat             export tar → upload FTP
  host: vlagent.qdccb.cn             (不部署，只准备制品)
```

#### PRD 流水线

**文件：** `Jenkinsfile-k8s-cd-prd`

**无构建过程**，纯部署：

```
1. SFTP 下载镜像 tar + Chart tar.gz (从 FTP 服务器)
2. nerdctl load < image.tar
3. nerdctl push 到生产 Harbor
4. 解压 Helm Chart
5. helm upgrade --install
   namespace: vl-flow
   tolerations: env=prd:NoSchedule
   replicas: 2
```

### 2.5 Helm Chart 分析

#### values.yaml 结构

```yaml
fullnameOverride: "vlagent-frontend"

image:
  repository: harbor.devops.qdb.com/star/vlagent-frontend
  tag: "latest"            # 被 Jenkins --set 覆盖

command: ["/usr/local/openresty/bin/openresty"]
args: ["-g", "daemon off;", "-c", "/usr/local/openresty/nginx/conf/nginx.conf"]

config: |                   # OpenResty 完整配置（通过 ConfigMap 注入）
  worker_processes auto;
  events { worker_connections 1024; }
  http {
    server {
      listen 8001;
      root /usr/local/openresty/nginx/html;
      location / { try_files $uri $uri/ /index.html; }
      # ... gzip, 静态资源缓存
    }
  }

ports:
  - containerPort: 8001

service:
  port: 8001

ingress:
  enabled: false            # SIT 由 Jenkins --set 启用

volumeMounts:
  - mountPath: /usr/local/openresty/nginx/conf/nginx.conf
    subPath: nginx.conf      # 从 ConfigMap 挂载 nginx 配置
```

#### 模板文件

| 文件 | 资源 | 说明 |
|------|------|------|
| `deployment.yaml` | Deployment + Service | Pod 反亲和、时区挂载、ConfigMap 挂载 |
| `configmap.yaml` | ConfigMap | 存储 `config` 字段中的 nginx.conf |
| `ingress.yaml` | Ingress | 条件创建（`ingress.enabled`） |
| `timezone-cm.yaml` | ConfigMap | `Asia/Shanghai` 时区配置 |

### 2.6 环境变量文件

| 文件 | `VITE_API_BASE_URL` | 用途 |
|------|---------------------|------|
| `.env.development` | `http://localhost:8000/api` | 本地开发 |
| `.env.sit` | `/api` | SIT 环境 |
| `.env.uat` | `/api` | UAT 环境 |
| `.env.production` | `/api` | 生产环境 |

构建时通过 `vite build --mode sit` 加载对应的 `.env.sit`，API 地址被编译进 JS Bundle 中。

---

## 3. 后端项目构建流水线

### 3.1 项目目录结构

```
vlagent-backend/
├── Dockerfile                  # 运行时镜像（预构建 .venv）
├── Dockerfile.base             # 基础运行时镜像定义
├── Makefile                    # 构建编排
├── Jenkinsfile-k8s-cd-sit     # SIT 流水线
├── Jenkinsfile-k8s-cd-uat     # UAT/生产镜像构建流水线
├── Jenkinsfile-k8s-cd-prd     # 生产部署流水线
├── pyproject.toml              # Python 依赖管理
└── deploy/charts/              # Helm Chart
    ├── Chart.yaml
    ├── values.yaml
    └── templates/
        ├── _helpers.tpl
        ├── deployment.yaml     # Deployment + Service
        ├── ingress.yaml        # 共享 Ingress（前端 + 后端）
        ├── env-configmap.yaml  # 非敏感环境变量
        ├── env-secret.yaml     # 敏感配置（Secret）
        ├── config.yaml         # 应用配置文件
        ├── pvc.yaml            # 持久化存储
        └── timezone-cm.yaml    # 时区配置
```

### 3.2 Dockerfile 分析

**文件：** `Dockerfile`

后端采用 **预构建 + 打包** 的分步策略（非多阶段构建）：

```dockerfile
FROM harbor.devops.qdb.com/star/vlagent-backend-runtime:1.0

# 复制预构建的 Python 虚拟环境（由 make ci-prepare 在 Jenkins Agent 上构建）
COPY .venv /app/.venv

# 复制应用代码
COPY main.py api.py /app/
COPY src/ config/ lib/ services/ scripts/ /app/

# 修正 .venv 内的 Python 符号链接（Agent 和镜像的 Python 路径不同）
RUN ln -sf $(which python3) /app/.venv/bin/python3 && \
    ln -sf $(which python3) /app/.venv/bin/python

# 非 root 用户运行
USER appuser

EXPOSE 8000
ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**与前端的关键区别：**

| 对比项 | 前端 | 后端 |
|--------|------|------|
| 构建方式 | 多阶段 Docker 构建 | Jenkins Agent 预构建 + Docker 打包 |
| 原因 | Node.js 编译快，镜像内构建即可 | Python 依赖多，需在 Agent 上网络环境构建 |
| 基础镜像 | node:lts-bullseye + openresty | 自定义 runtime 镜像（含系统库） |

**Dockerfile.base** 定义了自定义运行时基础镜像，包含：
- PDF 渲染库（`poppler-utils`）
- OpenCV 依赖（`libgl1`, `libglib2.0-0`）
- 中文字体（`fonts-wqy-zenhei`）
- 进程管理器（`tini`）

### 3.3 Makefile 分析

**文件：** `Makefile`

```makefile
# CI 目标
ci-prepare:                    # Jenkins Agent 上执行
	uv lock
	uv sync --no-dev            # 创建 .venv（从内网 Nexus 下载依赖）
	find . -type d -name __pycache__ -exec rm -rf {} +

ci-build:                      # Docker 镜像构建
	nerdctl build -t $(RELEASE_IMAGE)-amd64 .

ci-push:                       # 推送到 Harbor
	nerdctl --insecure-registry=true push $(RELEASE_IMAGE)-amd64

ci-export:                     # 导出镜像 tar（用于 FTP 传输）
	nerdctl save -o image.tar $(RELEASE_IMAGE)

ci-chart:                      # 打包 Helm Chart
	tar czf chart.tar.gz deploy/charts/
```

**构建流程对比：**

```
前端:                              后端:
COPY . .                          make ci-prepare
npm install                       (在 Jenkins Agent 上)
npm run sit                           ↓
(Docker 容器内)                   .venv/ 已就绪
      ↓                           COPY .venv /app/.venv
dist/ 已就绪                     COPY src/ /app/
                                      ↓
                                镜像构建完成
```

### 3.4 Jenkinsfile 分析

#### SIT 流水线

```
Stage 1: Init
Stage 2: Get sit Branches (checkout master → sit)
Stage 3: Get Gitlab Info (获取 commit ID)

Stage 4: Build and Push Image
    ├── make ci-prepare          # Agent 上构建 .venv
    ├── make ci-build            # nerdctl build
    └── make ci-push             # 推送到 Harbor

Stage 5: Helm Deploy Application
    └── helm upgrade --install vlagent-backend deploy/charts \
          --namespace vlagent-backend-sit \
          --set image.tag=${COMMIT_ID}-amd64 \
          --set server.ingress.hosts[0].host=vlagent.devops.qdb.com \
          --set envConfig.APP_ENV=sit \
          --set envConfig.QWEN35_URL=... \
          --set secret.DATABASE_URL=... \
          --set secret.QWEN35_KEY=...
```

**与前端 Jenkinsfile 的区别：**

| 对比项 | 前端 | 后端 |
|--------|------|------|
| 构建工具 | `make -e release-image.amd64` | `make ci-prepare && ci-build && ci-push` |
| 配置注入 | 少量 `--set` | 大量 `--set`（环境变量 + 密钥） |
| 敏感信息 | 无 | 通过 `secret.*` 注入 |

### 3.5 Helm Chart 分析

#### values.yaml 关键结构

```yaml
fullnameOverride: "vlagent-backend"

server:
  replicaCount: 1
  command: ["python", "-m", "uvicorn", "main:app"]
  args: ["--host", "0.0.0.0", "--port", "8000"]

  ports:
    - containerPort: 8000

  ingress:
    enabled: true
    name: "vlagent"                    # 网关名称
    hosts:
      - host: vlagent.sit.qdb.com
        paths:
          - path: /api                 # 后端 API
            servicePortName: http
          - path: /                     # 前端静态资源
            serviceName: vlagent-frontend
            servicePortName: http

  # 健康检查
  startupProbe:   { path: /health, period: 5s,  failureThreshold: 30 }
  livenessProbe:  { path: /health, period: 30s }
  readinessProbe: { path: /health, period: 10s }

# 环境变量（ConfigMap）
envConfig:
  APP_ENV: "production"
  QWEN35_URL: "http://10.1.84.77/v1"
  DATABASE_ECHO: "false"

# 敏感配置（Secret）
secret:
  enabled: true
  DATABASE_URL: ""
  QWEN35_KEY: ""
  JWT_SECRET: ""

# 持久化存储
persistence:
  enabled: true
  storageClass: "nfs-client"
  uploadSize: 10Gi
  downloadSize: 10Gi
```

#### 模板文件

| 文件 | 资源 | 说明 |
|------|------|------|
| `deployment.yaml` | Deployment + Service | Pod 定义、健康检查、卷挂载 |
| `ingress.yaml` | Ingress | **前后端共享网关**，支持 per-path serviceName |
| `env-configmap.yaml` | ConfigMap | 非敏感环境变量 |
| `env-secret.yaml` | Secret | 敏感配置（DB URL、API Key） |
| `pvc.yaml` | PVC | NFS 持久化存储（upload + download） |

#### 配置注入机制

```
values.yaml                    Kubernetes 资源
┌──────────────┐              ┌──────────────────┐
│ envConfig:   │   渲染       │ ConfigMap        │
│   APP_ENV    │  ──────>     │   APP_ENV=sit    │
│   QWEN35_URL │              │   QWEN35_URL=... │
└──────────────┘              └────────┬─────────┘
                                       │ envFrom
                                       v
┌──────────────┐              ┌──────────────────┐
│ secret:      │   渲染       │ Secret           │
│   DATABASE   │  ──────>     │   DATABASE_URL=  │
│   QWEN35_KEY │              │   QWEN35_KEY=    │
└──────────────┘              └──────────────────┘

Pod annotations:
  config-hash: <sha256 of ConfigMap>    # 配置变更时自动重启 Pod
  secret-hash: <sha256 of Secret>
```

---

## 4. 共享 Ingress 架构

### 4.1 路由设计

前后端共用一个 Ingress 资源，由后端 Helm Chart 管理：

```yaml
# 后端 values.yaml → ingress.yaml 模板
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: vlagent                  # 统一网关名称
spec:
  rules:
    - host: vlagent.sit.qdb.com
      http:
        paths:
          - path: /api
            backend:
              service:
                name: vlagent-backend       # 后端 Service
          - path: /
            backend:
              service:
                name: vlagent-frontend      # 前端 Service
```

### 4.2 请求流转

```
浏览器请求 http://vlagent.sit.qdb.com/
    │
    v
DNS 解析 → Ingress Controller (10.238.146.99)
    │
    ├── GET /           → vlagent-frontend:8001 (OpenResty → index.html)
    ├── GET /assets/*   → vlagent-frontend:8001 (静态资源，30天缓存)
    ├── GET /api/*      → vlagent-backend:8000  (FastAPI 后端)
    └── POST /api/dev-token → vlagent-backend:8000 (开发 token)
```

### 4.3 前端 API 请求路径

```
前端代码                              实际请求
import.meta.env.VITE_API_BASE_URL     → /api
axios.get('/api/users')               → http://vlagent.sit.qdb.com/api/users
                                          │
                                          v
                                     Ingress 匹配 /api
                                          │
                                          v
                                     vlagent-backend:8000
```

---

## 5. 构建流水线完整流程

### 5.1 前端 SIT 构建

```
开发者 push 到 sit 分支
        │
        v
Jenkins 触发构建 (Jenkinsfile-k8s-cd-sit)
        │
        ├── 1. checkout sit 分支
        │
        ├── 2. 获取 commit ID (如 a54f898)
        │
        ├── 3. 构建镜像 (make -e release-image.amd64)
        │       │
        │       ├── nerdctl build
        │       │     ├── Stage 1: npm install + vite build --mode sit
        │       │     │     .env.sit → VITE_API_BASE_URL=/api
        │       │     │     输出: dist/ (index.html + assets/)
        │       │     │
        │       │     └── Stage 2: COPY dist/ → OpenResty 镜像
        │       │           输出: harbor.devops.qdb.com/star/vlagent-frontend:a54f898-amd64
        │       │
        │       └── nerdctl push 到 Harbor
        │
        └── 4. Helm 部署
                │
                ├── 清理旧 ConfigMap
                │
                └── helm upgrade --install vlagent-front deploy/charts
                      --namespace star-sit
                      --set image.tag=a54f898-amd64
                      --set ingress.hosts[0].host=vlagent.devops.qdb.com
                            │
                            v
                      创建/更新资源:
                      - ConfigMap (nginx.conf)
                      - Deployment (OpenResty Pod)
                      - Service (ClusterIP:8001)
                      - Ingress (如启用)
```

### 5.2 后端 SIT 构建

```
开发者 push 到 sit 分支
        │
        v
Jenkins 触发构建 (Jenkinsfile-k8s-cd-sit)
        │
        ├── 1. checkout sit 分支
        │
        ├── 2. 获取 commit ID
        │
        ├── 3. make ci-prepare (在 Jenkins Agent 上)
        │       │
        │       ├── uv lock + uv sync --no-dev
        │       │     从内网 Nexus 下载 Python 依赖
        │       │     输出: .venv/ (完整虚拟环境)
        │       │
        │       └── 清理 __pycache__
        │
        ├── 4. make ci-build (nerdctl build)
        │       │   COPY .venv + 源码 → 运行时镜像
        │       │   输出: harbor.devops.qdb.com/star/vlagent-backend:{ID}-amd64
        │       │
        │       └── make ci-push (推送到 Harbor)
        │
        └── 5. Helm 部署
                │
                └── helm upgrade --install vlagent-backend deploy/charts
                      --namespace star-sit
                      --set image.tag={ID}-amd64
                      --set envConfig.APP_ENV=sit
                      --set secret.DATABASE_URL=...
                      --set secret.QWEN35_KEY=...
                            │
                            v
                      创建/更新资源:
                      - ConfigMap (环境变量)
                      - Secret (密钥)
                      - PVC (NFS 存储)
                      - Deployment (FastAPI Pod)
                      - Service (ClusterIP:8000)
                      - Ingress (共享网关 vlagent)
```

---

## 6. 生产环境离线部署

生产环境与开发/UAT 环境网络隔离，通过 FTP 中转制品：

```
UAT Jenkins                        FTP 服务器                    生产 Jenkins
┌──────────────┐               ┌──────────────┐               ┌──────────────┐
│ purpose=     │               │              │               │              │
│ production   │               │ 10.1.89.31   │               │              │
│              │   SFTP upload │              │  SFTP download│              │
│ 1. 构建镜像  │ ─────────────>│ image.tar    │<───────────── │ 1. 下载制品  │
│ 2. 导出 tar  │               │ chart.tar.gz │               │ 2. load 镜像 │
│ 3. 打包 Chart│               │              │               │ 3. push 到   │
│              │               │              │               │   生产Harbor │
└──────────────┘               └──────────────┘               │ 4. helm部署  │
                                                              └──────────────┘
```

---

## 7. 技术栈汇总

### 前端

| 层级 | 技术 | 版本 |
|------|------|------|
| 框架 | Vue | 3.5.x |
| 构建工具 | Vite | 7.2.x |
| 语言 | TypeScript | 5.9.x |
| 样式 | Tailwind CSS | 4.1.x |
| HTTP 客户端 | Axios | 1.13.x |
| 路由 | Vue Router | 4.6.x |
| 运行时 | OpenResty | 1.17.8.2 |

### 后端

| 层级 | 技术 | 版本 |
|------|------|------|
| 框架 | FastAPI + Uvicorn | - |
| 语言 | Python | 3.13 |
| 包管理 | uv | - |
| ORM | SQLModel + asyncpg | - |
| 运行时 | 自定义 Python 镜像 | 3.13-bullseye-slim |

### 基础设施

| 组件 | 技术 |
|------|------|
| 容器运行时 | containerd (nerdctl) |
| 镜像仓库 | Harbor (dev/prod) |
| 编排 | Kubernetes + Helm |
| CI/CD | Jenkins + Shared Library |
| Ingress | nginx-ingress-controller |
| 存储 | NFS (StorageClass: nfs-client) |
| 代码仓库 | GitLab |
