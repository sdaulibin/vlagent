from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime


class FileRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    file_path: str
    status: str = "pending"
    bank_type: Optional[str] = None  # 银行模板类型: shandong_local, everbright, cmb
    created_at: datetime = Field(default_factory=datetime.now)
    error_msg: Optional[str] = None
    
    # 山东地方银行关联（保持向后兼容）
    transactions: List["ShandongLocalTransaction"] = Relationship(back_populates="file_record")
    summary: Optional["ShandongLocalSummary"] = Relationship(back_populates="file_record")
    
    # 光大银行关联
    everbright_transactions: List["EverbrightTransaction"] = Relationship(back_populates="file_record")
    everbright_summary: Optional["EverbrightSummary"] = Relationship(back_populates="file_record")
    
    # 招商银行关联
    cmb_transactions: List["CmbTransaction"] = Relationship(back_populates="file_record")
    cmb_summary: Optional["CmbSummary"] = Relationship(back_populates="file_record")


# ============================================================
# 山东地方银行（潍坊银行、莱商银行、齐鲁银行）
# ============================================================

class ShandongLocalSummary(SQLModel, table=True):
    """山东地方银行流水汇总信息"""
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


class ShandongLocalTransaction(SQLModel, table=True):
    """山东地方银行交易明细"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    sequence: Optional[str] = None           # 序号
    transaction_time: Optional[str] = None   # 交易时间
    channel: Optional[str] = None            # 交易渠道
    income: Optional[str] = None             # 收入
    expense: Optional[str] = None            # 支出
    balance: Optional[str] = None            # 账户余额
    currency: Optional[str] = None           # 币种
    counterparty_account: Optional[str] = None  # 对方账号
    counterparty_name: Optional[str] = None     # 对方户名
    description: Optional[str] = None           # 摘要备注
    
    file_record: Optional[FileRecord] = Relationship(back_populates="transactions")


# ============================================================
# 光大银行
# ============================================================

class EverbrightSummary(SQLModel, table=True):
    """光大银行流水汇总信息"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    account_name: Optional[str] = None       # 账户名称
    account_number: Optional[str] = None     # 账号
    date_range: Optional[str] = None         # 交易日期
    debit_amount: Optional[str] = None       # 借方发生额
    credit_amount: Optional[str] = None      # 贷方发生额
    debit_count: Optional[str] = None        # 借方笔数
    credit_count: Optional[str] = None       # 贷方笔数
    bank_name: str = "光大银行"              # 开户行
    
    file_record: Optional[FileRecord] = Relationship(back_populates="everbright_summary")


class EverbrightTransaction(SQLModel, table=True):
    """光大银行交易明细"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    sequence: Optional[str] = None           # 序号
    transaction_date: Optional[str] = None   # 交易日期
    transaction_time: Optional[str] = None   # 时间
    debit_credit: Optional[str] = None       # 借/贷
    amount: Optional[str] = None             # 交易金额
    balance: Optional[str] = None            # 账户余额
    counterparty_account: Optional[str] = None  # 对方账号
    counterparty_name: Optional[str] = None     # 对方名称
    voucher_no: Optional[str] = None            # 凭证号
    description: Optional[str] = None           # 摘要
    serial_no: Optional[str] = None             # 流水号
    
    file_record: Optional[FileRecord] = Relationship(back_populates="everbright_transactions")


# ============================================================
# 招商银行
# ============================================================

class CmbSummary(SQLModel, table=True):
    """招商银行流水汇总信息"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    account_number: Optional[str] = None     # 账号
    account_name: Optional[str] = None       # 账号名
    start_date: Optional[str] = None         # 开始日期
    end_date: Optional[str] = None           # 结束日期
    debit_count: Optional[str] = None        # 出账总笔数
    credit_count: Optional[str] = None       # 入账总笔数
    debit_total: Optional[str] = None        # 出账总金额
    credit_total: Optional[str] = None       # 入账总金额
    total_count: Optional[str] = None        # 笔数
    bank_name: str = "招商银行"              # 开户行
    
    file_record: Optional[FileRecord] = Relationship(back_populates="cmb_summary")


class CmbTransaction(SQLModel, table=True):
    """招商银行交易明细"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    serial_no: Optional[str] = None          # 交易流水号
    transaction_date: Optional[str] = None   # 交易日期
    debit_amount: Optional[str] = None       # 借方出账
    credit_amount: Optional[str] = None      # 贷方入账
    balance: Optional[str] = None            # 余额
    counterparty_name: Optional[str] = None  # 收付方名称
    counterparty_account: Optional[str] = None  # 收付方账号
    description: Optional[str] = None        # 摘要
    transaction_type: Optional[str] = None   # 交易类型
    card_no: Optional[str] = None            # 公司一卡通号
    print_instance_no: Optional[str] = None  # 打印实例号
    
    file_record: Optional[FileRecord] = Relationship(back_populates="cmb_transactions")


# 向后兼容的别名
SummaryRecord = ShandongLocalSummary
TransactionRecord = ShandongLocalTransaction

