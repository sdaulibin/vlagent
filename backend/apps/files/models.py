from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime


class FileRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    file_path: str
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.now)
    error_msg: Optional[str] = None
    
    transactions: List["TransactionRecord"] = Relationship(back_populates="file_record")
    summary: Optional["SummaryRecord"] = Relationship(back_populates="file_record")


class SummaryRecord(SQLModel, table=True):
    """银行流水汇总信息"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    account_name: Optional[str] = None       # 账户名称
    account_number: Optional[str] = None     # 账(卡)号
    date_range: Optional[str] = None         # 起止日期
    income_count: Optional[str] = None       # 收入总笔数
    income_total: Optional[str] = None       # 收入总金额
    expense_count: Optional[str] = None      # 支出总笔数
    expense_total: Optional[str] = None      # 支出总金额
    has_stamp: Optional[str] = None          # 是否有盖章
    bank_name: Optional[str] = None          # 开户行
    stamp_type: Optional[str] = None         # 盖章类型
    
    file_record: Optional[FileRecord] = Relationship(back_populates="summary")


class TransactionRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    sequence: Optional[str] = None  # 序号
    transaction_time: Optional[str] = None  # 交易时间
    channel: Optional[str] = None  # 交易渠道
    income: Optional[str] = None  # 收入
    expense: Optional[str] = None  # 支出
    balance: Optional[str] = None  # 账户余额
    currency: Optional[str] = None  # 币种
    counterparty_account: Optional[str] = None  # 对方账号
    counterparty_name: Optional[str] = None  # 对方户名
    description: Optional[str] = None  # 摘要备注
    
    file_record: Optional[FileRecord] = Relationship(back_populates="transactions")
