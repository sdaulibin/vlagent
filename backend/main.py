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


def _run_alembic_upgrade():
    """通过子进程执行 alembic 迁移，完全隔离"""
    import subprocess
    import sys
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, timeout=15,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        if result.returncode == 0:
            logger.info("[ALEMBIC] upgrade to head: ok")
        else:
            logger.warning(f"[ALEMBIC] upgrade failed: {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        logger.warning("[ALEMBIC] upgrade timed out")
    except Exception as e:
        logger.warning(f"[ALEMBIC] upgrade error: {e}")


# 在模块加载时执行迁移（在 async 上下文之前）
_run_alembic_upgrade()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[STARTUP] 1. 开始 init_db")
    await init_db()
    logger.info("[STARTUP] 2. init_db 完成")
    if settings.ECM_ENABLED:
        if not init_jvm():
            logger.warning("JVM 启动失败，影像平台功能不可用")
    logger.info("[STARTUP] 3. DATABASE_UPSTREAM_URL=%s", bool(settings.DATABASE_UPSTREAM_URL))
    # 启动时立即执行一次同步，然后开启定时调度
    if settings.DATABASE_UPSTREAM_URL:
        logger.info("[STARTUP] 4. 开始上游数据同步")
        await run_sync()
        logger.info("[STARTUP] 5. 同步完成，启动定时调度")
        start_scheduler()
    logger.info("[STARTUP] 6. 启动完成，应用就绪")
    yield
    stop_scheduler()
    if settings.ECM_ENABLED:
        shutdown_jvm()


app = FastAPI(
    title="vlagent API",
    description="Bank Transaction Identification Service",
    version="1.0.0",
    lifespan=lifespan,
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
_api_prefix = os.getenv("API_PREFIX", "/api")
app.include_router(api_router, prefix=_api_prefix)


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
