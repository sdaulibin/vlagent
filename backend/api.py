from fastapi import APIRouter

from src.files.router import router as files_router
from src.transactions.router import router as transactions_router
from src.contracts.router import router as contracts_router

api_router = APIRouter()

# 文件管理
api_router.include_router(files_router)

# 交易记录
api_router.include_router(transactions_router)

# 合同比对
api_router.include_router(contracts_router)
