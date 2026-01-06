from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.files.models import FileRecord


class IcbcSummary(SQLModel, table=True):
    """工商银行流水汇总信息"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    account_number: Optional[str] = None      # 账号
    account_name: Optional[str] = None        # 本方账号户名
    currency: Optional[str] = None            # 币种
    bank_name: Optional[str] = None           # 本方账号开户行
    date_range: Optional[str] = None          # 财务日期范围
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="icbc_summary")


class IcbcTransaction(SQLModel, table=True):
    """工商银行交易明细"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    transaction_time: Optional[str] = None       # 交易时间
    income: Optional[str] = None                 # 转入金额
    expense: Optional[str] = None                # 转出金额
    counterparty_account: Optional[str] = None   # 对方账号
    debit_credit: Optional[str] = None           # 借贷标志
    counterparty_name: Optional[str] = None      # 对方单位
    counterparty_bank_code: Optional[str] = None # 对方行号
    description: Optional[str] = None            # 摘要
    purpose: Optional[str] = None                # 用途
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="icbc_transactions")
