"""各 compare 阶段共享依赖。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from financial_compare.compare.snapshot.hooks import NoopSnapshotHooks, SnapshotHooks


@dataclass
class CompareContext:
    view_budget: int
    preview_chars: int
    llm_judge_content: Callable[[str, str, dict[str, Any]], dict[str, Any]]
    llm_match_title: Callable[..., dict[str, Any]]
    llm_call_named: Callable[[str, str, str], str]
    log_info: Callable[[str, dict[str, Any]], None]
    snapshot: SnapshotHooks = field(default_factory=NoopSnapshotHooks)
    skip_phase1: bool = False
    skip_phase2: bool = False
