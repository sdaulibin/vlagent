"""
银行处理器模块

自动导入所有银行处理器以触发注册。
"""
from src.banks.base import get_bank_handler, get_all_handlers, BankHandler

# 导入所有处理器以触发 @register_bank 装饰器
from src.banks.shandong_handler import ShandongHandler
from src.banks.everbright_handler import EverbrightHandler
from src.banks.cmb_handler import CmbHandler
from src.banks.jining_handler import JiningHandler
from src.banks.cgb_handler import CgbHandler
from src.banks.psbc_handler import PsbcHandler
from src.banks.icbc_handler import IcbcHandler
from src.banks.ccb_handler import CcbHandler
from src.banks.abc_handler import AbcHandler

__all__ = [
    "get_bank_handler",
    "get_all_handlers",
    "BankHandler",
    "ShandongHandler",
    "EverbrightHandler",
    "CmbHandler",
    "JiningHandler",
    "CgbHandler",
    "PsbcHandler",
    "IcbcHandler",
    "CcbHandler",
    "AbcHandler",
]
