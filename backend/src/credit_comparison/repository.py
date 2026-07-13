"""
信用金额对账 - 异步数据访问层。

把旧的 6 个同步 raw SQL repository 重写为基于 SQLAlchemy 异步 session 的查询。
对账核心（compare.py）和展示服务（view 聚合）通过本模块读写数据。

关键设计：
- 写入接口返回 dict（含自增 id），与旧 repository 返回结构对齐，
  便于 service 层回填 word_record_id 后再批量写企业明细。
- 展示查询接口返回 dict 列表，对账/聚合逻辑沿用旧 view_repository 的字段命名。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio.session import AsyncSession

from src.credit_comparison.models import (
    CreditCompanyProfitLoss,
    CreditCompareLink,
    CreditExceptionGroup,
    CreditExcelProfitLoss,
    CreditFinancialRecord,
)


def _financial_to_dict(row: CreditFinancialRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "batch_id": row.batch_id,
        "user_id": row.user_id,
        "title": row.title,
        "sheet": row.sheet,
        "code": row.code,
        "name": row.name,
        "direction": row.direction,
        "amount": row.amount,
        "amount_unit": row.amount_unit,
        "amount_scale": row.amount_scale,
        "calc_scope_hint": row.calc_scope_hint,
        "paraindex": row.paraindex,
        "source_ref": row.source_ref,
        "context": row.context,
        "file_name": row.file_name,
    }


def _excel_to_dict(row: CreditExcelProfitLoss) -> dict[str, Any]:
    return {
        "id": row.id,
        "batch_id": row.batch_id,
        "user_id": row.user_id,
        "sheet": row.sheet,
        "code": row.code,
        "name": row.name,
        "cur_rmb_balance": row.cur_rmb_balance,
        "cur_rmb_occur": row.cur_rmb_occur,
        "cur_foreign_balance": row.cur_foreign_balance,
        "cur_foreign_occur": row.cur_foreign_occur,
        "cur_foreign_total_balance": row.cur_foreign_total_balance,
        "cur_foreign_total_occur": row.cur_foreign_total_occur,
        "pre_rmb_balance": row.pre_rmb_balance,
        "pre_rmb_occur": row.pre_rmb_occur,
        "pre_foreign_balance": row.pre_foreign_balance,
        "pre_foreign_occur": row.pre_foreign_occur,
        "pre_foreign_total_balance": row.pre_foreign_total_balance,
        "pre_foreign_total_occur": row.pre_foreign_total_occur,
        "excel_row_index": row.excel_row_index,
        "file_name": row.file_name,
    }


# ====== financial_table ======


async def insert_financial_records(
    db: AsyncSession, records: list[dict[str, Any]]
) -> list[int]:
    """批量插入 Word 主记录，flush 后返回自增主键列表（供回填企业明细的 word_record_id）。"""

    if not records:
        return []
    objects = [CreditFinancialRecord(**record) for record in records]
    db.add_all(objects)
    await db.flush()
    return [int(obj.id) for obj in objects]


async def list_financial_by_batch(db: AsyncSession, batch_id: str) -> list[dict[str, Any]]:
    """按批次查询 Word 主记录。"""

    stmt = (
        select(CreditFinancialRecord)
        .where(CreditFinancialRecord.batch_id == batch_id)
        .order_by(
            CreditFinancialRecord.file_name,
            CreditFinancialRecord.sheet,
            CreditFinancialRecord.paraindex.is_(None),
            CreditFinancialRecord.paraindex,
            CreditFinancialRecord.id,
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_financial_to_dict(row) for row in rows]


async def get_financial_by_id(db: AsyncSession, record_id: int) -> dict[str, Any] | None:
    """按主键查询一条 Word 主记录。"""

    row = await db.get(CreditFinancialRecord, record_id)
    return _financial_to_dict(row) if row else None


async def count_financial_by_batch(db: AsyncSession, batch_id: str) -> int:
    """按批次统计主记录数量。"""

    stmt = select(func.count()).select_from(CreditFinancialRecord).where(
        CreditFinancialRecord.batch_id == batch_id
    )
    return int((await db.execute(stmt)).scalar() or 0)


# ====== company_profit_loss_table ======


async def insert_company_records(
    db: AsyncSession, records: list[dict[str, Any]]
) -> None:
    """批量插入企业明细。"""

    if not records:
        return
    objects = [CreditCompanyProfitLoss(**record) for record in records]
    db.add_all(objects)


async def list_company_by_batch(db: AsyncSession, batch_id: str) -> list[dict[str, Any]]:
    """按批次查询企业明细。"""

    stmt = (
        select(CreditCompanyProfitLoss)
        .where(CreditCompanyProfitLoss.batch_id == batch_id)
        .order_by(
            CreditCompanyProfitLoss.file_name,
            CreditCompanyProfitLoss.sheet,
            CreditCompanyProfitLoss.code,
            CreditCompanyProfitLoss.company,
            CreditCompanyProfitLoss.id,
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": row.id,
            "batch_id": row.batch_id,
            "user_id": row.user_id,
            "company": row.company,
            "direction": row.direction,
            "profit_loss": row.profit_loss,
            "profit_loss_unit": row.profit_loss_unit,
            "word_record_id": row.word_record_id,
            "sheet": row.sheet,
            "code": row.code,
            "file_name": row.file_name,
        }
        for row in rows
    ]


async def list_company_by_word_record(
    db: AsyncSession, word_record_id: int
) -> list[dict[str, Any]]:
    """按 Word 主记录查询企业明细。"""

    stmt = (
        select(CreditCompanyProfitLoss)
        .where(CreditCompanyProfitLoss.word_record_id == word_record_id)
        .order_by(CreditCompanyProfitLoss.id)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": row.id,
            "company": row.company,
            "direction": row.direction,
            "profit_loss": row.profit_loss,
            "profit_loss_unit": row.profit_loss_unit,
            "word_record_id": row.word_record_id,
            "sheet": row.sheet,
            "code": row.code,
            "file_name": row.file_name,
        }
        for row in rows
    ]


async def count_company_by_batch(db: AsyncSession, batch_id: str) -> int:
    """按批次统计企业明细数量。"""

    stmt = select(func.count()).select_from(CreditCompanyProfitLoss).where(
        CreditCompanyProfitLoss.batch_id == batch_id
    )
    return int((await db.execute(stmt)).scalar() or 0)


# ====== excel_profit_loss_table ======


async def insert_excel_records(
    db: AsyncSession, records: list[dict[str, Any]]
) -> None:
    """批量插入 Excel 指标记录。"""

    if not records:
        return
    objects = [CreditExcelProfitLoss(**record) for record in records]
    db.add_all(objects)


async def list_excel_by_batch(db: AsyncSession, batch_id: str) -> list[dict[str, Any]]:
    """按批次查询 Excel 记录。"""

    stmt = (
        select(CreditExcelProfitLoss)
        .where(CreditExcelProfitLoss.batch_id == batch_id)
        .order_by(
            CreditExcelProfitLoss.file_name,
            CreditExcelProfitLoss.sheet,
            CreditExcelProfitLoss.code,
            CreditExcelProfitLoss.id,
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_excel_to_dict(row) for row in rows]


async def find_excel_by_sheet(
    db: AsyncSession, batch_id: str, sheet: str
) -> list[dict[str, Any]]:
    """按表单查询全部 Excel 指标记录。"""

    stmt = (
        select(CreditExcelProfitLoss)
        .where(CreditExcelProfitLoss.batch_id == batch_id, CreditExcelProfitLoss.sheet == sheet)
        .order_by(CreditExcelProfitLoss.id)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_excel_to_dict(row) for row in rows]


async def get_excel_by_id(db: AsyncSession, record_id: int) -> dict[str, Any] | None:
    """按主键查询一条 Excel 记录。"""

    row = await db.get(CreditExcelProfitLoss, record_id)
    return _excel_to_dict(row) if row else None


async def count_excel_by_batch(db: AsyncSession, batch_id: str) -> int:
    """按批次统计 Excel 记录数量。"""

    stmt = select(func.count()).select_from(CreditExcelProfitLoss).where(
        CreditExcelProfitLoss.batch_id == batch_id
    )
    return int((await db.execute(stmt)).scalar() or 0)


# ====== compare_link_table ======


async def insert_compare_links(
    db: AsyncSession, records: list[dict[str, Any]]
) -> None:
    """批量写入对比关联记录。"""

    if not records:
        return
    objects = [CreditCompareLink(**record) for record in records]
    db.add_all(objects)


async def get_compare_link_by_id(
    db: AsyncSession, link_id: int
) -> dict[str, Any] | None:
    """按主键查询一条对比关联记录。"""

    row = await db.get(CreditCompareLink, link_id)
    if not row:
        return None
    return {
        "id": row.id,
        "batch_id": row.batch_id,
        "word_record_id": row.word_record_id,
        "excel_record_id": row.excel_record_id,
    }


# ====== exception_group_table ======


async def insert_exception_groups(
    db: AsyncSession, records: list[dict[str, Any]]
) -> None:
    """批量写入异常关联记录。"""

    if not records:
        return
    objects = [CreditExceptionGroup(**record) for record in records]
    db.add_all(objects)


async def count_exception_by_batch(db: AsyncSession, batch_id: str) -> int:
    """按批次统计异常关联记录数量。"""

    stmt = select(func.count()).select_from(CreditExceptionGroup).where(
        CreditExceptionGroup.batch_id == batch_id
    )
    return int((await db.execute(stmt)).scalar() or 0)


async def list_exception_word_record_ids(
    db: AsyncSession, batch_id: str
) -> set[int]:
    """查询当前批次中存在异常的 Word 主记录 id 集合。"""

    stmt = (
        select(CreditExceptionGroup.word_record_id)
        .where(
            CreditExceptionGroup.batch_id == batch_id,
            CreditExceptionGroup.word_record_id.is_not(None),
        )
        .distinct()
    )
    rows = (await db.execute(stmt)).all()
    return {int(row[0]) for row in rows if row[0] is not None}


async def list_exception_details_by_batch(
    db: AsyncSession, batch_id: str
) -> list[dict[str, Any]]:
    """查询当前批次全部异常详情（替代旧 vw_word_exception_detail 视图）。"""

    from src.credit_comparison.core.enums import EXCEPTION_TYPE_NAMES

    stmt = (
        select(
            CreditExceptionGroup.id,
            CreditExceptionGroup.batch_id,
            CreditExceptionGroup.word_record_id,
            CreditExceptionGroup.exception_id,
            CreditExceptionGroup.field_name,
            CreditExceptionGroup.value,
        )
        .where(
            CreditExceptionGroup.batch_id == batch_id,
            CreditExceptionGroup.word_record_id.is_not(None),
        )
        .order_by(CreditExceptionGroup.word_record_id, CreditExceptionGroup.id)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": row[0],
            "batch_id": row[1],
            "word_record_id": row[2],
            "exception_id": row[3],
            "exception_name": EXCEPTION_TYPE_NAMES.get(int(row[3] or 0), ""),
            "field_name": row[4],
            "value": row[5],
        }
        for row in rows
    ]


async def list_exception_details_by_word_record(
    db: AsyncSession, word_record_id: int
) -> list[dict[str, Any]]:
    """查询某条 Word 主记录的异常详情。"""

    from src.credit_comparison.core.enums import EXCEPTION_TYPE_NAMES

    stmt = (
        select(CreditExceptionGroup)
        .where(CreditExceptionGroup.word_record_id == word_record_id)
        .order_by(CreditExceptionGroup.id)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": row.id,
            "batch_id": row.batch_id,
            "word_record_id": row.word_record_id,
            "exception_id": row.exception_id,
            "exception_name": EXCEPTION_TYPE_NAMES.get(int(row.exception_id or 0), ""),
            "field_name": row.field_name,
            "value": row.value,
        }
        for row in rows
    ]


# ====== 展示层 JOIN 查询（替代旧视图）======


async def list_compare_link_details(
    db: AsyncSession, batch_id: str
) -> list[dict[str, Any]]:
    """查询用于画线展示的关联列表（替代旧 vw_compare_link_detail 视图）。

    compare_link JOIN financial LEFT JOIN excel_profit_loss。
    """

    stmt = (
        select(
            CreditCompareLink.id.label("compare_link_id"),
            CreditCompareLink.batch_id,
            CreditCompareLink.word_record_id,
            CreditCompareLink.excel_record_id,
            CreditFinancialRecord.title.label("word_title"),
            CreditFinancialRecord.sheet.label("word_sheet"),
            CreditFinancialRecord.code.label("word_code"),
            CreditFinancialRecord.name.label("word_name"),
            CreditFinancialRecord.direction.label("word_direction"),
            CreditFinancialRecord.amount.label("word_amount"),
            CreditFinancialRecord.amount_unit.label("word_amount_unit"),
            CreditFinancialRecord.amount_scale.label("word_amount_scale"),
            CreditFinancialRecord.calc_scope_hint.label("word_calc_scope_hint"),
            CreditFinancialRecord.paraindex.label("word_paraindex"),
            CreditFinancialRecord.source_ref.label("word_source_ref"),
            CreditFinancialRecord.context.label("word_context"),
            CreditFinancialRecord.file_name.label("word_file_name"),
            CreditExcelProfitLoss.sheet.label("excel_sheet"),
            CreditExcelProfitLoss.code.label("excel_code"),
            CreditExcelProfitLoss.name.label("excel_name"),
            CreditExcelProfitLoss.excel_row_index,
            CreditExcelProfitLoss.file_name.label("excel_file_name"),
        )
        .select_from(CreditCompareLink)
        .join(CreditFinancialRecord, CreditFinancialRecord.id == CreditCompareLink.word_record_id)
        .outerjoin(
            CreditExcelProfitLoss,
            CreditExcelProfitLoss.id == CreditCompareLink.excel_record_id,
        )
        .where(CreditCompareLink.batch_id == batch_id)
        .order_by(
            CreditFinancialRecord.file_name,
            CreditFinancialRecord.sheet,
            CreditFinancialRecord.paraindex.is_(None),
            CreditFinancialRecord.paraindex,
            CreditCompareLink.id,
        )
    )
    result = await db.execute(stmt)
    # Row._mapping 提供 {列名: 值} 的字典视图，便于对账/展示逻辑按字段名读取。
    return [dict(row._mapping) for row in result.all()]


async def list_batch_compare_stats(
    db: AsyncSession, batch_ids: list[str]
) -> dict[str, dict[str, int]]:
    from sqlalchemy import and_, case, func

    from src.credit_comparison.core.enums import ExceptionType
    from src.credit_comparison.models import (
        CreditCompareLink,
        CreditCompanyProfitLoss,
        CreditExceptionGroup,
    )

    targets = [str(value or "").strip() for value in batch_ids or [] if str(value or "").strip()]
    if not targets:
        return {}

    stats: dict[str, dict[str, int]] = {
        target: {"link_count": 0, "unmatched_count": 0, "exception_count": 0} for target in targets
    }

    link_stmt = (
        select(
            CreditCompareLink.batch_id.label("batch_id"),
            func.count(CreditCompareLink.id)
            .filter(CreditCompareLink.excel_record_id.is_not(None))
            .label("link_count"),
            func.count(CreditCompareLink.id)
            .filter(CreditCompareLink.excel_record_id.is_(None))
            .label("unmatched_count"),
        )
        .where(CreditCompareLink.batch_id.in_(targets))
        .group_by(CreditCompareLink.batch_id)
    )
    for batch_id, link_count, unmatched_count in (await db.execute(link_stmt)).all():
        key = str(batch_id)
        if key in stats:
            stats[key]["link_count"] = int(link_count or 0)
            stats[key]["unmatched_count"] = int(unmatched_count or 0)

    other_exception_ids = [
        int(ExceptionType.CODE_ERROR),
        int(ExceptionType.NAME_ERROR),
        int(ExceptionType.AMOUNT_ERROR),
        int(ExceptionType.SHEET_NOT_FOUND),
        int(ExceptionType.BALANCE_MISSING_ERROR),
        int(ExceptionType.CALCULATION_REQUIREMENT_ERROR),
        int(ExceptionType.EXCEL_ERROR),
    ]
    other_stmt = (
        select(CreditExceptionGroup.batch_id.label("batch_id"), func.count(CreditExceptionGroup.id))
        .where(
            CreditExceptionGroup.batch_id.in_(targets),
            CreditExceptionGroup.word_record_id.is_not(None),
            CreditExceptionGroup.exception_id.in_(other_exception_ids),
        )
        .group_by(CreditExceptionGroup.batch_id)
    )
    for batch_id, count_value in (await db.execute(other_stmt)).all():
        key = str(batch_id)
        if key in stats:
            stats[key]["exception_count"] += int(count_value or 0)

    format_stmt = (
        select(
            CreditExceptionGroup.batch_id.label("batch_id"),
            func.count(func.distinct(CreditExceptionGroup.word_record_id)).label("cnt"),
        )
        .where(
            CreditExceptionGroup.batch_id.in_(targets),
            CreditExceptionGroup.word_record_id.is_not(None),
            CreditExceptionGroup.exception_id.in_(
                [
                    int(ExceptionType.FORMAT_ERROR),
                    int(ExceptionType.COMPANY_FORMAT_ERROR),
                    int(ExceptionType.PUNCTUATION_ERROR),
                ]
            ),
        )
        .group_by(CreditExceptionGroup.batch_id)
    )
    for batch_id, count_value in (await db.execute(format_stmt)).all():
        key = str(batch_id)
        if key in stats:
            stats[key]["exception_count"] += int(count_value or 0)

    company_merge_subq = (
        select(
            CreditExceptionGroup.batch_id.label("batch_id"),
            CreditExceptionGroup.exception_id.label("exception_id"),
            CreditExceptionGroup.word_record_id.label("word_record_id"),
            CreditExceptionGroup.value.label("company"),
        )
        .where(
            CreditExceptionGroup.batch_id.in_(targets),
            CreditExceptionGroup.word_record_id.is_not(None),
            CreditExceptionGroup.exception_id.in_(
                [
                    int(ExceptionType.COMPANY_DIRECTION_ERROR),
                    int(ExceptionType.COMPANY_DUPLICATE_ERROR),
                ]
            ),
        )
        .distinct()
        .subquery()
    )
    company_merge_stmt = (
        select(company_merge_subq.c.batch_id.label("batch_id"), func.count().label("cnt"))
        .select_from(company_merge_subq)
        .group_by(company_merge_subq.c.batch_id)
    )
    for batch_id, count_value in (await db.execute(company_merge_stmt)).all():
        key = str(batch_id)
        if key in stats:
            stats[key]["exception_count"] += int(count_value or 0)

    exc7_subq = (
        select(
            CreditExceptionGroup.id.label("exc_id"),
            CreditExceptionGroup.batch_id.label("batch_id"),
            CreditExceptionGroup.word_record_id.label("word_record_id"),
            CreditExceptionGroup.value.label("company"),
        )
        .where(
            CreditExceptionGroup.batch_id.in_(targets),
            CreditExceptionGroup.word_record_id.is_not(None),
            CreditExceptionGroup.exception_id == int(ExceptionType.COMPANY_AMOUNT_ERROR),
        )
        .subquery()
    )
    per_exc7_subq = (
        select(
            exc7_subq.c.batch_id.label("batch_id"),
            case(
                (func.count(CreditCompanyProfitLoss.id) > 0, func.count(CreditCompanyProfitLoss.id)),
                else_=1,
            ).label("cnt"),
        )
        .select_from(exc7_subq)
        .outerjoin(
            CreditCompanyProfitLoss,
            and_(
                CreditCompanyProfitLoss.batch_id == exc7_subq.c.batch_id,
                CreditCompanyProfitLoss.word_record_id == exc7_subq.c.word_record_id,
                CreditCompanyProfitLoss.company == exc7_subq.c.company,
            ),
        )
        .group_by(exc7_subq.c.batch_id, exc7_subq.c.exc_id)
        .subquery()
    )
    company7_stmt = (
        select(per_exc7_subq.c.batch_id.label("batch_id"), func.sum(per_exc7_subq.c.cnt).label("cnt"))
        .select_from(per_exc7_subq)
        .group_by(per_exc7_subq.c.batch_id)
    )
    for batch_id, count_value in (await db.execute(company7_stmt)).all():
        key = str(batch_id)
        if key in stats:
            stats[key]["exception_count"] += int(count_value or 0)

    return stats


# ====== 批次清理 ======


async def delete_batch_business_data(db: AsyncSession, batch_id: str) -> None:
    """删除某个批次在数据库中的全部业务数据（不含任务表）。"""

    await db.execute(
        delete(CreditCompareLink).where(CreditCompareLink.batch_id == batch_id)
    )
    await db.execute(
        delete(CreditExceptionGroup).where(CreditExceptionGroup.batch_id == batch_id)
    )
    await db.execute(
        delete(CreditCompanyProfitLoss).where(CreditCompanyProfitLoss.batch_id == batch_id)
    )
    await db.execute(
        delete(CreditExcelProfitLoss).where(CreditExcelProfitLoss.batch_id == batch_id)
    )
    await db.execute(
        delete(CreditFinancialRecord).where(CreditFinancialRecord.batch_id == batch_id)
    )
