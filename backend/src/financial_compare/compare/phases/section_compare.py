"""阶段一：目录 DFS + 节内文本/表格比较。"""

from __future__ import annotations

from typing import Any

from financial_compare.compare.aligners.content_aligner import align_content_units
from financial_compare.compare.aligners.table_aligner import TableAligner
from financial_compare.compare.aligners.table_text_cross_align import TableTextCrossAligner
from financial_compare.compare.models.node import RemainderPool
from financial_compare.compare.models.result import SectionCompareResult
from financial_compare.compare.models.section_buffer import SectionBuffer
from financial_compare.compare.services.compare_context import CompareContext
from financial_compare.compare.utils.remainder_utils import RemainderUtils
from financial_compare.compare.utils.text_unit_utils import TextUnitUtils
from financial_compare.document.item import DocumentItem, TableBlock, is_table_block
from financial_compare.document.tree import DocumentNode


class SectionComparePhase:
    """节内混合比较：标题配对 DFS、表表/文表/文文（表优先于文）。"""

    def __init__(self, context: CompareContext) -> None:
        self._ctx = context

    def run(self, root_a: DocumentNode, root_b: DocumentNode) -> SectionCompareResult:
        if self._ctx.skip_phase1:
            return SectionCompareResult(
                content_diffs=[],
                missing_titles_a=[],
                missing_titles_b=[],
                traces=[],
                first_title_mismatch=None,
                remainder_pool=RemainderPool(),
            )
        pool = RemainderPool()
        state: dict[str, Any] = {
            "content_diffs": [],
            "missing_titles_a": [],
            "missing_titles_b": [],
            "traces": [],
            "first_title_mismatch": None,
        }
        self._compare_sibling_group(
            a_nodes=root_a.children,
            b_nodes=root_b.children,
            state=state,
            parent_path_a="ROOT_A",
            parent_path_b="ROOT_B",
            pool=pool,
        )
        if not state["content_diffs"]:
            if state["missing_titles_a"] or state["missing_titles_b"]:
                if RemainderUtils.node_has_substance(root_a):
                    RemainderUtils.flatten_node_content_to_remainder(root_a, pool.remainder_a)
                if RemainderUtils.node_has_substance(root_b):
                    RemainderUtils.flatten_node_content_to_remainder(root_b, pool.remainder_b)
            else:
                if RemainderUtils.node_has_substance(root_a):
                    RemainderUtils.flatten_subtree_to_remainder(root_a, pool.remainder_a)
                if RemainderUtils.node_has_substance(root_b):
                    RemainderUtils.flatten_subtree_to_remainder(root_b, pool.remainder_b)
        return SectionCompareResult(
            content_diffs=state["content_diffs"],
            missing_titles_a=state["missing_titles_a"],
            missing_titles_b=state["missing_titles_b"],
            traces=state["traces"],
            first_title_mismatch=state["first_title_mismatch"],
            remainder_pool=pool,
        )

    def _compare_sibling_group(
        self,
        *,
        a_nodes: list[DocumentNode],
        b_nodes: list[DocumentNode],
        state: dict[str, Any],
        parent_path_a: str,
        parent_path_b: str,
        pool: RemainderPool,
    ) -> None:
        a_idx = 0
        b_idx = 0
        while a_idx < len(a_nodes) and b_idx < len(b_nodes):
            node_a = a_nodes[a_idx]
            node_b = b_nodes[b_idx]
            match, title_from_replay = self._resolve_title_match(
                node_a=node_a,
                node_b=node_b,
                parent_path_a=parent_path_a,
                parent_path_b=parent_path_b,
                a_index=a_idx,
                b_index=b_idx,
            )
            if not title_from_replay:
                self._ctx.snapshot.on_title_paired(
                    path_a=node_a.path,
                    path_b=node_b.path,
                    is_match=bool(match.get("is_match", False)),
                    parent_path_a=parent_path_a,
                    parent_path_b=parent_path_b,
                    a_index=a_idx,
                    b_index=b_idx,
                    reason=match.get("reason") if isinstance(match.get("reason"), str) else None,
                )
            if not match.get("is_match", False):
                mismatch_anchor = {
                    "parent_path_a": parent_path_a,
                    "parent_path_b": parent_path_b,
                    "a_index": a_idx,
                    "b_index": b_idx,
                    "path_a": node_a.path,
                    "title_a": node_a.title,
                    "path_b": node_b.path,
                    "title_b": node_b.title,
                    "reason": match.get("reason"),
                    "confidence": match.get("confidence"),
                }
                if state["first_title_mismatch"] is None:
                    state["first_title_mismatch"] = mismatch_anchor
                state["missing_titles_a"].append(
                    {
                        "parent_path_a": parent_path_a,
                        "a_index": a_idx,
                        "title_a": node_a.title,
                        "path_a": node_a.path,
                        "reason": match.get("reason"),
                    }
                )
                state["missing_titles_b"].append(
                    {
                        "parent_path_b": parent_path_b,
                        "b_index": b_idx,
                        "title_b": node_b.title,
                        "path_b": node_b.path,
                    }
                )
                RemainderUtils.flatten_subtree_to_remainder(node_a, pool.remainder_a)
                RemainderUtils.flatten_subtree_to_remainder(node_b, pool.remainder_b)
                a_idx += 1
                b_idx += 1
                continue

            content = self._compare_node_content(node_a=node_a, node_b=node_b)
            pool.remainder_a.extend(content.pop("_remainder_a"))
            pool.remainder_b.extend(content.pop("_remainder_b"))
            state["content_diffs"].append(content)
            state["traces"].append(
                {"path_a": node_a.path, "path_b": node_b.path, "title_match": match}
            )
            self._compare_sibling_group(
                a_nodes=node_a.children,
                b_nodes=node_b.children,
                state=state,
                parent_path_a=node_a.path,
                parent_path_b=node_b.path,
                pool=pool,
            )
            a_idx += 1
            b_idx += 1

        while a_idx < len(a_nodes):
            node_a = a_nodes[a_idx]
            state["missing_titles_a"].append(
                {
                    "parent_path_a": parent_path_a,
                    "a_index": a_idx,
                    "title_a": node_a.title,
                    "path_a": node_a.path,
                    "reason": "no remaining b node",
                }
            )
            RemainderUtils.flatten_subtree_to_remainder(node_a, pool.remainder_a)
            self._ctx.snapshot.on_title_tail(
                side="a",
                parent_path_a=parent_path_a,
                parent_path_b=parent_path_b,
                a_index=a_idx,
                b_index=None,
                path=node_a.path,
                reason="no remaining b node",
            )
            a_idx += 1

        while b_idx < len(b_nodes):
            node_b = b_nodes[b_idx]
            state["missing_titles_b"].append(
                {
                    "parent_path_b": parent_path_b,
                    "b_index": b_idx,
                    "title_b": node_b.title,
                    "path_b": node_b.path,
                }
            )
            RemainderUtils.flatten_subtree_to_remainder(node_b, pool.remainder_b)
            self._ctx.snapshot.on_title_tail(
                side="b",
                parent_path_a=parent_path_a,
                parent_path_b=parent_path_b,
                a_index=None,
                b_index=b_idx,
                path=node_b.path,
                reason="no remaining a node",
            )
            b_idx += 1

    def _resolve_title_match(
        self,
        *,
        node_a: DocumentNode,
        node_b: DocumentNode,
        parent_path_a: str,
        parent_path_b: str,
        a_index: int,
        b_index: int,
    ) -> tuple[dict[str, Any], bool]:
        store = getattr(self._ctx.snapshot, "store", None)
        if store is not None:
            cached = store.lookup_title_match(
                parent_path_a=parent_path_a,
                parent_path_b=parent_path_b,
                a_index=a_index,
                b_index=b_index,
            )
            if cached is not None:
                return {"is_match": cached, "reason": "replay"}, True
        return (
            self._ctx.llm_match_title(
                node_a=node_a,
                node_b=node_b,
                parent_path_a=parent_path_a,
                parent_path_b=parent_path_b,
                a_index=a_index,
                b_index=b_index,
            ),
            False,
        )

    def _compare_node_content(self, *, node_a: DocumentNode, node_b: DocumentNode) -> dict[str, Any]:
        buf_a = SectionBuffer.from_node(node_a)
        buf_b = SectionBuffer.from_node(node_b)
        text_diffs: list[dict[str, Any]] = []

        tables_b = buf_b.tables()
        table_diffs: list[dict[str, Any]] = []
        unmatched_a: list[TableBlock] = []
        for table_a in buf_a.tables():
            out = TableAligner.align_pair(table_a, tables_b, llm_call=self._ctx.llm_call_named)
            if out.matched and out.matched_b is not None:
                table_diffs.extend(out.table_diffs)
                self._ctx.snapshot.on_table_diffs(
                    scope_path_a=node_a.path,
                    scope_path_b=node_b.path,
                    payloads=out.table_diffs,
                )
                buf_a.remove(table_a)
                buf_b.remove(out.matched_b)
                tables_b.remove(out.matched_b)
            else:
                unmatched_a.append(table_a)

        cross = TableTextCrossAligner.align_in_section(
            tables_a=unmatched_a,
            tables_b=tables_b,
            text_lines_a=buf_a.text_lines(),
            text_lines_b=buf_b.text_lines(),
            llm_call=self._ctx.llm_call_named,
        )
        if cross.table_diffs:
            table_diffs.extend(cross.table_diffs)
            self._ctx.snapshot.on_table_diffs(
                scope_path_a=node_a.path,
                scope_path_b=node_b.path,
                payloads=cross.table_diffs,
            )
        for td in cross.text_diffs:
            if td.get("diff_type") == "text" and td.get("diff"):
                text_diffs.append(td)
                self._ctx.snapshot.on_text_diff(
                    scope_path_a=node_a.path,
                    scope_path_b=node_b.path,
                    payload=td,
                )

        buf_a.replace_text_lines(cross.text_remainder_a)
        buf_b.replace_text_lines(cross.text_remainder_b)
        buf_a.replace_tables(cross.table_remainder_a)
        buf_b.replace_tables(cross.table_remainder_b)

        a_units, a_locs, a_refs = TextUnitUtils.units_from_text_items(buf_a.items)
        b_units, b_locs, b_refs = TextUnitUtils.units_from_text_items(buf_b.items)
        flow = align_content_units(
            a_units=a_units,
            b_units=b_units,
            llm_judge=self._ctx.llm_judge_content,
            view_budget=self._ctx.view_budget,
        )
        flow_text_diffs = TextUnitUtils.flow_to_paired_text_diffs(flow, a_locs, b_locs)
        text_diffs.extend(flow_text_diffs)
        for td in flow_text_diffs:
            self._ctx.snapshot.on_text_diff(
                scope_path_a=node_a.path,
                scope_path_b=node_b.path,
                payload=td,
            )
        TextUnitUtils.consume_aligned_units(
            buf_a, units=a_units, line_refs=a_refs, missing=flow.get("missing_in_b", [])
        )
        TextUnitUtils.consume_aligned_units(
            buf_b, units=b_units, line_refs=b_refs, missing=flow.get("missing_in_a", [])
        )

        remainder_a: list[DocumentItem] = buf_a.drain()
        remainder_b: list[DocumentItem] = buf_b.drain()

        return {
            "path_a": node_a.path,
            "path_b": node_b.path,
            "title_a": node_a.title,
            "title_b": node_b.title,
            "text_diffs": text_diffs,
            "table_diffs": table_diffs,
            "_remainder_a": remainder_a,
            "_remainder_b": remainder_b,
        }
