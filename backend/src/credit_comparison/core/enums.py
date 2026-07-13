from __future__ import annotations

from enum import IntEnum


class Direction(IntEnum):
    """增减方向。"""

    DECREASE = -1
    UNKNOWN = 0
    INCREASE = 1


class ExceptionType(IntEnum):
    """异常类型定义。"""

    CODE_ERROR = 1
    NAME_ERROR = 2
    AMOUNT_ERROR = 3
    AMOUNT_UNIT_ERROR = 4
    SHEET_NOT_FOUND = 5
    INDICATOR_NOT_FOUND = 6
    COMPANY_AMOUNT_ERROR = 7
    BALANCE_MISSING_ERROR = 8
    CALCULATION_REQUIREMENT_ERROR = 9
    EXCEL_ERROR = 10
    OTHER = 11
    FORMAT_ERROR = 12
    COMPANY_DIRECTION_ERROR = 13
    COMPANY_FORMAT_ERROR = 14
    COMPANY_DUPLICATE_ERROR = 15
    PUNCTUATION_ERROR = 16


# 异常类型中文名映射（替代旧 exception_table 字典表）。
EXCEPTION_TYPE_NAMES: dict[int, str] = {
    1: "指标代码异常",
    2: "指标名称异常",
    3: "指标数值异常",
    4: "指标数值单位异常",
    5: "表单无对应异常",
    6: "指标无对应异常",
    7: "关联公司数值异常",
    8: "余额缺失异常",
    9: "计算要求异常",
    10: "excel异常",
    11: "其他异常",
    12: "格式异常",
    13: "关联公司方向不一致",
    14: "关联公司格式异常",
    15: "同一记录关联公司重复出现",
    16: "标点符号异常",
}
