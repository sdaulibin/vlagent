# vl_flow

基于 Qwen-VL 大模型的智能文档识别与分析平台。

## ✨ 功能

| 场景 | 状态 | 说明 |
|------|------|------|
| 🏦 银行流水识别 | ✅ | 提取交易明细和汇总信息 |
| 📋 合同比对 | ✅ | 智能比对 PDF/Word 文档差异，支持高亮联动 |
| 📄 发票识别 | 🔜 | 敬请期待 |

## 🛠️ 技术栈

- **前端**: Vue 3 + TypeScript + Tailwind CSS + Tiptap
- **后端**: FastAPI + Python 3.11+ + SQLModel + Celery (Optional)
- **数据库**: PostgreSQL
- **AI**: Qwen-VL (Local Deployment)

## 🚀 快速开始

```bash
# 1. 启动数据库
docker compose up -d

# 2. 启动后端 (确保安装 poppler, libreoffice 等依赖)
cd backend && uv sync && uv run uvicorn main:app --reload

# 3. 启动前端
cd frontend && npm install && npm run dev
```

访问 http://localhost:5173

## 📁 项目结构

```
vl_flow/
├── frontend/           # Vue 3 前端
│   ├── src/views/      # 页面 (Home, BankStatement, ContractCompare)
│   ├── src/components/ # 组件 (TiptapViewer, ContractResultView)
│   └── src/assets/     # 样式 (main.css, contract.css)
├── backend/            # FastAPI 后端
│   ├── apps/           # 应用模块
│   │   ├── files/          # 银行流水模块
│   │   └── contracts/      # 合同比对模块
│   ├── core/           # 核心配置
│   └── services/       # 业务逻辑 (pdf_processor, contract_processor)
└── docker-compose.yml
```

## 📡 API

### 银行流水
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/files` | 文件列表 |
| POST | `/api/files/upload` | 上传文件 |
| GET | `/api/transactions/{id}` | 交易明细 |

### 合同比对
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/contracts/compare` | 上传并比对 |
| GET | `/api/contracts/{id}` | 获取任务状态 |
| GET | `/api/contracts/{id}/diffs` | 获取差异列表 |
| GET | `/api/contracts/{id}/file/{type}` | 获取原始文件预览 |

## 📄 License

MIT
