# vl_flow

基于 Qwen-VL 大模型的智能文档识别与分析平台。

## ✨ 功能

| 场景                | 状态 | 说明                                                   |
| :------------------ | :--: | :----------------------------------------------------- |
| **🏦 银行流水识别** |  ✅  | 智能提取交易明细、对方账户信息，支持多银行模板自动识别 |
| **📋 合同比对**     |  ✅  | 智能比对 PDF/Word 文档差异，支持并排高亮显示增删改内容 |
| **📄 发票识别**     |  🔜  | 开发中，支持多票据自动分类与关键信息提取               |

### 🏦 银行流水识别 - 多银行支持

| 银行             | 模板 ID          | 汇总信息                     | 交易明细                                   |
| :--------------- | :--------------- | :--------------------------- | :----------------------------------------- |
| **山东地方银行** | `shandong_local` | 账户名称、账(卡)号、收支汇总 | 交易时间、收支金额、对方户名、摘要备注     |
| **光大银行**     | `everbright`     | 账户名称、账号、借贷发生额   | 交易日期、借/贷、对方名称、凭证号、流水号  |
| **招商银行**     | `cmb`            | 账号名、出入账汇总           | 交易流水号、收付方信息、公司一卡通号       |
| **济宁银行**     | `jining`         | 账户名称、账号、收支汇总     | 交易时间、收付金额、对方信息、开户机构     |
| **广发银行**     | `cgb`            | 户名、账号、收支笔数金额     | 流水号、交易时间、对方账户、摘要附言       |
| **邮储银行**     | `psbc`           | 账号、户名、收支汇总         | 交易时间、收支金额、对方行名、用途附言     |
| **工商银行**     | `icbc`           | 本方账号户名、币种、开户行   | 交易时间、转入/转出金额、对方单位、用途    |
| **建设银行**     | `ccb`            | 本方户名、打印日期           | 交易时间、借贷金额、对方开户机构、记账日期 |

> 💡 通过策略模式扩展新银行模板，只需创建 Handler 文件即可
> 🆕 广发银行支持多汇总识别、跨页记录自动合并

## 🛠️ 技术栈

- **前端**: Vue 3.5 + TypeScript 5.9 + Tailwind CSS 4 + Tiptap 3
- **后端**: FastAPI 0.124 + SQLModel 0.0.27 + Python 3.11
- **数据库**: PostgreSQL / SQLite (开发环境)
- **AI 模型**: Qwen-VL (本地部署) / 通义千问 VL
- **包管理**: uv (后端) + npm (前端)

## 🚀 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- Poppler (PDF 处理依赖)
  - macOS: `brew install poppler`
  - Ubuntu: `sudo apt-get install poppler-utils`

### 1. 配置环境变量

```bash
cd backend
cp .env.example .env
# 编辑 .env 配置本地 LLM 地址
```

### 2. 启动后端服务

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000
```

### 3. 启动前端服务

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
│   ├── src/views/           # 页面视图 (Home, BankStatement, ContractCompare)
│   ├── src/components/      # 组件 (FileList, ResultList 等)
│   │   └── bank-results/    # 🆕 银行汇总组件 (按银行拆分)
│   ├── src/api/             # API 请求封装
│   └── src/types.ts         # TypeScript 类型定义
├── backend/                 # FastAPI 后端服务
│   ├── main.py              # 应用入口
│   ├── api.py               # 路由注册
│   ├── src/                 # 业务模块
│   │   ├── banks/           # 银行处理器模块 (策略模式)
│   │   │   ├── base.py          # 基类 BankHandler + 注册表
│   │   │   ├── *_handler.py     # 各银行处理器
│   │   │   └── ...              # shandong, everbright, cmb, jining, cgb, psbc, icbc, ccb
│   │   ├── models/          # 🆕 银行模型模块 (按银行拆分)
│   │   │   ├── *_models.py      # 各银行数据模型
│   │   │   └── ...              # shandong, everbright, cmb, jining, cgb, psbc, icbc, ccb
│   │   ├── files/           # 文件上传与处理
│   │   ├── transactions/    # 交易明细查询 (统一导出入口)
│   │   ├── contracts/       # 合同比对逻辑
│   │   ├── config.py        # 环境变量配置
│   │   └── database.py      # 数据库连接
│   ├── config/
│   │   ├── bank_schemas/    # 银行模板配置 (JSON)
│   │   └── prompts/         # 🆕 AI 提示词配置 (按银行拆分)
│   │       ├── default.json
│   │       └── *.json           # 各银行专属提示词
│   └── services/            # 通用服务
│       ├── pdf_processor.py     # PDF 解析与银行识别
│       ├── pdf/                 # PDF 处理子模块
│       └── contract_processor.py    # 合同比对
└── docker-compose.yml       # 基础设施编排
```

## 🏗️ 架构设计

### 银行处理器策略模式

采用策略模式封装各银行的处理逻辑，提升可维护性和扩展性：

```
┌─────────────────────────────────────────────────────────┐
│                    BankHandler (基类)                    │
├─────────────────────────────────────────────────────────┤
│ + get_transactions()    获取交易明细                     │
│ + get_summary()         获取汇总信息                     │
│ + export_to_excel()     导出 Excel                      │
│ + create_records()      创建数据库记录                   │
│ + delete_records()      删除关联记录                     │
│ + get_bank_names()      银行匹配名称                     │
│ + get_summary_schema()  汇总 Schema                     │
│ + get_transaction_schema()  交易 Schema                 │
└─────────────────────────────────────────────────────────┘
          ▲
          │ 继承
     ┌──────┴──────┬────────┬────────┬────────┬────────┬────────┐
     │             │        │        │        │        │        │
 ┌───┴───┐ ┌───────┴──┐ ┌───┴──┐ ┌───┴──┐ ┌───┴──┐ ┌───┴──┐ ┌───┴──┐
 │Shandong│ │Everbright│ │ CMB  │ │Jining│ │ CGB  │ │ PSBC │ │ ICBC │
 │Handler │ │ Handler  │ │Handle│ │Handle│ │Handle│ │Handle│ │Handle│
 └────────┘ └──────────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘
```

### 添加新银行（3 步）

1. 创建 `backend/src/banks/xxx_handler.py`
2. 继承 `BankHandler` 并实现所有抽象方法
3. 使用 `@register_bank` 装饰器注册

**无需修改任何 Router 代码！**

## 📡 API 概览

访问 Swagger UI: http://localhost:8000/docs

### 🏦 银行流水

- `GET /api/files` - 获取已上传文件列表
- `POST /api/files/upload` - 上传银行流水文件
- `POST /api/files/{id}/recognize` - 触发识别
- `GET /api/files/{id}/export` - 导出 Excel
- `GET /api/transactions/{id}` - 获取交易明细
- `GET /api/transactions/{id}/summary` - 获取汇总信息

### 📋 合同比对

- `POST /api/contracts/compare` - 上传文档进行比对
- `GET /api/contracts/{id}` - 查询任务状态
- `GET /api/contracts/{id}/diffs` - 获取差异数据

## 📄 License

MIT License
