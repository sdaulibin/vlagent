import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# 加载项目配置（会读取 .env 文件）
from src.config import settings

config = context.config

# 从 settings 获取数据库 URL，覆盖 alembic.ini 中的占位符
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 导入所有 SQLModel 模型，确保 metadata 包含全部表定义
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
from src.confirmation_compare.models import FormatCompareFile, FormatCompareResult
from src.invoice_recognition.models import InvoiceFile, InvoiceResult
from src.credentials.models import CredentialRecord, CredentialResult
from src.pdf_extract.models import PdfExtractTask, PdfExtractResult
from src.permissions.models import UserPermission
from src.modules.models import Module

from sqlmodel import SQLModel

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
