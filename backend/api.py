from fastapi import APIRouter

from apps.files.api import router as files_router
from apps.transactions.api import router as transactions_router
from apps.contracts.api import router as contracts_router

api_router = APIRouter()

# 文件管理
api_router.include_router(files_router)

# 交易记录
api_router.include_router(transactions_router)

# 合同比对
api_router.include_router(contracts_router)

