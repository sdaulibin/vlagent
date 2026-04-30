from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from decimal import Decimal
from sqlalchemy import Column, DECIMAL

if TYPE_CHECKING:
    from src.files.models import FileRecord


class PsbcSummary(SQLModel, table=True):
    """邮储银行流水汇总信息"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(default=None, index=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    account_name: Optional[str] = None       # 户名
    account_number: Optional[str] = None     # 账号
    income_total: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))       # 收入总金额
    expense_total: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))      # 支出总金额
    income_count: Optional[str] = None       # 收入总笔数
    expense_count: Optional[str] = None      # 支出总笔数
    start_date: Optional[str] = None         # 起始日期
    end_date: Optional[str] = None           # 结束日期
    bank_name: str = "邮储银行"              # 开户行
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="psbc_summary")


class PsbcTransaction(SQLModel, table=True):
    """邮储银行交易明细"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(default=None, index=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    serial_no: Optional[str] = None              # 交易流水号
    global_route_no: Optional[str] = None        # 全局路由号
    transaction_time: Optional[str] = None       # 交易时间
    transaction_date: Optional[str] = None       # 记账日期
    income: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))                 # 收入金额
    expense: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))                # 支出金额
    balance: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))                # 余额
    counterparty_account: Optional[str] = None   # 对方账号
    counterparty_name: Optional[str] = None      # 对方户名
    counterparty_bank: Optional[str] = None      # 对方行名
    purpose: Optional[str] = None                # 用途
    postscript: Optional[str] = None             # 附言
    description: Optional[str] = None            # 摘要
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="psbc_transactions")
