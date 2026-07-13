from __future__ import annotations


UNIT_TO_YI = {
    "亿元": 1.0,
    "亿美元": 1.0,
    "亿": 1.0,
    "万元": 0.0001,
    "万": 0.0001,
    "万美元": 0.0001,
    "元": 0.00000001,
    "美元": 0.00000001,
}

USD_DENOMINATION_UNITS = {"美元", "万美元", "亿美元"}
RMB_DENOMINATION_UNITS = {"元", "万", "万元", "亿", "亿元"}


def normalize_unit(unit: str | None) -> str:
    """标准化单位文本。"""

    if not unit:
        return ""
    return unit.strip()


def is_wan_unit(unit: str | None) -> bool:
    """判断是否为“万”口径单位。"""

    return normalize_unit(unit) in {"万元", "万", "万美元"}


def is_yi_scale_unit(unit: str | None) -> bool:
    """判断是否为“亿”口径单位。"""

    return normalize_unit(unit) in {"亿元", "亿", "亿美元"}


def is_supported_word_amount_unit(unit: str | None) -> bool:
    """判断是否为当前规则下支持的 Word 金额单位。"""

    return normalize_unit(unit) in UNIT_TO_YI


def is_usd_denomination_unit(unit: str | None) -> bool:
    """判断是否为美元口径单位。"""

    return normalize_unit(unit) in USD_DENOMINATION_UNITS


def is_rmb_denomination_unit(unit: str | None) -> bool:
    """判断是否为人民币口径单位。"""

    return normalize_unit(unit) in RMB_DENOMINATION_UNITS


def has_calc_scope_unit_conflict(calc_scope_hint: str | None, amount_unit: str | None) -> bool:
    """判断计算口径提示与主句金额单位是否冲突。"""

    normalized_scope = str(calc_scope_hint or "").strip()
    normalized_unit = normalize_unit(amount_unit)
    if not normalized_scope or not normalized_unit:
        return False
    if normalized_scope in {"foreign", "rmb"}:
        return is_usd_denomination_unit(normalized_unit)
    if normalized_scope == "usd_total":
        return is_rmb_denomination_unit(normalized_unit)
    return False


def convert_to_yi(amount: float | int | None, unit: str | None) -> float | None:
    """将数值换算为亿元。"""

    if amount is None:
        return None
    normalized_unit = normalize_unit(unit)
    factor = UNIT_TO_YI.get(normalized_unit)
    if factor is None:
        return None
    return float(amount) * factor


def is_yi_unit(unit: str | None) -> bool:
    """判断是否为亿元。"""

    return normalize_unit(unit) == "亿元"


def convert_wan_to_yi(amount_in_wan: float | int | None) -> float | None:
    """将“万”口径数值转换为“亿”口径数值。"""

    if amount_in_wan is None:
        return None
    return float(amount_in_wan) / 10000
