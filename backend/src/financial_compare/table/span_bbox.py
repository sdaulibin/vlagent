"""PDF 表格 span 消费与 bbox 合并（原生表 parse + 虚拟表 rebuild 共用）。"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from typing import Any

_SPAN_MATCH_WS_RE = re.compile(r"[\s\u00a0\f\v]+", re.UNICODE)
_PUNCT_NORM = str.maketrans(
    {
        "（": "(",
        "）": ")",
        "，": ",",
        "：": ":",
        "／": "/",
        "╱": "/",
    }
)
_DRAWING_PLACEHOLDER_RE = re.compile(r"^[\-—_=\s]+$")

TextsMatchFn = Callable[[str, str], bool]


def coord_pt_for_llm(v: float) -> int:
    """LLM 输入坐标四舍五入为整数 pt。"""
    return round(v)


def is_table_drawing_placeholder(text: str) -> bool:
    piece = text.strip()
    if not piece:
        return True
    return _DRAWING_PLACEHOLDER_RE.match(piece) is not None


def _norm_for_span_match(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).translate(_PUNCT_NORM)
    return _SPAN_MATCH_WS_RE.sub("", normalized)


def default_texts_match(accumulated: str, cell_text: str) -> bool:
    return _norm_for_span_match(accumulated) == _norm_for_span_match(cell_text)


def script_aware_texts_match(accumulated: str, cell_text: str) -> bool:
    """简繁归一 + 空白/标点归一。"""
    from financial_compare.compare.utils.zh_script import script_equal

    if script_equal(accumulated, cell_text):
        return True
    return default_texts_match(accumulated, cell_text)


def _is_norm_prefix(accumulated: str, target: str) -> bool:
    acc_n = _norm_for_span_match(accumulated)
    tgt_n = _norm_for_span_match(target)
    return tgt_n.startswith(acc_n) and acc_n != tgt_n


def _span_x_bounds(span: dict[str, Any]) -> tuple[float, float]:
    if "x" in span and "x1" in span:
        return float(span["x"]), float(span["x1"])
    bbox = span.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 4:
        return float(bbox[0]), float(bbox[2])
    return 0.0, 0.0


def _span_y_ref(span: dict[str, Any]) -> float:
    if "y" in span:
        return float(span["y"])
    bbox = span.get("bbox")
    if isinstance(bbox, list) and len(bbox) >= 2:
        return float(bbox[1])
    return 0.0


def _span_prompt_part(span: dict[str, Any]) -> str:
    x0, x1 = _span_x_bounds(span)
    text = str(span.get("text", ""))
    return f"{text!r}@({coord_pt_for_llm(x0)},{coord_pt_for_llm(x1)})"


def _is_mappable_table_span(span: dict[str, Any]) -> bool:
    """进入 flat 流、参与 HTML→cell bbox 回写的 span（有 bbox 的非 drawing 文本）。"""
    if not isinstance(span, dict):
        return False
    text = str(span.get("text", ""))
    if is_table_drawing_placeholder(text):
        return False
    bbox = span.get("bbox")
    return isinstance(bbox, list) and len(bbox) >= 4


def build_table_span_matrix(
    llm_rows: list[list[dict[str, Any]]],
    *,
    char_cap: int | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """一次构建坐标 prompt 与 flat span 流（阅读序：y 上→下，行内 x 左→右）。

    prompt 含 drawing 占位；flat 仅含可回写 bbox 的文本 span，与 HTML cell 顺序消费一致。
    """
    flat: list[dict[str, Any]] = []
    out_lines: list[str] = []
    char_count = 0

    for row in llm_rows:
        if not row:
            continue
        if char_cap is not None and char_count >= char_cap:
            break

        y_ref = _span_y_ref(row[0])
        parts: list[str] = []
        for span in row:
            if char_cap is not None and char_count >= char_cap:
                break
            parts.append(_span_prompt_part(span))
            if _is_mappable_table_span(span):
                flat.append(dict(span))
                char_count += len(str(span.get("text", "")))

        if parts:
            out_lines.append(f"[y≈{coord_pt_for_llm(y_ref)}] " + " | ".join(parts))

    return "\n".join(out_lines), flat


def merge_span_bboxes(spans: list[dict[str, Any]]) -> list[float] | None:
    boxes = [s["bbox"] for s in spans if isinstance(s.get("bbox"), list) and len(s["bbox"]) >= 4]
    if not boxes:
        return None
    return [
        min(float(b[0]) for b in boxes),
        min(float(b[1]) for b in boxes),
        max(float(b[2]) for b in boxes),
        max(float(b[3]) for b in boxes),
    ]


def find_cell_span_indices(
    cell_text: str,
    flat_spans: list[dict[str, Any]],
    row_start: int,
    used: set[int],
    *,
    texts_match: TextsMatchFn | None = None,
) -> list[int]:
    """阅读序子序列检索：跳过与当前 cell 无关的 span（如多行表头列交错）。"""
    match = texts_match or default_texts_match
    target = cell_text.strip()
    if not target:
        return []

    target_n = _norm_for_span_match(target)

    for begin in range(row_start, len(flat_spans)):
        if begin in used:
            continue
        acc = ""
        picked: list[int] = []
        for i in range(begin, len(flat_spans)):
            if i in used:
                continue
            piece = str(flat_spans[i].get("text", ""))
            if not piece:
                continue
            trial = acc + piece
            if match(trial, target):
                return picked + [i]
            if _is_norm_prefix(trial, target):
                acc = trial
                picked.append(i)
        # 换起点再试
    return []


def consume_spans_for_cell(
    cell_text: str,
    flat_spans: list[dict[str, Any]],
    start: int,
    *,
    texts_match: TextsMatchFn | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """按 cell 文本在阅读序 flat 中检索 span 子序列。"""
    indices = find_cell_span_indices(
        cell_text,
        flat_spans,
        start,
        set(),
        texts_match=texts_match,
    )
    if not indices:
        return [], start
    return [flat_spans[i] for i in indices], indices[-1] + 1


def _first_unused_index(
    flat_spans: list[dict[str, Any]],
    used: set[int],
    *,
    hint: int = 0,
) -> int:
    """flat 中第一个尚未分配给 cell 的下标（阅读序回写游标）。"""
    for i in range(max(0, hint), len(flat_spans)):
        if i not in used:
            return i
    return len(flat_spans)


def row_geometry_from_cells(
    cells: list[str],
    flat_spans: list[dict[str, Any]],
    start: int = 0,
    *,
    used_indices: set[int] | None = None,
    texts_match: TextsMatchFn | None = None,
) -> tuple[list[float] | None, list[list[float] | None], int]:
    """返回 (row_bbox, cell_bboxes, next_span_index)。"""
    used = used_indices if used_indices is not None else set()
    row_start = _first_unused_index(flat_spans, used, hint=start)
    cell_bboxes: list[list[float] | None] = []
    all_used: list[dict[str, Any]] = []
    for cell in cells:
        target = cell.strip()
        if not target:
            cell_bboxes.append(None)
            continue
        indices = find_cell_span_indices(
            cell,
            flat_spans,
            row_start,
            used,
            texts_match=texts_match,
        )
        if indices:
            for i in indices:
                used.add(i)
            spans = [flat_spans[i] for i in indices]
            all_used.extend(spans)
            cell_bboxes.append(merge_span_bboxes(spans))
        else:
            cell_bboxes.append(None)
    next_idx = _first_unused_index(flat_spans, used, hint=start)
    row_bbox = merge_span_bboxes(all_used) if all_used else None
    return row_bbox, cell_bboxes, next_idx


def all_row_geometries_from_html(
    parsed_rows: list[tuple[list[str], str]],
    flat_spans: list[dict[str, Any]],
    *,
    texts_match: TextsMatchFn | None = None,
) -> list[tuple[list[float] | None, list[list[float] | None]]]:
    """HTML 逻辑行 → 每行 (row_bbox, cell_bboxes)；跨行共享 used，游标取首个未用 span。"""
    out: list[tuple[list[float] | None, list[list[float] | None]]] = []
    used: set[int] = set()
    cursor = 0
    for cells, _row_type in parsed_rows:
        row_bbox, cell_bboxes, cursor = row_geometry_from_cells(
            cells,
            flat_spans,
            cursor,
            used_indices=used,
            texts_match=texts_match,
        )
        out.append((row_bbox, cell_bboxes))
    return out
