# VL_Flow

VL_Flow 是一个基于本地大模型（Local LLM）的银行流水智能识别与分析系统。

## 项目结构

本项目包含前后端分离的两个部分：

-   **[Frontend](./frontend)**: 基于 Vue 3 + TypeScript + Tailwind CSS 构建的 Web 界面。
-   **[Backend](./backend)**: 基于 FastAPI + Python 构建的后端服务，处理 PDF 识别与 LLM 交互。

## 技术栈

| 模块 | 技术 |
|------|------|
| 前端 | Vue 3, TypeScript, Tailwind CSS, Vite |
| 后端 | FastAPI, Python 3.11+, SQLModel |
| 数据库 | PostgreSQL (Docker) |
| AI | Qwen-VL (本地部署) |

## 快速开始

### 1. 启动数据库

```bash
docker compose up -d
```

### 2. 启动后端

请参考 [Backend README](./backend/README.md) 进行详细配置。

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000
```

### 3. 启动前端

请参考 [Frontend README](./frontend/README.md) 进行详细配置。

```bash
cd frontend
npm install
npm run dev
```

打开浏览器访问 [http://localhost:5173](http://localhost:5173) 即可使用。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/files` | 获取文件列表 |
| GET | `/api/files/{id}` | 获取文件详情 |
| POST | `/api/files/upload` | 上传PDF文件 |
| GET | `/api/transactions/{file_id}` | 获取交易记录 |

## License

MIT
