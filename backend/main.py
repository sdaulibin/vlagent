import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.database import init_db
from src.config import settings
from src.file_provider.service import init_jvm, shutdown_jvm
from api import api_router

logger = logging.getLogger(__name__)


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
    title="vl_flow API",
    description="Bank Transaction Identification Service",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

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
    return {"message": "Welcome to VL_Flow API"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
