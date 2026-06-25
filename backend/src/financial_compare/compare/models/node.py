"""Compare remainder 池。"""

from __future__ import annotations

from dataclasses import dataclass, field

from financial_compare.document.item import DocumentItem


@dataclass
class RemainderPool:
    remainder_a: list[DocumentItem] = field(default_factory=list)
    remainder_b: list[DocumentItem] = field(default_factory=list)
