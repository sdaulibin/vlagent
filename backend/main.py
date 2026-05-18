import logging
import os
import random
import time

import jwt

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.database import init_db
from src.config import settings
from src.file_provider.service import init_jvm, shutdown_jvm
from src.sync.scheduler import start_scheduler, stop_scheduler, run_sync
from api import api_router

logger = logging.getLogger(__name__)

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("src.auth").setLevel(logging.INFO)
logging.getLogger("src.auth").addHandler(logging.StreamHandler())


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Alembic: 直接写入版本标记，不走 env.py 的 async 引擎
    try:
        from sqlalchemy import text
        from src.database import engine
        revision = "135eef68092d"  # baseline revision
        async with engine.begin() as conn:
            await conn.execute(text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
            ))
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.first()
            if row is None:
                await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES (:rev)"), {"rev": revision})
                logger.info(f"Alembic version stamped: {revision}")
            else:
                logger.info(f"Alembic version: {row[0]}")
    except Exception as e:
        logger.debug(f"Alembic stamp skipped: {e}")
    if settings.ECM_ENABLED:
        if not init_jvm():
            logger.warning("JVM 启动失败，影像平台功能不可用")
    # 启动时立即执行一次同步，然后开启定时调度
    if settings.DATABASE_UPSTREAM_URL:
        await run_sync()
        start_scheduler()
    yield
    stop_scheduler()
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


@app.get("/")
async def root():
    return {"message": "Welcome to VLAgent API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/dev-token")
async def dev_token():
    """开发模式：生成测试用 JWT token（无需认证），随机分配测试用户"""
    _DEV_USERS = [
        {"name": "QD24000010", "user_name": "李彬"},
        {"name": "QD24000099", "user_name": "张三"},
        {"name": "QD24000088", "user_name": "王二"},
    ]
    now = time.time()
    user = random.choice(_DEV_USERS)
    payload = {
        "name": user["name"],
        "user_name": user["user_name"],
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
