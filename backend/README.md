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
│   ├── files/          # 银行流水模块
│   │   ├── api.py
│   │   └── models.py   # FileRecord, SummaryRecord
│   ├── contracts/      # 合同比对模块
│   │   ├── api.py
│   │   └── models.py   # CompareTask, DiffRecord
│   └── transactions/   # 交易模块
├── core/
│   ├── config.py       # LLM 配置
│   ├── database.py     # 数据库
│   └── request_ai.py   # AI 请求
└── services/
    ├── pdf_processor.py      # PDF 处理
    └── contract_processor.py # 合同处理服务
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
| POST | `/api/contracts/compare` | 上传并比对 (支持 PDF/Docx) |
| GET | `/api/contracts/{id}` | 获取任务状态 |
| GET | `/api/contracts/{id}/diffs` | 获取差异列表 |

## 🗄️ 数据模型

- `CompareTask` - 比对任务 (存储原文件/比对文件路径)
- `DiffRecord` - 差异记录 (包含差异类型、原文、比对内容)

## 💡 核心特性

### 智能长文档比对
- **分块策略**：使用 `difflib` 对文档进行预处理和对齐。
- **动态切分**：将长文档切分为 ~3000字符的语义块，突破 AI Token 限制。
- **高精度匹配**：优化 AI Prompt，支持检测微小差异（标点、数字、截断）。
