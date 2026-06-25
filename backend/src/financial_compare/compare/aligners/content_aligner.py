"""节内双游标对齐：六种几何 overlap_kind + 剩余提升 + B 双相位扫描。"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Callable

from financial_compare.compare.utils.text_compare import filter_text_diff_pairs, texts_equal

# span 规则化比较：NFKC + 去空白（用于子串校验与文本 unit 消费兜底）
_SPAN_CMP_WS_RE = re.compile(r"[\s\u00a0\f\v]+", re.UNICODE)

_NOISE_RE = re.compile(
    r"[（）()【】\[\]：:，,。.\-—_|｜、；;！!？?·•\s]+"
)
_SUBSTANTIVE_CHAR_RE = re.compile(r"[\w\u4e00-\u9fff]", re.UNICODE)
MIN_OVERLAP_SPAN_LEN = 4
# 超短 unit：实质字符数 ≤ 此值；不参与 LLM 匹配，终局记入 missing_*。
ULTRA_SHORT_MAX_SUBSTANTIVE_CHARS = 3
_WEAK_SPAN_EXACT = frozenset(
    {
        "包括",
        "及",
        "的",
        "了",
        "与",
        "和",
        "等",
        "为",
        "在",
        "是",
        "以",
        "对",
        "将",
        "由",
        "从",
        "到",
    }
)

OverlapKind = str  # none|a_in_b|b_in_a|tail_head|head_tail|head_head|tail_tail

_OVERLAP_KINDS = frozenset(
    {
        "a_in_b",
        "b_in_a",
        "tail_head",
        "head_tail",
        "head_head",
        "tail_tail",
    }
)

_LLM_DECISION = dict[str, Any]
_JudgeFn = Callable[[str, str, dict[str, Any]], _LLM_DECISION]


def consume_text(units: list[str], unit_idx: int, span: str) -> int:
    """文本 unit：按 span 切分，剩余首尾提升为新 unit。"""
    return _consume_span(units, unit_idx, span)


def align_content_units(
    *,
    a_units: list[str],
    b_units: list[str],
    llm_judge: _JudgeFn,
    view_budget: int = 2400,
    max_steps: int = 5000,
) -> dict[str, Any]:
    """对齐 unit 列表，返回 ``diff_items`` / ``missing_in_*``。

    跨形态文表不走本函数，见 ``TableTextCrossAligner``（仅 PDF 文本侧虚拟表重建；DOCX 文本侧不参与）。
    """
    a_remains = list(a_units)
    b_remains = list(b_units)
    diff_items: list[dict[str, Any]] = []

    if not a_units:
        return {
            "diff_items": diff_items,
            "missing_in_b": [],
            "missing_in_a": [
                {"b_index": idx, "text": text} for idx, text in enumerate(b_remains) if text.strip()
            ],
        }
    if not b_units:
        return {
            "diff_items": diff_items,
            "missing_in_b": [{"a_index": idx, "text": text} for idx, text in enumerate(a_remains) if text.strip()],
            "missing_in_a": [],
        }

    a_pos = 0
    b_probe = 0
    b_anchor = 0
    b_scan_phase = "forward"
    steps = 0
    a_segment_start = 0

    while steps < max_steps:
        steps += 1
        a_pos = _skip_empty(a_remains, a_pos)
        if a_pos >= len(a_remains):
            break

        a_view_peek = _gather(a_remains, a_pos, view_budget)
        if is_ultra_short_unit(a_view_peek):
            a_pos = _advance_past_unit(a_remains, a_pos)
            a_segment_start = a_pos
            continue

        b_count = len(b_remains)
        if not _b_probe_in_phase(b_probe, b_scan_phase, b_anchor, b_count):
            wrap = _try_begin_wrap_scan(b_remains, b_scan_phase, b_anchor)
            if wrap is not None:
                b_scan_phase, b_probe = wrap
                continue
            a_pos, a_segment_start, b_probe, b_scan_phase = _advance_unmatched_a(
                a_remains=a_remains,
                a_segment_start=a_segment_start,
                b_anchor=b_anchor,
            )
            continue

        b_probe = _skip_empty(b_remains, b_probe)
        a_view = _gather(a_remains, a_pos, view_budget)
        b_view = _gather(b_remains, b_probe, view_budget)
        if is_ultra_short_unit(b_view):
            b_probe = _advance_past_unit(b_remains, b_probe)
            continue
        if not has_substantive_content(a_view):
            a_pos = _advance_past_unit(a_remains, a_pos)
            a_segment_start = a_pos
            continue
        if not b_view.strip():
            b_probe = _advance_past_unit(b_remains, b_probe)
            continue

        trace = {
            "a_index": a_pos,
            "b_index": b_probe,
            "b_scan_phase": b_scan_phase,
            "step": steps,
        }
        if texts_equal(a_view, b_view):
            decision = validate_overlap_decision(
                {
                    "overlap_kind": "head_head",
                    "A_span": a_view,
                    "B_span": b_view,
                    "diff": [],
                    "confidence": 1.0,
                },
                a_view=a_view,
                b_view=b_view,
            )
        else:
            decision = validate_overlap_decision(
                llm_judge(a_view, b_view, trace),
                a_view=a_view,
                b_view=b_view,
            )
        overlap = _normalize_overlap_kind(decision.get("overlap_kind"))

        if overlap == "none":
            next_b = _advance_past_unit(b_remains, b_probe)
            if _b_probe_in_phase(next_b, b_scan_phase, b_anchor, b_count):
                b_probe = next_b
                continue
            wrap = _try_begin_wrap_scan(b_remains, b_scan_phase, b_anchor)
            if wrap is not None:
                b_scan_phase, b_probe = wrap
                continue
            a_pos, a_segment_start, b_probe, b_scan_phase = _advance_unmatched_a(
                a_remains=a_remains,
                a_segment_start=a_segment_start,
                b_anchor=b_anchor,
            )
            continue

        before_a, before_b = a_pos, b_probe
        a_pos = consume_text(a_remains, a_pos, str(decision.get("A_span") or ""))
        b_pos = consume_text(b_remains, b_probe, str(decision.get("B_span") or ""))
        if before_a == a_pos and before_b == b_pos:
            b_probe = _advance_past_unit(b_remains, b_probe)
            continue
        b_probe = b_pos
        b_anchor = b_probe
        b_scan_phase = "forward"
        if _unit_done(a_remains, a_pos):
            a_pos = _advance_past_unit(a_remains, a_pos)
        a_segment_start = a_pos

        diff = filter_text_diff_pairs(decision.get("diff") or [])
        if diff:
            diff_items.append(
                {
                    "a_index": trace["a_index"],
                    "b_index": trace["b_index"],
                    "a_window_text": a_view,
                    "b_window_text": b_view,
                    "overlap_kind": overlap,
                    "diff": diff,
                    "confidence": decision.get("confidence"),
                }
            )

        if _unit_done(a_remains, a_segment_start) and a_pos > a_segment_start:
            a_segment_start = a_pos

    missing_in_b = [
        {"a_index": idx, "text": text}
        for idx, text in enumerate(a_remains)
        if _counts_as_missing_unit(text)
    ]
    missing_in_a = [
        {"b_index": idx, "text": text}
        for idx, text in enumerate(b_remains)
        if _counts_as_missing_unit(text)
    ]
    return {
        "diff_items": diff_items,
        "missing_in_b": missing_in_b,
        "missing_in_a": missing_in_a,
    }


def substantive_char_count(text: str) -> int:
    normalized = unicodedata.normalize("NFKC", text.strip())
    return len(_SUBSTANTIVE_CHAR_RE.findall(normalized))


def has_substantive_content(text: str) -> bool:
    return substantive_char_count(text) >= 2


def is_ultra_short_unit(text: str) -> bool:
    """超短 unit 标准（A/B、promote 剩余、终局 missing 共用）。"""
    count = substantive_char_count(text)
    return 0 < count <= ULTRA_SHORT_MAX_SUBSTANTIVE_CHARS


def is_rejected_overlap_span(span: str) -> bool:
    piece = span.strip()
    if not piece:
        return True
    if not has_substantive_content(piece):
        return True
    if len(piece) < MIN_OVERLAP_SPAN_LEN:
        return True
    # NFKC 归一化并去掉标点/空白后，与弱词表精确匹配则拒绝
    if _NOISE_RE.sub("", unicodedata.normalize("NFKC", piece)) in _WEAK_SPAN_EXACT:
        return True
    return False


def _norm_for_span_match(text: str) -> str:
    return _SPAN_CMP_WS_RE.sub("", unicodedata.normalize("NFKC", text))


def _span_in_view(span: str, view: str) -> bool:
    piece = span.strip()
    window = view.strip()
    if not piece or not window:
        return False
    if piece in window:
        return True
    norm_piece = _norm_for_span_match(piece)
    norm_window = _norm_for_span_match(window)
    if not norm_piece or not norm_window:
        return False
    return norm_piece in norm_window


def validate_overlap_decision(
    decision: _LLM_DECISION,
    *,
    a_view: str = "",
    b_view: str = "",
) -> _LLM_DECISION:
    overlap = _normalize_overlap_kind(decision.get("overlap_kind"))
    if overlap == "none":
        return decision

    a_span = str(decision.get("A_span") or "").strip()
    b_span = str(decision.get("B_span") or "").strip()
    if not a_span or not b_span:
        return _none_decision()
    if is_rejected_overlap_span(a_span) or is_rejected_overlap_span(b_span):
        return _none_decision()

    if a_view and b_view:
        a_ok = _span_in_view(a_span, a_view)
        b_ok = _span_in_view(b_span, b_view)
        if not a_ok or not b_ok:
            if _norm_for_span_match(a_view) == _norm_for_span_match(b_view):
                a_span = a_view
                b_span = b_view
            else:
                return _none_decision()
        else:
            a_span = _pick_span_from_view(a_span, a_view)
            b_span = _pick_span_from_view(b_span, b_view)
        out = dict(decision)
        out["A_span"] = a_span
        out["B_span"] = b_span
        return out
    return decision


def _pick_span_from_view(span: str, view: str) -> str:
    """规则化一致时从 view 取原文子串，避免 LLM 在 span 里插入空格。"""
    piece = span.strip()
    window = view.strip()
    if piece in window:
        return piece
    if _norm_for_span_match(piece) == _norm_for_span_match(window):
        return window
    return piece


def _normalize_overlap_kind(value: Any) -> str:
    if value is None:
        return "none"
    kind = str(value).strip().lower()
    if kind in _OVERLAP_KINDS:
        return kind
    return "none"


def _none_decision() -> _LLM_DECISION:
    return {
        "overlap_kind": "none",
        "A_span": "",
        "B_span": "",
        "diff": [],
        "confidence": None,
    }


def _try_begin_wrap_scan(
    b_remains: list[str],
    b_scan_phase: str,
    b_anchor: int,
) -> tuple[str, int] | None:
    """forward 相位扫尽且 anchor>0 时，切到 wrap 并从 B 头部重扫。"""
    if b_scan_phase == "forward" and b_anchor > 0:
        return "wrap", _skip_empty(b_remains, 0)
    return None


def _advance_unmatched_a(
    *,
    a_remains: list[str],
    a_segment_start: int,
    b_anchor: int,
) -> tuple[int, int, int, str]:
    """B 侧无匹配时推进 A 并重置 B 扫描相位。"""
    a_pos = _advance_past_unit(a_remains, a_segment_start)
    return a_pos, a_pos, b_anchor, "forward"


def _unit_done(units: list[str], unit_idx: int) -> bool:
    if unit_idx >= len(units):
        return True
    return not has_substantive_content(units[unit_idx])


def _counts_as_missing_unit(text: str) -> bool:
    """终局 missing：含可匹配正文或超短 unit（匹配阶段已跳过）。"""
    return has_substantive_content(text) or is_ultra_short_unit(text)


def _skip_empty(units: list[str], unit_idx: int) -> int:
    while unit_idx < len(units) and not has_substantive_content(units[unit_idx]):
        unit_idx += 1
    return unit_idx


def _advance_past_unit(units: list[str], unit_idx: int) -> int:
    return _skip_empty(units, unit_idx + 1)


def _gather(units: list[str], unit_idx: int, budget: int) -> str:
    if unit_idx >= len(units):
        return ""
    return units[unit_idx][:budget]


def _b_probe_in_phase(probe: int, phase: str, anchor: int, unit_count: int) -> bool:
    if phase == "forward":
        return probe < unit_count
    return probe < anchor


def _promote_remainder(units: list[str], unit_idx: int, remainder: str) -> int:
    """消费后若仍有文本，提升为独立 unit 并返回其索引。"""
    units[unit_idx] = ""
    tail = remainder.strip()
    if not tail or not has_substantive_content(tail):
        return _skip_empty(units, unit_idx + 1)
    insert_at = unit_idx + 1
    units.insert(insert_at, tail)
    return insert_at


def _consume_span(units: list[str], unit_idx: int, span: str) -> int:
    """文本 unit：按 span 切分；剩余首尾提升；规则化全行相等时整行消费。"""
    if not span:
        return _skip_empty(units, unit_idx)
    unit_idx = _skip_empty(units, unit_idx)
    if unit_idx >= len(units):
        return unit_idx

    text = units[unit_idx]
    idx = text.find(span)
    if idx < 0:
        norm_span = _norm_for_span_match(span)
        norm_text = _norm_for_span_match(text)
        if norm_span and norm_span == norm_text:
            units[unit_idx] = ""
            return _skip_empty(units, unit_idx + 1)
        return unit_idx

    remainder = text[:idx] + text[idx + len(span) :]
    return _promote_remainder(units, unit_idx, remainder)
