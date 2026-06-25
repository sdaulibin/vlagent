"""阶段二：remainder 展平 + 表锚点对齐 + 表间条带文本。"""

from __future__ import annotations

from typing import Any

from financial_compare.compare.aligners.content_aligner import align_content_units
from financial_compare.compare.aligners.table_aligner import TableAligner
from financial_compare.compare.aligners.table_text_cross_align import TableTextCrossAligner
from financial_compare.compare.models.node import RemainderPool
from financial_compare.compare.models.result import TableAnchorCompareResult
from financial_compare.compare.services.compare_context import CompareContext
from financial_compare.compare.utils.remainder_utils import RemainderUtils
from financial_compare.compare.utils.text_unit_utils import TextUnitUtils
from financial_compare.document.item import DocumentItem, TableBlock, TextLine, is_table_block, is_text_line

_SCOPE_A = "TABLE_ANCHOR/A"
_SCOPE_B = "TABLE_ANCHOR/B"
_GAP_A = "TABLE_GAP/A"
_GAP_B = "TABLE_GAP/B"


class TableAnchorComparePhase:
    """穷尽 residual 表配对；表间条带；跨形态表行↔文本；终局 table_only。"""

    def __init__(self, context: CompareContext) -> None:
        self._ctx = context

    def run(self, pool: RemainderPool) -> TableAnchorCompareResult:
        if self._ctx.skip_phase2:
            return TableAnchorCompareResult(table_anchor_diffs=[], remainder_pool=pool)

        flat_a = RemainderUtils.sort_remainder(pool.remainder_a)
        flat_b = RemainderUtils.sort_remainder(pool.remainder_b)
        if not flat_a and not flat_b:
            return TableAnchorCompareResult(table_anchor_diffs=[], remainder_pool=RemainderPool())

        text_a = [e for e in flat_a if is_text_line(e)]
        text_b = [e for e in flat_b if is_text_line(e)]
        tables_a = [e for e in flat_a if is_table_block(e)]
        tables_b = [e for e in flat_b if is_table_block(e)]

        text_diffs: list[dict[str, Any]] = []
        table_diffs: list[dict[str, Any]] = []
        pool_b = list(tables_b)
        unmatched_a: list[TableBlock] = []
        matched_pairs: list[tuple[TableBlock, TableBlock]] = []

        for table_a in tables_a:
            out = TableAligner.align_pair(table_a, pool_b, llm_call=self._ctx.llm_call_named)
            if out.matched and out.matched_b is not None:
                if out.table_diffs:
                    table_diffs.extend(out.table_diffs)
                    self._ctx.snapshot.on_table_diffs(
                        scope_path_a=_SCOPE_A,
                        scope_path_b=_SCOPE_B,
                        payloads=out.table_diffs,
                        phase=2,
                    )
                pool_b.remove(out.matched_b)
                matched_pairs.append((table_a, out.matched_b))
            else:
                unmatched_a.append(table_a)

        if unmatched_a or pool_b:
            cross = TableTextCrossAligner.align_in_global_remainder(
                tables_a=unmatched_a,
                tables_b=pool_b,
                text_lines_a=text_a,
                text_lines_b=text_b,
                llm_call=self._ctx.llm_call_named,
            )
            if cross.table_diffs:
                table_diffs.extend(cross.table_diffs)
                self._ctx.snapshot.on_table_diffs(
                    scope_path_a=_SCOPE_A,
                    scope_path_b=_SCOPE_B,
                    payloads=cross.table_diffs,
                    phase=2,
                    kind="text_table",
                )
            for td in cross.text_diffs:
                text_diffs.append(td)
                self._record_phase2_text_diff_payload(td)
            text_a = cross.text_remainder_a
            text_b = cross.text_remainder_b
            for table in cross.table_remainder_a:
                only = TableAligner.table_only_diff(table, side="a")
                table_diffs.append(only)
                self._ctx.snapshot.on_table_diffs(
                    scope_path_a=_SCOPE_A,
                    scope_path_b=_SCOPE_B,
                    payloads=[only],
                    phase=2,
                )
            for table in cross.table_remainder_b:
                only = TableAligner.table_only_diff(table, side="b")
                table_diffs.append(only)
                self._ctx.snapshot.on_table_diffs(
                    scope_path_a=_SCOPE_A,
                    scope_path_b=_SCOPE_B,
                    payloads=[only],
                    phase=2,
                )

        for table_a, table_b in matched_pairs:
            alive_text_a = {id(e) for e in text_a}
            alive_text_b = {id(e) for e in text_b}
            for direction in ("before", "after"):
                gap_lines_a = self._gap_lines_in_pool(
                    flat_a, table_a, alive_text_a, direction=direction
                )
                gap_lines_b = self._gap_lines_in_pool(
                    flat_b, table_b, alive_text_b, direction=direction
                )
                if not gap_lines_a and not gap_lines_b:
                    continue
                a_units, a_locs = TextUnitUtils.units_and_locs_from_text_lines(gap_lines_a)
                b_units, b_locs = TextUnitUtils.units_and_locs_from_text_lines(gap_lines_b)
                g_flow = align_content_units(
                    a_units=a_units,
                    b_units=b_units,
                    llm_judge=self._ctx.llm_judge_content,
                    view_budget=self._ctx.view_budget,
                )
                self._record_phase2_text_diffs(
                    text_diffs,
                    g_flow,
                    a_locs,
                    b_locs,
                    scope_a=_GAP_A,
                    scope_b=_GAP_B,
                )
                RemainderUtils.remove_entries(text_a, gap_lines_a)
                RemainderUtils.remove_entries(text_b, gap_lines_b)

        next_pool = RemainderPool(remainder_a=list(text_a), remainder_b=list(text_b))
        if not text_diffs and not table_diffs:
            return TableAnchorCompareResult(table_anchor_diffs=[], remainder_pool=next_pool)

        return TableAnchorCompareResult(
            table_anchor_diffs=[
                {
                    "path_a": _SCOPE_A,
                    "path_b": _SCOPE_B,
                    "text_diffs": text_diffs,
                    "table_diffs": table_diffs,
                }
            ],
            remainder_pool=next_pool,
        )

    def _record_phase2_text_diffs(
        self,
        text_diffs: list[dict[str, Any]],
        flow: dict[str, Any],
        a_locs: list[dict[str, Any]],
        b_locs: list[dict[str, Any]],
        *,
        scope_a: str,
        scope_b: str,
    ) -> None:
        for td in TextUnitUtils.flow_to_text_diffs(flow, a_locs, b_locs):
            text_diffs.append(td)
            self._ctx.snapshot.on_text_diff(
                scope_path_a=scope_a,
                scope_path_b=scope_b,
                payload=td,
                phase=2,
            )

    @staticmethod
    def _gap_lines_in_pool(
        flat: list[DocumentItem],
        table: TableBlock,
        alive_text_ids: set[int],
        *,
        direction: str,
    ) -> list[TextLine]:
        return [
            entry
            for entry in TableAligner.extract_gap_entries(flat, table, direction=direction)
            if id(entry) in alive_text_ids
        ]

    def _record_phase2_text_diff_payload(self, td: dict[str, Any]) -> None:
        dt = str(td.get("diff_type", ""))
        scope_a = str(td.get("path_a") or _SCOPE_A)
        scope_b = str(td.get("path_b") or _SCOPE_B)
        if dt == "text" and td.get("diff"):
            self._ctx.snapshot.on_text_diff(
                scope_path_a=scope_a,
                scope_path_b=scope_b,
                payload=td,
                phase=2,
            )
        elif dt in ("text_only_in_a", "text_only_in_b"):
            self._ctx.snapshot.on_text_diff(
                scope_path_a=scope_a,
                scope_path_b=scope_b,
                payload=td,
                phase=2,
            )
