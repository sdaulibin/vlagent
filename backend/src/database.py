from sqlmodel import SQLModel, select
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

# 上游数据库（只读，ioa 库）
upstream_engine = None
UpstreamSessionLocal = None

if settings.DATABASE_UPSTREAM_URL:
    upstream_engine = create_async_engine(
        settings.DATABASE_UPSTREAM_URL,
        echo=settings.DATABASE_ECHO,
        future=True,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=3,
        pool_recycle=300,
        pool_timeout=30,
    )
    UpstreamSessionLocal = sessionmaker(
        upstream_engine, class_=AsyncSession, expire_on_commit=False
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
    from src.modules.models import Module

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

        # modules 表：新增 agent_id 字段（幂等）
        await conn.execute(text(
            "ALTER TABLE modules ADD COLUMN IF NOT EXISTS agent_id INTEGER"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_modules_agent_id ON modules (agent_id)"
        ))

    # Seed modules 表（幂等：仅表为空时插入）
    async with SessionLocal() as session:
        result = await session.execute(select(Module).limit(1))
        if result.first() is None:
            from src.modules.models import Module as M
            seeds = [
                M(key="bank-statement", title="流水识别",
                  description="AI 识别银行流水 PDF，提取交易明细、账户信息和汇总数据，支持光大、招商、工商等多家银行格式",
                  icon="CreditCard", route="/bank-statement",
                  gradient="icon-gradient-blue", hover_class="group-hover:text-blue-700", sort_order=1),
                M(key="confirmation-letter", title="询证函识别",
                  description="AI 识别银行询证函 PDF，自动提取编号、事务所、联系方式、账户等 13 个关键字段",
                  icon="FileText", route="/confirmation-letter",
                  gradient="icon-gradient-green", hover_class="group-hover:text-emerald-700", sort_order=2),
                M(key="document-compare", title="文档比对",
                  description="逐页对比两份文档（PDF / Word），逐行标注新增、删除、修改内容，支持表格结构化比对",
                  icon="FileDiff", route="/document-compare",
                  gradient="icon-gradient-orange", hover_class="group-hover:text-orange-600", sort_order=3),
                M(key="format-compare", title="询证函格式比对",
                  description="将询证函与标准模板比对，检查格式类型、章节标题、表头字段是否符合规范",
                  icon="FileSearch", route="/format-compare",
                  gradient="icon-gradient-purple", hover_class="group-hover:text-violet-700", sort_order=4),
                M(key="invoice-recognition", title="发票识别",
                  description="识别电子发票 PDF 及图片，提取发票类型、号码、金额、购销方名称及税号等信息",
                  icon="Receipt", route="/invoice-recognition",
                  gradient="icon-gradient-red", hover_class="group-hover:text-rose-600", sort_order=5),
                M(key="credential-recognition", title="类凭证识别",
                  description="识别身份证、银行卡、电子印章、网银申请书、授权书等多种凭证类型的关键信息",
                  icon="FileCheck2", route="/credential-recognition",
                  gradient="icon-gradient-indigo", hover_class="group-hover:text-indigo-700", sort_order=6),
                M(key="pdf-extract", title="通用 PDF 提取",
                  description="自定义提取字段（最多 10 个），AI 从任意 PDF 中提取结构化数据，支持导出 Excel / CSV",
                  icon="FileScan", route="/pdf-extract",
                  gradient="icon-gradient-cyan", hover_class="group-hover:text-cyan-700", sort_order=7),
            ]
            for seed in seeds:
                session.add(seed)
            await session.commit()


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
