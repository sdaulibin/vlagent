"""JSON 解析与 LLM 输出归一化。"""

from __future__ import annotations

import json
import re
from typing import Any

_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")


class JsonUtils:
    @staticmethod
    def parse_object(text: str) -> dict[str, Any] | None:
        if not text.strip():
            return None
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        m = _JSON_BLOCK_RE.search(text)
        if not m:
            return None
        try:
            parsed = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def normalize_diff_list(value: Any) -> list[dict[str, str]]:
        if not isinstance(value, list):
            return []
        out: list[dict[str, str]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            left = item.get("A")
            right = item.get("B")
            if not isinstance(left, str) or not isinstance(right, str):
                continue
            a_text = left.strip()
            b_text = right.strip()
            if not a_text and not b_text:
                continue
            out.append({"A": a_text, "B": b_text})
        return out

    @staticmethod
    def normalize_confidence(value: Any) -> float | None:
        if value is None:
            return None
        try:
            conf = float(value)
        except (TypeError, ValueError):
            return None
        return max(0.0, min(1.0, conf))

    @staticmethod
    def to_float(value: Any, *, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
