from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.files.models import FileRecord


class JiningSummary(SQLModel, table=True):
    """济宁银行流水汇总信息"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    account_number: Optional[str] = None     # 账号
    account_name: Optional[str] = None       # 账户名称
    date_range: Optional[str] = None         # 起止日期
    currency: Optional[str] = None           # 币种
    income_total: Optional[str] = None       # 收入金额合计
    expense_total: Optional[str] = None      # 支出金额合计
    bank_name: Optional[str] = None          # 开户机构
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="jining_summary")


class JiningTransaction(SQLModel, table=True):
    """济宁银行交易明细"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    sequence: Optional[str] = None           # 序号
    transaction_date: Optional[str] = None   # 记账日期
    channel: Optional[str] = None            # 交易渠道
    income: Optional[str] = None             # 收入
    expense: Optional[str] = None            # 支出
    balance: Optional[str] = None            # 账户余额
    description: Optional[str] = None        # 摘要备注
    counterparty_info: Optional[str] = None  # 交易对手信息
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="jining_transactions")
