from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from decimal import Decimal
from sqlalchemy import Column, DECIMAL

if TYPE_CHECKING:
    from src.files.models import FileRecord


class BocSummary(SQLModel, table=True):
    """中国银行流水汇总信息（中英双语表头）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    # 首页顶部账户信息
    account_number: Optional[str] = None      # 账号 Account No.
    account_name: Optional[str] = None        # 账户名称 Account Name
    currency: Optional[str] = None            # 币种 Currency
    account_type: Optional[str] = None        # 账户类型 Account Type
    bank_name: Optional[str] = None           # 开户行 Bank Name
    start_date: Optional[str] = None          # 起始日期 From
    end_date: Optional[str] = None            # 截止日期 To
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="boc_summary")


class BocTransaction(SQLModel, table=True):
    """中国银行交易明细（中英双语表头）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    sequence: Optional[str] = None               # 序号 No.
    booking_date: Optional[str] = None           # 记账日 Bk.D.
    value_date: Optional[str] = None             # 起息日 Val.D.
    transaction_type: Optional[str] = None       # 交易类型 Type
    voucher: Optional[str] = None                # 凭证 Vou.
    transaction_details: Optional[str] = None    # 凭证号/业务号/用途/摘要
    debit_amount: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))           # 借方发生额 Debit Amount
    credit_amount: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))          # 贷方发生额 Credit Amount
    balance: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))                # 余额 Balance
    reference_no: Optional[str] = None           # 机构/柜员/流水 Reference No.
    notes: Optional[str] = None                  # 备注 Notes (对方信息)
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="boc_transactions")
