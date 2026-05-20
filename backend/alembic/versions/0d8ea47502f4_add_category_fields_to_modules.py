"""add category fields to modules

Revision ID: 0d8ea47502f4
Revises: 135eef68092d
Create Date: 2026-05-19 17:13:05.805320

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0d8ea47502f4'
down_revision: Union[str, Sequence[str], None] = '135eef68092d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # modules 表：新增分类字段（幂等：IF NOT EXISTS）
    op.execute("""
        ALTER TABLE modules ADD COLUMN IF NOT EXISTS category VARCHAR DEFAULT '';
        ALTER TABLE modules ADD COLUMN IF NOT EXISTS category_label VARCHAR DEFAULT '';
        ALTER TABLE modules ADD COLUMN IF NOT EXISTS category_color VARCHAR DEFAULT '';
        ALTER TABLE modules ADD COLUMN IF NOT EXISTS bg_color VARCHAR DEFAULT '';
        ALTER TABLE modules ADD COLUMN IF NOT EXISTS name_en VARCHAR DEFAULT '';
    """)

    # 回填已有数据
    op.execute("""
        UPDATE modules SET
            category = 'bank', category_label = '银行流水', category_color = '#2563eb',
            bg_color = 'linear-gradient(135deg, #2563eb, #3b82f6)', name_en = 'Bank Statement'
        WHERE key = 'bank-statement';
        UPDATE modules SET
            category = 'credential', category_label = '凭证提取', category_color = '#7c3aed',
            bg_color = 'linear-gradient(135deg, #059669, #10b981)', name_en = 'Confirmation Letter'
        WHERE key = 'confirmation-letter';
        UPDATE modules SET
            category = 'document', category_label = '文档比对', category_color = '#ea580c',
            bg_color = 'linear-gradient(135deg, #ea580c, #f97316)', name_en = 'Document Compare'
        WHERE key = 'document-compare';
        UPDATE modules SET
            category = 'document', category_label = '文档比对', category_color = '#ea580c',
            bg_color = 'linear-gradient(135deg, #d97706, #f59e0b)', name_en = 'Format Compare'
        WHERE key = 'format-compare';
        UPDATE modules SET
            category = 'invoice', category_label = '发票识别', category_color = '#dc2626',
            bg_color = 'linear-gradient(135deg, #dc2626, #ef4444)', name_en = 'Invoice Recognition'
        WHERE key = 'invoice-recognition';
        UPDATE modules SET
            category = 'credential', category_label = '凭证提取', category_color = '#7c3aed',
            bg_color = 'linear-gradient(135deg, #7c3aed, #8b5cf6)', name_en = 'Credential Recognition'
        WHERE key = 'credential-recognition';
        UPDATE modules SET
            category = 'credential', category_label = '凭证提取', category_color = '#7c3aed',
            bg_color = 'linear-gradient(135deg, #0891b2, #06b6d4)', name_en = 'PDF Extract'
        WHERE key = 'pdf-extract';
    """)

    # 权限表：确保联合唯一索引存在（幂等）
    op.execute("""
        DROP INDEX IF EXISTS uq_user_permission_module;
        CREATE UNIQUE INDEX IF NOT EXISTS uq_user_permission_module ON user_permissions (user_id, module);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        ALTER TABLE modules DROP COLUMN IF EXISTS name_en;
        ALTER TABLE modules DROP COLUMN IF EXISTS bg_color;
        ALTER TABLE modules DROP COLUMN IF EXISTS category_color;
        ALTER TABLE modules DROP COLUMN IF EXISTS category_label;
        ALTER TABLE modules DROP COLUMN IF EXISTS category;
    """)
