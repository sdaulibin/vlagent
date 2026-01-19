# 🌊 vl_flow

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.124-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue 3.5](https://img.shields.io/badge/Vue-3.5-4FC08D.svg)](https://vuejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**vl_flow** 是一个基于 **Qwen-VL** 大模型的智能文档识别与分析平台。它利用先进的多模态模型能力，实现了银行流水的高精度识别与结构化。

---

## ✨ 核心功能

### 🏦 银行流水识别 (Multi-Bank Support)

智能识别多种银行流水 PDF，自动提取账户信息、余额明细、交易双方等关键数据。

- **高精度识别**: 基于 Qwen-VL，支持复杂表格和跨页识别。
- **自动检测**: 自动识别银行类型，智能匹配识别策略。
- **一键导出**: 识别结果可直接导出为 Excel 文档。
- **跨页合并**: 自动处理跨页连续记录，确保数据完整性。

---

## 🛠️ 技术栈

| 领域        | 技术选择                                                         |
| :---------- | :--------------------------------------------------------------- |
| **前端**    | Vue 3.5 + TypeScript 5.9 + Tailwind CSS 4 + Tiptap 3             |
| **后端**    | FastAPI 0.124 + SQLModel 0.0.27 + Python 3.11                    |
| **AI 模型** | Qwen-VL (Local Deployment) / DashScope API                       |
| **数据库**  | PostgreSQL (Production) / SQLite (Dev)                           |
| **包管理**  | [uv](https://github.com/astral-sh/uv) (Backend) + npm (Frontend) |

---

## 🚀 快速开始

### 📋 环境要求

- **Python 3.11+**
- **Node.js 18+**
- **Poppler** (用于 PDF 转图片)
  - macOS: `brew install poppler`
  - Ubuntu: `sudo apt-get install poppler-utils`

### 1️⃣ 克隆与配置

```bash
git clone https://github.com/your-repo/vl_flow.git
cd vl_flow
```

### 2️⃣ 启动后端

```bash
cd backend
cp .env.example .env
# 编辑 .env 配置 LLM 地址与数据库连接
uv sync
uv run uvicorn main:app --reload --port 8000
```

### 3️⃣ 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 [http://localhost:5173](http://localhost:5173) 即可进入系统。

---

## 📁 项目结构

```bash
vl_flow/
├── backend/          # FastAPI 后端服务 (Logic, AI, DB)
│   ├── src/banks/    # 银行处理策略实现
│   ├── src/models/   # 结构化数据模型
│   └── config/       # 识别提示词与 Schema 配置
├── frontend/         # Vue 3 前端应用 (UI, Dashboard)
│   ├── src/views/    # 核心页面 (流水识别)
│   └── src/components/ bank-results/ # 各银行 UI 展示组件
└── docker-compose.yml # 容器化部署配置
```

---

## 🏗️ 架构概览

### 插件化银行处理器 (Strategy Pattern)

系统采用策略模式，添加新银行支持仅需 3 步：

1. **定义模型**: 在 `backend/src/models` 添加结构。
2. **实现处理器**: 继承 `BankHandler` 并实现提取逻辑。
3. **前端渲染**: 在 `frontend/src/components/bank-results` 添加展示组件。

---

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。
