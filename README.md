# VL_Flow

VL_Flow 是一个基于本地大模型（Local LLM）的银行流水智能识别与分析系统。

## 项目结构

本项目包含前后端分离的两个部分：

-   **[Frontend](./frontend)**: 基于 Vue 3 + TypeScript + Tailwind CSS 构建的 Web 界面。
-   **[Backend](./backend)**: 基于 FastAPI + Python 构建的后端服务，处理 PDF 识别与 LLM 交互。

## 快速开始

### 1. 启动后端

请参考 [Backend README](./backend/README.md) 进行详细配置。

```bash
cd backend
# 使用 uv 或 pip 安装依赖
uv sync
# 启动服务
uv run uvicorn main:app --reload
```

### 2. 启动前端

请参考 [Frontend README](./frontend/README.md) 进行详细配置。

```bash
cd frontend
npm install
npm run dev
```

打开浏览器访问 [http://localhost:5173](http://localhost:5173) 即可使用。
