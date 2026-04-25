# ⚙️ Backend Service

基于 **FastAPI** + **Python 3.11** 构建的高性能后端服务，集成了 **Qwen-VL** 多模态大模型，支持银行流水识别、询证函识别与格式比对、证件识别、发票识别、文档比对等多种文档智能处理功能。

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
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost/vlagent
   ```

3. **运行服务**:
   ```bash
   uv run uvicorn main:app --reload --port 8000
   ```
   API 文档将自动生成在: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🏗️ 核心架构：策略模式 (Strategy Pattern)

后端采用高度解耦的策略模式来处理不同银行的流水模板。每种银行都有其专属的 `Handler`，这使得系统具有极强的扩展性。目前已适配 11 家银行。

### 🧩 BankHandler 接口

所有的银行处理器都必须继承 `BankHandler` 基类并实现核心方法：

| 方法                 | 说明                                       |
| :------------------- | :----------------------------------------- |
| `get_transactions()` | 从数据库检索该银行的交易明细               |
| `get_summary()`      | 从数据库检索该银行的汇总信息               |
| `create_records()`   | 将 AI 提取的原始数据转换为数据库持久化记录 |
| `get_bank_names()`   | 返回用于匹配该银行的关键词列表             |
| `get_schemas()`      | 提供给 AI 的 JSON Schema 定义              |

### 🆕 添加新银行支持 (只需 3 步)

1. **定义 Model**: 在 `src/models/` 创建 `xxx_models.py`，定义汇总和明细表结构。
2. **实现 Handler**: 创建 `src/banks/xxx_handler.py`，继承 `BankHandler` 并使用 `@register_bank` 装饰。
3. **配置 Prompt**: 在 `config/` 添加专属的 AI 提取提示词和 Schema。

---

## 📁 目录结构

```bash
backend/
├── main.py                   # FastAPI 应用入口与中间件配置
├── api.py                    # 统一路由分发中心
├── src/
│   ├── banks/                # 银行流水处理器 (Strategy Pattern, 11家银行)
│   │   ├── abc_handler.py    #   农业银行
│   │   ├── boc_handler.py    #   中国银行
│   │   ├── bocom_handler.py  #   交通银行
│   │   ├── ccb_handler.py    #   建设银行
│   │   ├── cgb_handler.py    #   广发银行
│   │   ├── cmb_handler.py    #   招商银行
│   │   ├── everbright_handler.py  # 光大银行
│   │   ├── icbc_handler.py   #   工商银行
│   │   ├── jining_handler.py #   济宁银行
│   │   ├── psbc_handler.py   #   邮储银行
│   │   └── shandong_handler.py   # 齐鲁银行
│   ├── models/               # 各银行数据模型 (SQLModel)
│   ├── files/                # 文件上传、存储与识别状态管理
│   ├── transactions/         # 统一的交易数据查询接口
│   ├── confirmation_letter/  # 📝 询证函识别模块
│   │   ├── models.py         #   ConfirmationFile + ConfirmationResult
│   │   ├── router.py         #   API 路由
│   │   └── service.py        #   AI 识别逻辑与 Prompt
│   ├── confirmation_compare/ # 📐 询证函格式比对模块
│   │   ├── models.py         #   FormatTask + FormatDifference
│   │   ├── router.py         #   API 路由
│   │   ├── service.py        #   比对逻辑
│   │   └── templates.py      #   标准模板定义
│   ├── credentials/          # 🪪 证件识别模块
│   │   ├── models.py         #   凭证数据模型
│   │   ├── router.py         #   API 路由
│   │   ├── service.py        #   AI 识别与网格切片逻辑
│   │   └── prompts.py        #   各证件类型提示词
│   ├── invoice_recognition/  # 🧾 发票识别模块
│   │   ├── models.py         #   InvoiceFile + InvoiceResult
│   │   ├── router.py         #   API 路由
│   │   └── service.py        #   发票识别逻辑
│   ├── native_statement/     # 📊 原生电子流水解析模块
│   │   ├── router.py         #   API 路由
│   │   └── service.py        #   PDF 原生解析逻辑
│   ├── documents/            # 📄 文档比对模块
│   │   ├── models.py         #   DocumentCompareTask + DocumentPageDiff
│   │   ├── router.py         #   API 路由（含公开文件访问）
│   │   └── service.py        #   文档提取、页级对齐、diff 计算
│   ├── legal_contact/        # 📋 律师联系方式提取
│   ├── file_provider/        # 📦 ECM 影像平台文件服务
│   │   ├── router.py         #   API 路由
│   │   └── service.py        #   SunECM Java SDK 集成
│   ├── config.py             # 全局配置
│   ├── database.py           # 数据库引擎与会话管理
│   └── exceptions.py         # 自定义异常
├── services/                 # 通用业务逻辑
│   ├── pdf/                  # PDF 解析、银行检测、数据提取、Excel 导出
│   └── core/                 # AI 请求、JSON 修复、配置管理
└── config/                   # 外部化配置 (JSON schemas, Prompts, 银行模板)
```

---

## 📡 核心 API 概览

### 🏦 银行流水模块

- `POST /api/files/upload`: 上传 PDF/图片。
- `POST /api/files/{id}/recognize`: 异步启动 AI 识别任务。
- `GET /api/transactions/{id}`: 获取识别后的结构化明细。
- `GET /api/files/{id}/export`: 生成并下载标准化的 Excel 报表。

### 📊 原生电子流水模块

- `POST /api/native-statement/check`: 检测 PDF 是否为原生电子格式。
- `POST /api/native-statement/parse`: 解析原生电子流水返回 JSON。
- `POST /api/native-statement/parse-to-excel`: 解析并导出 Excel。

### 📝 询证函识别模块

文件信息与识别结果分表存储（`confirmation_files` + `confirmation_results`）：

- `POST /api/confirmation/upload`: 上传询证函 PDF。
- `POST /api/confirmation/{id}/recognize`: AI 识别 12 个关键字段。
- `GET /api/confirmation`: 获取所有询证函列表（含识别结果）。
- `PUT /api/confirmation/{id}/result`: 人工修改识别结果。
- `DELETE /api/confirmation/{id}`: 删除询证函及关联数据。

### 📐 询证函格式比对模块

- `GET /api/format-compare/templates`: 获取可用模板列表。
- `POST /api/format-compare/upload`: 上传询证函。
- `POST /api/format-compare/{task_id}/compare`: 执行格式比对。
- `GET /api/format-compare/{task_id}`: 获取比对结果（含差异分级）。
- `GET /api/format-compare/templates/{format_key}/preview`: 预览模板 PDF。

### 🪪 证件识别模块

- `POST /api/credentials/extract`: 上传证件文件并提取结构化数据（支持 8 种类型）。

### 🧾 发票识别模块

- `POST /api/invoice_recognition/upload`: 上传发票进行识别。
- `GET /api/invoice_recognition/list`: 获取所有已识别发票列表。
- `GET /api/invoice_recognition/list/{file_id}`: 获取指定发票识别结果。
- `DELETE /api/invoice_recognition/{file_id}`: 删除发票及结果。

### 📄 文档比对模块

- `POST /api/documents/compare`: 上传两份文档并启动异步比对。
- `POST /api/documents/list`: 获取所有比对任务列表。
- `POST /api/documents/list/{task_id}`: 获取任务详情（含页级 diff）。
- `POST /api/documents/{task_id}/status`: 轮询任务状态。
- `POST /api/documents/{task_id}/file/{doc_type}`: 获取原始文件（需认证）。
- `GET /api/documents/{task_id}/file/{doc_type}`: 获取原始文件（无需认证，用于 iframe 嵌入）。
- `DELETE /api/documents/{task_id}`: 删除比对任务及关联数据。

### 📦 ECM 文件服务模块

- `GET /api/file-provider/status`: 检查 JVM 和 ECM SDK 状态。
- `POST /api/file-provider/upload`: 上传文件到 ECM。
- `POST /api/file-provider/download`: 从 ECM 下载文件（多文件自动打包 ZIP）。
- `POST /api/file-provider/query`: 查询 ECM 文件信息。
- `DELETE /api/file-provider/{busi_serial_no}`: 删除 ECM 文件。

---

## 📦 技术栈详情

- **Framework**: FastAPI (Asynchronous)
- **ORM**: SQLModel (SQLAlchemy + Pydantic)
- **DB Driver**: asyncpg
- **PDF Engine**: pdf2image + pdfplumber + camelot + Pillow
- **Data Export**: Pandas + Openpyxl
- **AI Integration**: OpenAI SDK (兼容本地 LLM 网关)
- **Java Integration**: JPype (ECM SDK 调用)
