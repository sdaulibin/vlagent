"""表格对齐：表配对 LLM（类型+表头）、body 行 LLM 配对、cell 规则 diff、阶段二表间条带。"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from financial_compare.compare.llm.prompts.table_align import (
    TABLE_PAIR_MATCH_SYSTEM_PROMPT,
    TABLE_ROW_MATCH_SYSTEM_PROMPT,
)
from financial_compare.compare.utils.json_utils import JsonUtils
from financial_compare.compare.utils.text_compare import texts_equal
from financial_compare.compare.utils.zh_script import script_equal
from financial_compare.document.item import DocumentItem, Row, TableBlock, TableKind, TextLine, is_table_block, is_text_line
from financial_compare.table.span_bbox import merge_span_bboxes

_TABLE_PAIR_SIM_THRESHOLD = 0.75
_TABLE_PREVIEW_MAX_ROWS = 8
_GAP_CHAR_CAP = 3000

_KV_TABLE_KIND: TableKind = "KVTable"
_COM_TABLE_KIND: TableKind = "ComTable"

# cell 比对：仅去掉空白（含换行/tab/空格），保留标点
_KV_WS_RE = re.compile(r"[\s\u00a0\f\v]+", re.UNICODE)

_ROW_ALIGN_MAX_STEPS = 5000
_ROW_B_CANDIDATE_MAX = 8

_LlmFn = Callable[[str, str, str], str]


@dataclass
class TableAlignResult:
    matched: bool = False
    matched_b: TableBlock | None = None
    table_diffs: list[dict[str, Any]] = field(default_factory=list)


class TableAligner:
    """表格配对与 cell diff。"""

    @staticmethod
    def header_rows(table: TableBlock) -> list[str]:
        return [row.content for row in table.rows if row.row_type == "header"]

    @staticmethod
    def body_rows(table: TableBlock) -> list[Row]:
        return [row for row in table.rows if row.row_type == "body"]

    @staticmethod
    def _rows_preview(table: TableBlock) -> list[dict[str, object]]:
        return [
            {"row_index": row.row_index, "content": row.content}
            for row in table.rows[:_TABLE_PREVIEW_MAX_ROWS]
        ]

    @staticmethod
    def _hint_header_indices(table: TableBlock) -> list[int]:
        return [row.row_index for row in table.rows if row.row_type == "header"]

    @staticmethod
    def _parse_table_kind(value: object) -> TableKind:
        if value == _COM_TABLE_KIND:
            return _COM_TABLE_KIND
        return _KV_TABLE_KIND

    @staticmethod
    def _parse_header_indices(value: object) -> list[int]:
        if not isinstance(value, list):
            return []
        out: list[int] = []
        for item in value:
            try:
                out.append(int(item))
            except (TypeError, ValueError):
                continue
        return out

    @classmethod
    def _apply_table_structure(
        cls,
        table: TableBlock,
        kind: TableKind,
        header_indices: list[int],
    ) -> None:
        if kind == _KV_TABLE_KIND:
            table.table_kind = _KV_TABLE_KIND
            for row in table.rows:
                row.row_type = "body"
            return
        header_set = set(header_indices)
        table.table_kind = _COM_TABLE_KIND
        for row in table.rows:
            row.row_type = "header" if row.row_index in header_set else "body"

    @classmethod
    def body_rows_for_compare(cls, table: TableBlock) -> list[Row]:
        if table.table_kind == _KV_TABLE_KIND:
            return list(table.rows)
        return cls.body_rows(table)

    @staticmethod
    def _split_row_cells(content: str) -> list[str]:
        return content.split("|")

    @staticmethod
    def _row_first_key(content: str) -> str:
        parts = TableAligner._split_row_cells(content)
        return parts[0].strip() if parts else ""

    @staticmethod
    def _norm_cell_kv(value: str) -> str:
        """KVTable 专用：去 cell 内空白，保留标点。"""
        return _KV_WS_RE.sub("", unicodedata.normalize("NFKC", value))

    @staticmethod
    def _row_has_substance(row: Row) -> bool:
        if TableAligner._row_first_key(row.content).strip():
            return True
        return any(part.strip() for part in TableAligner._split_row_cells(row.content))

    @staticmethod
    def _strip_cell_ws(value: str) -> str:
        return _KV_WS_RE.sub("", unicodedata.normalize("NFKC", value))

    @staticmethod
    def _cells_string_equal(va: str, vb: str) -> bool:
        """字符串完全相同则跳过 LLM（含去空白后一致）。"""
        if va == vb:
            return True
        return TableAligner._strip_cell_ws(va) == TableAligner._strip_cell_ws(vb)

    @classmethod
    def _parse_numeric_cell(cls, value: str) -> Decimal | None:
        """可解析为纯数值时返回 Decimal，否则 None。"""
        stripped = value.strip()
        if not stripped:
            return None
        negative = False
        core = stripped
        if (core.startswith("(") and core.endswith(")")) or (core.startswith("（") and core.endswith("）")):
            negative = True
            core = core[1:-1].strip()
        core = cls._strip_cell_ws(core)
        if core.endswith("%") or core.endswith("％"):
            core = core[:-1]
        core = core.replace(",", "").replace("，", "")
        if not core or not re.fullmatch(r"\d+(?:\.\d+)?", core):
            return None
        try:
            val = Decimal(core)
        except InvalidOperation:
            return None
        return -val if negative else val

    @classmethod
    def _resolve_cell_shortcut(
        cls,
        va: str,
        vb: str,
    ) -> tuple[bool, str | None, str | None] | None:
        """字面/简繁/数值短路；None 表示文本不等且需进一步规则判定。"""
        if not va.strip() and not vb.strip():
            return False, None, None
        if cls._cells_string_equal(va, vb):
            return False, None, None
        if texts_equal(va, vb):
            return False, None, None
        if not va.strip() or not vb.strip():
            return True, "only_in", None
        na = cls._parse_numeric_cell(va)
        nb = cls._parse_numeric_cell(vb)
        if na is not None and nb is not None:
            if na == nb:
                return False, None, None
            return True, "value", None
        return None

    @classmethod
    def _resolve_cell_for_paired_row(cls, va: str, vb: str) -> tuple[bool, str | None, str | None]:
        """已配对行的 cell 比对（纯规则，不调 LLM）。"""
        resolved = cls._resolve_cell_shortcut(va, vb)
        if resolved is not None:
            return resolved
        if script_equal(va, vb):
            return False, None, None
        return True, "other", None

    @classmethod
    def _table_row_cells_equal(cls, content_a: str, content_b: str) -> bool:
        """重叠列规则一致即视为同行；多出的列不参与同行判定。"""
        cells_a = cls._split_row_cells(content_a)
        cells_b = cls._split_row_cells(content_b)
        n_overlap = min(len(cells_a), len(cells_b))
        for col in range(n_overlap):
            va = cells_a[col]
            vb = cells_b[col]
            if cls._cells_string_equal(va, vb) or texts_equal(va, vb) or script_equal(va, vb):
                continue
            if not va.strip() and not vb.strip():
                continue
            na = cls._parse_numeric_cell(va)
            nb = cls._parse_numeric_cell(vb)
            if na is not None and nb is not None and na == nb:
                continue
            return False
        return True

    @classmethod
    def _collect_row_pair_cell_diffs(cls, row_a: Row, row_b: Row) -> list[dict[str, Any]]:
        cells_a = cls._split_row_cells(row_a.content)
        cells_b = cls._split_row_cells(row_b.content)
        n = max(len(cells_a), len(cells_b))
        items: list[dict[str, Any]] = []
        for col in range(n):
            va = cells_a[col] if col < len(cells_a) else ""
            vb = cells_b[col] if col < len(cells_b) else ""
            has_diff, category, reason = cls._resolve_cell_for_paired_row(va, vb)
            if not has_diff:
                continue
            items.append(
                {
                    "row_a": row_a,
                    "row_b": row_b,
                    "col": col,
                    "va": va,
                    "vb": vb,
                    "category": category,
                    "reason": reason,
                }
            )
        return items

    @classmethod
    def _llm_match_row_in_window(
        cls,
        row_a: Row,
        candidates_b: list[Row],
        *,
        llm_call: _LlmFn,
    ) -> Row | None:
        if not candidates_b:
            return None
        for row in candidates_b:
            if cls._table_row_cells_equal(row_a.content, row.content):
                return row
        payload = {
            "row_a": {"row_index": row_a.row_index, "content": row_a.content},
            "candidates_b": [
                {"row_index": row.row_index, "content": row.content}
                for row in candidates_b
            ],
        }
        raw = llm_call(
            "table_row_match",
            TABLE_ROW_MATCH_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
        )
        parsed = JsonUtils.parse_object(raw) or {}
        b_idx = parsed.get("b_row_index")
        if b_idx is None:
            return None
        if not isinstance(b_idx, int):
            return None
        for row in candidates_b:
            if row.row_index == b_idx:
                return row
        return None

    @staticmethod
    def _skip_empty_body_row(rows: list[Row], idx: int) -> int:
        while idx < len(rows) and not TableAligner._row_has_substance(rows[idx]):
            idx += 1
        return idx

    @staticmethod
    def _advance_body_row(rows: list[Row], idx: int) -> int:
        return TableAligner._skip_empty_body_row(rows, idx + 1)

    @staticmethod
    def _b_row_probe_in_phase(probe: int, phase: str, anchor: int, count: int) -> bool:
        if phase == "forward":
            return probe < count
        return probe < anchor

    @staticmethod
    def _try_begin_wrap_body_row(
        rows: list[Row],
        phase: str,
        anchor: int,
    ) -> tuple[str, int] | None:
        if phase == "forward" and anchor > 0:
            return "wrap", TableAligner._skip_empty_body_row(rows, 0)
        return None

    @classmethod
    def _collect_b_row_candidates(
        cls,
        b_rows: list[Row],
        b_probe: int,
        paired_b: set[int],
        *,
        phase: str,
        b_anchor: int,
    ) -> tuple[list[Row], int]:
        """从 b_probe 起在 phase 范围内收集至多 _ROW_B_CANDIDATE_MAX 条未配对 B 行。"""
        candidates: list[Row] = []
        probe = b_probe
        b_count = len(b_rows)
        while len(candidates) < _ROW_B_CANDIDATE_MAX:
            if not cls._b_row_probe_in_phase(probe, phase, b_anchor, b_count):
                break
            probe = cls._skip_empty_body_row(b_rows, probe)
            if not cls._b_row_probe_in_phase(probe, phase, b_anchor, b_count):
                break
            row_b = b_rows[probe]
            if row_b.row_index not in paired_b:
                candidates.append(row_b)
            probe = cls._advance_body_row(b_rows, probe)
        return candidates, probe

    @classmethod
    def _b_row_list_index(cls, b_rows: list[Row], row_index: int) -> int | None:
        for i, row in enumerate(b_rows):
            if row.row_index == row_index:
                return i
        return None

    @classmethod
    def _align_rows_anchor_llm(
        cls,
        a_rows: list[Row],
        b_rows: list[Row],
        *,
        llm_call: _LlmFn,
    ) -> dict[str, Any]:
        """A 按序；B 用 anchor+wrap 滑动窗；每次 A 一行 + B 至多 8 候选行一次 LLM 判同行。"""
        row_pairs: list[dict[str, int | float]] = []
        paired_b: set[int] = set()

        a_pos = 0
        b_probe = 0
        b_anchor = 0
        b_phase = "forward"
        steps = 0

        while steps < _ROW_ALIGN_MAX_STEPS:
            steps += 1
            a_pos = cls._skip_empty_body_row(a_rows, a_pos)
            if a_pos >= len(a_rows):
                break

            b_count = len(b_rows)
            if not cls._b_row_probe_in_phase(b_probe, b_phase, b_anchor, b_count):
                wrap = cls._try_begin_wrap_body_row(b_rows, b_phase, b_anchor)
                if wrap is not None:
                    b_phase, b_probe = wrap
                    continue
                a_pos = cls._advance_body_row(a_rows, a_pos)
                b_probe = b_anchor
                b_phase = "forward"
                continue

            b_probe = cls._skip_empty_body_row(b_rows, b_probe)
            row_a = a_rows[a_pos]
            candidates_b, next_probe = cls._collect_b_row_candidates(
                b_rows,
                b_probe,
                paired_b,
                phase=b_phase,
                b_anchor=b_anchor,
            )

            if not candidates_b:
                wrap = cls._try_begin_wrap_body_row(b_rows, b_phase, b_anchor)
                if wrap is not None:
                    b_phase, b_probe = wrap
                    continue
                a_pos = cls._advance_body_row(a_rows, a_pos)
                b_probe = b_anchor
                b_phase = "forward"
                continue

            matched_b = cls._llm_match_row_in_window(row_a, candidates_b, llm_call=llm_call)
            if matched_b is not None:
                paired_b.add(matched_b.row_index)
                row_pairs.append(
                    {
                        "a_row_index": row_a.row_index,
                        "b_row_index": matched_b.row_index,
                        "similarity": 1.0,
                    }
                )
                a_pos = cls._advance_body_row(a_rows, a_pos)
                matched_list_idx = cls._b_row_list_index(b_rows, matched_b.row_index)
                if matched_list_idx is not None:
                    b_probe = cls._advance_body_row(b_rows, matched_list_idx)
                else:
                    b_probe = next_probe
                b_anchor = b_probe
                b_phase = "forward"
                continue

            if cls._b_row_probe_in_phase(next_probe, b_phase, b_anchor, b_count):
                b_probe = next_probe
                continue
            wrap = cls._try_begin_wrap_body_row(b_rows, b_phase, b_anchor)
            if wrap is not None:
                b_phase, b_probe = wrap
                continue
            a_pos = cls._advance_body_row(a_rows, a_pos)
            b_probe = b_anchor
            b_phase = "forward"

        paired_a = {int(p["a_row_index"]) for p in row_pairs}
        only_a = [
            r.row_index
            for r in a_rows
            if r.row_index not in paired_a and cls._row_has_substance(r)
        ]
        only_b = [
            r.row_index
            for r in b_rows
            if r.row_index not in paired_b and cls._row_has_substance(r)
        ]
        return {
            "row_pairs": row_pairs,
            "only_in_a_rows": only_a,
            "only_in_b_rows": only_b,
        }

    @classmethod
    def align_matched_tables(
        cls,
        table_a: TableBlock,
        table_b: TableBlock,
        *,
        llm_call: _LlmFn,
    ) -> tuple[list[dict[str, Any]], int, float]:
        """``TABLE_PAIR_MATCH`` 判同表并解析结构，再 body 行配对 + cell diff。"""
        match_out = cls._llm_match_tables(table_a, table_b, llm_call=llm_call)
        if not match_out.get("is_same_table"):
            return [], 0, 0.0
        similarity = float(match_out.get("similarity") or 0.0)
        if similarity < _TABLE_PAIR_SIM_THRESHOLD:
            return [], 0, similarity
        kind_a = match_out["table_kind_a"]
        kind_b = match_out["table_kind_b"]
        if kind_a != kind_b:
            return [], 0, similarity
        cls._apply_table_structure(table_a, kind_a, match_out["header_row_indices_a"])
        cls._apply_table_structure(table_b, kind_b, match_out["header_row_indices_b"])
        a_body = cls.body_rows_for_compare(table_a)
        b_body = cls.body_rows_for_compare(table_b)
        row_out = cls._align_rows_anchor_llm(a_body, b_body, llm_call=llm_call)
        matched_count = len(row_out.get("row_pairs", []))
        diffs = cls._diff_matched_tables(
            table_a,
            table_b,
            row_out,
            a_rows=a_body,
            b_rows=b_body,
        )
        return diffs, matched_count, similarity

    @classmethod
    def align_pair(
        cls,
        table_a: TableBlock,
        candidates_b: list[TableBlock],
        *,
        llm_call: _LlmFn,
    ) -> TableAlignResult:
        best: TableAlignResult | None = None
        best_score = -1.0
        for table_b in candidates_b:
            diffs, matched, similarity = cls.align_matched_tables(
                table_a, table_b, llm_call=llm_call
            )
            if matched == 0:
                continue
            result = TableAlignResult(matched=True, matched_b=table_b, table_diffs=diffs)
            if similarity > best_score:
                best_score = similarity
                best = result
        return best or TableAlignResult(matched=False)

    @classmethod
    def align_pool(
        cls,
        tables_a: list[TableBlock],
        tables_b: list[TableBlock],
        *,
        llm_call: _LlmFn,
    ) -> tuple[list[dict[str, Any]], list[TableBlock], list[TableBlock]]:
        pool_b = list(tables_b)
        all_table_diffs: list[dict[str, Any]] = []
        unmatched_a: list[TableBlock] = []
        for table_a in tables_a:
            out = cls.align_pair(table_a, pool_b, llm_call=llm_call)
            if out.matched and out.matched_b is not None:
                all_table_diffs.extend(out.table_diffs)
                pool_b.remove(out.matched_b)
            else:
                unmatched_a.append(table_a)
        return all_table_diffs, unmatched_a, pool_b

    @staticmethod
    def table_only_diff(table: TableBlock, *, side: str) -> dict[str, Any]:
        diff_type = "table_only_in_a" if side == "a" else "table_only_in_b"
        return {
            "diff_type": diff_type,
            "loc_a": TableAligner._table_loc(table) if side == "a" else None,
            "loc_b": TableAligner._table_loc(table) if side == "b" else None,
            "header_preview_a": TableAligner.header_rows(table) if side == "a" else None,
            "header_preview_b": TableAligner.header_rows(table) if side == "b" else None,
        }

    @classmethod
    def _llm_match_tables(
        cls,
        table_a: TableBlock,
        table_b: TableBlock,
        *,
        llm_call: _LlmFn,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rows_preview_a": cls._rows_preview(table_a),
            "total_row_count_a": len(table_a.rows),
            "hint_header_indices_a": cls._hint_header_indices(table_a),
            "rows_preview_b": cls._rows_preview(table_b),
            "total_row_count_b": len(table_b.rows),
            "hint_header_indices_b": cls._hint_header_indices(table_b),
        }
        if table_a.table_kind is not None:
            payload["table_kind_a"] = table_a.table_kind
        if table_b.table_kind is not None:
            payload["table_kind_b"] = table_b.table_kind
        raw = llm_call(
            "table_pair_match",
            TABLE_PAIR_MATCH_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
        )
        parsed = JsonUtils.parse_object(raw) or {}
        kind_a = cls._parse_table_kind(parsed.get("table_kind_a"))
        kind_b = cls._parse_table_kind(parsed.get("table_kind_b"))
        indices_a = cls._parse_header_indices(parsed.get("header_row_indices_a"))
        indices_b = cls._parse_header_indices(parsed.get("header_row_indices_b"))
        if kind_a == _COM_TABLE_KIND and not indices_a:
            kind_a = _KV_TABLE_KIND
        if kind_b == _COM_TABLE_KIND and not indices_b:
            kind_b = _KV_TABLE_KIND
        if kind_a == _KV_TABLE_KIND:
            indices_a = []
        if kind_b == _KV_TABLE_KIND:
            indices_b = []
        return {
            "is_same_table": bool(parsed.get("is_same_table")),
            "similarity": JsonUtils.to_float(parsed.get("similarity"), default=0.0),
            "reason": parsed.get("reason"),
            "table_kind_a": kind_a,
            "table_kind_b": kind_b,
            "header_row_indices_a": indices_a,
            "header_row_indices_b": indices_b,
        }

    @classmethod
    def extract_gap_entries(
        cls,
        flat: list[DocumentItem],
        table: TableBlock,
        *,
        direction: str,
    ) -> list[TextLine]:
        bounds = cls._gap_bounds(flat, table)
        prev_table_si, next_table_si, table_si = bounds
        entries: list[TextLine] = []
        char_count = 0
        for entry in flat:
            if not is_text_line(entry):
                continue
            si = entry.loc.stream_index
            if direction == "before":
                lower = prev_table_si if prev_table_si is not None else -1
                if si <= lower or si >= table_si:
                    continue
            else:
                if si <= table_si:
                    continue
                if next_table_si is not None and si >= next_table_si:
                    continue
            text = cls._entry_text(entry)
            if not text:
                continue
            entries.append(entry)
            char_count += len(text)
            if char_count > _GAP_CHAR_CAP:
                break
        return entries

    @classmethod
    def extract_gap_text(
        cls,
        flat: list[DocumentItem],
        table: TableBlock,
        *,
        direction: str,
    ) -> str:
        parts = [cls._entry_text(entry) for entry in cls.extract_gap_entries(flat, table, direction=direction)]
        joined = "\n".join(part for part in parts if part)
        return joined[:_GAP_CHAR_CAP] if len(joined) > _GAP_CHAR_CAP else joined

    @classmethod
    def _gap_bounds(
        cls,
        flat: list[DocumentItem],
        table: TableBlock,
    ) -> tuple[int | None, int | None, int]:
        table_si = table.loc.stream_index
        prev_table_si: int | None = None
        next_table_si: int | None = None
        for entry in flat:
            block = cls._as_table(entry)
            if block is None:
                continue
            si = block.loc.stream_index
            if si < table_si:
                prev_table_si = si
            elif si > table_si and next_table_si is None:
                next_table_si = si
        return prev_table_si, next_table_si, table_si

    @classmethod
    def _diff_matched_tables(
        cls,
        table_a: TableBlock,
        table_b: TableBlock,
        row_out: dict[str, Any],
        *,
        a_rows: list[Row],
        b_rows: list[Row],
    ) -> list[dict[str, Any]]:
        a_map = {r.row_index: r for r in a_rows}
        b_map = {r.row_index: r for r in b_rows}
        diffs: list[dict[str, Any]] = []
        paired_a: set[int] = set()
        paired_b: set[int] = set()

        matched_pairs: list[tuple[Row, Row]] = []
        for pair in row_out.get("row_pairs", []):
            ai = int(pair["a_row_index"])
            bi = int(pair["b_row_index"])
            paired_a.add(ai)
            paired_b.add(bi)
            row_a = a_map.get(ai)
            row_b = b_map.get(bi)
            if row_a is None or row_b is None:
                continue
            matched_pairs.append((row_a, row_b))

        for row_a, row_b in matched_pairs:
            diffs.extend(cls._diff_row_cells(table_a, table_b, row_a, row_b))

        for ai, row_a in a_map.items():
            if ai in paired_a:
                continue
            diffs.append(
                {
                    "diff_type": "table_row_only_in_a",
                    "loc_a": cls._row_loc(table_a, row_a),
                    "loc_b": None,
                    "a_row_content": row_a.content,
                }
            )
        for bi, row_b in b_map.items():
            if bi in paired_b:
                continue
            diffs.append(
                {
                    "diff_type": "table_row_only_in_b",
                    "loc_a": None,
                    "loc_b": cls._row_loc(table_b, row_b),
                    "b_row_content": row_b.content,
                }
            )
        return diffs

    @classmethod
    def _make_table_cell_diff(
        cls,
        *,
        table_a: TableBlock,
        table_b: TableBlock,
        row_a: Row,
        row_b: Row,
        col: int,
        va: str,
        vb: str,
        category: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "diff_type": "table_cell",
            "loc_a": {**cls._row_loc(table_a, row_a, col=col)},
            "loc_b": {**cls._row_loc(table_b, row_b, col=col)},
            "a_value": va,
            "b_value": vb,
        }
        if category:
            entry["diff_category"] = category
        if reason:
            entry["diff_reason"] = reason
        return entry

    @classmethod
    def _diff_row_cells(
        cls,
        table_a: TableBlock,
        table_b: TableBlock,
        row_a: Row,
        row_b: Row,
    ) -> list[dict[str, Any]]:
        diffs: list[dict[str, Any]] = []
        for item in cls._collect_row_pair_cell_diffs(row_a, row_b):
            diffs.append(
                cls._make_table_cell_diff(
                    table_a=table_a,
                    table_b=table_b,
                    row_a=item["row_a"],
                    row_b=item["row_b"],
                    col=item["col"],
                    va=item["va"],
                    vb=item["vb"],
                    category=item["category"],
                    reason=item["reason"],
                )
            )
        return diffs

    @staticmethod
    def _row_bbox_from_cells(row: Row) -> list[float] | None:
        if not row.cell_bboxes:
            return None
        boxes = [
            b for b in row.cell_bboxes if isinstance(b, list) and len(b) >= 4
        ]
        if not boxes:
            return None
        return merge_span_bboxes([{"bbox": b} for b in boxes])

    @staticmethod
    def _row_loc(table: TableBlock, row: Row, *, col: int | None = None) -> dict[str, Any]:
        out = TableAligner._table_loc(table)
        out.pop("bbox", None)
        out["row"] = row.row_index
        if col is not None and row.cell_bboxes and 0 <= col < len(row.cell_bboxes):
            cell_bbox = row.cell_bboxes[col]
            if cell_bbox is not None:
                out["bbox"] = cell_bbox
                out["col"] = col
                return out
        if row.bbox is not None:
            out["bbox"] = row.bbox
        else:
            row_bbox = TableAligner._row_bbox_from_cells(row)
            if row_bbox is not None:
                out["bbox"] = row_bbox
        if col is not None:
            out["col"] = col
        return out

    @staticmethod
    def _table_loc(table: TableBlock) -> dict[str, Any]:
        loc = table.loc
        out: dict[str, Any] = {
            "stream_index": loc.stream_index,
            "section_path": loc.section_path,
            "table_index": loc.table_index,
        }
        if loc.element_index is not None:
            out["element_index"] = loc.element_index
        if loc.page is not None:
            out["page"] = loc.page
        if loc.bbox is not None:
            out["bbox"] = loc.bbox
        return out

    @staticmethod
    def _as_table(entry: DocumentItem) -> TableBlock | None:
        return entry if is_table_block(entry) else None

    @staticmethod
    def _entry_stream_index(entry: DocumentItem) -> int:
        return entry.loc.stream_index

    @staticmethod
    def _entry_text(entry: DocumentItem) -> str:
        if is_text_line(entry):
            return entry.text
        if is_table_block(entry):
            return " ".join(r.content for r in entry.rows)
        return ""

