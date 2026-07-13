from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FinancialRecord:
    """Word 指标主记录。"""

    title: str = ""
    sheet: str = ""
    code: str = ""
    name: str = ""
    direction: int = 0
    amount: float | None = None
    amount_unit: str = ""
    amount_scale: int = 1
    calc_scope_hint: str = ""
    paraindex: int | None = None
    source_ref: str = ""
    context: str = ""
    file_name: str = ""
    batch_id: str = ""
    user_id: str = ""

    def to_db_dict(self) -> dict[str, Any]:
        """转换为数据库可写入字典。"""

        return {
            "title": self.title,
            "sheet": self.sheet,
            "code": self.code,
            "name": self.name,
            "direction": self.direction,
            "amount": self.amount,
            "amount_unit": self.amount_unit,
            "amount_scale": self.amount_scale,
            "calc_scope_hint": self.calc_scope_hint,
            "paraindex": self.paraindex,
            "source_ref": self.source_ref,
            "context": self.context,
            "file_name": self.file_name,
            "batch_id": self.batch_id,
            "user_id": self.user_id,
        }


@dataclass
class CompanyProfitLossRecord:
    """Word 企业明细记录。"""

    company: str = ""
    direction: int = 0
    profit_loss: float | None = None
    profit_loss_unit: str = ""
    word_record_id: int | None = None
    sheet: str = ""
    code: str = ""
    file_name: str = ""
    batch_id: str = ""
    user_id: str = ""

    def to_db_dict(self) -> dict[str, Any]:
        """转换为数据库可写入字典。"""

        return {
            "company": self.company,
            "direction": self.direction,
            "profit_loss": self.profit_loss,
            "profit_loss_unit": self.profit_loss_unit,
            "word_record_id": self.word_record_id,
            "sheet": self.sheet,
            "code": self.code,
            "file_name": self.file_name,
            "batch_id": self.batch_id,
            "user_id": self.user_id,
        }


@dataclass
class ExcelProfitLossRecord:
    """Excel 指标记录。"""

    sheet: str = ""
    code: str = ""
    name: str = ""
    cur_rmb_balance: float | None = None
    cur_rmb_occur: float | None = None
    cur_foreign_balance: float | None = None
    cur_foreign_occur: float | None = None
    cur_foreign_total_balance: float | None = None
    cur_foreign_total_occur: float | None = None
    pre_rmb_balance: float | None = None
    pre_rmb_occur: float | None = None
    pre_foreign_balance: float | None = None
    pre_foreign_occur: float | None = None
    pre_foreign_total_balance: float | None = None
    pre_foreign_total_occur: float | None = None
    excel_row_index: int | None = None
    file_name: str = ""
    batch_id: str = ""
    user_id: str = ""

    def to_db_dict(self) -> dict[str, Any]:
        """转换为数据库可写入字典。"""

        return {
            "sheet": self.sheet,
            "code": self.code,
            "name": self.name,
            "cur_rmb_balance": self.cur_rmb_balance,
            "cur_rmb_occur": self.cur_rmb_occur,
            "cur_foreign_balance": self.cur_foreign_balance,
            "cur_foreign_occur": self.cur_foreign_occur,
            "cur_foreign_total_balance": self.cur_foreign_total_balance,
            "cur_foreign_total_occur": self.cur_foreign_total_occur,
            "pre_rmb_balance": self.pre_rmb_balance,
            "pre_rmb_occur": self.pre_rmb_occur,
            "pre_foreign_balance": self.pre_foreign_balance,
            "pre_foreign_occur": self.pre_foreign_occur,
            "pre_foreign_total_balance": self.pre_foreign_total_balance,
            "pre_foreign_total_occur": self.pre_foreign_total_occur,
            "excel_row_index": self.excel_row_index,
            "file_name": self.file_name,
            "batch_id": self.batch_id,
            "user_id": self.user_id,
        }


@dataclass
class CompareLinkRecord:
    """Word 与 Excel 的对比关联记录。"""

    batch_id: str = ""
    word_record_id: int | None = None
    excel_record_id: int | None = None

    def to_db_dict(self) -> dict[str, Any]:
        """转换为数据库可写入字典。"""

        return {
            "batch_id": self.batch_id,
            "word_record_id": self.word_record_id,
            "excel_record_id": self.excel_record_id,
        }


@dataclass
class ExceptionGroupRecord:
    """异常关联记录。"""

    exception_id: int
    word_record_id: int | None = None
    field_name: str = ""
    value: str = ""
    batch_id: str = ""

    def to_db_dict(self) -> dict[str, Any]:
        """转换为数据库可写入字典。"""

        return {
            "exception_id": self.exception_id,
            "word_record_id": self.word_record_id,
            "field_name": self.field_name,
            "value": self.value,
            "batch_id": self.batch_id,
        }
