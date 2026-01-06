from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.files.models import FileRecord


class CgbSummary(SQLModel, table=True):
    """广发银行流水汇总信息"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    
    account_name: Optional[str] = None       # 户名
    account_number: Optional[str] = None     # 账号
    date_range: Optional[str] = None         # 起止日期
    currency: Optional[str] = None           # 币种
    unit: Optional[str] = None               # 单位
    expense_total: Optional[str] = None      # 支出总金额
    expense_count: Optional[str] = None      # 支出总笔数
    income_total: Optional[str] = None       # 收入总金额
    income_count: Optional[str] = None       # 收入总笔数
    current_balance: Optional[str] = None    # 账户当前余额
    record_count: Optional[str] = None       # 记录数
    bank_name: str = "广发银行"              # 开户行
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="cgb_summary")
    # 一对多关系：一个汇总对应多条交易明细
    transactions: List["CgbTransaction"] = Relationship(back_populates="summary")


class CgbTransaction(SQLModel, table=True):
    """广发银行交易明细"""
    id: Optional[int] = Field(default=None, primary_key=True)
    file_id: Optional[int] = Field(default=None, foreign_key="filerecord.id")
    summary_id: Optional[int] = Field(default=None, foreign_key="cgbsummary.id")  # 关联汇总
    
    serial_no: Optional[str] = None              # 流水号
    transaction_time: Optional[str] = None       # 交易时间
    income: Optional[str] = None                 # 收入
    expense: Optional[str] = None                # 支出
    balance: Optional[str] = None                # 余额
    currency: Optional[str] = None               # 币种
    counterparty_account: Optional[str] = None   # 对方账号
    counterparty_name: Optional[str] = None      # 对方户名
    transaction_branch: Optional[str] = None     # 交易行所
    counterparty_bank_code: Optional[str] = None # 对方开户行联行号
    counterparty_bank: Optional[str] = None      # 对方开户行
    voucher_no: Optional[str] = None             # 凭证号
    description: Optional[str] = None            # 摘要
    remark: Optional[str] = None                 # 备注
    postscript: Optional[str] = None             # 附言
    
    file_record: Optional["FileRecord"] = Relationship(back_populates="cgb_transactions")
    summary: Optional["CgbSummary"] = Relationship(back_populates="transactions")
