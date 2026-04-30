from sqlmodel import SQLModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    future=True,
    # 连接池配置 - 解决连接被关闭的问题
    pool_pre_ping=True,      # 每次使用前检查连接是否有效
    pool_size=5,             # 连接池大小
    max_overflow=10,         # 允许额外创建的连接数
    pool_recycle=300,        # 5分钟后回收连接，避免数据库主动断开
    pool_timeout=30,         # 获取连接超时时间
)

SessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db():
    # Import models to register them with SQLModel
    from src.files.models import FileRecord
    from src.transactions.models import (
        ShandongLocalSummary, ShandongLocalTransaction,
        EverbrightSummary, EverbrightTransaction,
        CmbSummary, CmbTransaction,
        JiningSummary, JiningTransaction,
        CgbSummary, CgbTransaction,
        PsbcSummary, PsbcTransaction,
        IcbcSummary, IcbcTransaction,
        CcbSummary, CcbTransaction,
        AbcSummary, AbcTransaction,
        BocSummary, BocTransaction,
        BocomSummary, BocomTransaction,
    )
    from src.documents.models import DocumentCompareTask, DocumentPageDiff
    from src.confirmation_letter.models import ConfirmationFile, ConfirmationResult
    from src.confirmation_compare.models import FormatCompareTask
    from src.invoice_recognition.models import InvoiceFile, InvoiceResult
    from src.credentials.models import CredentialRecord, CredentialResult
    from src.pdf_extract.models import PdfExtractTask, PdfExtractResult
    from src.permissions.models import UserPermission

    async with engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
        # 兼容已有数据库：补充询证函新增字段（幂等）
        await conn.execute(text(
            "ALTER TABLE confirmation_results "
            "ADD COLUMN IF NOT EXISTS signature_name VARCHAR"
        ))
        await conn.execute(text(
            "ALTER TABLE confirmation_results "
            "ADD COLUMN IF NOT EXISTS format_type VARCHAR"
        ))
        await conn.execute(text(
            "ALTER TABLE confirmation_results "
            "ADD COLUMN IF NOT EXISTS format_check_passed BOOLEAN"
        ))
        await conn.execute(text(
            "ALTER TABLE confirmation_results "
            "ADD COLUMN IF NOT EXISTS format_mismatches_json TEXT"
        ))
        # 格式比对：补充 AI 提取内容字段
        await conn.execute(text(
            "ALTER TABLE format_compare_tasks "
            "ADD COLUMN IF NOT EXISTS extracted_content_json TEXT"
        ))
        # 文档比对：补充 HTML 展示字段
        for col in [("html_a", "TEXT"), ("html_b", "TEXT")]:
            await conn.execute(text(
                f"ALTER TABLE document_page_diffs "
                f"ADD COLUMN IF NOT EXISTS {col[0]} {col[1]}"
            ))
        # 发票识别：补充 invoice_results 缺失字段（幂等）
        for col in [
            ("invoice_no", "VARCHAR"),
            ("invoice_date", "VARCHAR"),
            ("buyer_name", "VARCHAR"),
            ("buyer_tax_id", "VARCHAR"),
            ("seller_name", "VARCHAR"),
            ("seller_tax_id", "VARCHAR"),
            ("error_msg", "VARCHAR"),
        ]:
            await conn.execute(text(
                f"ALTER TABLE invoice_results "
                f"ADD COLUMN IF NOT EXISTS {col[0]} {col[1]}"
            ))

        # 用户权限系统：为所有表添加 user_id 字段（幂等）
        _ALL_TABLES = [
            "filerecord",
            "shandonglocalsummary", "shandonglocaltransaction",
            "everbrightsummary", "everbrighttransaction",
            "cmbsummary", "cmbtransaction",
            "jiningsummary", "jiningtransaction",
            "cgbsummary", "cgbtransaction",
            "psbcsummary", "psbctransaction",
            "icbcsummary", "icbctransaction",
            "ccbsummary", "ccbtransaction",
            "abcsummary", "abctransaction",
            "bocsummary", "boctransaction",
            "bocomsummary", "bocomtransaction",
            "document_compare_tasks", "document_page_diffs",
            "confirmation_files", "confirmation_results",
            "format_compare_tasks",
            "invoice_files", "invoice_results",
            "credential_records", "credential_results",
            "pdf_extract_tasks", "pdf_extract_results",
        ]
        for tbl in _ALL_TABLES:
            await conn.execute(text(
                f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS user_id VARCHAR"
            ))
            await conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS ix_{tbl}_user_id ON {tbl} (user_id)"
            ))


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
