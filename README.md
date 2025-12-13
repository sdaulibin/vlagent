# vl_flow

基于 Qwen-VL 大模型的智能文档识别与分析平台。

## ✨ 功能

| 场景 | 状态 | 说明 |
|------|------|------|
| 🏦 银行流水识别 | ✅ | 提取交易明细和汇总信息 |
| 📄 发票识别 | 🔜 | 敬请期待 |
| 📋 合同识别 | 🔜 | 敬请期待 |

## 🛠️ 技术栈

- **前端**: Vue 3 + TypeScript + Tailwind CSS + Vue Router
- **后端**: FastAPI + Python 3.11+ + SQLModel
- **数据库**: PostgreSQL
- **AI**: Qwen-VL

## 🚀 快速开始

```bash
# 1. 启动数据库
docker compose up -d

# 2. 启动后端
cd backend && uv sync && uv run uvicorn main:app --reload

# 3. 启动前端
cd frontend && npm install && npm run dev
```

访问 http://localhost:5173

## 📁 项目结构

```
vl_flow/
├── frontend/           # Vue 3 前端
│   ├── src/views/      # 页面 (Home, BankStatement)
│   ├── src/components/ # 组件
│   └── src/assets/     # 样式 (main.css)
├── backend/            # FastAPI 后端
│   ├── apps/           # 应用模块
│   ├── core/           # 核心配置
│   └── services/       # 业务逻辑
└── docker-compose.yml
```

## 📡 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/files` | 文件列表 |
| POST | `/api/files/upload` | 上传文件 |
| DELETE | `/api/files/{id}` | 删除文件 |
| GET | `/api/transactions/{id}` | 交易明细 |
| GET | `/api/transactions/{id}/summary` | 汇总信息 |

## 📄 License

MIT
