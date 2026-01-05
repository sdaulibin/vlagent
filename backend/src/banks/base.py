"""
银行处理器基类和注册表

使用策略模式将每种银行的处理逻辑封装为独立的处理器类，
通过注册表动态分发，避免在 Router 中堆积大量条件分支。
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Type
from sqlalchemy.ext.asyncio import AsyncSession


class BankHandler(ABC):
    """银行处理器基类"""
    
    # 银行标识符，子类必须重写
    bank_type: str = ""
    
    @abstractmethod
    async def get_transactions(
        self, 
        session: AsyncSession, 
        file_id: int, 
        summary_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        获取交易明细
        
        Args:
            session: 数据库会话
            file_id: 文件ID
            summary_id: 可选的汇总ID（用于广发银行多汇总场景）
            
        Returns:
            交易记录列表
        """
        pass
    
    @abstractmethod
    async def get_summary(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> Optional[Dict[str, Any] | List[Dict[str, Any]]]:
        """
        获取汇总信息
        
        Args:
            session: 数据库会话
            file_id: 文件ID
            
        Returns:
            汇总信息字典或列表（广发银行支持多汇总）
        """
        pass
    
    @abstractmethod
    async def export_to_excel(
        self, 
        session: AsyncSession, 
        file_id: int, 
        ws
    ) -> None:
        """
        导出数据到 Excel worksheet
        
        Args:
            session: 数据库会话
            file_id: 文件ID
            ws: openpyxl worksheet 对象
        """
        pass
    
    @abstractmethod
    def create_records(
        self, 
        file_id: int, 
        transactions_data: List[Dict], 
        summary_data: Dict
    ) -> tuple:
        """
        创建交易和汇总记录对象
        
        Args:
            file_id: 文件ID
            transactions_data: 原始交易数据列表
            summary_data: 原始汇总数据
            
        Returns:
            (transactions_list, summary_obj) 元组
        """
        pass
    
    @abstractmethod
    async def delete_records(
        self, 
        session: AsyncSession, 
        file_id: int
    ) -> None:
        """
        删除指定文件关联的所有记录
        
        Args:
            session: 数据库会话
            file_id: 文件ID
        """
        pass
    
    # ============================================================
    # 识别配置相关方法（用于 PDF 处理）
    # ============================================================
    
    @abstractmethod
    def get_bank_names(self) -> List[str]:
        """
        获取用于匹配的银行名称列表
        
        Returns:
            银行名称列表，用于从文件名或图片内容识别银行类型
        """
        pass
    
    @abstractmethod
    def get_summary_schema(self) -> Dict[str, Any]:
        """
        获取汇总信息的 Schema
        
        Returns:
            汇总字段 Schema 字典
        """
        pass
    
    @abstractmethod
    def get_transaction_schema(self) -> Dict[str, Any]:
        """
        获取交易明细的 Schema
        
        Returns:
            交易字段 Schema 字典
        """
        pass
    
    def get_vertical_line_config(self) -> Dict[str, Any]:
        """
        获取垂直辅助线配置（可选覆盖）
        
        Returns:
            辅助线配置字典，默认为禁用
        """
        return {"enabled": False, "lines": []}
    
    def get_summary_config(self) -> Dict[str, Any]:
        """
        获取汇总提取配置（可选覆盖）
        
        Returns:
            汇总配置字典，默认只从第一页提取
        """
        return {"first_page_only": True}


# 银行处理器注册表
_bank_handlers: Dict[str, BankHandler] = {}


def register_bank(handler_class: Type[BankHandler]):
    """
    装饰器：注册银行处理器
    
    Usage:
        @register_bank
        class PsbcHandler(BankHandler):
            bank_type = "psbc"
            ...
    """
    instance = handler_class()
    if not instance.bank_type:
        raise ValueError(f"Handler {handler_class.__name__} must define bank_type")
    _bank_handlers[instance.bank_type] = instance
    return handler_class


def get_bank_handler(bank_type: str) -> Optional[BankHandler]:
    """
    获取指定银行类型的处理器
    
    Args:
        bank_type: 银行类型标识符
        
    Returns:
        对应的银行处理器实例，如果不存在则返回 None
    """
    return _bank_handlers.get(bank_type)


def get_all_handlers() -> Dict[str, BankHandler]:
    """
    获取所有已注册的银行处理器
    
    Returns:
        银行类型到处理器的映射字典
    """
    return _bank_handlers.copy()
