import logging
import os
import random
import time
from logging.handlers import RotatingFileHandler

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

# ── 日志配置：同时输出到控制台和文件 ──
LOG_FORMAT = f"%(asctime)s [PID={os.getpid()}] %(levelname)s %(name)s: %(message)s"
LOG_DIR = os.getenv("LOG_DIR", "/app/logs")
LOG_FILE = os.path.join(LOG_DIR, "vlagent.log")

# 容器环境写文件，本地环境无法创建目录则只输出到控制台
_file_handler = None
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    _file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=50 * 1024 * 1024, backupCount=5, encoding="utf-8",
    )
    _file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
except OSError:
    pass  # 本地开发环境，只输出到控制台

_formatter = logging.Formatter(LOG_FORMAT)

# 控制台 handler
_console = logging.StreamHandler()
_console.setFormatter(_formatter)

# 应用到 root logger，所有子 logger 自动继承
_root = logging.getLogger()
_root.setLevel(logging.INFO)
_root.addHandler(_console)
if _file_handler:
    _root.addHandler(_file_handler)

# 确保 uvicorn 的 access/error 日志也写入文件
for _name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    _uv = logging.getLogger(_name)
    _uv.handlers.clear()
    _uv.setLevel(logging.INFO)
    _uv.addHandler(_console)
    if _file_handler:
        _uv.addHandler(_file_handler)


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


# 把 src/ 加入 sys.path，使引擎包（financial_compare.compare.xxx 等裸名风格）可导入。
# 引擎移植自参考项目，内部 import 用 financial_compare.xxx 前缀（不带 src.），
# 需要 src/ 在 import 搜索路径里。
import sys as _sys
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC_DIR not in _sys.path:
    _sys.path.insert(0, _SRC_DIR)

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


# 请求日志中间件：记录每个请求落到哪个 worker（PID）+ 耗时
@app.middleware("http")
async def log_request_with_pid(request, call_next):
    import os as _os
    pid = _os.getpid()
    t0 = time.monotonic()
    response = await call_next(request)
    elapsed = (time.monotonic() - t0) * 1000
    logger.info(
        f"[PID={pid}] {request.method} {request.url.path} "
        f"{response.status_code} {elapsed:.0f}ms"
    )
    return response

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
