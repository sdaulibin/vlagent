"""阶段三：全量残差文本 unit 对齐。"""

from __future__ import annotations

from typing import Any

from financial_compare.compare.aligners.content_aligner import align_content_units
from financial_compare.compare.models.node import RemainderPool
from financial_compare.compare.models.result import ResidualTextCompareResult
from financial_compare.compare.services.compare_context import CompareContext
from financial_compare.compare.utils.text_unit_utils import TextUnitUtils
from financial_compare.document.item import is_text_line

_SCOPE_A = "RESIDUAL/A"
_SCOPE_B = "RESIDUAL/B"


class ResidualTextComparePhase:
    """仅文本 unit 全池 align，TableBlock 不在此阶段处理。"""

    def __init__(self, context: CompareContext) -> None:
        self._ctx = context

    def run(self, pool: RemainderPool) -> ResidualTextCompareResult:
        lines_a = [e for e in pool.remainder_a if is_text_line(e)]
        lines_b = [e for e in pool.remainder_b if is_text_line(e)]
        a_units, a_locs = TextUnitUtils.units_and_locs_from_text_lines(lines_a)
        b_units, b_locs = TextUnitUtils.units_and_locs_from_text_lines(lines_b)
        if not a_units and not b_units:
            return ResidualTextCompareResult(residual_content_diffs=None)

        flow = align_content_units(
            a_units=a_units,
            b_units=b_units,
            llm_judge=self._ctx.llm_judge_content,
            view_budget=self._ctx.view_budget,
        )
        text_diffs = TextUnitUtils.flow_to_text_diffs(flow, a_locs, b_locs)
        self._record_text_diffs(text_diffs)
        return ResidualTextCompareResult(
            residual_content_diffs={
                "path_a": _SCOPE_A,
                "path_b": _SCOPE_B,
                "text_diffs": text_diffs,
            }
        )

    def _record_text_diffs(self, text_diffs: list[dict[str, Any]]) -> None:
        for td in text_diffs:
            dt = str(td.get("diff_type", ""))
            if dt == "text" and td.get("diff"):
                self._ctx.snapshot.on_text_diff(
                    scope_path_a=_SCOPE_A,
                    scope_path_b=_SCOPE_B,
                    payload=td,
                    phase=3,
                )
            elif dt in ("text_only_in_a", "text_only_in_b"):
                self._ctx.snapshot.on_text_diff(
                    scope_path_a=_SCOPE_A,
                    scope_path_b=_SCOPE_B,
                    payload=td,
                    phase=3,
                )
