from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from decimal import Decimal
from sqlalchemy import Column, DECIMAL

if TYPE_CHECKING:
    from src.files.models import FileRecord


class AbcSummary(SQLModel, table=True):
    """农业银行流水汇总信息"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    # 首页顶部信息
    account_number: Optional[str] = None      # 账号
    account_name: Optional[str] = None        # 户名
    currency: Optional[str] = None            # 币种
    date_range: Optional[str] = None          # 起止日期
    
    # 末页底部汇总
    income_count: Optional[str] = None        # 总收入笔数
    income_total: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))        # 总收入金额
    expense_count: Optional[str] = None       # 总支出笔数
    expense_total: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))       # 总支出金额
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="abc_summary")


class AbcTransaction(SQLModel, table=True):
    """农业银行交易明细"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    transaction_time: Optional[str] = None       # 交易时间
    income: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))                 # 收入金额
    expense: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))                # 支出金额
    balance: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))                # 账户余额
    counterparty_account: Optional[str] = None   # 对方账号
    counterparty_name: Optional[str] = None      # 对方户名
    counterparty_bank: Optional[str] = None      # 对方开户行
    description: Optional[str] = None            # 摘要
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="abc_transactions")
