"""PDF span 坐标 prompt 与 bbox 工具（文表路径）。

虚拟表重建仅用于 PDF TextLine（含 ``loc.spans``）；DOCX 文本侧不做表重建。
"""

from __future__ import annotations

from typing import Any

from financial_compare.document.item import TextLine
from financial_compare.table.span_bbox import build_table_span_matrix

_GAP_CHAR_CAP = 3000

__all__ = [
    "SpanCoordMissingError",
    "build_span_prompt_from_lines",
    "estimate_tail_line_index",
    "is_pdf_text_line",
    "line_spans",
    "tail_candidate_range",
]


class SpanCoordMissingError(ValueError):
    """PDF TextLine 缺少 loc.spans，无法组装虚拟表 span prompt。"""


def is_pdf_text_line(line: TextLine) -> bool:
    """PDF 文本行：有 page、无 DOCX element_index。"""
    if line.loc.element_index is not None:
        return False
    return line.loc.page is not None


def line_spans(line: TextLine) -> list[dict[str, Any]]:
    """从 TextLine loc 取 span 列表。"""
    loc = line.loc
    raw = loc.spans
    if isinstance(raw, list) and raw:
        out: list[dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", ""))
            if not text:
                continue
            bbox = item.get("bbox")
            if not (isinstance(bbox, list) and len(bbox) >= 4):
                continue
            bb = [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
            out.append(
                {
                    "text": text,
                    "bbox": bb,
                    "x": float(item.get("x", bb[0])),
                    "x1": float(item.get("x1", bb[2])),
                    "y": float(item.get("y", bb[1])),
                }
            )
        if out:
            return out

    if is_pdf_text_line(line):
        raise SpanCoordMissingError(
            f"PDF TextLine 缺少 loc.spans（page={line.loc.page!r}, "
            f"stream_index={line.loc.stream_index}）；"
            f"请用 parsed v6 重新导出，勿使用无 spans 的旧 parsed.json"
        )
    return []


def build_span_prompt_from_lines(
    lines: list[TextLine],
    *,
    start: int = 0,
    end: int | None = None,
    char_cap: int = _GAP_CHAR_CAP,
) -> tuple[str, list[dict[str, Any]]]:
    """TextLine 区间 → ``build_table_span_matrix`` prompt + flat。"""
    if end is None:
        end = len(lines)
    llm_rows: list[list[dict[str, Any]]] = []
    for li in range(start, min(end, len(lines))):
        line = lines[li]
        spans = line_spans(line)
        if not spans:
            continue
        llm_rows.append(
            [
                {
                    **sp,
                    "line_index": li,
                    "stream_index": line.loc.stream_index,
                    "page": line.loc.page,
                    "section_path": line.loc.section_path,
                }
                for sp in spans
            ]
        )
    return build_table_span_matrix(llm_rows, char_cap=char_cap)


def estimate_tail_line_index(
    lines: list[TextLine],
    slide_start: int,
    char_budget: int,
) -> int:
    """从表头行 slide_start 起累加 B 行字符，定位预估表尾行下标（仅用于开窗，不进入提示词）。"""
    total = len(lines)
    if total == 0 or slide_start >= total:
        return max(0, total - 1)
    if char_budget <= 0:
        return slide_start

    accumulated = 0
    est_tail = slide_start
    for i in range(slide_start, total):
        accumulated += len(lines[i].text)
        est_tail = i
        if accumulated >= char_budget:
            break
    return est_tail


def tail_candidate_range(
    slide_start: int,
    text_lines: list[TextLine],
    *,
    a_char_budget: int,
    before: int = 2,
    after: int = 2,
) -> tuple[int, int]:
    """按 A 表字符量从表头偏移定位预估表尾行，再取 [est_tail-before, est_tail+after] 开窗（半开）。"""
    total = len(text_lines)
    if total == 0:
        return 0, 0

    est_tail = estimate_tail_line_index(text_lines, slide_start, a_char_budget)
    lo = max(slide_start, est_tail - before)
    hi = min(total, est_tail + after + 1)
    if lo >= hi:
        hi = min(total, lo + 1)
    return lo, hi
