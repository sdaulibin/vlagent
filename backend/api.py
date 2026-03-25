from fastapi import APIRouter

from src.files.router import router as files_router
from src.transactions.router import router as transactions_router
from src.contracts.router import router as contracts_router
from src.confirmation_letter.router import router as confirmation_router
from src.confirmation_letter.router import router as confirmation_router
from src.confirmation_compare.router import router as format_compare_router
from src.invoice_recognition.router import router as invoice_router
from src.native_statement.router import router as native_statement_router
from src.credentials.router import router as credentials_router

api_router = APIRouter()

# 文件管理
api_router.include_router(files_router)

# 交易记录
api_router.include_router(transactions_router)

# 合同比对
api_router.include_router(contracts_router)

# 询证函识别（独立模块）
api_router.include_router(confirmation_router)

# 询证函格式比对（独立模块）
api_router.include_router(format_compare_router)

# 发票识别（独立模块）
api_router.include_router(invoice_router)

# 原生 PDF 流水识别（独立模块）
api_router.include_router(native_statement_router)

# 类凭证识别（独立模块）
api_router.include_router(credentials_router)
