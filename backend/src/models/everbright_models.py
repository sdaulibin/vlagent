from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING
from decimal import Decimal
from sqlalchemy import Column, DECIMAL

if TYPE_CHECKING:
    from src.files.models import FileRecord


class EverbrightSummary(SQLModel, table=True):
    """光大银行流水汇总信息"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    account_name: Optional[str] = None       # 账户名称
    account_number: Optional[str] = None     # 账号
    date_range: Optional[str] = None         # 交易日期
    debit_amount: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))       # 借方发生额
    credit_amount: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))      # 贷方发生额
    debit_count: Optional[str] = None        # 借方笔数
    credit_count: Optional[str] = None       # 贷方笔数
    bank_name: str = "光大银行"              # 开户行
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="everbright_summary")


class EverbrightTransaction(SQLModel, table=True):
    """光大银行交易明细"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    sequence: Optional[str] = None           # 序号
    transaction_date: Optional[str] = None   # 交易日期
    transaction_time: Optional[str] = None   # 时间
    debit_credit: Optional[str] = None       # 借/贷
    amount: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))             # 交易金额
    balance: Optional[Decimal] = Field(default=None, sa_column=Column(DECIMAL(11, 2)))            # 账户余额
    counterparty_account: Optional[str] = None  # 对方账号
    counterparty_name: Optional[str] = None     # 对方名称
    voucher_no: Optional[str] = None            # 凭证号
    description: Optional[str] = None           # 摘要
    serial_no: Optional[str] = None             # 流水号
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="everbright_transactions")
