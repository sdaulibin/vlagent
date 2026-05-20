import asyncio
import logging
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# 加载项目配置（会读取 .env 文件）
from src.config import settings

_logger = logging.getLogger("alembic.env")

config = context.config

# 确定数据库 URL：优先用调用方设置的，否则从 settings 获取
current_url = config.get_main_option("sqlalchemy.url")
if current_url and current_url != "placeholder" and "+psycopg2" in current_url:
    _logger.info("使用 sync URL (psycopg2)")
else:
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    _logger.info("使用 async URL")

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
    _logger.info("do_run_migrations: 开始")
    context.configure(connection=connection, target_metadata=target_metadata)
    _logger.info("do_run_migrations: context.configure 完成")
    with context.begin_transaction():
        _logger.info("do_run_migrations: 事务已开始，开始执行迁移")
        context.run_migrations()
        _logger.info("do_run_migrations: 迁移执行完成")


# ===== 同步迁移路径（用于程序化调用） =====

def run_sync_migrations() -> None:
    """使用同步引擎执行迁移"""
    url = config.get_main_option("sqlalchemy.url")
    _logger.info("run_sync_migrations: url=%s", url[:30] + "...")
    sync_url = url.replace("+asyncpg", "+psycopg2")
    connectable = create_engine(sync_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        do_run_migrations(connection)
    _logger.info("run_sync_migrations: connection 已关闭")
    connectable.dispose()
    _logger.info("run_sync_migrations: engine 已 dispose")


# ===== 异步迁移路径（用于 alembic CLI） =====

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
    url = config.get_main_option("sqlalchemy.url")
    if "+asyncpg" in url:
        _logger.info("走 async 路径")
        asyncio.run(run_async_migrations())
    else:
        _logger.info("走 sync 路径")
        run_sync_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
