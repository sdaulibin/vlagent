"""add credit comparison tables

Revision ID: 5789ff6184f5
Revises: e9c4a1f7b203
Create Date: 2026-06-26 10:30:00.000000

信用金额对账模块：6 张业务表。
- credit_compare_task        对账任务（上传/状态机，替代旧 task_table）
- credit_financial           Word 指标主记录
- credit_company_profit_loss Word 企业明细
- credit_excel_profit_loss   Excel 指标记录（12 金额列）
- credit_compare_link        Word ↔ Excel 对比关联
- credit_exception_group     异常关联记录

异常字典改为内存枚举，不再建 exception_table。
"""
from typing import Sequence, Union

from alembic import op

revision: str = "5789ff6184f5"
down_revision: Union[str, Sequence[str], None] = "4b0b262e3938"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 对账任务表
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_compare_task (
            id SERIAL PRIMARY KEY,
            batch_id VARCHAR NOT NULL UNIQUE,
            user_id VARCHAR,
            word_file_name VARCHAR NOT NULL,
            excel_file_name VARCHAR NOT NULL,
            word_dir VARCHAR DEFAULT '',
            excel_dir VARCHAR DEFAULT '',
            status VARCHAR DEFAULT 'pending',
            error_msg VARCHAR DEFAULT '',
            link_count INTEGER DEFAULT 0,
            exception_count INTEGER DEFAULT 0,
            unmatched_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_compare_task_user_id ON credit_compare_task (user_id)")

    # 2. Word 指标主记录
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_financial (
            id SERIAL PRIMARY KEY,
            batch_id VARCHAR NOT NULL,
            user_id VARCHAR,
            title VARCHAR DEFAULT '',
            sheet VARCHAR DEFAULT '',
            code VARCHAR DEFAULT '',
            name VARCHAR DEFAULT '',
            direction INTEGER DEFAULT 0,
            amount FLOAT,
            amount_unit VARCHAR DEFAULT '',
            amount_scale INTEGER DEFAULT 1,
            calc_scope_hint VARCHAR DEFAULT '',
            paraindex INTEGER,
            source_ref VARCHAR DEFAULT '',
            context VARCHAR DEFAULT '',
            file_name VARCHAR DEFAULT ''
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_financial_batch_id ON credit_financial (batch_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_financial_user_id ON credit_financial (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_financial_sheet_code ON credit_financial (sheet, code)")

    # 3. Word 企业明细
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_company_profit_loss (
            id SERIAL PRIMARY KEY,
            batch_id VARCHAR NOT NULL,
            user_id VARCHAR,
            company VARCHAR DEFAULT '',
            direction INTEGER DEFAULT 0,
            profit_loss FLOAT,
            profit_loss_unit VARCHAR DEFAULT '',
            word_record_id INTEGER REFERENCES credit_financial(id),
            sheet VARCHAR DEFAULT '',
            code VARCHAR DEFAULT '',
            file_name VARCHAR DEFAULT ''
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_company_batch_id ON credit_company_profit_loss (batch_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_company_word_record_id ON credit_company_profit_loss (word_record_id)")

    # 4. Excel 指标记录
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_excel_profit_loss (
            id SERIAL PRIMARY KEY,
            batch_id VARCHAR NOT NULL,
            user_id VARCHAR,
            sheet VARCHAR DEFAULT '',
            code VARCHAR DEFAULT '',
            name VARCHAR DEFAULT '',
            cur_rmb_balance FLOAT,
            cur_rmb_occur FLOAT,
            cur_foreign_balance FLOAT,
            cur_foreign_occur FLOAT,
            cur_foreign_total_balance FLOAT,
            cur_foreign_total_occur FLOAT,
            pre_rmb_balance FLOAT,
            pre_rmb_occur FLOAT,
            pre_foreign_balance FLOAT,
            pre_foreign_occur FLOAT,
            pre_foreign_total_balance FLOAT,
            pre_foreign_total_occur FLOAT,
            excel_row_index INTEGER,
            file_name VARCHAR DEFAULT ''
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_excel_batch_id ON credit_excel_profit_loss (batch_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_excel_sheet_code ON credit_excel_profit_loss (sheet, code)")

    # 5. Word ↔ Excel 对比关联
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_compare_link (
            id SERIAL PRIMARY KEY,
            batch_id VARCHAR NOT NULL,
            word_record_id INTEGER REFERENCES credit_financial(id),
            excel_record_id INTEGER REFERENCES credit_excel_profit_loss(id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_compare_link_batch_id ON credit_compare_link (batch_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_compare_link_word_record_id ON credit_compare_link (word_record_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_compare_link_excel_record_id ON credit_compare_link (excel_record_id)")

    # 6. 异常关联记录
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_exception_group (
            id SERIAL PRIMARY KEY,
            batch_id VARCHAR NOT NULL,
            exception_id INTEGER NOT NULL,
            word_record_id INTEGER REFERENCES credit_financial(id),
            field_name VARCHAR DEFAULT '',
            value VARCHAR DEFAULT ''
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_exception_batch_id ON credit_exception_group (batch_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_credit_exception_word_record_id ON credit_exception_group (word_record_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS credit_exception_group")
    op.execute("DROP TABLE IF EXISTS credit_compare_link")
    op.execute("DROP TABLE IF EXISTS credit_excel_profit_loss")
    op.execute("DROP TABLE IF EXISTS credit_company_profit_loss")
    op.execute("DROP TABLE IF EXISTS credit_financial")
    op.execute("DROP TABLE IF EXISTS credit_compare_task")
