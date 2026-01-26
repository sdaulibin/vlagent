# 🖥️ 虚拟机部署指南 (无 Docker)

本文档介绍如何将 vl_flow 前后端程序直接部署在虚拟机中，不使用 Docker 容器。

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
CREATE DATABASE vl_flow;
CREATE USER vl_flow_user WITH ENCRYPTED PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE vl_flow TO vl_flow_user;
\q
```

> ⚠️ **安全提示**: 请将 `your_secure_password` 替换为强密码。

### 3️⃣ 克隆项目

```bash
sudo mkdir -p /opt/vl_flow
sudo chown $USER:$USER /opt/vl_flow
cd /opt/vl_flow
git clone https://github.com/your-repo/vl_flow.git .
```

### 4️⃣ 后端部署

```bash
cd /opt/vl_flow/backend

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
cd /opt/vl_flow/frontend
npm install
npm run build

# 部署到 Nginx
sudo mkdir -p /var/www/vl_flow
sudo cp -r dist/* /var/www/vl_flow/
sudo chown -R www-data:www-data /var/www/vl_flow
```

---

## 🔌 离线部署 (麒麟系统 / 无外网环境)

> 适用于**无法连接外网**的麒麟操作系统等环境。

### 步骤一：在联网机器上准备离线包

在一台能上网的 Linux 机器（推荐与目标机器相同架构）上执行：

```bash
# 创建离线包目录
mkdir -p ~/vl_flow_offline/{rpms,python,node,frontend}
cd ~/vl_flow_offline

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
cd /path/to/vl_flow/backend
uv export --no-hashes > requirements.txt
pip download -d ~/vl_flow_offline/python/packages -r requirements.txt

# ===== 6. 准备前端依赖 =====
cd /path/to/vl_flow/frontend
npm install
npm run build
tar -czvf ~/vl_flow_offline/frontend/node_modules.tar.gz node_modules/
tar -czvf ~/vl_flow_offline/frontend/dist.tar.gz dist/

# ===== 7. 打包离线包 =====
cd ~
tar -czvf vl_flow_offline.tar.gz vl_flow_offline/
```

### 步骤二：传输到离线机器

```bash
# 使用 U 盘、scp 或 ftp 传输
cd /home/user
tar -xzvf vl_flow_offline.tar.gz
```

### 步骤三：离线安装系统依赖

```bash
# 安装 RPM 包
cd /home/user/vl_flow_offline/rpms
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
cd /home/user/vl_flow_offline/node
tar -xJf node-v20.18.0-linux-x64.tar.xz
sudo mv node-v20.18.0-linux-x64 /usr/local/node
sudo ln -sf /usr/local/node/bin/node /usr/local/bin/node
sudo ln -sf /usr/local/node/bin/npm /usr/local/bin/npm

# 安装 uv
cd /home/user/vl_flow_offline
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
sudo mkdir -p /opt/vl_flow
sudo chown $USER:$USER /opt/vl_flow
cp -r /path/to/vl_flow/* /opt/vl_flow/

cd /opt/vl_flow/backend
python3.11 -m venv .venv
source .venv/bin/activate

# 离线安装依赖
pip install --no-index --find-links=/home/user/vl_flow_offline/python/packages -r requirements.txt

cp .env.example .env
nano .env
```

### 步骤五：离线部署前端

```bash
cd /opt/vl_flow/frontend
tar -xzf /home/user/vl_flow_offline/frontend/dist.tar.gz

sudo mkdir -p /var/www/vl_flow
sudo cp -r dist/* /var/www/vl_flow/
sudo chown -R nginx:nginx /var/www/vl_flow
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
WorkingDirectory=/opt/vl_flow/backend
Environment="PATH=/opt/vl_flow/backend/.venv/bin:/usr/local/bin:/usr/bin"
ExecStart=/opt/vl_flow/backend/.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4
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

创建 `/etc/nginx/sites-available/vl_flow`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    root /var/www/vl_flow;
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
sudo ln -s /etc/nginx/sites-available/vl_flow /etc/nginx/sites-enabled/
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
cd /opt/vl_flow
git pull origin main

# 更新后端
cd backend
uv sync  # 或 pip install -r requirements.txt
sudo systemctl restart vl-flow-backend

# 更新前端
cd ../frontend
npm install
npm run build
sudo cp -r dist/* /var/www/vl_flow/
sudo systemctl reload nginx
```

---

## 📊 目录结构

```
/opt/vl_flow/                 # 项目根目录
├── backend/                  # 后端代码
│   ├── .env                  # 环境配置
│   ├── .venv/                # Python 虚拟环境
│   └── res/                  # 上传文件存储
└── frontend/                 # 前端代码
    └── dist/                 # 构建产物

/var/www/vl_flow/             # Nginx 静态文件
```
