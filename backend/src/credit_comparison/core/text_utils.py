from __future__ import annotations

import re


LEADING_INDICATOR_INDEX_PATTERN = re.compile(
    r"^\s*(?:"
    r"[（(]?\d+(?:[.．]\d+)*[）).、．\-－—–:：]?\s*"
    r"|[一二三四五六七八九十]+\s*[、.]?\s*"
    r"|[A-Za-z]\s*[.．]\s*"
    r")"
)


def normalize_indicator_name(name: str | None) -> str:
    """标准化指标名称。

    当前规则仅做两件事：
    - 去掉名称前导序号
    - 去掉全部空白字符

    这样可以保留原始名称用于展示，同时在对账阶段进行严格的标准化匹配。
    """

    text = str(name or "").strip()
    if not text:
        return ""
    text = LEADING_INDICATOR_INDEX_PATTERN.sub("", text, count=1)
    return re.sub(r"\s+", "", text)
