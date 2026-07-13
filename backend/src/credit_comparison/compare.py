"""
信用金额对账 - 对账核心服务（异步改造版）。

业务逻辑与旧 CompareService 完全一致，仅把同步 DB 调用替换为异步 repository 调用。
包含两部分：
- run_word_internal_checks:   Word 内部一致性校验（同企业多记录冲突）
- run_cross_source_compare:   Word 与 Excel 的跨源对账（sheet/code/name/金额）
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.ext.asyncio.session import AsyncSession

from src.credit_comparison import repository
from src.credit_comparison.core.enums import ExceptionType
from src.credit_comparison.core.regex_utils import (
    has_blocking_main_sentence_format,
    has_amount_without_inc_dec,
    strip_company_detail_section,
)
from src.credit_comparison.core.text_utils import normalize_indicator_name
from src.credit_comparison.core.unit_utils import (
    convert_to_yi,
    convert_wan_to_yi,
    has_calc_scope_unit_conflict,
    is_wan_unit,
)

SCOPE_BALANCE_FIELDS: dict[str, tuple[str, str]] = {
    "usd_total": ("cur_foreign_total_balance", "pre_foreign_total_balance"),
    "foreign": ("cur_foreign_balance", "pre_foreign_balance"),
    "rmb": ("cur_rmb_balance", "pre_rmb_balance"),
}

SCOPE_ALL_FIELDS: dict[str, tuple[str, ...]] = {
    "usd_total": (
        "cur_foreign_total_balance",
        "pre_foreign_total_balance",
        "cur_foreign_total_occur",
        "pre_foreign_total_occur",
    ),
    "foreign": (
        "cur_foreign_balance",
        "pre_foreign_balance",
        "cur_foreign_occur",
        "pre_foreign_occur",
    ),
    "rmb": (
        "cur_rmb_balance",
        "pre_rmb_balance",
        "cur_rmb_occur",
        "pre_rmb_occur",
    ),
}


class CompareService:
    """对账与校验服务（异步）。

    与旧实现一致，采用“对比统一从数据库读取”的策略：
    - 解析阶段只生成记录并写库
    - 对账阶段从数据库读取落库结果进行校验
    """

    def __init__(self) -> None:
        import logging

        self.logger = logging.getLogger(self.__class__.__name__)

    # ====== Word 内部一致性校验 ======

    async def run_word_internal_checks(self, db: AsyncSession, batch_id: str) -> None:
        """执行 Word 内部一致性校验。"""

        company_rows = await repository.list_company_by_batch(db, batch_id)
        financial_rows = await repository.list_financial_by_batch(db, batch_id)
        financial_direction_by_id = {
            int(row["id"]): int(row.get("direction") or 0)
            for row in financial_rows
            if row.get("id") is not None
        }
        format_error_word_record_ids = {
            int(row["id"] or 0)
            for row in financial_rows
            if row.get("id") is not None
            and has_blocking_main_sentence_format(strip_company_detail_section(str(row.get("context") or "")))
        }
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        pending_exception_records: list[dict[str, Any]] = []
        company_direction_seen: set[tuple[int, str]] = set()
        duplicate_company_counts: dict[int, Counter[str]] = defaultdict(Counter)
        for row in company_rows:
            word_record_id = row.get("word_record_id")
            company_name = str(row.get("company") or "").strip()
            company_direction = int(row.get("direction") or 0)
            company_profit_loss_unit = str(row.get("profit_loss_unit") or "").strip()
            company_is_valid = (
                bool(company_name)
                and company_direction in (-1, 1)
                and row.get("profit_loss") is not None
                and bool(company_profit_loss_unit)
            )
            if word_record_id is not None and company_name:
                duplicate_company_counts[int(word_record_id)][company_name] += 1
            if word_record_id is not None:
                word_record_id_int = int(word_record_id)
                main_direction = financial_direction_by_id.get(word_record_id_int, 0)
                seen_key = (word_record_id_int, company_name)
                if (
                    seen_key not in company_direction_seen
                    and word_record_id_int not in format_error_word_record_ids
                    and main_direction in (-1, 1)
                    and company_is_valid
                    and main_direction != company_direction
                ):
                    company_direction_seen.add(seen_key)
                    pending_exception_records.append(
                        {
                            "batch_id": batch_id,
                            "exception_id": int(ExceptionType.COMPANY_DIRECTION_ERROR),
                            "word_record_id": word_record_id_int,
                            "field_name": "company_direction",
                            "value": company_name,
                        }
                    )
            key = (str(row.get("batch_id") or ""), str(row.get("file_name") or ""), company_name)
            if company_is_valid:
                grouped[key].append(row)

        for word_record_id_int, counter in duplicate_company_counts.items():
            for company_name, count in counter.items():
                if count < 2:
                    continue
                pending_exception_records.append(
                    {
                        "batch_id": batch_id,
                        "exception_id": int(ExceptionType.COMPANY_DUPLICATE_ERROR),
                        "word_record_id": int(word_record_id_int),
                        "field_name": "company_repeat",
                        "value": company_name,
                    }
                )

        for (_group_batch_id, _file_name, company_name), rows in grouped.items():
            if not rows:
                continue
            directions = {row["direction"] for row in rows}
            amounts = {row["profit_loss"] for row in rows}
            units = {row["profit_loss_unit"] for row in rows}
            if len(rows) > 1 and (len(directions) > 1 or len(amounts) > 1 or len(units) > 1):
                target_word_record_ids = {
                    int(row["word_record_id"])
                    for row in rows
                    if row.get("word_record_id") is not None
                }
                for target_word_record_id in target_word_record_ids:
                    pending_exception_records.append(
                        {
                            "batch_id": batch_id,
                            "exception_id": int(ExceptionType.COMPANY_AMOUNT_ERROR),
                            "word_record_id": target_word_record_id,
                            "field_name": "company",
                            "value": company_name,
                        }
                    )
        await repository.insert_exception_groups(db, pending_exception_records)

    # ====== 数值工具（原样保留）======

    def round_to_one_decimal(self, value: float | int) -> float:
        """按四舍五入规则保留 1 位小数。"""

        return float(Decimal(str(value)).quantize(Decimal("0.0"), rounding=ROUND_HALF_UP))

    def round_to_scale(self, value: float | int, scale: int) -> float:
        normalized_scale = max(0, min(int(scale), 12))
        if normalized_scale <= 0:
            quant = Decimal("1")
        else:
            quant = Decimal("0." + ("0" * (normalized_scale - 1)) + "1")
        return float(Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP))

    # ====== 跨源对账 ======

    def build_excel_indexes(
        self,
        excel_rows: list[dict[str, Any]],
    ) -> tuple[set[str], dict[tuple[str, str], list[dict[str, Any]]]]:
        """为当前批次 Excel 记录建立查询索引。"""

        available_sheets: set[str] = set()
        sheet_code_rows: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in excel_rows:
            sheet = str(row.get("sheet") or "")
            code = str(row.get("code") or "")
            available_sheets.add(sheet)
            sheet_code_rows[(sheet, code)].append(row)
        return available_sheets, sheet_code_rows

    def match_excel_records(
        self,
        financial_record: dict[str, Any],
        sheet_code_rows: dict[tuple[str, str], list[dict[str, Any]]],
    ) -> tuple[list[dict[str, Any]], tuple[int, str, str] | None]:
        """先按 sheet，再按 code 查找 Excel 记录列表。"""

        sheet_rows = sheet_code_rows.get((str(financial_record["sheet"]), str(financial_record["code"])), [])
        if len(sheet_rows) > 1:
            return sheet_rows, (int(ExceptionType.EXCEL_ERROR), "code", str(financial_record["code"]))
        if len(sheet_rows) == 1:
            excel_record = sheet_rows[0]
            if normalize_indicator_name(excel_record["name"]) != financial_record["name"]:
                return [excel_record], (int(ExceptionType.NAME_ERROR), "name", str(financial_record["name"]))
            return [excel_record], None
        return [], (int(ExceptionType.CODE_ERROR), "code", str(financial_record["code"]))

    def compare_amount(self, financial_record: dict[str, Any], excel_record: dict[str, Any]) -> list[tuple[int, str, str]]:
        """比较金额。"""

        exceptions: list[tuple[int, str, str]] = []
        context = str(financial_record.get("context") or "")
        main_context = strip_company_detail_section(context) if context else ""
        if context and (
            has_blocking_main_sentence_format(main_context)
            or has_amount_without_inc_dec(main_context)
        ):
            return exceptions
        direction = int(financial_record.get("direction") or 0)
        if direction not in (-1, 1):
            exceptions.append((int(ExceptionType.AMOUNT_ERROR), "direction", str(financial_record.get("direction") or "")))
            return exceptions
        amount_scale = int(financial_record.get("amount_scale") or 1)
        calc_scope_hint = str(financial_record.get("calc_scope_hint") or "").strip()
        amount_unit = str(financial_record.get("amount_unit") or "").strip()
        scope_hint = self.resolve_scope_hint(calc_scope_hint, amount_unit, excel_record)
        if has_calc_scope_unit_conflict(scope_hint, amount_unit):
            exceptions.append(
                (int(ExceptionType.CALCULATION_REQUIREMENT_ERROR), "amount_unit", amount_unit)
            )
            return exceptions
        if is_wan_unit(amount_unit):
            word_base_amount = financial_record.get("amount")
            if word_base_amount is None:
                exceptions.append((int(ExceptionType.AMOUNT_ERROR), "amount", ""))
                return exceptions
            word_signed_amount = self.round_to_scale(direction * float(word_base_amount), amount_scale)
        else:
            word_amount_in_yi = convert_to_yi(financial_record["amount"], amount_unit)
            if word_amount_in_yi is None:
                exceptions.append((int(ExceptionType.AMOUNT_ERROR), "amount", str(financial_record.get("amount") or "")))
                return exceptions
            word_signed_amount = self.round_to_scale(direction * float(word_amount_in_yi), amount_scale)

        excel_amount, excel_exceptions = self.calculate_excel_delta(financial_record, excel_record)
        exceptions.extend(excel_exceptions)
        if excel_amount is None:
            return exceptions

        if excel_amount is None or word_signed_amount != excel_amount:
            word_amount_text = f"{financial_record.get('direction', '')}*{financial_record.get('amount', '')}{amount_unit}"
            exceptions.append((int(ExceptionType.AMOUNT_ERROR), "amount", word_amount_text))
        return exceptions

    def calculate_excel_delta(
        self,
        financial_record: dict[str, Any],
        excel_record: dict[str, Any],
    ) -> tuple[float | None, list[tuple[int, str, str]]]:
        """根据 Word 记录口径提示、主句单位和 Excel 记录选择差值列。"""

        calc_scope_hint = str(financial_record.get("calc_scope_hint") or "").strip()
        amount_unit = str(financial_record.get("amount_unit") or "").strip()
        amount_scale = int(financial_record.get("amount_scale") or 1)
        scope_hint = self.resolve_scope_hint(calc_scope_hint, amount_unit, excel_record)
        if not self.has_scope_values(excel_record, scope_hint):
            return None, [
                (
                    int(ExceptionType.CALCULATION_REQUIREMENT_ERROR),
                    "calc_scope_hint",
                    scope_hint,
                )
            ]
        current_field, previous_field = SCOPE_BALANCE_FIELDS[scope_hint]

        current_value = excel_record.get(current_field)
        previous_value = excel_record.get(previous_field)
        exceptions: list[tuple[int, str, str]] = []

        if current_value is None:
            exceptions.append((int(ExceptionType.BALANCE_MISSING_ERROR), current_field, ""))
            current_value = 0
        if previous_value is None:
            exceptions.append((int(ExceptionType.BALANCE_MISSING_ERROR), previous_field, ""))
            previous_value = 0

        try:
            delta_in_wan = float(current_value) - float(previous_value)
        except (TypeError, ValueError):
            if not isinstance(current_value, (int, float)):
                exceptions.append((int(ExceptionType.CALCULATION_REQUIREMENT_ERROR), current_field, str(current_value)))
            if not isinstance(previous_value, (int, float)):
                exceptions.append((int(ExceptionType.CALCULATION_REQUIREMENT_ERROR), previous_field, str(previous_value)))
            return None, exceptions
        if is_wan_unit(amount_unit):
            return self.round_to_scale(delta_in_wan, amount_scale), exceptions

        delta_in_yi = convert_wan_to_yi(delta_in_wan)
        if delta_in_yi is None:
            exceptions.append((int(ExceptionType.CALCULATION_REQUIREMENT_ERROR), "excel_delta", ""))
            return None, exceptions
        return self.round_to_scale(delta_in_yi, amount_scale), exceptions

    def resolve_scope_hint(
        self,
        calc_scope_hint: str,
        amount_unit: str,
        excel_record: dict[str, Any],
    ) -> str:
        """解析当前记录应使用的计算口径。"""

        if calc_scope_hint in SCOPE_BALANCE_FIELDS:
            return calc_scope_hint
        if "美元" in amount_unit:
            return "usd_total"
        if self.has_scope_values(excel_record, "rmb"):
            return "rmb"
        return "foreign"

    def has_scope_values(self, excel_record: dict[str, Any], scope_hint: str) -> bool:
        """判断 Excel 记录是否存在指定口径的相关值。"""

        return any(
            excel_record.get(field) is not None
            for field in SCOPE_ALL_FIELDS.get(scope_hint, ())
        )

    async def run_cross_source_compare(self, db: AsyncSession, batch_id: str) -> None:
        """执行 Word 与 Excel 的跨源对账。"""

        financial_rows = await repository.list_financial_by_batch(db, batch_id)
        excel_rows = await repository.list_excel_by_batch(db, batch_id)
        company_rows = await repository.list_company_by_batch(db, batch_id)
        company_rows_by_word_record_id: dict[int, list[dict[str, Any]]] = {}
        for row in company_rows:
            word_record_id = row.get("word_record_id")
            if word_record_id is None:
                continue
            company_rows_by_word_record_id.setdefault(int(word_record_id), []).append(row)
        available_sheets, sheet_code_rows = self.build_excel_indexes(excel_rows)
        pending_compare_link_records: list[dict[str, Any]] = []
        pending_exception_records: list[dict[str, Any]] = []

        for record in financial_rows:
            word_record_id = int(record["id"])
            seen_exceptions: set[tuple[int, str, str]] = set()
            if record["sheet"] not in available_sheets:
                pending_compare_link_records.append(
                    {"batch_id": batch_id, "word_record_id": word_record_id, "excel_record_id": None}
                )
                self._append_exception(
                    seen_exceptions, pending_exception_records,
                    batch_id=batch_id, word_record_id=word_record_id,
                    exception_id=int(ExceptionType.SHEET_NOT_FOUND),
                    field_name="sheet", value=str(record["sheet"]),
                )
                continue

            excel_records, pre_exception = self.match_excel_records(record, sheet_code_rows)
            if excel_records:
                for excel_record in excel_records:
                    pending_compare_link_records.append(
                        {
                            "batch_id": batch_id,
                            "word_record_id": word_record_id,
                            "excel_record_id": int(excel_record["id"]),
                        }
                    )
            else:
                pending_compare_link_records.append(
                    {
                        "batch_id": batch_id,
                        "word_record_id": word_record_id,
                        "excel_record_id": None,
                    }
                )
            if pre_exception is not None:
                self._append_exception(
                    seen_exceptions, pending_exception_records,
                    batch_id=batch_id, word_record_id=word_record_id,
                    exception_id=pre_exception[0], field_name=pre_exception[1], value=pre_exception[2],
                )
                if int(pre_exception[0]) in {int(ExceptionType.CODE_ERROR), int(ExceptionType.EXCEL_ERROR)}:
                    continue

            if len(excel_records) == 1:
                excel_record = excel_records[0]
                for exception_id, field_name, value in self.compare_amount(record, excel_record):
                    self._append_exception(
                        seen_exceptions, pending_exception_records,
                        batch_id=batch_id, word_record_id=word_record_id,
                        exception_id=exception_id, field_name=field_name, value=value,
                    )
        await repository.insert_compare_links(db, pending_compare_link_records)
        await repository.insert_exception_groups(db, pending_exception_records)

    @staticmethod
    def _append_exception(
        seen_exceptions: set[tuple[int, str, str]],
        pending_exception_records: list[dict[str, Any]],
        *,
        batch_id: str,
        word_record_id: int,
        exception_id: int,
        field_name: str = "",
        value: str = "",
    ) -> None:
        """向异常表追加当前主记录对应的异常（去重）。"""

        key = (exception_id, field_name, value)
        if key in seen_exceptions:
            return
        seen_exceptions.add(key)
        pending_exception_records.append(
            {
                "batch_id": batch_id,
                "exception_id": exception_id,
                "word_record_id": word_record_id,
                "field_name": field_name,
                "value": value,
            }
        )
