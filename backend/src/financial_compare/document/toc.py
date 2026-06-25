"""TOC 虚拟补齐相关类型（Parser / Compare 共用）。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

AnchorResolver = Callable[["TocEntry", list["AnchorCandidate"]], int | None]


@dataclass(frozen=True)
class TocEntry:
    ordinal_key: str
    section_title: str


@dataclass(frozen=True)
class AnchorCandidate:
    line_index: int
    line_text: str
    score: float


@dataclass(frozen=True)
class TocVirtualStats:
    applied: bool
    missing_count: int
    injected_count: int
    anchor_misses: tuple[str, ...]
