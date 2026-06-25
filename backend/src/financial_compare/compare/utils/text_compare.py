"""字符串比较基础工具：字面 → 基础归一 → 简繁（可选，懒加载字表）。"""

from __future__ import annotations

from financial_compare.app_config import get_app_config
from financial_compare.compare.utils.zh_script import norm_for_compare, script_equal

_zh_script_override: bool | None = None
_char_map_path: str | None = None


def configure(*, zh_script: bool = False, char_map_path: str | None = None) -> None:
    """测试或特殊场景下覆盖 compare 行为（不重新读配置文件）。"""
    global _zh_script_override, _char_map_path
    _zh_script_override = zh_script
    if char_map_path is not None:
        _char_map_path = char_map_path


def _resolve_zh_script(zh_script: bool | None) -> bool:
    if zh_script is not None:
        return zh_script
    if _zh_script_override is not None:
        return _zh_script_override
    compare = get_app_config().get("compare") or {}
    return bool(compare.get("zh_script", False))


def texts_equal(a: str, b: str, *, zh_script: bool | None = None) -> bool:
    """比较两字符串；zh_script=False 时不加载简繁字表。"""
    if a == b:
        return True
    na = norm_for_compare(a, side="a", char_map_path=_char_map_path)
    nb = norm_for_compare(b, side="a", char_map_path=_char_map_path)
    if na == nb:
        return True
    if not _resolve_zh_script(zh_script):
        return False
    return script_equal(a, b, char_map_path=_char_map_path)


def texts_equal_list(a: list[str], b: list[str], *, zh_script: bool | None = None) -> bool:
    if len(a) != len(b):
        return False
    return all(texts_equal(x, y, zh_script=zh_script) for x, y in zip(a, b))


def filter_text_diff_pairs(diff: list[object]) -> list[dict[str, str]]:
    """剔除简繁归一后等价的 {A,B} 对；用于 text overlap diff 落库前过滤。"""
    out: list[dict[str, str]] = []
    for item in diff:
        if not isinstance(item, dict):
            continue
        a = str(item.get("A") or "")
        b = str(item.get("B") or "")
        if script_equal(a, b):
            continue
        out.append({"A": a, "B": b})
    return out
