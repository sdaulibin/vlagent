"""
银行流水数据模型统一导出入口

各银行模型定义已拆分到 src/models/*_models.py 文件中，
本文件作为统一导出入口，保持向后兼容。
"""

# 山东地方银行
from src.models.shandong_models import ShandongLocalSummary, ShandongLocalTransaction

# 光大银行
from src.models.everbright_models import EverbrightSummary, EverbrightTransaction

# 招商银行
from src.models.cmb_models import CmbSummary, CmbTransaction

# 济宁银行
from src.models.jining_models import JiningSummary, JiningTransaction

# 广发银行
from src.models.cgb_models import CgbSummary, CgbTransaction

# 邮储银行
from src.models.psbc_models import PsbcSummary, PsbcTransaction

# 工商银行
from src.models.icbc_models import IcbcSummary, IcbcTransaction

# 建设银行
from src.models.ccb_models import CcbSummary, CcbTransaction

# 农业银行
from src.models.abc_models import AbcSummary, AbcTransaction


# 向后兼容的别名
SummaryRecord = ShandongLocalSummary
TransactionRecord = ShandongLocalTransaction


__all__ = [
    # 山东地方银行
    "ShandongLocalSummary", "ShandongLocalTransaction",
    # 光大银行
    "EverbrightSummary", "EverbrightTransaction",
    # 招商银行
    "CmbSummary", "CmbTransaction",
    # 济宁银行
    "JiningSummary", "JiningTransaction",
    # 广发银行
    "CgbSummary", "CgbTransaction",
    # 邮储银行
    "PsbcSummary", "PsbcTransaction",
    # 工商银行
    "IcbcSummary", "IcbcTransaction",
    # 建设银行
    "CcbSummary", "CcbTransaction",
    # 农业银行
    "AbcSummary", "AbcTransaction",
    # 向后兼容别名
    "SummaryRecord", "TransactionRecord",
]
