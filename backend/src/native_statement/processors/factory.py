"""
处理器工厂

根据银行类型创建对应的处理器。
"""
from typing import Dict, Type, Optional

from ..models.schema import BankSchema
from .base_processor import BaseBankProcessor


class ProcessorFactory:
    """处理器工厂"""

    # 注册的处理器
    _processors: Dict[str, Type[BaseBankProcessor]] = {}

    @classmethod
    def register(cls, bank_type: str, processor_class: Type[BaseBankProcessor]) -> None:
        """
        注册处理器

        Args:
            bank_type: 银行类型
            processor_class: 处理器类
        """
        cls._processors[bank_type] = processor_class

    @classmethod
    def create(cls, schema: BankSchema) -> BaseBankProcessor:
        """
        创建处理器实例

        Args:
            schema: 银行模版

        Returns:
            处理器实例
        """
        bank_type = schema.template_id

        # 查找注册的处理器
        processor_class = cls._processors.get(bank_type)
        if processor_class:
            return processor_class(schema)

        # 返回默认处理器
        return DefaultProcessor(schema)

    @classmethod
    def get_registered_banks(cls) -> list:
        """获取已注册的银行列表"""
        return list(cls._processors.keys())


class DefaultProcessor(BaseBankProcessor):
    """默认处理器"""

    def detect_format(self, rows: list) -> bool:
        """默认处理器总是返回 True"""
        return True


# 导入银行特定处理器以触发注册
def _register_bank_processors():
    """注册所有银行特定处理器"""
    try:
        from .banks.cmb_processor import CMBProcessor
        ProcessorFactory.register("cmb", CMBProcessor)
    except ImportError:
        pass

    try:
        from .banks.shandong_processor import ShandongLocalProcessor
        ProcessorFactory.register("shandong_local", ShandongLocalProcessor)
    except ImportError:
        pass

    # 可以在这里添加更多银行处理器的注册


# 模块加载时自动注册
_register_bank_processors()
