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
    """使用 alembic Python API 执行迁移（无需 CLI）"""
    from alembic.config import Config
    from alembic import command
    try:
        alembic_cfg = Config(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "alembic.ini")
        )
        alembic_cfg.set_main_option(
            "script_location",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "alembic"),
        )
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic upgrade to head: ok")
    except Exception as e:
        logger.warning(f"Alembic upgrade failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_alembic_upgrade()
    await init_db()
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
