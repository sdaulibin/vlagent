import logging
import os
import time

import jwt

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.database import init_db
from src.config import settings
from src.file_provider.service import init_jvm, shutdown_jvm
from api import api_router, public_api_router

logger = logging.getLogger(__name__)

# 配置日志
logging.getLogger("src.auth").setLevel(logging.INFO)
logging.getLogger("src.auth").addHandler(logging.StreamHandler())


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if settings.ECM_ENABLED:
        if not init_jvm():
            logger.warning("JVM 启动失败，影像平台功能不可用")
    yield
    if settings.ECM_ENABLED:
        shutdown_jvm()


app = FastAPI(
    title="vlagent API",
    description="Bank Transaction Identification Service",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# 允许通过环境变量添加额外的 CORS 源（逗号分隔）
_extra_origins = os.getenv("CORS_ORIGINS", "")
if _extra_origins:
    origins.extend([o.strip() for o in _extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix="/api")
app.include_router(public_api_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Welcome to VLAgent API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/dev-token")
async def dev_token():
    """开发模式：生成测试用 JWT token（无需认证）"""
    now = time.time()
    payload = {
        "user_id": "QD24000010",
        "name": "李彬",
        "org_id": "",
        "user_type": "",
        "iat": int(now),
        "exp": int(now) + 86400,
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return {"token": token}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
