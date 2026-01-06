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
├── src/                    # 业务模块
│   ├── config.py           # 环境变量配置 (pydantic-settings)
│   ├── database.py         # 数据库连接 (SQLModel + asyncpg)
│   ├── exceptions.py       # 自定义异常
│   ├── json_repir.py       # JSON 修复工具
│   ├── banks/              # 🆕 银行处理器模块 (策略模式)
│   │   ├── __init__.py         # 模块入口，自动注册所有 Handler
│   │   ├── base.py             # 基类 BankHandler + 注册装饰器
│   │   ├── shandong_handler.py # 山东地方银行
│   │   ├── everbright_handler.py # 光大银行
│   │   ├── cmb_handler.py      # 招商银行
│   │   ├── jining_handler.py   # 济宁银行
│   │   ├── cgb_handler.py      # 广发银行
│   │   └── psbc_handler.py     # 邮储银行
│   ├── files/              # 文件上传与银行识别
│   │   ├── router.py       # 上传/识别/导出 API
│   │   └── models.py       # 数据模型
│   ├── transactions/       # 交易明细查询
│   │   ├── router.py       # 交易查询 API
│   │   ├── models.py       # 交易数据模型
│   │   └── service.py      # 记录创建服务
│   └── contracts/          # 合同比对
│       ├── router.py       # 比对任务 API
│       └── models.py       # 合同数据模型
├── config/
│   ├── bank_schemas/       # 银行模板配置 (JSON)
│   │   ├── bank_registry.json   # 银行注册表
│   │   ├── shandong_local.json  # 山东地方银行
│   │   ├── everbright.json      # 光大银行
│   │   ├── cmb.json             # 招商银行
│   │   ├── jining.json          # 济宁银行
│   │   ├── cgb.json             # 广发银行
│   │   └── psbc.json            # 邮储银行
│   └── prompts.json        # AI 提示词配置
└── services/               # 通用服务
    ├── pdf_processor.py        # PDF 解析 & 银行识别入口
    ├── pdf/                    # PDF 处理子模块
    │   ├── bank_detector.py    # 银行类型检测 (文件名/印章/Logo)
    │   ├── data_extractor.py   # AI 数据提取
    │   ├── excel_exporter.py   # Excel 导出 (广发跨页合并)
    │   ├── image_marker.py     # 图像标注处理
    │   └── pdf_utils.py        # PDF 工具函数
    └── contract_processor.py   # 合同比对处理
```

## 🏗️ 银行处理器架构

### 策略模式设计

采用策略模式将各银行的处理逻辑封装为独立的 Handler 类：

```python
from src.banks import get_bank_handler

# 获取银行处理器
handler = get_bank_handler("psbc")

# 调用统一接口
transactions = await handler.get_transactions(session, file_id)
summary = await handler.get_summary(session, file_id)
```

### BankHandler 抽象方法

| 方法 | 类型 | 说明 |
| :--- | :--- | :--- |
| `get_transactions()` | 抽象 | 获取交易明细 |
| `get_summary()` | 抽象 | 获取汇总信息 |
| `export_to_excel()` | 抽象 | 导出到 Excel |
| `create_records()` | 抽象 | 创建数据库记录 |
| `delete_records()` | 抽象 | 删除关联记录 |
| `get_bank_names()` | 抽象 | 银行匹配名称列表 |
| `get_summary_schema()` | 抽象 | 汇总 Schema |
| `get_transaction_schema()` | 抽象 | 交易 Schema |
| `get_vertical_line_config()` | 可选 | 辅助线配置 |
| `get_summary_config()` | 可选 | 汇总提取配置 |

### 添加新银行模板

**只需 3 步，无需修改任何 Router 代码：**

1. 创建 `src/banks/xxx_handler.py`：

```python
from src.banks.base import BankHandler, register_bank

@register_bank
class XxxHandler(BankHandler):
    bank_type = "xxx"
    
    def get_bank_names(self) -> List[str]:
        return ["XXX银行", "XXX Bank"]
    
    def get_summary_schema(self) -> Dict[str, Any]:
        return {"账号": "", "户名": "", ...}
    
    def get_transaction_schema(self) -> Dict[str, Any]:
        return {"交易时间": "", "金额": "", ...}
    
    # ... 实现其他抽象方法
```

2. 在 `src/banks/__init__.py` 中导入新 Handler
3. 在 `src/transactions/models.py` 添加对应数据表

## 📡 API 接口

### 🏦 银行流水

| 方法 | 路径 | 描述 |
| :--- | :--- | :--- |
| `GET` | `/api/files` | 获取文件列表 |
| `POST` | `/api/files/upload` | 上传文件 |
| `POST` | `/api/files/{id}/recognize` | 触发识别 |
| `GET` | `/api/files/{id}/export` | 导出 Excel |
| `DELETE` | `/api/files/{id}` | 删除文件及关联数据 |
| `GET` | `/api/transactions/{id}` | 获取交易明细 |
| `GET` | `/api/transactions/{id}/summary` | 获取汇总信息 |

### 📋 合同比对

| 方法 | 路径 | 描述 |
| :--- | :--- | :--- |
| `POST` | `/api/contracts/compare` | 创建比对任务 |
| `GET` | `/api/contracts/{id}` | 查询任务状态 |
| `GET` | `/api/contracts/{id}/diffs` | 获取差异列表 |

## 📦 主要依赖

| 包名 | 版本 | 用途 |
| :--- | :--- | :--- |
| `fastapi` | ≥0.124.2 | Web 框架 |
| `sqlmodel` | ≥0.0.27 | ORM |
| `openai` | ≥2.9.0 | LLM API 调用 |
| `pdf2image` | ≥1.17.0 | PDF 转图片 |
| `openpyxl` | ≥3.1.5 | Excel 导出 |
| `pandas` | ≥2.3.3 | 数据处理 |
| `pillow` | ≥12.0.0 | 图像处理 |
| `asyncpg` | ≥0.31.0 | PostgreSQL 异步驱动 |

## 🗄️ 数据模型

### 银行流水表结构

| 银行 | 汇总表 | 明细表 |
| :--- | :--- | :--- |
| 山东地方银行 | `ShandongLocalSummary` | `ShandongLocalTransaction` |
| 光大银行 | `EverbrightSummary` | `EverbrightTransaction` |
| 招商银行 | `CmbSummary` | `CmbTransaction` |
| 济宁银行 | `JiningSummary` | `JiningTransaction` |
| 广发银行 | `CgbSummary` | `CgbTransaction` |
| 邮储银行 | `PsbcSummary` | `PsbcTransaction` |

每种银行的表结构与其 Schema 字段对应，确保数据完整性。
