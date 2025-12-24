"""
全局异常定义
"""
from fastapi import HTTPException, status


class AppException(HTTPException):
    """应用基础异常"""
    def __init__(self, status_code: int = 500, detail: str = "服务器内部错误"):
        super().__init__(status_code=status_code, detail=detail)


class NotFoundError(AppException):
    """资源未找到"""
    def __init__(self, resource: str = "资源"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"{resource}不存在"
        )


class BadRequestError(AppException):
    """请求错误"""
    def __init__(self, detail: str = "请求参数错误"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=detail
        )


class ConflictError(AppException):
    """资源冲突"""
    def __init__(self, detail: str = "资源状态冲突"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT, 
            detail=detail
        )


class TimeoutError(AppException):
    """操作超时"""
    def __init__(self, detail: str = "操作超时"):
        super().__init__(
            status_code=status.HTTP_408_REQUEST_TIMEOUT, 
            detail=detail
        )
