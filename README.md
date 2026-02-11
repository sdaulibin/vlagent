# 🌊 vl_flow

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.124-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue 3.5](https://img.shields.io/badge/Vue-3.5-4FC08D.svg)](https://vuejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**vl_flow** 是一个基于 **Qwen-VL** 大模型的智能文档识别与分析平台。它利用先进的多模态模型能力，实现了银行流水识别、询证函识别和合同比对等多种文档智能处理功能。

---

## ✨ 核心功能

### 🏦 银行流水识别 (Multi-Bank Support)

智能识别多种银行流水 PDF，自动提取账户信息、余额明细、交易双方等关键数据。

- **高精度识别**: 基于 Qwen-VL，支持复杂表格和跨页识别。
- **自动检测**: 自动识别银行类型，智能匹配识别策略。
- **一键导出**: 识别结果可直接导出为 Excel 文档。
- **跨页合并**: 自动处理跨页连续记录，确保数据完整性。

### 📝 询证函智能识别 (Confirmation Letter)

银行询证函的 AI 识别与结构化提取，支持 12 个关键字段。

- **智能提取**: 自动识别函证编号、事务所名称、回函地址等关键信息。
- **人工修正**: 支持人工校对和修改识别结果。
- **分表存储**: 文件信息与识别结果独立存储，架构清晰。

### 📄 合同比对 (Contract Compare)

智能比对两份合同文档的差异，精确定位变更内容。

- **逐段比对**: 基于文本段落的细粒度差异检测。
- **可视化展示**: 前端直观展示新增、删除、修改的内容。

---

## 🛠️ 技术栈

| 领域        | 技术选择                                                         |
| :---------- | :--------------------------------------------------------------- |
| **前端**    | Vue 3.5 + TypeScript 5.9 + Tailwind CSS 4 + Tiptap 3             |
| **后端**    | FastAPI 0.124 + SQLModel 0.0.27 + Python 3.11                    |
| **AI 模型** | Qwen-VL (Local Deployment) / DashScope API                       |
| **数据库**  | PostgreSQL (Production) / SQLite (Dev)                           |
| **包管理**  | [uv](https://github.com/astral-sh/uv) (Backend) + npm (Frontend) |

---

## 🚀 快速开始

### 📋 环境要求

- **Python 3.11+**
- **Node.js 18+**
- **Poppler** (用于 PDF 转图片)
  - macOS: `brew install poppler`
  - Ubuntu: `sudo apt-get install poppler-utils`

### 1️⃣ 克隆与配置

```bash
git clone https://github.com/your-repo/vl_flow.git
cd vl_flow
```

### 2️⃣ 启动后端

```bash
cd backend
cp .env.example .env
# 编辑 .env 配置 LLM 地址与数据库连接
uv sync
uv run uvicorn main:app --reload --port 8000
```

### 3️⃣ 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 [http://localhost:5173](http://localhost:5173) 即可进入系统。

---

## 📁 项目结构

```bash
vl_flow/
├── backend/                    # FastAPI 后端服务
│   ├── src/banks/              # 银行处理策略实现 (Strategy Pattern)
│   ├── src/models/             # 银行流水数据模型 (SQLModel)
│   ├── src/files/              # 文件上传与识别管理
│   ├── src/transactions/       # 交易数据查询接口
│   ├── src/confirmation_letter/# 询证函识别模块
│   ├── src/contracts/          # 合同比对模块
│   ├── services/               # PDF 处理、数据提取等通用服务
│   └── config/                 # 识别提示词与 Schema 配置
├── frontend/                   # Vue 3 前端应用
│   ├── src/views/              # 页面 (Home, BankStatement, ConfirmationLetter, ContractCompare)
│   └── src/components/         # UI 组件 (bank-results/ 等)
├── docs/                       # 项目文档与 ER 图
└── docker-compose.yml          # 容器化部署配置
```

---

## 🏗️ 架构概览

![系统架构图](docs/architecture.svg)

### 插件化银行处理器 (Strategy Pattern)

系统采用策略模式，添加新银行支持仅需 3 步：

1. **定义模型**: 在 `backend/src/models` 添加结构。
2. **实现处理器**: 继承 `BankHandler` 并实现提取逻辑。
3. **前端渲染**: 在 `frontend/src/components/bank-results` 添加展示组件。

---

## 🖥️ 虚拟机部署方案 (无 Docker)

本节介绍如何将前后端程序直接部署在虚拟机中，不使用 Docker 容器。

---

### 📋 系统要求

| 组件         | 最低要求                 | 推荐配置          |
| :----------- | :----------------------- | :---------------- |
| **操作系统** | Ubuntu 22.04 / CentOS 7+ | Ubuntu 22.04 LTS  |
| **CPU**      | 2 核                     | 4 核+             |
| **内存**     | 4 GB                     | 8 GB+             |
| **磁盘**     | 20 GB                    | 50 GB+ (SSD 推荐) |
| **Python**   | 3.11+                    | 3.11              |
| **Node.js**  | 18+                      | 20 LTS            |
| **数据库**   | PostgreSQL 14+           | PostgreSQL 15     |

---

### 1️⃣ 系统依赖安装

#### Ubuntu / Debian

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装基础工具
sudo apt install -y git curl wget unzip build-essential

# 安装 Python 3.11
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# 安装 Node.js 20 (使用 NodeSource)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# 安装 Poppler (PDF 处理)
sudo apt install -y poppler-utils

# 安装 PostgreSQL
sudo apt install -y postgresql postgresql-contrib

# 安装 Nginx
sudo apt install -y nginx

# 安装 uv (Python 包管理器)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

#### CentOS / RHEL

```bash
# 更新系统
sudo yum update -y

# 安装 EPEL 仓库
sudo yum install -y epel-release

# 安装基础工具
sudo yum groupinstall -y "Development Tools"
sudo yum install -y git curl wget unzip

# 安装 Python 3.11 (使用 IUS 或源码编译)
sudo yum install -y python311 python311-devel python311-pip

# 安装 Node.js 20
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
sudo yum install -y nodejs

# 安装 Poppler
sudo yum install -y poppler-utils

# 安装 PostgreSQL 15
sudo yum install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-7-x86_64/pgdg-redhat-repo-latest.noarch.rpm
sudo yum install -y postgresql15-server postgresql15
sudo /usr/pgsql-15/bin/postgresql-15-setup initdb
sudo systemctl enable postgresql-15
sudo systemctl start postgresql-15

# 安装 Nginx
sudo yum install -y nginx

# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

---

### 2️⃣ 数据库配置

```bash
# 切换到 postgres 用户
sudo -u postgres psql

# 在 PostgreSQL 命令行中执行
CREATE DATABASE vl_flow;
CREATE USER vl_flow_user WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE vl_flow TO vl_flow_user;
\q
```

> ⚠️ **安全提示**: 请将 `your_secure_password` 替换为强密码，并妥善保管。

---

### 3️⃣ 克隆项目

```bash
# 创建应用目录
sudo mkdir -p /opt/vl_flow
sudo chown $USER:$USER /opt/vl_flow

# 克隆代码
cd /opt/vl_flow
git clone https://github.com/your-repo/vl_flow.git .
```

---

### 4️⃣ 后端部署

#### 4.1 配置环境

```bash
cd /opt/vl_flow/backend

# 复制并编辑配置文件
cp .env.example .env
nano .env
```

修改 `.env` 文件中的关键配置:

```ini
# AI 模型配置
OPENAI_KEY=your-api-key
OPENAI_URL=http://your-llm-endpoint/v1
MODEL_LOCAL=your-model-name

# 应用配置
RES_DIR=/opt/vl_flow/backend/res
RECOGNITION_TIMEOUT=300

# 数据库配置 (使用上面创建的用户)
DATABASE_URL=postgresql+asyncpg://vl_flow_user:your_secure_password@localhost/vl_flow
```

#### 4.2 安装依赖

```bash
cd /opt/vl_flow/backend

# 使用 uv 安装依赖
uv sync

# 验证安装
uv run python -c "import fastapi; print('FastAPI OK')"
```

#### 4.3 初始化数据库表

```bash
# 如果有数据库迁移脚本，运行它
# uv run alembic upgrade head

# 或者让应用自动创建表 (首次启动时)
uv run uvicorn main:app --host 0.0.0.0 --port 8000 &
sleep 10
kill %1
```

#### 4.4 创建 Systemd 服务

创建后端服务文件:

```bash
sudo nano /etc/systemd/system/vl-flow-backend.service
```

写入以下内容:

```ini
[Unit]
Description=VL Flow Backend Service
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/vl_flow/backend
Environment="PATH=/home/YOUR_USER/.local/bin:/usr/local/bin:/usr/bin"
ExecStart=/home/YOUR_USER/.local/bin/uv run uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=5

# 日志配置
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vl-flow-backend

[Install]
WantedBy=multi-user.target
```

> ⚠️ 请将 `YOUR_USER` 替换为实际的用户名 (运行 `whoami` 查看)

```bash
# 设置目录权限
sudo chown -R www-data:www-data /opt/vl_flow/backend/res

# 启用并启动服务
sudo systemctl daemon-reload
sudo systemctl enable vl-flow-backend
sudo systemctl start vl-flow-backend

# 检查状态
sudo systemctl status vl-flow-backend
```

---

### 5️⃣ 前端部署

#### 5.1 构建生产版本

```bash
cd /opt/vl_flow/frontend

# 安装依赖
npm install

# 构建生产版本
npm run build

# 构建产物在 dist/ 目录
ls dist/
```

#### 5.2 部署静态文件

```bash
# 复制构建产物到 Nginx 目录
sudo mkdir -p /var/www/vl_flow
sudo cp -r dist/* /var/www/vl_flow/
sudo chown -R www-data:www-data /var/www/vl_flow
```

---

### 6️⃣ Nginx 反向代理配置

#### 6.1 创建站点配置

```bash
sudo nano /etc/nginx/sites-available/vl_flow
```

写入以下内容:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名或 IP

    # 前端静态文件
    root /var/www/vl_flow;
    index index.html;

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # 前端路由 (Vue Router history 模式)
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 文件上传大小限制
        client_max_body_size 100M;

        # 超时设置 (AI 处理可能较慢)
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

#### 6.2 启用站点

```bash
# 创建符号链接
sudo ln -s /etc/nginx/sites-available/vl_flow /etc/nginx/sites-enabled/

# 删除默认站点 (可选)
sudo rm /etc/nginx/sites-enabled/default

# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

### 7️⃣ HTTPS 配置 (推荐)

使用 Certbot 获取免费 SSL 证书:

```bash
# 安装 Certbot
sudo apt install -y certbot python3-certbot-nginx  # Ubuntu
# sudo yum install -y certbot python3-certbot-nginx  # CentOS

# 获取证书 (自动配置 Nginx)
sudo certbot --nginx -d your-domain.com

# 自动续期测试
sudo certbot renew --dry-run
```

---

### 8️⃣ 防火墙配置

```bash
# Ubuntu (UFW)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# CentOS (firewalld)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

---

### 9️⃣ 部署验证

```bash
# 检查所有服务状态
sudo systemctl status postgresql
sudo systemctl status vl-flow-backend
sudo systemctl status nginx

# 测试后端 API
curl http://localhost:8000/docs

# 测试前端访问
curl http://localhost/
```

访问 `http://your-server-ip` 或 `https://your-domain.com` 验证系统是否正常运行。

---

### 🔧 常见问题排查

#### 后端服务无法启动

```bash
# 查看详细日志
sudo journalctl -u vl-flow-backend -f

# 常见问题:
# 1. 检查 Python 路径是否正确
# 2. 确认 .env 文件配置正确
# 3. 确保 PostgreSQL 已启动且可连接
```

#### 数据库连接失败

```bash
# 检查 PostgreSQL 配置
sudo nano /etc/postgresql/15/main/pg_hba.conf
# 确保有本地连接权限:
# local   all   all   md5

sudo systemctl restart postgresql
```

#### Nginx 502 Bad Gateway

```bash
# 确认后端服务正在运行
sudo systemctl status vl-flow-backend

# 检查后端端口占用
sudo lsof -i :8000
```

---

### 📊 推荐的目录结构

```bash
/opt/vl_flow/                 # 项目根目录
├── backend/                  # 后端代码
│   ├── .env                  # 环境配置
│   ├── res/                  # 上传文件存储
│   └── ...
├── frontend/                 # 前端代码
│   └── dist/                 # 构建产物
└── logs/                     # 日志目录 (可选)

/var/www/vl_flow/             # Nginx 静态文件目录
└── (前端构建产物)
```

---

### 🔄 更新部署

当有新版本发布时，执行以下步骤:

```bash
cd /opt/vl_flow

# 拉取最新代码
git pull origin main

# 更新后端
cd backend
uv sync
sudo systemctl restart vl-flow-backend

# 更新前端
cd ../frontend
npm install
npm run build
sudo cp -r dist/* /var/www/vl_flow/
sudo systemctl reload nginx
```

---

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。
