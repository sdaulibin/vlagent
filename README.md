# vl_flow

基于 Qwen-VL 大模型的智能文档识别与分析平台。

## ✨ 功能

| 场景 | 状态 | 说明 |
| :--- | :---: | :--- |
| **🏦 银行流水识别** | ✅ | 智能提取交易明细、对方账户信息，自动生成结构化报表 |
| **📋 合同比对** | ✅ | 智能比对 PDF/Word 文档差异，支持并排高亮显示增删改内容 |
| **📄 发票识别** | 🔜 | 开发中，支持多票据自动分类与关键信息提取 |

## 🛠️ 技术栈

*   **前端**:
    *   [Vue 3](https://vuejs.org/) - 渐进式 JavaScript 框架
    *   [TypeScript](https://www.typescriptlang.org/) - 强类型支持
    *   [Tailwind CSS](https://tailwindcss.com/) - 原子化 CSS 框架
    *   [Tiptap](https://tiptap.dev/) - 无头富文本编辑器
*   **后端**:
    *   [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Python Web 框架
    *   [SQLModel](https://sqlmodel.tiangolo.com/) - 结合 SQLAlchemy 与 Pydantic
    *   [Celery](https://docs.celeryq.dev/) - 分布式任务队列 (可选)
*   **数据库**:
    *   [PostgreSQL](https://www.postgresql.org/) - 强大的开源关系型数据库
*   **AI 模型**:
    *   Qwen-VL (本地部署) - 通义千问视觉语言模型

## 🚀 快速开始

### 前置要求

确保您的环境已安装以下工具：

*   Docker & Docker Compose
*   Python 3.11+
*   Node.js 18+
*   Poppler (PDF 处理依赖)

### 1. 启动基础服务

使用 Docker Compose 启动 PostgreSQL 数据库：

```bash
docker compose up -d
```

### 2. 启动后端服务

详细指南请参考 [Backend README](backend/README.md)。

```bash
cd backend
# 推荐使用 uv 进行包管理
uv sync
uv run uvicorn main:app --reload
```

### 3. 启动前端服务

详细指南请参考 [Frontend README](frontend/README.md)。

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 即可开始使用。

## 📁 项目结构

```
vl_flow/
├── frontend/           # Vue 3 前端应用
│   ├── src/views/      # 页面视图 (Home, BankStatement, ContractCompare)
│   ├── src/components/ #包括 TiptapViewer, ContractResultView 等组件
│   └── src/assets/     # 静态资源与样式
├── backend/            # FastAPI 后端服务
│   ├── apps/           # 业务模块
│   │   ├── files/          # 银行流水处理
│   │   └── contracts/      # 合同比对逻辑
│   ├── core/           # 核心配置 (DB, Config, AI client)
│   └── services/       # 通用服务 (PDF 解析, 差异比对)
└── docker-compose.yml  # 基础设施编排
```

## 📡 API 概览

详细 API 文档请访问 Swagger UI: http://localhost:8000/docs

### 🏦 银行流水
*   `GET /api/files`: 获取已上传文件列表
*   `POST /api/files/upload`: 上传并解析银行流水文件
*   `GET /api/transactions/{id}`: 获取指定文件的交易明细

### 📋 合同比对
*   `POST /api/contracts/compare`: 上传两份文档进行智能比对
*   `GET /api/contracts/{id}`: 查询比对任务状态
*   `GET /api/contracts/{id}/diffs`: 获取详细差异数据
*   `GET /api/contracts/{id}/file/{type}`: 获取原始文件以进行预览

## 📄 License

MIT License
