from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from decimal import Decimal
from sqlalchemy import Column, DECIMAL

if TYPE_CHECKING:
    from src.files.models import FileRecord


class CcbSummary(SQLModel, table=True):
    """建设银行流水汇总信息"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    account_name: Optional[str] = None        # 本方户名
    print_date: Optional[str] = None          # 打印日期
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="ccb_summary")


class CcbTransaction(SQLModel, table=True):
    """建设银行交易明细"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    account_number: Optional[str] = None           # 账号
    transaction_time: Optional[str] = None         # 交易时间
    debit_amount: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))             # 借方发生额（支出）
    credit_amount: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))            # 贷方发生额（收入）
    balance: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))                  # 余额
    currency: Optional[str] = None                 # 币种
    counterparty_name: Optional[str] = None        # 对方户名
    counterparty_account: Optional[str] = None     # 对方账号
    counterparty_bank: Optional[str] = None        # 对方开户机构
    booking_date: Optional[str] = None             # 记账日期
    description: Optional[str] = None              # 摘要
    remark: Optional[str] = None                   # 备注
    transaction_serial: Optional[str] = None       # 账户明细编号-交易流水号
    enterprise_serial: Optional[str] = None        # 企业流水号
    voucher_type: Optional[str] = None             # 凭证种类
    voucher_number: Optional[str] = None           # 凭证号
    transaction_medium: Optional[str] = None       # 交易介质编号
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="ccb_transactions")
