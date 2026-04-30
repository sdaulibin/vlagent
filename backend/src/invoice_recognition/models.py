"""
发票识别数据模型和校验模式

分为两张表：
- InvoiceFile: 文件上传信息
- InvoiceResult: 每页的发票识别结果明细
"""
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional, List


class InvoiceFile(SQLModel, table=True):
    """发票上传记录"""
    __tablename__ = "invoice_files"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(default=None, index=True)
    filename: str = Field(index=True)
    file_path: str
    status: str = Field(default="pending")  # pending, processing, done, failed
    error_msg: Optional[str] = None
    recognition_duration: Optional[float] = Field(default=None, description="识别耗时(s)")
    page_count: Optional[int] = Field(default=0, description="PDF总页数")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class InvoiceResult(SQLModel, table=True):
    """单张发票的识别结果"""
    __tablename__ = "invoice_results"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[str] = Field(default=None, index=True)
    file_id: int = Field(index=True, foreign_key="invoice_files.id")
    page_number: int = Field(description="PDF页码(1-indexed)")
    
    invoice_type: Optional[str] = Field(default=None, description="发票类型")
    invoice_no: Optional[str] = Field(default=None, description="发票号码")
    invoice_date: Optional[str] = Field(default=None, description="开票日期")
    invoice_amount: Optional[str] = Field(default=None, description="发票金额(价税合计)")
    buyer_name: Optional[str] = Field(default=None, description="购买方名称")
    buyer_tax_id: Optional[str] = Field(default=None, description="购买方同一社会信用代码/纳税人识别号")
    seller_name: Optional[str] = Field(default=None, description="销售方名称")
    seller_tax_id: Optional[str] = Field(default=None, description="销售方同一社会信用代码/纳税人识别号")
    
    raw_text: Optional[str] = Field(default=None, description="当前页提取的原文本（可选存储备用）")
    error_msg: Optional[str] = Field(default=None, description="单页识别错误信息")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class InvoiceFileListItem(SQLModel):
    """Pydantic / API 返回结构 - 文件列表项"""
    id: int
    filename: str
    status: str
    page_count: Optional[int] = None
    recognition_duration: Optional[float] = None
    error_msg: Optional[str] = None
    created_at: Optional[datetime] = None


class InvoiceRecognitionResult(SQLModel):
    """Pydantic / API 返回结构 - 单页"""
    page_number: int
    invoice_type: Optional[str] = None
    invoice_no: Optional[str] = None
    invoice_date: Optional[str] = None
    invoice_amount: Optional[str] = None
    buyer_name: Optional[str] = None
    buyer_tax_id: Optional[str] = None
    seller_name: Optional[str] = None
    seller_tax_id: Optional[str] = None
    raw_text: Optional[str] = None
    error_msg: Optional[str] = None


class InvoiceRecognitionResponse(SQLModel):
    """Pydantic / API 返回结构 - 整个 PDF 文件"""
    file_id: int
    filename: str
    status: str
    page_count: Optional[int] = None
    recognition_duration: Optional[float] = None
    results: List[InvoiceRecognitionResult] = []
    error_msg: Optional[str] = None
