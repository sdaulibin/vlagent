"""三阶段 compare 输出结果。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .node import RemainderPool


@dataclass
class SectionCompareResult:
    content_diffs: list[dict[str, Any]]
    missing_titles_a: list[dict[str, Any]]
    missing_titles_b: list[dict[str, Any]]
    traces: list[dict[str, Any]]
    first_title_mismatch: dict[str, Any] | None
    remainder_pool: RemainderPool


@dataclass
class TableAnchorCompareResult:
    table_anchor_diffs: list[dict[str, Any]]
    remainder_pool: RemainderPool


@dataclass
class ResidualTextCompareResult:
    residual_content_diffs: dict[str, Any] | None
