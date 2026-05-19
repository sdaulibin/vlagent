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
    # modules 表：新增分类相关字段
    op.add_column('modules', sa.Column('category', sa.VARCHAR(), nullable=True))
    op.add_column('modules', sa.Column('category_label', sa.VARCHAR(), nullable=True))
    op.add_column('modules', sa.Column('category_color', sa.VARCHAR(), nullable=True))
    op.add_column('modules', sa.Column('bg_color', sa.VARCHAR(), nullable=True))
    op.add_column('modules', sa.Column('name_en', sa.VARCHAR(), nullable=True))

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

    # 设置 NOT NULL 约束（回填后再加）
    op.alter_column('modules', 'category',
               existing_type=sa.VARCHAR(),
               nullable=False,
               existing_server_default=sa.text("''::character varying"))
    op.alter_column('modules', 'category_label',
               existing_type=sa.VARCHAR(),
               nullable=False,
               existing_server_default=sa.text("''::character varying"))
    op.alter_column('modules', 'category_color',
               existing_type=sa.VARCHAR(),
               nullable=False,
               existing_server_default=sa.text("''::character varying"))
    op.alter_column('modules', 'bg_color',
               existing_type=sa.VARCHAR(),
               nullable=False,
               existing_server_default=sa.text("''::character varying"))
    op.alter_column('modules', 'name_en',
               existing_type=sa.VARCHAR(),
               nullable=False,
               existing_server_default=sa.text("''::character varying"))

    # 权限表：添加联合唯一索引
    op.drop_index(op.f('uq_user_permission_module'), table_name='user_permissions')
    op.create_unique_constraint('uq_user_permission_module', 'user_permissions', ['user_id', 'module'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_user_permission_module', 'user_permissions', type_='unique')
    op.create_index(op.f('uq_user_permission_module'), 'user_permissions', ['user_id', 'module'], unique=True)

    op.drop_column('modules', 'name_en')
    op.drop_column('modules', 'bg_color')
    op.drop_column('modules', 'category_color')
    op.drop_column('modules', 'category_label')
    op.drop_column('modules', 'category')
