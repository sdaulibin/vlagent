# Backend - VL_Flow

这部分是 VL_Flow 项目的后端服务，基于 FastAPI 构建。它负责接收前端上传的银行流水 PDF 文件，处理文件（拆分、转图、OCR），并调用本地部署的大模型（Local LLM）提取交易信息，最终返回结构化的交易数据。

## 功能特性

-   **API 服务**: 提供 RESTful API 供前端调用。
-   **PDF 处理**: 使用 `pdf2image` 将 PDF 转换为图片。
-   **智能识别**: 集成 LLM (Qwen-VL) 进行视觉识别和信息提取。
-   **数据格式化**: 将非结构化数据转换为标准 JSON 格式并支持 Excel 导出。

## 技术栈

-   **Python**: >= 3.11
-   **Web 框架**: FastAPI
-   **依赖管理**: uv
-   **PDF 工具**: pdf2image, Poppler
-   **数据处理**: Pandas, Pillow

## 环境准备

### 1. 安装系统依赖

由于使用了 `pdf2image`，需要在系统中安装 `poppler`。

-   **MacOS**:
    ```bash
    brew install poppler
    ```
-   **Linux (Ubuntu/Debian)**:
    ```bash
    sudo apt-get install poppler-utils
    ```

### 2. 安装 Python 依赖

本项目使用 [uv](https://github.com/astral-sh/uv) 进行快速依赖管理。

```bash
# 进入后端目录
cd backend

# 初始化环境并安装依赖
uv sync
```

或者使用传统的 pip：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # 如果有 requirements.txt
# 或者
pip install fastapi uvicorn python-multipart pydantic pdf2image Pillow pandas openai openpyxl
```

## 运行服务

使用 `uv` 运行：

```bash
# 在 backend 目录下
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

或者在激活虚拟环境后：

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

服务启动后，API 将在 `http://localhost:8000` 监听。

## API 文档

FastAPI 自动生成的交互式文档可在以下地址访问：
-   **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
-   **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 主要接口

-   `POST /api/upload`: 上传 PDF 文件并进行识别。
    -   Web 参数: `file` (Multipart/form-data)
    -   返回: 包含交易列表的 JSON 对象。

## 配置说明

核心配置位于 `services/core/config.py`，包括：
-   LLM 模型配置
-   API Key 和 URL
-   资源目录路径

## 目录结构

```
backend/
├── main.py                 # 应用入口
├── pyproject.toml          # 项目配置与依赖
├── uv.lock                 # 依赖锁定文件
├── routers/                # API 路由
│   └── upload.py           # 上传接口
├── services/               # 核心业务逻辑
│   ├── pdf_processor.py    # PDF 处理流程
│   ├── llm_service.py      # LLM 服务接口
│   └── core/               # 核心配置与工具
│       ├── config.py       # 配置文件
│       └── request_ai.py   # AI 请求封装
└── res/                    # 资源文件（上传的 PDF 和中间结果）
```
