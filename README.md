# VL_Flow

VL_Flow 是一个基于本地大模型（Qwen-VL）的智能文档识别与分析平台。

## ✨ 功能特性

- 🏦 **银行流水识别** - 智能解析银行流水 PDF，提取交易明细和汇总信息
- 📄 **发票识别** - 敬请期待
- 📋 **合同识别** - 敬请期待

## 🛠️ 技术栈

| 模块 | 技术 |
|------|------|
| 前端 | Vue 3, TypeScript, Tailwind CSS, Vue Router |
| 后端 | FastAPI, Python 3.11+, SQLModel |
| 数据库 | PostgreSQL (Docker) |
| AI | Qwen-VL (本地部署) |

## 🚀 快速开始

### 1. 启动数据库

```bash
docker compose up -d
```

### 2. 启动后端

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 即可使用。

## 📁 项目结构

```
vl_flow/
├── frontend/               # Vue 3 前端
│   ├── src/views/          # 页面组件
│   ├── src/components/     # 通用组件
│   └── src/router/         # 路由配置
├── backend/                # FastAPI 后端
│   ├── apps/               # 应用模块 (files, transactions)
│   ├── core/               # 核心模块 (config, database)
│   └── services/           # 业务服务 (pdf_processor)
└── docker-compose.yml      # PostgreSQL 配置
```

## 📡 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/files` | 获取文件列表 |
| GET | `/api/files/{id}` | 获取文件详情 |
| POST | `/api/files/upload` | 上传 PDF 文件 |
| GET | `/api/transactions/{file_id}` | 获取交易记录 |
| GET | `/api/transactions/{file_id}/summary` | 获取汇总信息 |

## 📄 License

MIT
