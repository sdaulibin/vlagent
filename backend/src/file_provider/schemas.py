from typing import Optional

from pydantic import BaseModel


class DownloadRequest(BaseModel):
    """影像平台文件下载请求"""
    busi_serial_no: str
    system_code: str = "OL_PT"
    params: Optional[dict] = None
    is_tfs: bool = False


class QueryRequest(BaseModel):
    """影像平台文件查询请求"""
    busi_serial_no: str
    system_code: str = "OL_PT"
    params: Optional[dict] = None


class FileProviderResponse(BaseModel):
    """统一响应"""
    success: bool
    message: str
    data: Optional[dict | str] = None
