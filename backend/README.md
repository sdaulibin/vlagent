# Backend

FastAPI + Python 构建的后端服务。

## 🚀 启动

```bash
# 安装依赖 (需要 poppler)
brew install poppler  # macOS

# 启动数据库
docker compose up -d

# 启动服务
uv sync
uv run uvicorn main:app --reload --port 8000
```

API 文档: http://localhost:8000/docs

## 📁 结构

```
backend/
├── main.py             # 入口
├── api.py              # 路由汇总
├── apps/
│   ├── files/          # 文件模块
│   │   ├── api.py
│   │   └── models.py   # FileRecord, SummaryRecord, TransactionRecord
│   └── transactions/   # 交易模块
│       └── api.py
├── core/
│   ├── config.py       # LLM 配置
│   ├── database.py     # 数据库
│   └── request_ai.py   # AI 请求
└── services/
    └── pdf_processor.py
```

## 📡 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/files` | 文件列表 |
| GET | `/api/files/{id}` | 文件详情 |
| POST | `/api/files/upload` | 上传文件 |
| DELETE | `/api/files/{id}` | 删除文件 |
| GET | `/api/transactions/{id}` | 交易明细 |
| GET | `/api/transactions/{id}/summary` | 汇总信息 |

## 🗄️ 数据模型

- `FileRecord` - 文件信息
- `SummaryRecord` - 汇总信息 (账户、收支统计)
- `TransactionRecord` - 交易明细
