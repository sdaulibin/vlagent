"""结构化文档类型（Parser 产出、Compare 输入）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from financial_compare.document.toc import TocVirtualStats
from financial_compare.document.tree import DocumentNode

Role = Literal["section", "h2", "h3", "h4", "body", "root"]


@dataclass(frozen=True)
class StructuredLine:
    """单行结构化结果。"""

    level: int
    role: Role
    text: str


@dataclass(frozen=True)
class TocBlock:
    """一段目录（从单独成行的「目录／目錄」起至 TOC 结束）。"""

    lines: tuple[StructuredLine, ...]


@dataclass
class StructuredDocument:
    """结构化文档：文档树、目录块与后处理统计。"""

    root: DocumentNode
    toc: list[TocBlock] = field(default_factory=list)
    toc_virtual_stats: TocVirtualStats | None = None
    dedup_stats: dict[str, int] | None = None
