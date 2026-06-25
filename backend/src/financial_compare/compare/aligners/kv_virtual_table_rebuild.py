"""虚拟表重建：A 表结构参考 + B 侧 span → ephemeral TableBlock。

仅当对侧文本为 PDF TextLine（含 ``loc.spans``）时执行；DOCX 文本侧不做虚拟表重建。
"""

from __future__ import annotations

import json
from typing import Any, Callable

from financial_compare.compare.aligners.kv_table_text_gate import TableTextGateResult
from financial_compare.compare.llm.prompts.table_rebuild import VIRTUAL_TABLE_REBUILD_SYSTEM
from financial_compare.compare.utils.span_text_utils import build_span_prompt_from_lines
from financial_compare.document.item import Row, TableBlock, TableKind, TableLoc, TextLine
from financial_compare.parser.extract.docx_table import DocxTableExtractor
from financial_compare.table.span_bbox import (
    all_row_geometries_from_html,
    merge_span_bboxes,
    script_aware_texts_match,
)
from financial_compare.table.span_layout import html_table_to_rows

_LlmFn = Callable[[str, str, str], str]
_VIRTUAL_TABLE_INDEX = -1
_PREVIEW_MAX_ROWS = 8


def build_rebuild_user_payload(
    table: TableBlock,
    span_prompt: str,
    *,
    preview_rows: int = _PREVIEW_MAX_ROWS,
) -> str:
    preview_html = DocxTableExtractor.rows_to_html(table.rows, max_rows=preview_rows)
    return json.dumps(
        {
            "table_a_preview_html": preview_html,
            "span_prompt": span_prompt,
        },
        ensure_ascii=False,
    )


def _assemble_virtual_table(
    interval: list[TextLine],
    flat_spans: list[dict[str, Any]],
    parsed_rows: list[tuple[list[str], str]],
) -> TableBlock | None:
    if not parsed_rows:
        return None

    first = interval[0]
    stream_index = first.loc.stream_index
    page = first.loc.page
    section_path = first.loc.section_path

    geometries = all_row_geometries_from_html(
        parsed_rows,
        flat_spans,
        texts_match=script_aware_texts_match,
    )
    rows: list[Row] = []
    for (_cells, row_type), (row_bbox, cell_bboxes) in zip(parsed_rows, geometries, strict=True):
        content = "|".join(_cells)
        if not content.strip():
            continue
        rows.append(
            Row(
                content=content,
                row_type=row_type,
                row_index=len(rows),
                bbox=row_bbox,
                cell_bboxes=cell_bboxes,
            )
        )

    if not rows:
        return None

    region_bbox = merge_span_bboxes(flat_spans) if flat_spans else None
    table_kind: TableKind = "ComTable" if any(row.row_type == "header" for row in rows) else "KVTable"
    return TableBlock(
        rows=rows,
        loc=TableLoc(
            stream_index=stream_index,
            table_index=_VIRTUAL_TABLE_INDEX,
            section_path=str(section_path) if section_path else None,
            page=int(page) if page is not None else None,
            bbox=region_bbox,
        ),
        table_kind=table_kind,
    )


def rebuild_virtual_table(
    table: TableBlock,
    text_lines: list[TextLine],
    gate: TableTextGateResult,
    *,
    llm_call: _LlmFn,
) -> TableBlock | None:
    interval = text_lines[gate.start_line_index : gate.end_line_index]
    if not interval:
        return None

    span_prompt, flat_spans = build_span_prompt_from_lines(interval, start=0, end=len(interval))
    if not span_prompt.strip():
        return None

    user_payload = build_rebuild_user_payload(table, span_prompt)
    raw = llm_call(
        "virtual_table_rebuild",
        VIRTUAL_TABLE_REBUILD_SYSTEM,
        user_payload,
    )
    parsed_rows = html_table_to_rows(raw, implicit_first_row_header=False)
    return _assemble_virtual_table(interval, flat_spans, parsed_rows)
