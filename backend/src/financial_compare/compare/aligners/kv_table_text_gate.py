"""文表门控：LLM 判定 PDF 文本侧表首表尾区间。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from financial_compare.compare.llm.prompts.table_gate import (
    TABLE_TEXT_GATE_HEADER_SYSTEM,
    TABLE_TEXT_GATE_TAIL_SYSTEM,
)
from financial_compare.compare.utils.json_utils import JsonUtils
from financial_compare.compare.utils.span_text_utils import tail_candidate_range
from financial_compare.compare.utils.text_compare import texts_equal
from financial_compare.document.item import TableBlock, TextLine

_GATE_HEAD_TAIL_N = 3
_GATE_HEAD_MIN_MATCH = 2
_TAIL_LINE_BEFORE = 2
_TAIL_LINE_AFTER = 4
_GATE_HEAD_CANDIDATE_MAX = 8
_LlmFn = Callable[[str, str, str], str]


@dataclass
class TableTextGateResult:
    header_match: bool
    tail_match: bool
    start_line_index: int
    end_line_index: int
    header_peel_text: str = ""
    tail_peel_text: str = ""
    same_unit: bool = False
    reason: str = ""

    @property
    def ok(self) -> bool:
        return (
            self.header_match
            and self.tail_match
            and self.end_line_index > self.start_line_index
        )


def _table_row_contents(table: TableBlock) -> list[str]:
    return [row.content for row in table.rows if row.content.strip()]


def _table_char_budget(rows: list[str]) -> int:
    if not rows:
        return 0
    return len("\n".join(rows))


def _min_head_match(head_rows: list[str]) -> int:
    n = len(head_rows)
    if n <= 1:
        return 1
    return min(_GATE_HEAD_MIN_MATCH, n)


def _head_row_matches_line(head_row: str, line_text: str) -> bool:
    stripped = head_row.strip()
    if stripped in ("|", ""):
        return not line_text.strip() or line_text.strip() == "|"
    return texts_equal(head_row, line_text)


def _score_head_anchor(
    head_rows: list[str],
    text_lines: list[TextLine],
    start_idx: int,
) -> int:
    count = 0
    line_idx = start_idx
    for head_row in head_rows:
        while line_idx < len(text_lines) and not text_lines[line_idx].text.strip():
            line_idx += 1
        if line_idx >= len(text_lines):
            break
        if _head_row_matches_line(head_row, text_lines[line_idx].text):
            count += 1
            line_idx += 1
        else:
            break
    return count


def _lines_payload(lines: list[TextLine], lo: int, hi: int) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for i in range(lo, min(hi, len(lines))):
        text = lines[i].text
        if text.strip():
            out.append({"line_index": i, "text": text})
    return out


def _collect_head_candidates(
    text_lines: list[TextLine],
    slide_start: int,
) -> tuple[list[dict[str, object]], int]:
    candidates: list[dict[str, object]] = []
    probe = slide_start
    total = len(text_lines)
    while len(candidates) < _GATE_HEAD_CANDIDATE_MAX and probe < total:
        text = text_lines[probe].text
        if text.strip():
            candidates.append({"line_index": probe, "text": text})
        probe += 1
    return candidates, probe


def _find_head_anchor_shortcut(
    head_rows: list[str],
    candidates: list[dict[str, object]],
    text_lines: list[TextLine],
    min_match: int,
) -> int | None:
    best_idx: int | None = None
    best_score = 0
    for candidate in candidates:
        idx = candidate.get("line_index")
        if not isinstance(idx, int):
            continue
        score = _score_head_anchor(head_rows, text_lines, idx)
        if score < min_match:
            continue
        if score > best_score or (score == best_score and (best_idx is None or idx < best_idx)):
            best_score = score
            best_idx = idx
    return best_idx


def _match_gate_tail_shortcut(
    *,
    tail_rows: list[str],
    slide_start: int,
    text_lines: list[TextLine],
    tail_lo: int,
    tail_hi: int,
) -> TableTextGateResult | None:
    if not tail_rows or tail_lo >= tail_hi:
        return None
    tail_row = tail_rows[-1]
    matches: list[int] = []
    for i in range(tail_lo, min(tail_hi, len(text_lines))):
        if texts_equal(tail_row, text_lines[i].text):
            matches.append(i)
    if len(matches) != 1:
        return None
    end = matches[0] + 1
    if end <= slide_start:
        return None
    return TableTextGateResult(
        header_match=True,
        tail_match=True,
        start_line_index=slide_start,
        end_line_index=end,
        same_unit=(end - slide_start == 1),
        reason="tail_equal",
    )


def _parse_head_gate_response(
    parsed: dict[str, object],
    *,
    candidates: list[dict[str, object]],
    min_match: int,
) -> int | None:
    slide = parsed.get("slide_start")
    if slide is None:
        return None
    if not isinstance(slide, int):
        return None
    valid = {int(c["line_index"]) for c in candidates if isinstance(c.get("line_index"), int)}
    if slide not in valid:
        return None
    count = parsed.get("head_match_count")
    if isinstance(count, int) and count < min_match:
        return None
    return slide


def _llm_match_gate_header(
    *,
    head_rows: list[str],
    candidates: list[dict[str, object]],
    text_lines: list[TextLine],
    llm_call: _LlmFn,
) -> int | None:
    if not candidates:
        return None
    min_match = _min_head_match(head_rows)
    slide = _find_head_anchor_shortcut(head_rows, candidates, text_lines, min_match)
    if slide is not None:
        return slide
    user = json.dumps(
        {
            "head_rows_a": head_rows,
            "head_candidates_b": candidates,
            "min_head_match": min_match,
        },
        ensure_ascii=False,
    )
    raw = llm_call("table_text_gate_header", TABLE_TEXT_GATE_HEADER_SYSTEM, user)
    parsed = JsonUtils.parse_object(raw) or {}
    slide = _parse_head_gate_response(parsed, candidates=candidates, min_match=min_match)
    if slide is None:
        return None
    if _score_head_anchor(head_rows, text_lines, slide) >= min_match:
        return slide
    count = parsed.get("head_match_count")
    if isinstance(count, int) and count >= min_match:
        return slide
    return None


def _llm_match_gate_tail(
    *,
    tail_rows: list[str],
    char_budget: int,
    slide_start: int,
    text_lines: list[TextLine],
    llm_call: _LlmFn,
    line_before: int = _TAIL_LINE_BEFORE,
    line_after: int = _TAIL_LINE_AFTER,
) -> TableTextGateResult | None:
    tail_lo, tail_hi = tail_candidate_range(
        slide_start,
        text_lines,
        a_char_budget=char_budget,
        before=line_before,
        after=line_after,
    )
    shortcut = _match_gate_tail_shortcut(
        tail_rows=tail_rows,
        slide_start=slide_start,
        text_lines=text_lines,
        tail_lo=tail_lo,
        tail_hi=tail_hi,
    )
    if shortcut is not None:
        return shortcut
    if tail_lo >= tail_hi:
        return None
    user = json.dumps(
        {
            "tail_rows_a": tail_rows,
            "slide_start": slide_start,
            "tail_candidate_b": {
                "line_indices": list(range(tail_lo, tail_hi)),
                "lines": _lines_payload(text_lines, tail_lo, tail_hi),
            },
        },
        ensure_ascii=False,
    )
    raw = llm_call("table_text_gate_tail", TABLE_TEXT_GATE_TAIL_SYSTEM, user)
    parsed = JsonUtils.parse_object(raw) or {}
    if not bool(parsed.get("tail_match")):
        return None
    abs_start = int(parsed.get("start_line_index", slide_start))
    abs_end = int(parsed.get("end_line_index", abs_start + 1))
    if abs_start < slide_start or abs_end <= abs_start or abs_end > len(text_lines):
        return None
    peel_h = str(parsed.get("header_peel_text") or "")
    peel_t = str(parsed.get("tail_peel_text") or "")
    return TableTextGateResult(
        header_match=True,
        tail_match=True,
        start_line_index=abs_start,
        end_line_index=abs_end,
        header_peel_text=peel_h,
        tail_peel_text=peel_t,
        same_unit=(abs_end - abs_start == 1),
        reason=str(parsed.get("reason") or ""),
    )


def _gate_table_text_split(
    *,
    head_rows: list[str],
    tail_rows: list[str],
    all_rows: list[str],
    text_lines: list[TextLine],
    llm_call: _LlmFn,
    line_before: int = _TAIL_LINE_BEFORE,
    line_after: int = _TAIL_LINE_AFTER,
) -> TableTextGateResult | None:
    if not head_rows or not tail_rows or not text_lines:
        return None

    slide = 0
    while slide < len(text_lines):
        candidates, next_slide = _collect_head_candidates(text_lines, slide)
        if not candidates:
            break
        matched = _llm_match_gate_header(
            head_rows=head_rows,
            candidates=candidates,
            text_lines=text_lines,
            llm_call=llm_call,
        )
        if matched is not None:
            tail_result = _llm_match_gate_tail(
                tail_rows=tail_rows,
                char_budget=_table_char_budget(all_rows),
                slide_start=matched,
                text_lines=text_lines,
                llm_call=llm_call,
                line_before=line_before,
                line_after=line_after,
            )
            if tail_result is not None:
                return tail_result
        slide = next_slide
    return None


def gate_table_text(
    table: TableBlock,
    text_lines: list[TextLine],
    *,
    llm_call: _LlmFn,
    line_before: int = _TAIL_LINE_BEFORE,
    line_after: int = _TAIL_LINE_AFTER,
    section_scoped: bool = False,  # noqa: ARG001 — 保留 API，表尾开窗不再节内展平
) -> TableTextGateResult | None:
    rows = _table_row_contents(table)
    if not rows:
        return None

    n = min(_GATE_HEAD_TAIL_N, len(rows))
    return _gate_table_text_split(
        head_rows=rows[:n],
        tail_rows=rows[max(0, len(rows) - n) :],
        all_rows=rows,
        text_lines=text_lines,
        llm_call=llm_call,
        line_before=line_before,
        line_after=line_after,
    )
