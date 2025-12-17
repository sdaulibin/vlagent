# Backend Service

基于 **FastAPI** + **Python 3.11** 构建的高性能后端服务，负责处理文档识别、比对以及与本地 LLM 交互。

## 🚀 快速启动

### 1. 环境准备

确保系统已安装以下依赖：

*   **Python 3.11+**: 推荐使用 [uv](https://github.com/astral-sh/uv) 管理 Python 环境。
*   **Poppler**: 用于 PDF 转图片处理。
    *   macOS: `brew install poppler`
    *   Ubuntu: `sudo apt-get install poppler-utils`
*   **PostgreSQL**: 数据库服务。

### 2. 配置环境变量

复制 `.env.example` (如果存在) 或创建一个 `.env` 文件，配置关键参数：

```ini
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/vl_flow

# AI Model Configuration
LLM_MODEL_PATH=/path/to/Qwen-VL
LLM_DEVICE=cuda  # or cpu, mps

# App Settings
DEBUG=True
```

### 3. 安装与运行

```bash
# 1. 启动数据库 (如果尚未启动)
docker compose up -d

# 2. 安装 Python 依赖
uv sync

# 3. 运行开发服务器 (热重载)
uv run uvicorn main:app --reload --port 8000
```

API 文档地址: http://localhost:8000/docs

## 📁 目录结构

```
backend/
├── main.py             # 应用入口，配置中间件与全局路由
├── api.py              # 路由注册中心
├── core/               # 核心基础设施
│   ├── config.py       # 环境变量与配置加载
│   ├── database.py     # SQLModel 数据库连接会话
│   └── request_ai.py   # 统一的 AI 模型调用接口
├── apps/               # 业务领域模块
│   ├── files/          # 银行流水模块 (上传、解析)
│   ├── contracts/      # 合同比对模块 (任务管理、差异存储)
│   └── transactions/   # 交易明细查询
└── services/           # 通用业务服务
    ├── pdf_processor.py      # PDF 解析与预处理
    └── contract_processor.py # 智能合同比对核心逻辑
```

## 📡 API 接口说明

### 🏦 银行流水 (Files)
| 方法 | 路径 | 描述 |
| :--- | :--- | :--- |
| `GET` | `/api/files` | 获取已上传的文件列表 |
| `POST` | `/api/files/upload` | 上传 PDF/Image 并触发异步解析 |
| `GET` | `/api/transactions/{id}` | 获取特定文件的解析结果 (交易明细) |

### 📋 合同比对 (Contracts)
| 方法 | 路径 | 描述 |
| :--- | :--- | :--- |
| `POST` | `/api/contracts/compare` | 创建比对任务 (支持 PDF/Docx) |
| `GET` | `/api/contracts/{id}` | 轮询任务状态 (Pending/Processing/Completed/Failed) |
| `GET` | `/api/contracts/{id}/diffs` | 获取详细的差异列表与高亮坐标 |

## 🗄️ 核心数据模型

*   **`CompareTask`**: 记录比对任务元数据，包括原文件路径、目标文件路径及当前状态。
*   **`DiffRecord`**: 存储具体的差异点，包含差异类型 (Insert/Delete/Replace)、原始内容、修改内容及其位置信息。

## 💡 核心实现细节

### 智能长文档比对策略
为了突破 LLM 的 Context Window 限制并提高比对精度，我们采用了以下策略：

1.  **预处理与分块**: 使用 `difflib` 对文档进行初步的文本层面对齐，定位差异的大致区域。
2.  **动态语义切分**: 将长文档智能切分为 ~3000 字符的语义块，确保上下文完整。
3.  **Prompt 优化**: 针对性设计的 Prompt，专注于检测微小的语义和格式差异（如金额变动、条款修改）。
