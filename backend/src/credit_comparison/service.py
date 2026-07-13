"""
信用金额对账 - 任务编排服务（异步）。

替代旧 TaskService 的任务处理链路，采用宿主 invoice_recognition 的三段式：
1. 标记 processing 并提交，立即释放 session
2. 纯 CPU/文件 IO 阶段（soffice 转 docx、解析 Word/Excel）不持有连接，
   用 asyncio.to_thread 包裹避免阻塞事件循环，结果攒内存
3. 开新 session 一次性批量写库 → 跑对账 → 更新任务状态

解析阶段的异常登记（旧 word_service._register_*_exceptions）内联到此。
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio.session import AsyncSession

from src.config import CREDIT_CONVERTED_DIR, UPLOAD_DIR_CREDIT_COMPARISON
from src.credit_comparison import repository
from src.credit_comparison.compare import CompareService
from src.credit_comparison.core.enums import ExceptionType
from src.credit_comparison.core.format_validator import build_parse_stage_format_exceptions
from src.credit_comparison.core.unit_utils import (
    is_supported_word_amount_unit,
)
from src.credit_comparison.models import CreditCompareTask
from src.credit_comparison.parsers.excel_parser import parse_excel_file
from src.credit_comparison.parsers.word_converter import convert_doc_to_docx
from src.credit_comparison.parsers.word_parser import parse_docx_file

logger = logging.getLogger(__name__)
compare_service = CompareService()


def generate_batch_id() -> str:
    """生成唯一批次号（与旧实现格式一致：时间戳_uuid8）。"""

    return f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{uuid4().hex[:8]}"


# ====== 解析阶段异常登记（原样保留旧 word_service 逻辑）======


async def _register_financial_parse_exceptions(
    db: AsyncSession,
    batch_id: str,
    word_record_id: int,
    financial_record: dict[str, Any],
    company_records: list[dict[str, Any]] | None = None,
) -> None:
    """登记 Word 主记录在解析阶段发现的异常。"""

    pending: list[dict[str, Any]] = []

    amount_unit = str(financial_record.get("amount_unit") or "").strip()
    if amount_unit and not is_supported_word_amount_unit(amount_unit):
        pending.append(
            {
                "batch_id": batch_id,
                "exception_id": int(ExceptionType.AMOUNT_UNIT_ERROR),
                "word_record_id": word_record_id,
                "field_name": "amount_unit",
                "value": amount_unit,
            }
        )

    context = str(financial_record.get("context") or "")
    for exception_id, field_name, value in build_parse_stage_format_exceptions(
        context,
        amount_unit=amount_unit,
        company_records=company_records or [],
    ):
        pending.append(
            {
                "batch_id": batch_id,
                "exception_id": int(exception_id),
                "word_record_id": word_record_id,
                "field_name": field_name,
                "value": value,
            }
        )

    if pending:
        await repository.insert_exception_groups(db, pending)


async def _register_company_parse_exceptions(
    db: AsyncSession,
    batch_id: str,
    word_record_id: int,
    company_record: dict[str, Any],
    calc_scope_hint: str = "",
) -> None:
    """登记企业明细在解析阶段发现的异常。"""

    direction_value = 0
    try:
        direction_value = int(company_record.get("direction") or 0)
    except (TypeError, ValueError):
        direction_value = 0
    profit_loss = company_record.get("profit_loss")
    profit_loss_unit = str(company_record.get("profit_loss_unit") or "").strip()
    company_name = str(company_record.get("company") or "").strip()
    pending: list[dict[str, Any]] = []

    if profit_loss_unit and not is_supported_word_amount_unit(profit_loss_unit):
        pending.append(
            {
                "batch_id": batch_id,
                "exception_id": int(ExceptionType.AMOUNT_UNIT_ERROR),
                "word_record_id": word_record_id,
                "field_name": "profit_loss_unit",
                "value": profit_loss_unit,
            }
        )
    if pending:
        await repository.insert_exception_groups(db, pending)


# ====== 单文件解析（同步，包装为异步）======


def _parse_word_file_sync(file_path: str, batch_id: str, converted_dir: str) -> list[dict[str, Any]]:
    """同步解析单个 Word 文件（含 doc→docx 转换）。"""

    file_name = Path(file_path).name
    docx_path = convert_doc_to_docx(file_path, converted_dir, batch_id=batch_id)
    return parse_docx_file(docx_path, file_name, batch_id)


def _parse_excel_file_sync(file_path: str, batch_id: str) -> list[dict[str, Any]]:
    """同步解析单个 Excel 文件。"""

    file_name = Path(file_path).name
    return parse_excel_file(file_path, file_name, batch_id)


# ====== 批次清理 ======


async def delete_batch_business_data(db: AsyncSession, batch_id: str) -> None:
    """删除某个批次在数据库中的全部业务数据（不含任务表）。"""

    await repository.delete_batch_business_data(db, batch_id)


async def delete_task_with_files(db: AsyncSession, task_id: int) -> None:
    """删除任务及其关联业务数据和磁盘文件。"""

    task = await db.get(CreditCompareTask, task_id)
    if task is None:
        return
    batch_id = task.batch_id
    await delete_batch_business_data(db, batch_id)
    await db.execute(delete(CreditCompareTask).where(CreditCompareTask.id == task_id))
    # 清理磁盘文件
    for dir_path in (task.word_dir, task.excel_dir):
        if dir_path:
            parent = Path(dir_path).parent  # input/<batch_id>/
            if parent.exists():
                shutil.rmtree(parent, ignore_errors=True)


# ====== 后台任务主处理 ======


async def process_compare_task(task_id: int) -> None:
    """后台任务：解析 Word/Excel → 写库 → 对账 → 更新状态。

    三段式：长 IO 阶段不持有 DB 连接，避免连接池耗尽。
    """

    from src.database import SessionLocal

    # 阶段 1：标记 processing，释放连接
    async with SessionLocal() as db:
        task = await db.get(CreditCompareTask, task_id)
        if task is None:
            return
        if task.status not in ("pending", "failed"):
            logger.warning("任务 %s 当前状态为 %s，跳过处理", task_id, task.status)
            return
        batch_id = task.batch_id
        word_dir = task.word_dir
        excel_dir = task.excel_dir
        task.status = "processing"
        task.updated_at = datetime.utcnow()
        await db.commit()

    final_status = "done"
    error_msg = ""
    link_count = 0
    exception_count = 0
    unmatched_count = 0

    # 阶段 2：纯 CPU/文件 IO，不持有连接
    try:
        # 先清理该批次旧的业务数据（重新对账场景）
        async with SessionLocal() as db:
            await delete_batch_business_data(db, batch_id)
            await db.commit()

        # 扫描文件（to_thread 避免阻塞事件循环）
        word_files = await asyncio.to_thread(_scan_word_files, word_dir)
        excel_files = await asyncio.to_thread(_scan_excel_files, excel_dir)
        if not word_files or not excel_files:
            raise FileNotFoundError("任务文件缺失，无法执行处理")

        # 前置校验运行环境依赖（soffice/python-docx/xlrd/openpyxl），尽早失败。
        _validate_runtime_requirements(word_files, excel_files)

        # 解析 Word（同步阻塞，放线程池）
        word_parsed: list[dict[str, Any]] = []
        for wf in word_files:
            word_parsed.extend(await asyncio.to_thread(_parse_word_file_sync, wf, batch_id, CREDIT_CONVERTED_DIR))

        # 解析 Excel
        excel_parsed: list[dict[str, Any]] = []
        for ef in excel_files:
            excel_parsed.extend(await asyncio.to_thread(_parse_excel_file_sync, ef, batch_id))

    except Exception as exc:  # noqa: BLE001
        logger.exception("任务解析失败: task_id=%s, batch_id=%s", task_id, batch_id)
        final_status = "failed"
        error_msg = str(exc)
    else:
        # 阶段 3：批量写库 → 对账
        try:
            link_count, exception_count, unmatched_count = await _write_and_compare(
                batch_id, word_parsed, excel_parsed
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("任务对账失败: task_id=%s, batch_id=%s", task_id, batch_id)
            final_status = "failed"
            error_msg = str(exc)

    # 阶段 4：回写结果
    async with SessionLocal() as db:
        task = await db.get(CreditCompareTask, task_id)
        if task is not None:
            task.status = final_status
            task.error_msg = error_msg
            task.link_count = link_count
            task.exception_count = exception_count
            task.unmatched_count = unmatched_count
            task.updated_at = datetime.utcnow()
            await db.commit()


async def _write_and_compare(
    batch_id: str,
    word_parsed: list[dict[str, Any]],
    excel_parsed: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """批量写库 → 跑对账，返回 (link_count, exception_count, unmatched_count)。"""

    from src.database import SessionLocal

    async with SessionLocal() as db:
        # 1. 写 Word 主记录（含解析异常登记 + 企业明细）
        financial_records = [item["financial"] for item in word_parsed]
        inserted_ids = await repository.insert_financial_records(db, financial_records)

        company_records: list[dict[str, Any]] = []
        for word_record_id, item in zip(inserted_ids, word_parsed, strict=False):
            financial_record = item["financial"]
            await _register_financial_parse_exceptions(
                db,
                batch_id,
                word_record_id,
                financial_record,
                company_records=list(item.get("company_records") or []),
            )
            for company_record in item["company_records"]:
                company_record["word_record_id"] = word_record_id
                await _register_company_parse_exceptions(
                    db,
                    batch_id,
                    word_record_id,
                    company_record,
                    calc_scope_hint=str(financial_record.get("calc_scope_hint") or ""),
                )
                company_records.append({key: value for key, value in company_record.items() if not key.startswith("_")})
        await repository.insert_company_records(db, company_records)

        # 2. 写 Excel 记录
        await repository.insert_excel_records(db, excel_parsed)

        # 3. 跑对账
        await compare_service.run_word_internal_checks(db, batch_id)
        await compare_service.run_cross_source_compare(db, batch_id)
        await db.commit()

    # 4. 统计结果（单独 session 读）
    async with SessionLocal() as db:
        stats = await repository.list_batch_compare_stats(db, [batch_id])
        batch_stats = stats.get(str(batch_id), {})
        link_count = int(batch_stats.get("link_count", 0))
        exception_count = int(batch_stats.get("exception_count", 0))
        unmatched_count = int(batch_stats.get("unmatched_count", 0))
    return link_count, exception_count, unmatched_count


async def _count_compare_links(db: AsyncSession, batch_id: str) -> int:
    from sqlalchemy import func

    from src.credit_comparison.models import CreditCompareLink

    stmt = select(func.count()).select_from(CreditCompareLink).where(CreditCompareLink.batch_id == batch_id)
    return int((await db.execute(stmt)).scalar() or 0)


async def _count_unmatched_links(db: AsyncSession, batch_id: str) -> int:
    from sqlalchemy import func

    from src.credit_comparison.models import CreditCompareLink

    stmt = select(func.count()).select_from(CreditCompareLink).where(
        CreditCompareLink.batch_id == batch_id,
        CreditCompareLink.excel_record_id.is_(None),
    )
    return int((await db.execute(stmt)).scalar() or 0)


# ====== 文件扫描（工具）======


def _scan_word_files(dir_path: str) -> list[str]:
    root = Path(dir_path)
    if not root.exists():
        return []
    return sorted(str(p) for p in root.rglob("*") if p.suffix.lower() in {".doc", ".docx"})


def _scan_excel_files(dir_path: str) -> list[str]:
    root = Path(dir_path)
    if not root.exists():
        return []
    return sorted(str(p) for p in root.rglob("*") if p.suffix.lower() in {".xls", ".xlsx"})


def _validate_runtime_requirements(word_files: list[str], excel_files: list[str]) -> None:
    """按当前任务输入校验运行环境依赖，尽早失败。

    规则与原项目 system_utils.validate_runtime_requirements 对齐：
    - 若存在 .doc 文件，则必须提供 soffice
    - 若存在 .doc 或 .docx 文件，则必须提供 python-docx
    - 若存在 .xls 文件，则必须提供 xlrd
    - 若存在 .xlsx 文件，则必须提供 openpyxl
    """

    has_doc = any(file_path.lower().endswith(".doc") for file_path in word_files)
    has_docx = any(file_path.lower().endswith(".docx") for file_path in word_files)
    has_xls = any(file_path.lower().endswith(".xls") for file_path in excel_files)
    has_xlsx = any(file_path.lower().endswith(".xlsx") for file_path in excel_files)

    missing_items: list[str] = []

    if has_doc and not shutil.which("soffice"):
        missing_items.append("LibreOffice/soffice")
    if (has_doc or has_docx) and not importlib.util.find_spec("docx"):
        missing_items.append("python-docx")
    if has_xls and not importlib.util.find_spec("xlrd"):
        missing_items.append("xlrd==1.2.0")
    if has_xlsx and not importlib.util.find_spec("openpyxl"):
        missing_items.append("openpyxl")

    if missing_items:
        raise RuntimeError(f"运行环境缺少依赖: {', '.join(missing_items)}")


def build_task_dirs(batch_id: str, user_id: str) -> tuple[str, str]:
    """构建任务的 word/excel 输入目录（upload/credit_comparison/<user_id>/<batch_id>/{word,excel}）。"""

    base = os.path.join(UPLOAD_DIR_CREDIT_COMPARISON, user_id, batch_id)
    word_dir = os.path.join(base, "word")
    excel_dir = os.path.join(base, "excel")
    os.makedirs(word_dir, exist_ok=True)
    os.makedirs(excel_dir, exist_ok=True)
    return word_dir, excel_dir
