# Backend Service

基于 **FastAPI** + **Python 3.11** 构建的高性能后端服务，负责处理文档识别、比对以及与本地 LLM 交互。

## 🚀 快速启动

### 1. 环境准备

*   **Python 3.11+**: 推荐使用 [uv](https://github.com/astral-sh/uv) 管理环境
*   **Poppler**: PDF 转图片处理
    *   macOS: `brew install poppler`
    *   Ubuntu: `sudo apt-get install poppler-utils`

### 2. 配置环境变量

复制 `.env.example` 或创建 `.env` 文件：

```ini
# AI Model Configuration
MODEL_LOCAL=qwen-vl-local
MODEL_LOCAL_URL=http://localhost:8080/v1/chat/completions
MODEL_LOCAL_KEY=your-api-key

# Database (默认使用 SQLite)
# DATABASE_URL=postgresql://user:password@localhost:5432/vl_flow
```

### 3. 安装与运行

```bash
# 安装依赖
uv sync

# 启动服务
uv run uvicorn main:app --reload --port 8000
```

API 文档: http://localhost:8000/docs

## 📁 目录结构

```
backend/
├── main.py                 # 应用入口
├── api.py                  # 路由注册
├── core/                   # 核心基础设施
│   ├── config.py           # 环境变量配置
│   ├── database.py         # 数据库连接
│   └── request_ai.py       # AI 模型调用接口
├── apps/                   # 业务模块
│   ├── files/              # 文件上传与银行识别
│   │   ├── api.py          # 上传/识别 API
│   │   └── models.py       # 数据模型 (多银行表)
│   ├── transactions/       # 交易明细查询
│   └── contracts/          # 合同比对
├── config/
│   └── bank_schemas/       # 🆕 银行模板配置
│       ├── bank_registry.json   # 银行注册表
│       ├── shandong_local.json  # 山东地方银行
│       ├── everbright.json      # 光大银行
│       └── cmb.json             # 招商银行
└── services/               # 通用服务
    ├── pdf_processor.py        # PDF 解析 & 银行识别
    └── contract_processor.py   # 合同比对
```

## 🏦 多银行识别架构

### 银行识别流程

```
PDF上传 → 银行类型检测 → 加载对应Schema → AI提取 → 存入对应表
          ↓
    1. 文件名匹配
    2. 印章识别
    3. Logo识别
```

### 添加新银行模板

1. 在 `config/bank_schemas/` 创建新的 JSON 配置：

```json
{
    "template_id": "new_bank",
    "bank_names": ["新银行名称"],
    "summary_schema": { ... },
    "transaction_schema": [ ... ]
}
```

2. 在 `bank_registry.json` 中注册
3. 在 `models.py` 添加对应的数据表
4. 在 `api.py` 添加记录创建函数

## 📡 API 接口

### 🏦 银行流水

| 方法 | 路径 | 描述 |
| :--- | :--- | :--- |
| `GET` | `/api/files` | 获取文件列表 |
| `POST` | `/api/files/upload` | 上传文件 |
| `POST` | `/api/files/{id}/recognize` | 触发识别 |
| `GET` | `/api/transactions/{id}` | 获取交易明细与汇总 |

### 📋 合同比对

| 方法 | 路径 | 描述 |
| :--- | :--- | :--- |
| `POST` | `/api/contracts/compare` | 创建比对任务 |
| `GET` | `/api/contracts/{id}` | 查询任务状态 |
| `GET` | `/api/contracts/{id}/diffs` | 获取差异列表 |

## 🗄️ 数据模型

### 银行流水表结构

| 银行 | 汇总表 | 明细表 |
| :--- | :--- | :--- |
| 山东地方银行 | `ShandongLocalSummary` | `ShandongLocalTransaction` |
| 光大银行 | `EverbrightSummary` | `EverbrightTransaction` |
| 招商银行 | `CmbSummary` | `CmbTransaction` |

每种银行的表结构与其 Schema 字段对应，确保数据完整性。
