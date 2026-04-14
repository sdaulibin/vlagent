# 🖥️ 虚拟机部署指南 (无 Docker)

本文档介绍如何将 vlagent 前后端程序直接部署在虚拟机中，不使用 Docker 容器。

---

## 📋 系统要求

| 组件         | 最低要求                            | 推荐配置          |
| :----------- | :---------------------------------- | :---------------- |
| **操作系统** | Ubuntu 22.04 / CentOS 7+ / 麒麟 V10 | Ubuntu 22.04 LTS  |
| **CPU**      | 2 核                                | 4 核+             |
| **内存**     | 4 GB                                | 8 GB+             |
| **磁盘**     | 20 GB                               | 50 GB+ (SSD 推荐) |
| **Python**   | 3.11+                               | 3.11              |
| **Node.js**  | 18+                                 | 20 LTS            |
| **数据库**   | PostgreSQL 14+                      | PostgreSQL 15     |

---

## 🌐 在线部署 (可联网环境)

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

# 安装 Python 3.11
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

### 2️⃣ 数据库配置

```bash
# 切换到 postgres 用户
sudo -u postgres psql

# 在 PostgreSQL 命令行中执行
CREATE DATABASE vlagent;
CREATE USER vlagent_user WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE vlagent TO vlagent_user;
\q
```

> ⚠️ **安全提示**: 请将 `your_secure_password` 替换为强密码。

### 3️⃣ 克隆项目

```bash
sudo mkdir -p /opt/vlagent
sudo chown $USER:$USER /opt/vlagent
cd /opt/vlagent
git clone https://github.com/your-repo/vlagent.git .
```

### 4️⃣ 后端部署

```bash
cd /opt/vlagent/backend

# 配置环境变量
cp .env.example .env
nano .env  # 编辑配置

# 安装依赖
uv sync

# 验证
uv run python -c "import fastapi; print('FastAPI OK')"
```

### 5️⃣ 前端部署

```bash
cd /opt/vlagent/frontend
npm install
npm run build

# 部署到 Nginx
sudo mkdir -p /var/www/vlagent
sudo cp -r dist/* /var/www/vlagent/
sudo chown -R www-data:www-data /var/www/vlagent
```

---

## 🔌 离线部署 (麒麟系统 / 无外网环境)

> 适用于**无法连接外网**的麒麟操作系统等环境。

### 步骤一：在联网机器上准备离线包

在一台能上网的 Linux 机器（推荐与目标机器相同架构）上执行：

```bash
# 创建离线包目录
mkdir -p ~/vlagent_offline/{rpms,python,node,frontend}
cd ~/vlagent_offline

# ===== 1. 下载 RPM 依赖包 =====
sudo yum install -y yum-utils
yumdownloader --resolve --destdir=./rpms \
    gcc gcc-c++ make git wget unzip \
    poppler-utils nginx \
    postgresql15-server postgresql15 \
    openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel

# ===== 2. 下载 Python 3.11 源码 =====
cd python
wget https://www.python.org/ftp/python/3.11.9/Python-3.11.9.tgz

# ===== 3. 下载 Node.js 预编译包 =====
cd ../node
# x64 架构:
wget https://nodejs.org/dist/v20.18.0/node-v20.18.0-linux-x64.tar.xz
# arm64 架构 (飞腾/鲲鹏):
# wget https://nodejs.org/dist/v20.18.0/node-v20.18.0-linux-arm64.tar.xz

# ===== 4. 下载 uv =====
cd ..
# x64:
wget https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz -O uv.tar.gz
# arm64:
# wget https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-unknown-linux-gnu.tar.gz -O uv.tar.gz

# ===== 5. 准备 Python 依赖包 =====
cd /path/to/vlagent/backend
uv export --no-hashes > requirements.txt
pip download -d ~/vlagent_offline/python/packages -r requirements.txt

# ===== 6. 准备前端依赖 =====
cd /path/to/vlagent/frontend
npm install
npm run build
tar -czvf ~/vlagent_offline/frontend/node_modules.tar.gz node_modules/
tar -czvf ~/vlagent_offline/frontend/dist.tar.gz dist/

# ===== 7. 打包离线包 =====
cd ~
tar -czvf vlagent_offline.tar.gz vlagent_offline/
```

### 步骤二：传输到离线机器

```bash
# 使用 U 盘、scp 或 ftp 传输
cd /home/user
tar -xzvf vlagent_offline.tar.gz
```

### 步骤三：离线安装系统依赖

```bash
# 安装 RPM 包
cd /home/user/vlagent_offline/rpms
sudo yum localinstall -y *.rpm

# 编译安装 Python 3.11
cd ../python
tar -xzf Python-3.11.9.tgz
cd Python-3.11.9
./configure --enable-optimizations --prefix=/usr/local/python3.11
make -j$(nproc)
sudo make altinstall
sudo ln -sf /usr/local/python3.11/bin/python3.11 /usr/local/bin/python3.11
sudo ln -sf /usr/local/python3.11/bin/pip3.11 /usr/local/bin/pip3.11

# 安装 Node.js
cd /home/user/vlagent_offline/node
tar -xJf node-v20.18.0-linux-x64.tar.xz
sudo mv node-v20.18.0-linux-x64 /usr/local/node
sudo ln -sf /usr/local/node/bin/node /usr/local/bin/node
sudo ln -sf /usr/local/node/bin/npm /usr/local/bin/npm

# 安装 uv
cd /home/user/vlagent_offline
tar -xzf uv.tar.gz
sudo mv uv /usr/local/bin/
sudo chmod +x /usr/local/bin/uv

# 初始化 PostgreSQL
sudo /usr/pgsql-15/bin/postgresql-15-setup initdb
sudo systemctl enable postgresql-15
sudo systemctl start postgresql-15
```

### 步骤四：离线部署后端

```bash
sudo mkdir -p /opt/vlagent
sudo chown $USER:$USER /opt/vlagent
cp -r /path/to/vlagent/* /opt/vlagent/

cd /opt/vlagent/backend
python3.11 -m venv .venv
source .venv/bin/activate

# 离线安装依赖
pip install --no-index --find-links=/home/user/vlagent_offline/python/packages -r requirements.txt

cp .env.example .env
nano .env
```

### 步骤五：离线部署前端

```bash
cd /opt/vlagent/frontend
tar -xzf /home/user/vlagent_offline/frontend/dist.tar.gz

sudo mkdir -p /var/www/vlagent
sudo cp -r dist/* /var/www/vlagent/
sudo chown -R nginx:nginx /var/www/vlagent
```

---

## ⚙️ 服务配置

### Systemd 后端服务

创建 `/etc/systemd/system/vl-flow-backend.service`:

```ini
[Unit]
Description=VL Flow Backend Service
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/vlagent/backend
Environment="PATH=/opt/vlagent/backend/.venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/opt/vlagent/backend/.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable vl-flow-backend
sudo systemctl start vl-flow-backend
```

### Nginx 反向代理

创建 `/etc/nginx/sites-available/vlagent`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /var/www/vlagent;
    index index.html;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        client_max_body_size 100M;
        proxy_read_timeout 300s;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/vlagent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🔒 HTTPS 配置 (可选)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
sudo certbot renew --dry-run
```

---

## 🛡️ 防火墙配置

```bash
# Ubuntu (UFW)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# CentOS / 麒麟 (firewalld)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

---

## ✅ 部署验证

```bash
sudo systemctl status postgresql
sudo systemctl status vl-flow-backend
sudo systemctl status nginx

curl http://localhost:8000/docs
curl http://localhost/
```

---

## 🔧 常见问题

| 问题                    | 解决方案                                         |
| :---------------------- | :----------------------------------------------- |
| 后端无法启动            | `sudo journalctl -u vl-flow-backend -f` 查看日志 |
| 数据库连接失败          | 检查 `pg_hba.conf` 配置和 `.env` 中的连接字符串  |
| Nginx 502 Bad Gateway   | 确认后端服务运行中: `sudo lsof -i :8000`         |
| SELinux 阻止访问 (麒麟) | `sudo setenforce 0` 或配置正确策略               |
| 缺少 libssl.so.1.1      | 编译安装 OpenSSL 1.1.1                           |
| arm64 架构问题          | 确保 Node.js 和 uv 使用 arm64/aarch64 版本       |

---

## 🔄 更新部署

```bash
cd /opt/vlagent
git pull origin main

# 更新后端
cd backend
uv sync  # 或 pip install -r requirements.txt
sudo systemctl restart vl-flow-backend

# 更新前端
cd ../frontend
npm install
npm run build
sudo cp -r dist/* /var/www/vlagent/
sudo systemctl reload nginx
```

---

## 📊 目录结构

```
/opt/vlagent/                 # 项目根目录
├── backend/                  # 后端代码
│   ├── .env                  # 环境配置
│   ├── .venv/                # Python 虚拟环境
│   └── res/                  # 上传文件存储
└── frontend/                 # 前端代码
    └── dist/                 # 构建产物

/var/www/vlagent/             # Nginx 静态文件
```

---

# 🐳 Docker 容器化部署

本节介绍如何使用 Docker 容器化方式部署 vlagent。

---

## 📋 环境要求

| 组件           | 版本要求 |
| :------------- | :------- |
| Docker         | 20.10+   |
| Docker Compose | 2.0+     |
| 内存           | 4 GB+    |

---

## 🏗️ 架构概览

```
┌───────────────────────────────────────────────────────────────┐
│                   应用服务器                                   │
│  ┌─────────────┐   ┌─────────────┐   ┌──────────────────┐    │
│  │   Nginx     │──▶│  Frontend   │   │     Backend      │    │
│  │   :80/443   │   │   (static)  │   │   :8000 (API)    │    │
│  └─────────────┘   └─────────────┘   └────────┬─────────┘    │
└───────────────────────────────────────────────│──────────────┘
                                                │
                                   ┌────────────▼────────────┐
                                   │    数据库服务器          │
                                   │   PostgreSQL :5432      │
                                   └─────────────────────────┘
```

---

## 📁 创建 Dockerfile

### 后端 Dockerfile

创建 `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖 (poppler 用于 PDF 处理)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 复制依赖文件
COPY pyproject.toml uv.lock ./

# 安装 Python 依赖
RUN uv sync --frozen --no-dev

# 复制应用代码
COPY . .

# 创建资源目录
RUN mkdir -p /app/res

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 前端 Dockerfile

创建 `frontend/Dockerfile`:

```dockerfile
# 构建阶段
FROM node:20-alpine AS builder

WORKDIR /app

# 复制依赖文件
COPY package*.json ./

# 安装依赖
RUN npm ci

# 复制源码
COPY . .

# 构建
RUN npm run build

# 生产阶段
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### 前端 Nginx 配置

创建 `frontend/nginx.conf`:

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;

    # Vue Router history 模式
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API 代理
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 100M;
        proxy_read_timeout 300s;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

---

## 📝 docker-compose.yml

在项目根目录创建 `docker-compose.yml`:

```yaml
services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: vlagent_backend
    restart: always
    environment:
      # 数据库连接 (使用外部数据库服务器)
      DATABASE_URL: postgresql+asyncpg://用户名:密码@数据库IP:5432/vlagent
      # AI 模型配置
      OPENAI_KEY: ${OPENAI_KEY}
      OPENAI_URL: ${OPENAI_URL}
      MODEL_LOCAL: ${MODEL_LOCAL}
    volumes:
      - backend_res:/app/res
    ports:
      - "8000:8000"
    networks:
      - vlagent_net

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: vlagent_frontend
    restart: always
    ports:
      - "80:80"
    depends_on:
      - backend
    networks:
      - vlagent_net

volumes:
  backend_res:

networks:
  vlagent_net:
    driver: bridge
```

---

## 🔐 环境变量配置

在项目根目录创建 `.env` 文件:

```ini
# AI 模型配置
OPENAI_KEY=你的API密钥
OPENAI_URL=http://你的AI服务地址/v1
MODEL_LOCAL=模型名称
```

---

## 🚀 部署步骤

### 1. 代码传输到服务器

**方案 A: Git 仓库 (推荐)**

```bash
# 添加内部仓库
git remote add internal http://内部GitLab/group/vlagent.git
git push internal main

# 在服务器上克隆
ssh user@服务器IP
git clone http://内部GitLab/group/vlagent.git /opt/vlagent
```

**方案 B: 打包传输**

```bash
# 在开发机打包
tar --exclude='node_modules' --exclude='.venv' --exclude='__pycache__' \
    -czvf vlagent.tar.gz .

# 传输到服务器
scp vlagent.tar.gz user@服务器IP:/opt/

# 解压
ssh user@服务器IP
mkdir -p /opt/vlagent && cd /opt/vlagent
tar -xzvf ../vlagent.tar.gz
```

### 2. 构建并启动

```bash
cd /opt/vlagent

# 构建镜像
docker compose build

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f
```

### 3. 验证部署

```bash
# 后端健康检查
curl http://localhost:8000/health

# 前端页面
curl http://localhost/
```

---

## 📦 离线部署 (无外网环境)

### 在联网机器构建镜像

```bash
cd /path/to/vlagent

# 构建镜像
docker compose build

# 导出镜像
docker save vlagent-backend:latest | gzip > vlagent_backend.tar.gz
docker save vlagent-frontend:latest | gzip > vlagent_frontend.tar.gz
```

### 传输到内网服务器

```bash
scp vlagent_*.tar.gz user@内网服务器IP:/opt/vlagent/
scp docker-compose.yml .env user@内网服务器IP:/opt/vlagent/
```

### 在内网服务器加载并启动

```bash
cd /opt/vlagent

# 加载镜像
gunzip -c vlagent_backend.tar.gz | docker load
gunzip -c vlagent_frontend.tar.gz | docker load

# 启动服务
docker compose up -d
```

---

## 🛠️ 常用命令

| 操作         | 命令                                   |
| :----------- | :------------------------------------- |
| 启动服务     | `docker compose up -d`                 |
| 停止服务     | `docker compose down`                  |
| 重启服务     | `docker compose restart`               |
| 查看日志     | `docker compose logs -f backend`       |
| 重建镜像     | `docker compose build --no-cache`      |
| 进入容器     | `docker exec -it vlagent_backend bash` |
| 查看容器状态 | `docker compose ps`                    |

---

## 🔧 常见问题

| 问题             | 解决方案                               |
| :--------------- | :------------------------------------- |
| 无法拉取基础镜像 | 使用离线部署方案或配置镜像加速器       |
| 容器启动失败     | `docker compose logs backend` 查看日志 |
| 数据库连接失败   | 检查 DATABASE_URL 和网络连通性         |
| 端口被占用       | `lsof -i :80` 查找占用进程             |
| 文件上传失败     | 检查 volumes 挂载和权限                |
