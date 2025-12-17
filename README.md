# vl_flow

基于 Qwen-VL 大模型的智能文档识别与分析平台。

## ✨ 功能

| 场景 | 状态 | 说明 |
| :--- | :---: | :--- |
| **🏦 银行流水识别** | ✅ | 智能提取交易明细、对方账户信息，支持多银行模板自动识别 |
| **📋 合同比对** | ✅ | 智能比对 PDF/Word 文档差异，支持并排高亮显示增删改内容 |
| **📄 发票识别** | 🔜 | 开发中，支持多票据自动分类与关键信息提取 |

### 🏦 银行流水识别 - 多银行支持

| 银行 | 模板ID | 汇总信息 | 交易明细 |
| :--- | :--- | :--- | :--- |
| **山东地方银行** | `shandong_local` | 账户名称、账(卡)号、收支汇总 | 交易时间、收支金额、对方户名、摘要备注 |
| **光大银行** | `everbright` | 账户名称、账号、借贷发生额 | 交易日期、借/贷、对方名称、凭证号、流水号 |
| **招商银行** | `cmb` | 账号名、出入账汇总 | 交易流水号、收付方信息、公司一卡通号 |

> 💡 通过 JSON Schema 配置扩展新银行模板，无需修改代码

## 🛠️ 技术栈

*   **前端**: Vue 3 + TypeScript + Tailwind CSS + Tiptap
*   **后端**: FastAPI + SQLModel + Python 3.11
*   **数据库**: SQLite (开发) / PostgreSQL (生产)
*   **AI 模型**: Qwen-VL (本地部署)

## 🚀 快速开始

### 前置要求

*   Python 3.11+
*   Node.js 18+
*   Poppler (PDF 处理依赖)

### 1. 启动后端服务

```bash
cd backend
uv sync
uv run uvicorn main:app --reload
```

### 2. 启动前端服务

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 即可开始使用。

## 📁 项目结构

```
vl_flow/
├── frontend/                # Vue 3 前端应用
│   ├── src/views/           # 页面视图
│   ├── src/components/      # 组件 (FileList, ResultList, TiptapViewer)
│   └── src/types.ts         # TypeScript 类型定义
├── backend/                 # FastAPI 后端服务
│   ├── apps/                # 业务模块
│   │   ├── files/           # 文件上传与处理
│   │   ├── transactions/    # 交易明细查询
│   │   └── contracts/       # 合同比对逻辑
│   ├── config/
│   │   └── bank_schemas/    # 银行模板配置 (JSON)
│   ├── core/                # 核心配置 (DB, Config, AI)
│   └── services/            # 通用服务
│       ├── pdf_processor.py     # PDF 解析与银行识别
│       └── contract_processor.py # 合同比对
└── docker-compose.yml       # 基础设施编排
```

## 📡 API 概览

访问 Swagger UI: http://localhost:8000/docs

### 🏦 银行流水
*   `GET /api/files` - 获取已上传文件列表
*   `POST /api/files/upload` - 上传银行流水文件
*   `POST /api/files/{id}/recognize` - 触发识别
*   `GET /api/transactions/{id}` - 获取交易明细与汇总

### 📋 合同比对
*   `POST /api/contracts/compare` - 上传文档进行比对
*   `GET /api/contracts/{id}/diffs` - 获取差异数据

## 📄 License

MIT License
