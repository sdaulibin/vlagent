# ⚙️ Backend Service

基于 **FastAPI** + **Python 3.11** 构建的高性能后端服务，集成了 **Qwen-VL** 多模态大模型，专门用于文档的智能化处理与结构化数据提取。

---

## 🚀 快速启动

### 📋 前置要求
- **Python 3.11+**: 推荐使用 [uv](https://github.com/astral-sh/uv) 进行高效的包管理。
- **Poppler**: 用于 PDF 解析的核心依赖。
  - macOS: `brew install poppler`
  - Linux: `sudo apt-get install poppler-utils`

### 🛠️ 环境配置
1. **安装依赖**:
   ```bash
   uv sync
   ```
2. **配置环境变量**:
   复制 `.env.example` 并重命名为 `.env`，根据实际情况修改配置：
   ```ini
   # --- AI 模型配置 ---
   OPENAI_KEY=your-api-key-here
   OPENAI_URL=http://your-llm-gateway/v1
   MODEL_LOCAL=qwen-vl-local-name

   # --- 应用配置 ---
   RES_DIR=res                 # 资源存储目录
   RECOGNITION_TIMEOUT=300     # 识别超时时间 (秒)

   # --- 数据库配置 ---
   # 开发环境默认使用 SQLite，生产环境推荐 PostgreSQL
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost/vl_flow
   ```

3. **运行服务**:
   ```bash
   uv run uvicorn main:app --reload --port 8000
   ```
   API 文档将自动生成在: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🏗️ 核心架构：策略模式 (Strategy Pattern)

后端采用高度解耦的策略模式来处理不同银行的流水模板。每种银行都有其专属的 `Handler`，这使得系统具有极强的扩展性。

### 🧩 BankHandler 接口
所有的银行处理器都必须继承 `BankHandler` 基类并实现核心方法：

| 方法 | 说明 |
| :--- | :--- |
| `get_transactions()` | 从数据库检索该银行的交易明细 |
| `get_summary()` | 从数据库检索该银行的汇总信息 |
| `create_records()` | 将 AI 提取的原始数据转换为数据库持久化记录 |
| `get_bank_names()` | 返回用于匹配该银行的关键词列表 |
| `get_schemas()` | 提供给 AI 的 JSON Schema 定义 |

### 🆕 添加新银行支持 (只需 3 步)
1. **定义 Model**: 在 `src/models/` 创建 `xxx_models.py`，定义汇总和明细表结构。
2. **实现 Handler**: 创建 `src/banks/xxx_handler.py`，继承 `BankHandler` 并使用 `@register_bank` 装饰。
3. **配置 Prompt**: 在 `config/prompts/` 添加 `xxx.json`，定制专属的 AI 提取提示词。

---

## 📁 目录结构

```bash
backend/
├── main.py            # FastAPI 应用入口与中间件配置
├── api.py             # 统一路由分发中心
├── src/
│   ├── banks/         # 银行处理器实现 (Strategy implementations)
│   ├── models/        # 各银行数据模型 (SQLModel)
│   ├── files/         # 文件上传、存储与识别状态管理
│   ├── transactions/  # 统一的交易数据查询接口
│   └── contracts/     # 合同比对逻辑实现
├── services/          # 通用业务逻辑
│   ├── pdf/           # PDF 解析、银行检测、数据提取、Excel 导出
│   └── contract_processor.py # 文本比对算法
└── config/            # 外部化配置 (JSON schemas, Prompts)
```

---

## 📡 核心 API 概览

### 🏦 银行流水模块
- `POST /api/files/upload`: 上传 PDF/图片。
- `POST /api/files/{id}/recognize`: 异步启动 AI 识别任务。
- `GET /api/transactions/{id}`: 获取识别后的结构化明细。
- `GET /api/files/{id}/export`: 生成并下载标准化的 Excel 报表。

### 📋 合同比对模块
- `POST /api/contracts/compare`: 上传两个文档进行语义差异分析。
- `GET /api/contracts/{id}/diffs`: 获取详细的差异点列表（增删改）。

---

## 📦 技术栈详情
- **Framework**: FastAPI (Asynchronous)
- **ORM**: SQLModel (SQLAlchemy + Pydantic)
- **DB Driver**: asyncpg
- **PDF Engine**: pdf2image + Pillow
- **Data Export**: Pandas + Openpyxl
- **AI Integration**: OpenAI SDK (compatible with local LLM gateways)
