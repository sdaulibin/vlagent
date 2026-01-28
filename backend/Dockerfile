FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖 (poppler 用于 PDF 处理, 中文字体和 CID 映射用于正确渲染 PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    poppler-data \
    fonts-wqy-zenhei \
    fonts-noto-cjk \
    fontconfig \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY pyproject.toml ./

# 使用清华镜像源安装依赖
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    asyncpg>=0.31.0 \
    fastapi>=0.124.2 \
    greenlet>=3.3.0 \
    jpype1>=1.6.0 \
    openai>=2.9.0 \
    openpyxl>=3.1.5 \
    pandas>=2.3.3 \
    pdf2image>=1.17.0 \
    pillow>=12.0.0 \
    pydantic>=2.12.5 \
    pydantic-settings>=2.12.0 \
    python-multipart>=0.0.20 \
    sqlmodel>=0.0.27 \
    uvicorn>=0.38.0

# 复制应用代码
COPY . .

# 创建资源目录
RUN mkdir -p /app/res

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
