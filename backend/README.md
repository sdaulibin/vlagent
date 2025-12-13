# Backend - VL_Flow

基于 FastAPI 构建的智能文档识别后端服务。

## ✨ 功能特性

- 📤 **PDF 处理** - 使用 `pdf2image` 转换 PDF 为图片
- 🤖 **AI 识别** - 集成 Qwen-VL 进行智能信息提取
- 💾 **数据持久化** - PostgreSQL 存储文件、交易和汇总信息
- 📊 **汇总分析** - 提取账户信息和收支统计

## 🛠️ 技术栈

- Python >= 3.11
- FastAPI
- SQLModel + asyncpg
- uv (依赖管理)
- PostgreSQL

## 📁 目录结构

```
backend/
├── main.py                 # 应用入口
├── api.py                  # API 路由汇总
├── apps/                   # 应用模块
│   ├── files/              # 文件管理
│   │   ├── api.py          # 文件 API
│   │   └── models.py       # 数据模型 (FileRecord, SummaryRecord, TransactionRecord)
│   └── transactions/       # 交易管理
│       └── api.py          # 交易和汇总 API
├── core/                   # 核心模块
│   ├── config.py           # LLM 配置
│   ├── database.py         # 数据库连接
│   └── request_ai.py       # AI 请求封装
└── services/               # 公共服务
    └── pdf_processor.py    # PDF 处理核心逻辑
```

## 🚀 快速开始

### 1. 安装系统依赖

```bash
# MacOS
brew install poppler

# Linux
sudo apt-get install poppler-utils
```

### 2. 启动数据库

```bash
docker compose up -d
```

### 3. 启动服务

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000
```

## 📡 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/files` | 获取文件列表 |
| GET | `/api/files/{id}` | 获取文件详情 |
| POST | `/api/files/upload` | 上传 PDF 文件 |
| GET | `/api/transactions/{file_id}` | 获取交易记录 |
| GET | `/api/transactions/{file_id}/summary` | 获取汇总信息 |

API 文档：http://localhost:8000/docs
