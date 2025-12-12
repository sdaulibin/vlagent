# Backend - VL_Flow

VL_Flow 后端服务，基于 FastAPI 构建。负责接收前端上传的银行流水 PDF 文件，调用本地部署的大模型（Qwen-VL）提取交易信息。

## 功能特性

- **RESTful API**: 提供标准化的 API 接口
- **PDF 处理**: 使用 `pdf2image` 将 PDF 转换为图片
- **智能识别**: 集成 Qwen-VL 进行视觉识别和信息提取
- **数据持久化**: PostgreSQL 数据库存储文件和交易记录

## 技术栈

- **Python**: >= 3.11
- **Web 框架**: FastAPI
- **ORM**: SQLModel + asyncpg
- **依赖管理**: uv
- **数据库**: PostgreSQL

## 目录结构

```
backend/
├── main.py                 # 应用入口
├── api.py                  # API 路由汇总
├── apps/                   # 应用模块
│   ├── files/              # 文件管理
│   │   ├── api.py          # 文件API
│   │   └── models.py       # 数据模型
│   └── transactions/       # 交易管理
│       └── api.py          # 交易API
├── core/                   # 核心模块
│   ├── config.py           # 配置
│   ├── database.py         # 数据库连接
│   ├── request_ai.py       # AI请求封装
│   └── json_repir.py       # JSON修复
├── services/               # 公共服务
│   └── pdf_processor.py    # PDF处理
└── res/                    # 资源文件
```

## 环境准备

### 1. 安装系统依赖

```bash
# MacOS
brew install poppler

# Linux (Ubuntu/Debian)
sudo apt-get install poppler-utils
```

### 2. 启动数据库

```bash
# 在项目根目录
docker compose up -d
```

### 3. 安装 Python 依赖

```bash
cd backend
uv sync
```

## 运行服务

```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

服务启动后，API 文档可在以下地址访问：
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/files` | 获取所有文件列表 |
| GET | `/api/files/{id}` | 获取单个文件详情 |
| POST | `/api/files/upload` | 上传并处理PDF文件 |
| GET | `/api/transactions/{file_id}` | 获取指定文件的交易记录 |

## 配置说明

核心配置位于 `core/config.py`：
- LLM 模型配置
- API Key 和 URL
- 资源目录路径

数据库配置位于 `core/database.py`：
- 默认连接: `postgresql+asyncpg://postgres:123456@localhost/vl_flow`
