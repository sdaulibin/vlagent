from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from decimal import Decimal
from sqlalchemy import Column, DECIMAL

if TYPE_CHECKING:
    from src.files.models import FileRecord


class BocomSummary(SQLModel, table=True):
    """交通银行流水汇总信息"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    bank_branch: Optional[str] = None         # 开户机构
    account_number: Optional[str] = None      # 账号
    account_name: Optional[str] = None        # 户名
    currency: Optional[str] = None            # 币种
    year: Optional[str] = None                # 年份
    month: Optional[str] = None               # 月份
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="bocom_summary")


class BocomTransaction(SQLModel, table=True):
    """交通银行交易明细"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    sequence: Optional[str] = None               # 序号
    accounting_date: Optional[str] = None        # 会计日期
    transaction_date: Optional[str] = None       # 交易日期
    transaction_name: Optional[str] = None       # 交易名称
    voucher_type: Optional[str] = None           # 凭证种类
    voucher_number: Optional[str] = None         # 凭证号码
    debit_amount: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))           # 借方发生额
    credit_amount: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))          # 贷方发生额
    balance: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))                # 余额
    card_number: Optional[str] = None            # 卡号
    transaction_location: Optional[str] = None   # 交易地点
    counterparty_account: Optional[str] = None   # 对方账号
    counterparty_name: Optional[str] = None      # 对方户名
    counterparty_bank: Optional[str] = None      # 对方行名
    description: Optional[str] = None            # 摘要
    serial_no: Optional[str] = None              # 流水号
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="bocom_transactions")
