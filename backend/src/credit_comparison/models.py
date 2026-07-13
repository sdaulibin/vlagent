"""
信用金额对账（credit-amount-comparison）数据模型。

分为五张业务表 + 一张任务表：
- CreditCompareTask:         对账任务（替代旧 task_table，承接上传与状态机）
- CreditFinancialRecord:     Word 指标主记录（financial_table）
- CreditCompanyProfitLoss:   Word 企业明细（company_profit_loss_table）
- CreditExcelProfitLoss:     Excel 指标记录（excel_profit_loss_table）
- CreditCompareLink:         Word 与 Excel 的对比关联（compare_link_table）
- CreditExceptionGroup:      异常关联记录（exception_group_table）

异常字典改为内存枚举（见 core/enums.py 的 EXCEPTION_TYPE_NAMES），不再单独建表。
所有业务表带 user_id，遵循宿主多租户隔离模式。
"""
from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, SQLModel


# ====== 表模型（table=True）======


class CreditCompareTask(SQLModel, table=True):
    """对账任务。"""

    __tablename__ = "credit_compare_task"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(index=True, unique=True, description="批次号")
    user_id: Optional[str] = Field(default=None, index=True)
    word_file_name: str = Field(description="Word 文件名")
    excel_file_name: str = Field(description="Excel 文件名")
    word_dir: str = Field(default="", description="Word 输入目录（绝对路径）")
    excel_dir: str = Field(default="", description="Excel 输入目录（绝对路径）")
    status: str = Field(default="pending", description="pending/processing/done/failed")
    error_msg: str = Field(default="")
    link_count: int = Field(default=0)
    exception_count: int = Field(default=0)
    unmatched_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class CreditFinancialRecord(SQLModel, table=True):
    """Word 指标主记录。"""

    __tablename__ = "credit_financial"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(index=True)
    user_id: Optional[str] = Field(default=None, index=True)
    title: str = Field(default="")
    sheet: str = Field(default="", index=True)
    code: str = Field(default="", index=True)
    name: str = Field(default="")
    direction: int = Field(default=0, description="增加 1 / 减少 -1 / 未知 0")
    amount: Optional[float] = Field(default=None)
    amount_unit: str = Field(default="")
    amount_scale: int = Field(default=1, description="主句金额小数位数")
    calc_scope_hint: str = Field(default="", description="rmb/foreign/usd_total")
    paraindex: Optional[int] = Field(default=None)
    source_ref: str = Field(default="")
    context: str = Field(default="")
    file_name: str = Field(default="")


class CreditCompanyProfitLoss(SQLModel, table=True):
    """Word 企业明细。"""

    __tablename__ = "credit_company_profit_loss"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(index=True)
    user_id: Optional[str] = Field(default=None, index=True)
    company: str = Field(default="")
    direction: int = Field(default=0)
    profit_loss: Optional[float] = Field(default=None)
    profit_loss_unit: str = Field(default="")
    word_record_id: Optional[int] = Field(default=None, index=True, foreign_key="credit_financial.id")
    sheet: str = Field(default="")
    code: str = Field(default="")
    file_name: str = Field(default="")


class CreditExcelProfitLoss(SQLModel, table=True):
    """Excel 指标记录（12 个金额列）。"""

    __tablename__ = "credit_excel_profit_loss"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(index=True)
    user_id: Optional[str] = Field(default=None, index=True)
    sheet: str = Field(default="", index=True)
    code: str = Field(default="", index=True)
    name: str = Field(default="")
    cur_rmb_balance: Optional[float] = None
    cur_rmb_occur: Optional[float] = None
    cur_foreign_balance: Optional[float] = None
    cur_foreign_occur: Optional[float] = None
    cur_foreign_total_balance: Optional[float] = None
    cur_foreign_total_occur: Optional[float] = None
    pre_rmb_balance: Optional[float] = None
    pre_rmb_occur: Optional[float] = None
    pre_foreign_balance: Optional[float] = None
    pre_foreign_occur: Optional[float] = None
    pre_foreign_total_balance: Optional[float] = None
    pre_foreign_total_occur: Optional[float] = None
    excel_row_index: Optional[int] = None
    file_name: str = Field(default="")


class CreditCompareLink(SQLModel, table=True):
    """Word 与 Excel 的对比关联。"""

    __tablename__ = "credit_compare_link"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(index=True)
    word_record_id: Optional[int] = Field(default=None, index=True, foreign_key="credit_financial.id")
    excel_record_id: Optional[int] = Field(default=None, index=True, foreign_key="credit_excel_profit_loss.id")


class CreditExceptionGroup(SQLModel, table=True):
    """异常关联记录。"""

    __tablename__ = "credit_exception_group"

    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(index=True)
    exception_id: int = Field(description="异常类型 ID，见 core/enums.ExceptionType")
    word_record_id: Optional[int] = Field(default=None, index=True, foreign_key="credit_financial.id")
    field_name: str = Field(default="")
    value: str = Field(default="")


# ====== 响应 DTO（无 table=True）======


class CompareTaskItem(SQLModel):
    """任务列表项。"""

    id: int
    batch_id: str
    word_file_name: str
    excel_file_name: str
    status: str
    error_msg: str = ""
    link_count: int = 0
    exception_count: int = 0
    unmatched_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CompareTaskListResponse(SQLModel):
    """任务列表响应。"""

    items: List[CompareTaskItem] = []
    total: int = 0
