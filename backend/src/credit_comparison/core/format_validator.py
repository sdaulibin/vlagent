from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from src.credit_comparison.core.enums import ExceptionType
from src.credit_comparison.core.regex_utils import extract_company_detail_section

_DETAIL_MARKER_CANONICAL = "主要是"
_DETAIL_MARKERS = ("主要是", "主要为", "主要由", "主要原因是")
_DETAIL_COMPANY_HINT_PATTERN = re.compile(
    r"(公司|银行|集团)[\s\S]{0,40}(增加|减少|增|减)\s*(?:了|约|共|合计|累计|达|为|至|计)?\s*[0-9]"
)

_CN_LEFT_PAREN = "（"
_CN_RIGHT_PAREN = "）"
_EN_LEFT_PAREN = "("
_EN_RIGHT_PAREN = ")"
_CN_LEFT_QUOTE = "“"
_CN_RIGHT_QUOTE = "”"
_EN_QUOTE = '"'

_CN_COMMA = "，"
_CN_PERIOD = "。"

_MAIN_ALLOWED_PUNCTUATION = {_CN_LEFT_PAREN, _CN_RIGHT_PAREN, _CN_LEFT_QUOTE, _CN_RIGHT_QUOTE, _CN_COMMA, _CN_PERIOD}
_DETAIL_ALLOWED_PUNCTUATION = {_CN_COMMA, _CN_PERIOD}
_SIGNED_TOKENS = {"+", "-", "－", "−", "—", "–"}

_AMOUNT_UNIT_PATTERN = re.compile(r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(亿美元|万美元|美元|亿元|亿|万元|万|元)")
_MAIN_SENTENCE_PATTERN = re.compile(r"本期\s*(增加|减少)\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(亿美元|万美元|美元|亿元|亿|万元|万|元)")
_INDEX_PAREN_PATTERN = re.compile(r"^\s*[（(]\s*\d+\s*[）)]")
_ALNUM_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]{2,}")


def build_parse_stage_format_exceptions(
    context: str,
    *,
    amount_unit: str = "",
    company_records: Iterable[dict] | None = None,
) -> list[tuple[int, str, str]]:
    normalized_context = str(context or "")
    has_company_detail = bool(_DETAIL_COMPANY_HINT_PATTERN.search(normalized_context)) or bool(list(company_records or []))
    exceptions: list[tuple[int, str, str]] = []
    exceptions.extend(_validate_main_sentence(normalized_context, has_company_detail=has_company_detail))
    exceptions.extend(_validate_detail_section(normalized_context, has_company_detail=has_company_detail))
    exceptions.extend(_validate_company_records(company_records or []))
    exceptions.extend(_validate_unit_conflicts(normalized_context, amount_unit, company_records or []))
    return _unique_exceptions(exceptions)


def _unique_exceptions(items: list[tuple[int, str, str]]) -> list[tuple[int, str, str]]:
    seen: set[tuple[int, str, str]] = set()
    results: list[tuple[int, str, str]] = []
    for item in items:
        key = (int(item[0]), str(item[1]), str(item[2]))
        if key in seen:
            continue
        seen.add(key)
        results.append((key[0], key[1], key[2]))
    return results


def _is_numeric_separator(text: str, index: int) -> bool:
    if index <= 0 or index >= len(text) - 1:
        return False
    return text[index] in {".", ","} and text[index - 1].isdigit() and text[index + 1].isdigit()


def _iter_punctuation_chars(text: str) -> Iterable[tuple[int, str]]:
    normalized = str(text or "")
    for index, char in enumerate(normalized):
        if char.isspace():
            continue
        if _is_numeric_separator(normalized, index):
            continue
        if unicodedata.category(char).startswith("P") or char in _SIGNED_TOKENS:
            yield index, char


def _find_detail_marker(text: str, *, has_company_detail: bool) -> tuple[str, int]:
    normalized = str(text or "")
    if not has_company_detail:
        return "", -1
    best_marker = ""
    best_index = -1
    for marker in _DETAIL_MARKERS:
        index = normalized.find(marker)
        if index < 0:
            continue
        if best_index < 0 or index < best_index:
            best_index = index
            best_marker = marker
    return best_marker, best_index


def _extract_detail_section(text: str, *, has_company_detail: bool) -> tuple[str, str]:
    marker, index = _find_detail_marker(text, has_company_detail=has_company_detail)
    if not marker or index < 0:
        return "", ""
    section = str(text[index + len(marker) :])
    section = section.lstrip("：:、，,.。；; ").strip()
    return marker, section


def _validate_main_sentence(context: str, *, has_company_detail: bool) -> list[tuple[int, str, str]]:
    main_context = str(context or "")
    marker, marker_index = _find_detail_marker(main_context, has_company_detail=has_company_detail)
    if marker and marker_index >= 0:
        main_context = main_context[:marker_index]

    results: list[tuple[int, str, str]] = []
    full_context = str(context or "")
    amount_search_text = full_context[:marker_index] if marker_index >= 0 else full_context
    amount_match = _AMOUNT_UNIT_PATTERN.search(amount_search_text)
    if amount_match:
        comma_index = full_context.find(_CN_COMMA, int(amount_match.end()))
        if comma_index < 0:
            comma_index = full_context.find(",", int(amount_match.end()))
        if comma_index >= 0 and comma_index + 1 < len(full_context):
            tail = full_context[comma_index + 1 :].lstrip("：:、，,.。；; ").lstrip()
            if tail:
                segment_end = len(tail)
                for delimiter in (_CN_COMMA, ",", _CN_PERIOD, "。", "；", ";", "：", ":", "\n"):
                    pos = tail.find(delimiter)
                    if pos >= 0:
                        segment_end = min(segment_end, pos)
                segment = tail[:segment_end].strip()
                if segment and not segment.startswith(_DETAIL_MARKER_CANONICAL):
                    match = re.match(r"^([^\s，,。；;:：]{1,12}[是原因为由])", segment)
                    value = str(match.group(1) if match else segment[:12]).strip()
                    if value:
                        results.append((int(ExceptionType.FORMAT_ERROR), "company_marker", value))
    quote_ranges: list[tuple[int, int]] = []
    scan_index = 0
    while scan_index < len(main_context):
        start = main_context.find(_CN_LEFT_QUOTE, scan_index)
        if start < 0:
            break
        end = main_context.find(_CN_RIGHT_QUOTE, start + 1)
        if end < 0:
            break
        quote_ranges.append((start, end))
        scan_index = end + 1
    scan_index = 0
    while scan_index < len(main_context):
        start = main_context.find(_EN_QUOTE, scan_index)
        if start < 0:
            break
        end = main_context.find(_EN_QUOTE, start + 1)
        if end < 0:
            break
        quote_ranges.append((start, end))
        scan_index = end + 1

    def _is_in_quote(index: int) -> bool:
        for left, right in quote_ranges:
            if left <= index <= right:
                return True
        return False

    last_non_space_index = -1
    for index in range(len(main_context) - 1, -1, -1):
        if not main_context[index].isspace():
            last_non_space_index = index
            break

    if _INDEX_PAREN_PATTERN.search(main_context):
        if _EN_LEFT_PAREN in main_context or _EN_RIGHT_PAREN in main_context:
            results.append((int(ExceptionType.PUNCTUATION_ERROR), "main_sentence", _EN_LEFT_PAREN))

    if _EN_QUOTE in main_context:
        results.append((int(ExceptionType.PUNCTUATION_ERROR), "main_sentence", _EN_QUOTE))

    has_cn_left_quote = _CN_LEFT_QUOTE in main_context
    has_cn_right_quote = _CN_RIGHT_QUOTE in main_context
    if has_cn_left_quote != has_cn_right_quote:
        results.append((int(ExceptionType.FORMAT_ERROR), "main_sentence", _CN_LEFT_QUOTE if has_cn_left_quote else _CN_RIGHT_QUOTE))
    if not has_cn_left_quote and not has_cn_right_quote:
        token_match = _ALNUM_TOKEN_PATTERN.search(main_context)
        token_text = token_match.group(0) if token_match else "本期"
        results.append((int(ExceptionType.FORMAT_ERROR), "main_sentence", token_text))

    if not _MAIN_SENTENCE_PATTERN.search(main_context):
        extracted_tokens: list[str] = []
        amount_match = _AMOUNT_UNIT_PATTERN.search(main_context)
        if amount_match:
            prefix = main_context[: int(amount_match.start())]
        else:
            normalized = re.sub(r"^\s*[（(]\s*\d+\s*[）)]\s*", "", main_context)
            digit_match = re.search(r"[0-9]", normalized)
            prefix = normalized[: digit_match.start()] if digit_match else normalized
        quote_end = max(prefix.rfind(_CN_RIGHT_QUOTE), prefix.rfind(_EN_QUOTE))
        search_start = quote_end + 1 if quote_end >= 0 else 0
        period_index = prefix.find("本", search_start)
        period_token = ""
        if period_index >= 0:
            period_token = prefix[period_index : period_index + 2].strip()
        if period_token and period_token != "本期":
            extracted_tokens.append(period_token)

        direction_start = period_index + 2 if period_index >= 0 else search_start
        inc_pos = prefix.rfind("增加", direction_start)
        dec_pos = prefix.rfind("减少", direction_start)
        direction_pos = max(inc_pos, dec_pos)
        if direction_pos >= 0:
            if period_index >= 0:
                leading_between = prefix[direction_start:direction_pos].strip()
                if leading_between:
                    extracted_tokens.append(leading_between)
            trailing_between = prefix[direction_pos + 2 :].strip()
            if trailing_between:
                extracted_tokens.append(trailing_between)
        elif period_index >= 0:
            between_segment = prefix[direction_start:].strip()
            if between_segment:
                modifier_part = between_segment[:-1].strip()
                if modifier_part:
                    extracted_tokens.append(modifier_part)
                extracted_tokens.append(between_segment[-1])
        else:
            stripped_prefix = prefix.rstrip()
            bad_token = ""
            for char in reversed(stripped_prefix):
                if char.isspace():
                    continue
                bad_token = char
                break
            if bad_token:
                extracted_tokens.append(bad_token)

        for token in extracted_tokens:
            if token:
                results.append((int(ExceptionType.FORMAT_ERROR), "main_sentence", token))

        if not extracted_tokens:
            fallback = main_context.strip() or "本期"
            results.append((int(ExceptionType.FORMAT_ERROR), "main_sentence", fallback))

    for index, char in _iter_punctuation_chars(main_context):
        if char == _CN_PERIOD:
            if last_non_space_index >= 0 and index != last_non_space_index and not _is_in_quote(index):
                results.append((int(ExceptionType.PUNCTUATION_ERROR), "main_sentence", char))
            continue
        if char in _MAIN_ALLOWED_PUNCTUATION:
            continue
        if _is_in_quote(index):
            continue
        results.append((int(ExceptionType.PUNCTUATION_ERROR), "main_sentence", char))

    return results


def _validate_detail_section(context: str, *, has_company_detail: bool) -> list[tuple[int, str, str]]:
    marker, detail_section = _extract_detail_section(context, has_company_detail=has_company_detail)
    missing_marker = False
    if not marker:
        if not has_company_detail:
            return []
        detail_section = extract_company_detail_section(str(context or ""))
        if not detail_section:
            return []
        missing_marker = True

    results: list[tuple[int, str, str]] = []
    if missing_marker or marker != _DETAIL_MARKER_CANONICAL:
        marker_value = "缺少主要是"
        if not missing_marker and marker and marker.endswith(("是", "原", "因", "为", "由")):
            marker_value = marker
        if missing_marker and detail_section:
            match = re.match(r"^\s*([^\s，,。；;:：]{1,12}[是原因为由])", str(detail_section))
            if match:
                candidate = str(match.group(1) or "").strip()
                if candidate and candidate != _DETAIL_MARKER_CANONICAL:
                    marker_value = candidate
            if marker_value == "缺少主要是" and context:
                detail_start = str(context).find(str(detail_section))
                if detail_start > 0:
                    prefix = str(context)[:detail_start].rstrip("：:、，,.。；; ").rstrip()
                    match = re.search(r"([^\s，,。；;:：]{1,12}[是原因为由])\s*$", prefix)
                    if match:
                        candidate = str(match.group(1) or "").strip()
                        if candidate and candidate != _DETAIL_MARKER_CANONICAL:
                            marker_value = candidate
        results.append((int(ExceptionType.FORMAT_ERROR), "company_marker", marker_value))

    if not detail_section:
        return results

    segments = [str(segment or "").strip() for segment in detail_section.split(_CN_COMMA)]
    for segment in segments[1:]:
        normalized = str(segment or "").lstrip("：:、，,.。；; ").lstrip()
        if not normalized:
            continue
        if normalized.startswith("主要是"):
            results.append((int(ExceptionType.FORMAT_ERROR), "company_marker", "主要是"))
            continue
        if normalized.startswith("主要") and len(normalized) >= 3:
            results.append((int(ExceptionType.FORMAT_ERROR), "company_marker", normalized[:3]))
            continue
        if normalized.startswith(("主", "原", "因")) and len(normalized) >= 2:
            results.append((int(ExceptionType.FORMAT_ERROR), "company_marker", normalized[:2]))

    last_char = next((char for char in reversed(detail_section) if not char.isspace()), "")
    if last_char != _CN_PERIOD:
        if last_char and unicodedata.category(last_char).startswith("P"):
            results.append((int(ExceptionType.PUNCTUATION_ERROR), "company_detail", last_char))
        amount_tokens = list(_AMOUNT_UNIT_PATTERN.finditer(detail_section))
        if amount_tokens:
            match = amount_tokens[-1]
            amount_text = f"{str(match.group(1) or '').strip()}{str(match.group(2) or '').strip()}".strip()
            if amount_text:
                results.append((int(ExceptionType.FORMAT_ERROR), "company_detail_tail", amount_text))
            else:
                results.append((int(ExceptionType.FORMAT_ERROR), "company_detail_tail", last_char or "。"))
        else:
            results.append((int(ExceptionType.FORMAT_ERROR), "company_detail_tail", last_char or "。"))

    if not missing_marker and marker == _DETAIL_MARKER_CANONICAL:
        prefix = str(context or "")
        marker_index = prefix.find(marker)
        if marker_index > 0:
            probe = prefix[:marker_index].rstrip()
            prev_char = probe[-1:] if probe else ""
            if prev_char and prev_char != _CN_COMMA:
                if prev_char and unicodedata.category(prev_char).startswith("P"):
                    results.append((int(ExceptionType.PUNCTUATION_ERROR), "main_sentence", prev_char))

    depth = 0
    last_detail_index = -1
    for index in range(len(detail_section) - 1, -1, -1):
        if not detail_section[index].isspace():
            last_detail_index = index
            break
    for index, char in enumerate(detail_section):
        if char == _CN_LEFT_PAREN:
            depth += 1
            continue
        if char == _CN_RIGHT_PAREN:
            depth = max(0, depth - 1)
            continue
        if depth > 0:
            continue
        if char.isspace():
            continue
        if _is_numeric_separator(detail_section, index):
            continue
        if unicodedata.category(char).startswith("P") or char in _SIGNED_TOKENS:
            if char == _CN_COMMA:
                continue
            if char == _CN_PERIOD and index == last_detail_index:
                continue
            results.append((int(ExceptionType.PUNCTUATION_ERROR), "company_detail", char))

    return results


def _validate_company_records(company_records: Iterable[dict]) -> list[tuple[int, str, str]]:
    results: list[tuple[int, str, str]] = []
    for record in company_records:
        company_name = str(record.get("company") or "").strip()
        format_tag = str(record.get("_format_tag") or "").strip()
        if company_name and format_tag:
            results.append((int(ExceptionType.COMPANY_FORMAT_ERROR), "company_detail", company_name))
    return results


def _unit_group(unit: str) -> str:
    normalized = str(unit or "").strip()
    if not normalized:
        return ""
    if "美元" in normalized:
        return "usd"
    if any(token in normalized for token in ("元", "万", "亿")):
        return "rmb"
    return ""


def _validate_unit_conflicts(context: str, amount_unit: str, company_records: Iterable[dict]) -> list[tuple[int, str, str]]:
    main_group = _unit_group(amount_unit)
    if not main_group:
        main_match = _MAIN_SENTENCE_PATTERN.search(str(context or ""))
        if main_match:
            main_group = _unit_group(str(main_match.group(3) or ""))

    company_groups = {
        _unit_group(str(record.get("profit_loss_unit") or "").strip())
        for record in company_records
        if str(record.get("profit_loss_unit") or "").strip()
    }
    company_groups.discard("")
    if not main_group or not company_groups:
        return []
    if len(company_groups) == 1 and next(iter(company_groups)) == main_group:
        return []
    if main_group in company_groups and len(company_groups) == 1:
        return []
    conflict_units: set[str] = set()
    for record in company_records:
        unit = str(record.get("profit_loss_unit") or "").strip()
        if not unit:
            continue
        if _unit_group(unit) and _unit_group(unit) != main_group:
            conflict_units.add(unit)
    if not conflict_units:
        return []
    return [(int(ExceptionType.FORMAT_ERROR), "profit_loss_unit", unit) for unit in sorted(conflict_units)]
