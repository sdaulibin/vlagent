"""
信用金额对账 - 前端展示聚合服务（异步）。

等价于旧 ViewService，把 compare_link / exception / company 明细聚合为
前端对账工作台所需的结构（画线列表、异常分组、企业异常、锚点列表）。

高亮 token 构建逻辑（_build_exception_highlight_tokens 等）原样保留，
供前端在 Word 文本中框选高亮。
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession

from src.credit_comparison import repository
from src.credit_comparison.core.enums import ExceptionType
from src.credit_comparison.core.regex_utils import (
    AMOUNT_WITH_UNIT_PATTERN,
    CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN,
    COMPANY_DETAIL_WITH_MODIFIER_PATTERN,
    COMPANY_NAME_TRAILING_TOKENS,
    DIRECTION_SUFFIX_TOKENS,
    DIRECTION_TOKENS,
    FORMAT_TAG_CANONICAL_ASSIGNMENT,
    FORMAT_TAG_DIRECTION_WITH_MODIFIER,
    FORMAT_TAG_DIRECTION_WITH_SUFFIX,
    FORMAT_TAG_MISSING_INC_DEC,
    FORMAT_TAG_NON_STANDARD_MAIN,
    FORMAT_TAG_NON_STANDARD_INC_DEC,
    FORMAT_TAG_SIGNED_DIRECTION,
    MAIN_SENTENCE_ASSIGNMENT_TOKENS,
    MAIN_SENTENCE_INC_DEC_PATTERN,
    MAIN_SENTENCE_INC_DEC_WITH_MODIFIER_PATTERN,
    MAIN_SENTENCE_VALUE_PATTERN,
    SIGNED_DIRECTION_TOKENS,
    extract_company_detail_section,
    extract_structural_tail_token,
    extract_non_standard_main_sentence_token,
    iter_disallowed_punctuation_positions,
    split_text_segments,
    strip_company_detail_section,
)
from src.credit_comparison.models import CreditCompareTask

COMPANY_EXCEPTION_IDS = {
    int(ExceptionType.COMPANY_AMOUNT_ERROR),
    int(ExceptionType.COMPANY_DIRECTION_ERROR),
    int(ExceptionType.COMPANY_FORMAT_ERROR),
    int(ExceptionType.COMPANY_DUPLICATE_ERROR),
}


def _is_company_scoped_exception(exception_id: object, field_name: object = "") -> bool:
    try:
        exception_id_int = int(exception_id or 0)
    except (TypeError, ValueError):
        return False
    field_name_text = str(field_name or "").strip()
    if exception_id_int in COMPANY_EXCEPTION_IDS:
        return True
    return exception_id_int == int(ExceptionType.FORMAT_ERROR) and field_name_text == "company_detail"


def _presentation_exception_meta(exception_id: object, exception_name: object) -> tuple[int, str]:
    try:
        exception_id_int = int(exception_id or 0)
    except (TypeError, ValueError):
        exception_id_int = 0
    exception_name_text = str(exception_name or "").strip()
    if exception_id_int == int(ExceptionType.COMPANY_FORMAT_ERROR):
        return int(ExceptionType.FORMAT_ERROR), "格式异常"
    if exception_id_int == int(ExceptionType.PUNCTUATION_ERROR):
        return int(ExceptionType.FORMAT_ERROR), "格式异常"
    if exception_id_int == int(ExceptionType.COMPANY_DIRECTION_ERROR):
        return exception_id_int, "关联公司增减方向与当前主句不一致"
    return exception_id_int, exception_name_text


# ====== 高亮 token 构建（原样保留旧 ViewService 静态方法）======


def _format_company_amount_text(direction: object, profit_loss: object, profit_loss_unit: object) -> str:
    amount = "" if profit_loss is None else str(profit_loss).strip()
    unit = str(profit_loss_unit or "").strip()
    direction_text = ""
    try:
        direction_value = int(direction) if direction is not None else 0
    except (TypeError, ValueError):
        direction_value = 0
    if direction_value > 0:
        direction_text = "增加"
    elif direction_value < 0:
        direction_text = "减少"
    if not amount:
        return ""
    return f"{direction_text}{amount}{unit}".strip() if direction_text else f"{amount}{unit}".strip()


def _unique_tokens(*token_groups: object) -> list[str]:
    tokens: list[str] = []
    seen: set[str] = set()
    for group in token_groups:
        values = group if isinstance(group, (list, tuple, set)) else [group]
        for value in values:
            token = str(value or "").strip()
            if not token or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tokens


def _extract_amount_tokens(value: object) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    normalized = re.sub(r"^[+-]?\d+\*", "", text).strip()
    return _unique_tokens(text, normalized)


def _extract_company_highlight_segment(text: object, company_name: str) -> str:
    context = str(text or "").strip()
    company_text = str(company_name or "").strip()
    if not context or not company_text:
        return ""
    start = context.find(company_text)
    if start < 0:
        return ""
    end = len(context)
    for delimiter in ("，", ",", "；", ";", "。", "、"):
        delimiter_index = context.find(delimiter, start)
        if delimiter_index >= 0:
            end = min(end, delimiter_index)
    return context[start:end].strip()


def _make_highlight_token(
    text: object,
    variant: str = "",
    first_only: bool = True,
    within_text: object = "",
    within_offset: object = None,
) -> dict[str, object]:
    token = {
        "text": str(text or "").strip(),
        "first_only": first_only,
        "variant": variant,
    }
    within_text_value = str(within_text or "").strip()
    if within_text_value:
        token["within_text"] = within_text_value
    if within_offset is not None:
        try:
            within_offset_int = int(within_offset)
        except (TypeError, ValueError):
            within_offset_int = -1
        if within_offset_int >= 0:
            token["within_offset"] = within_offset_int
    return token


def _strip_company_suffix_token(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    tokens = list(DIRECTION_TOKENS) + list(DIRECTION_SUFFIX_TOKENS) + list(COMPANY_NAME_TRAILING_TOKENS)
    for token in tokens:
        if normalized.endswith(token):
            normalized = normalized[: -len(token)].strip()
            break
    return normalized


def _iter_company_segments(context: str, company_text: str) -> list[str]:
    source = str(context or "")
    target = str(company_text or "").strip()
    if not source or not target:
        return []
    segments: list[str] = []
    search_start = 0
    while search_start < len(source):
        start = source.find(target, search_start)
        if start < 0:
            break
        end = len(source)
        for delimiter in ("，", ",", "；", ";", "。", "、"):
            delimiter_index = source.find(delimiter, start)
            if delimiter_index >= 0:
                end = min(end, delimiter_index)
        segment = source[start:end].strip()
        if segment and segment not in segments:
            segments.append(segment)
        search_start = start + len(target)
    return segments


def _extract_main_sentence_amount_token(text: object) -> str:
    context = str(text or "").strip()
    if not context:
        return ""
    match = MAIN_SENTENCE_INC_DEC_PATTERN.search(context)
    if match:
        _, _direction_text, amount_text, unit = match.groups()
        return f"{str(amount_text or '').strip()}{str(unit or '').strip()}".strip()
    match = MAIN_SENTENCE_VALUE_PATTERN.search(context)
    if match:
        _, amount_text, unit = match.groups()
        return f"{str(amount_text or '').strip()}{str(unit or '').strip()}".strip()
    return ""


def _build_company_highlight_tokens(company_name: str, company_detail: dict | None, row: dict) -> list[dict[str, object]]:
    tokens: list[dict[str, object]] = []
    context = str(row.get("word_context", "") or "")
    segments = _iter_company_segments(context, company_name)
    if segments:
        for segment in segments:
            tokens.append(_make_highlight_token(company_name, "company-name", within_text=segment))
            amount_match = AMOUNT_WITH_UNIT_PATTERN.search(segment)
            if amount_match:
                tokens.append(
                    _make_highlight_token(
                        f"{str(amount_match.group(1) or '').strip()}{str(amount_match.group(2) or '').strip()}",
                        "company-amount",
                        within_text=segment,
                    )
                )
        return [token for token in tokens if str(token.get("text") or "").strip()]
    segment = _extract_company_highlight_segment(context, company_name)
    if company_name:
        tokens.append(_make_highlight_token(company_name, "company-name"))
    if segment:
        amount_match = AMOUNT_WITH_UNIT_PATTERN.search(segment)
        if amount_match:
            tokens.append(
                _make_highlight_token(
                    f"{str(amount_match.group(1) or '').strip()}{str(amount_match.group(2) or '').strip()}",
                    "company-amount",
                    within_text=segment,
                )
            )
        return [token for token in tokens if str(token.get("text") or "").strip()]
    if not company_detail:
        return [token for token in tokens if str(token.get("text") or "").strip()]
    amount_text = _format_company_amount_text(
        company_detail.get("direction"),
        company_detail.get("profit_loss"),
        company_detail.get("profit_loss_unit", ""),
    )
    if amount_text:
        amount_value = str(amount_text)
        if amount_value.startswith(("增加", "减少")):
            amount_value = amount_value[2:]
        tokens.append(_make_highlight_token(amount_value, "company-amount"))
    return [token for token in tokens if str(token.get("text") or "").strip()]


def _build_balance_highlight_tokens(_field_name: str, row: dict) -> list[str]:
    return _unique_tokens(_extract_main_sentence_amount_token(row.get("word_context", "")))


def _extract_company_format_error_token(segment: str, company_name: str) -> tuple[str, str, str]:
    amount_match = AMOUNT_WITH_UNIT_PATTERN.search(segment)
    if not amount_match:
        return "", "", ""

    amount_text = f"{str(amount_match.group(1) or '').strip()}{str(amount_match.group(2) or '').strip()}".strip()
    prefix = segment[: amount_match.start()].strip()
    trailing_text = extract_structural_tail_token(segment[amount_match.end() :])
    company_text = str(company_name or "").strip()
    between = prefix
    if company_text and prefix.startswith(company_text):
        between = prefix[len(company_text) :].strip()

    if trailing_text:
        return "format", trailing_text, company_text or prefix

    if not between:
        return "company-amount", amount_text, company_text or prefix

    if between.startswith("增加"):
        modifier_text = between[len("增加") :].strip()
        if not modifier_text:
            return "", "", company_text or prefix
        return "format", modifier_text, company_text or prefix
    if between.startswith("减少"):
        modifier_text = between[len("减少") :].strip()
        if not modifier_text:
            return "", "", company_text or prefix
        return "format", modifier_text, company_text or prefix

    if between in {"增加", "减少"}:
        return "", "", company_text or prefix

    return "format", between, company_text or prefix


def _build_format_highlight_tokens(field_name: object, value: object, row: dict) -> list[dict[str, object]]:
    field_name_text = str(field_name or "").strip()
    value_text = str(value or "").strip()
    context = str(row.get("word_context", "") or "")
    direction_with_suffix_pattern = re.compile(
        rf"(增加|减少)({'|'.join(re.escape(token) for token in DIRECTION_SUFFIX_TOKENS)})?"
    )

    if field_name_text in {"company_marker", "company_detail_tail"}:
        if value_text:
            if field_name_text == "company_marker":
                marker_token = value_text
                marker_index = context.find(marker_token) if context else -1
                if value_text == "缺少主要是":
                    detail_context = extract_company_detail_section(context) if context else ""
                    detail_start = context.find(detail_context) if context and detail_context else -1
                    if marker_index < 0 and detail_start > 0:
                        prefix = context[:detail_start].rstrip("：:、，,.。；; ").rstrip()
                        match = re.search(r"([^\s，,。；;:：]{1,12}[是原因为由])\s*$", prefix)
                        if match:
                            candidate = str(match.group(1) or "").strip()
                            if candidate and candidate != "主要是":
                                marker_token = candidate
                                marker_index = prefix.rfind(candidate)
                    if marker_index < 0 and detail_context:
                        match = re.match(r"^\s*([^\s，,。；;:：]{1,12}[是原因为由])", detail_context)
                        if match:
                            candidate = str(match.group(1) or "").strip()
                            if candidate and candidate != "主要是":
                                marker_token = candidate
                                marker_index = context.find(candidate)
                    if detail_start > 0:
                        raw_prefix = context[:detail_start]
                        raw_trimmed = raw_prefix.rstrip()
                        if raw_trimmed.endswith(("，", ",", "；", ";", "。", "、", ":", "：")):
                            marker_index = -1
                        prefix = raw_trimmed.rstrip("：:、，,.。；; ").rstrip()
                        last_delimiter = -1
                        for delimiter in ("，", ",", "；", ";", "。", "、", ":", "：", "\n"):
                            pos = prefix.rfind(delimiter)
                            if pos > last_delimiter:
                                last_delimiter = pos
                        intro = prefix[last_delimiter + 1 :].strip() if last_delimiter >= 0 else prefix.strip()
                        if intro and intro != "主要是":
                            marker_token = intro
                            marker_index = prefix.rfind(intro)
                    if marker_index < 0 and context:
                        detail_context = extract_company_detail_section(context)
                        if detail_context:
                            segment_end = -1
                            for delimiter in ("，", ",", "；", ";", "。", "、"):
                                pos = detail_context.find(delimiter)
                                if pos >= 0:
                                    segment_end = pos
                                    break
                            segment = detail_context[:segment_end].strip() if segment_end >= 0 else detail_context.strip()
                            if segment:
                                marker_token = segment
                                marker_index = context.find(segment)
                return [
                    _make_highlight_token(
                        marker_token,
                        "format",
                        first_only=False,
                        within_text=context,
                        within_offset=marker_index if marker_index >= 0 else None,
                    )
                ]
            detail_context = extract_company_detail_section(context)
            if detail_context:
                return [
                    _make_highlight_token(
                        value_text,
                        "format",
                        first_only=True,
                        within_text=detail_context,
                    )
                ]

    if field_name_text == "company_detail":
        tokens: list[dict[str, object]] = []
        company_probe = _strip_company_suffix_token(value_text)
        for probe in (company_probe, value_text):
            if not probe:
                continue
            segments = _iter_company_segments(context, probe)
            if segments:
                for segment in segments:
                    variant, token_text, company_text = _extract_company_format_error_token(segment, probe)
                    if not variant or not token_text:
                        continue
                    company_display = company_text or probe
                    if company_display:
                        tokens.append(_make_highlight_token(company_display, "company-name", within_text=segment))
                    tokens.append(_make_highlight_token(token_text, variant, within_text=segment))
                if tokens:
                    break
        return [token for token in tokens if str(token.get("text") or "").strip()]

    main_context = strip_company_detail_section(context) if context else ""
    if value_text == FORMAT_TAG_DIRECTION_WITH_MODIFIER:
        modifier_match = MAIN_SENTENCE_INC_DEC_WITH_MODIFIER_PATTERN.search(main_context)
        if modifier_match:
            direction_text = str(modifier_match.group(2) or "").strip()
            modifier_text = str(modifier_match.group(3) or "").strip()
            if direction_text:
                return [_make_highlight_token(modifier_text or f"{direction_text}{modifier_text}".strip(), "format")]
    if value_text == FORMAT_TAG_DIRECTION_WITH_SUFFIX:
        direction_match = re.search(r"(增加|减少)了", main_context)
        if direction_match:
            return [_make_highlight_token("了", "format")]
    if value_text == FORMAT_TAG_CANONICAL_ASSIGNMENT:
        amount_text = _extract_main_sentence_amount_token(main_context)
        tokens: list[dict[str, object]] = []
        for token in MAIN_SENTENCE_ASSIGNMENT_TOKENS:
            if token in main_context:
                tokens.append(_make_highlight_token(token, "format"))
                break
        if amount_text:
            tokens.append(_make_highlight_token(amount_text, "format"))
        return [token for token in tokens if str(token.get("text") or "").strip()]
    if value_text in set(MAIN_SENTENCE_ASSIGNMENT_TOKENS):
        amount_text = _extract_main_sentence_amount_token(main_context)
        tokens = [_make_highlight_token(value_text, "format")]
        if amount_text:
            tokens.append(_make_highlight_token(amount_text, "format"))
        return [token for token in tokens if str(token.get("text") or "").strip()]
    if value_text == FORMAT_TAG_NON_STANDARD_INC_DEC:
        direction_match = direction_with_suffix_pattern.search(main_context)
        if direction_match:
            suffix_text = str(direction_match.group(2) or "").strip()
            return [_make_highlight_token(suffix_text or direction_match.group(0), "format")]
    if value_text == FORMAT_TAG_NON_STANDARD_MAIN:
        token_text = extract_non_standard_main_sentence_token(main_context)
        if token_text:
            return [_make_highlight_token(token_text, "format")]
    if value_text == FORMAT_TAG_MISSING_INC_DEC:
        if CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN in main_context and "为" in main_context:
            amount_text = _extract_main_sentence_amount_token(main_context)
            tokens = [_make_highlight_token("为", "format")]
            if amount_text:
                tokens.append(_make_highlight_token(amount_text, "format"))
            return tokens
        signed_match = re.search(rf"[{re.escape(''.join(SIGNED_DIRECTION_TOKENS))}]", main_context)
        if signed_match:
            amount_text = _extract_main_sentence_amount_token(main_context)
            tokens = [_make_highlight_token(signed_match.group(0), "format")]
            if amount_text:
                tokens.append(_make_highlight_token(amount_text, "format"))
            return tokens
        amount_text = _extract_main_sentence_amount_token(main_context)
        if amount_text:
            return [_make_highlight_token(amount_text, "format")]
    if value_text in set(SIGNED_DIRECTION_TOKENS):
        amount_text = _extract_main_sentence_amount_token(main_context)
        tokens = [_make_highlight_token(value_text, "format")]
        if amount_text:
            tokens.append(_make_highlight_token(amount_text, "format"))
        return [token for token in tokens if str(token.get("text") or "").strip()]
    if value_text == FORMAT_TAG_SIGNED_DIRECTION:
        return [_make_highlight_token(token, "format", first_only=False) for token in ["+", "-", "－", "−", "—", "–"]]
    if value_text:
        return [_make_highlight_token(value_text, "format")]
    if main_context:
        return [_make_highlight_token(main_context, "format")]
    return []


def _build_company_direction_highlight_tokens(company_name: str, row: dict) -> list[dict[str, object]]:
    tokens: list[dict[str, object]] = []
    context = str(row.get("word_context", "") or "")
    segments = _iter_company_segments(context, company_name)
    if segments:
        for segment in segments:
            tokens.append(_make_highlight_token(company_name, "company-name", within_text=segment))
            direction_match = re.search(r"(增加|减少)", segment)
            if direction_match:
                tokens.append(_make_highlight_token(direction_match.group(1), "company-direction", within_text=segment))
        return [token for token in tokens if str(token.get("text") or "").strip()]
    if company_name:
        tokens.append(_make_highlight_token(company_name, "company-name"))
    segment = _extract_company_highlight_segment(context, company_name)
    if segment:
        direction_match = re.search(r"(增加|减少)", segment)
        if direction_match:
            tokens.append(_make_highlight_token(direction_match.group(1), "company-direction", within_text=segment))
    return [token for token in tokens if str(token.get("text") or "").strip()]


def _build_company_amount_error_highlight_tokens(company_name: str, company_detail: dict | None, row: dict) -> list[dict[str, object]]:
    tokens: list[dict[str, object]] = []
    context = str(row.get("word_context", "") or "")
    segments = _iter_company_segments(context, company_name)
    if segments:
        for segment in segments:
            tokens.append(_make_highlight_token(company_name, "company-name", within_text=segment))
            amount_match = AMOUNT_WITH_UNIT_PATTERN.search(segment)
            if amount_match:
                tokens.append(
                    _make_highlight_token(
                        f"{str(amount_match.group(1) or '').strip()}{str(amount_match.group(2) or '').strip()}",
                        "company-amount",
                        within_text=segment,
                    )
                )
        return [token for token in tokens if str(token.get("text") or "").strip()]
    if company_name:
        tokens.append(_make_highlight_token(company_name, "company-name"))
    segment = _extract_company_highlight_segment(context, company_name)
    if segment:
        amount_match = AMOUNT_WITH_UNIT_PATTERN.search(segment)
        if amount_match:
            tokens.append(
                _make_highlight_token(
                    f"{str(amount_match.group(1) or '').strip()}{str(amount_match.group(2) or '').strip()}",
                    "company-amount",
                    within_text=segment,
                )
            )
            return [token for token in tokens if str(token.get("text") or "").strip()]
    if company_detail:
        amount_text = _format_company_amount_text(
            company_detail.get("direction"),
            company_detail.get("profit_loss"),
            company_detail.get("profit_loss_unit", ""),
        )
        if amount_text:
            if amount_text.startswith(("增加", "减少")):
                amount_text = amount_text[2:]
            tokens.append(_make_highlight_token(amount_text, "company-amount"))
    return [token for token in tokens if str(token.get("text") or "").strip()]


def _build_company_duplicate_highlight_tokens(company_name: str, row: dict) -> list[dict[str, object]]:
    context = str(row.get("word_context", "") or "")
    segments = _iter_company_segments(context, company_name)
    if segments:
        return [
            _make_highlight_token(company_name, "company-name", within_text=segment)
            for segment in segments
            if company_name and str(segment or "").strip()
        ]
    if company_name:
        return [_make_highlight_token(company_name, "company-name")]
    return []


def _build_punctuation_highlight_tokens(field_name: str, value_text: str, row: dict) -> list[dict[str, object]]:
    context = str(row.get("word_context", "") or "")
    punctuation = str(value_text or "").strip()
    if not context or not punctuation:
        return []
    signed_minus_tokens = ("-", "－", "−", "—", "–")
    if punctuation == "+":
        return [_make_highlight_token("+", "format", first_only=False)]
    if punctuation in signed_minus_tokens:
        return [_make_highlight_token(token, "format", first_only=False) for token in signed_minus_tokens]
    scopes: list[str] = []
    if field_name == "main_sentence":
        main_context = strip_company_detail_section(context)
        if main_context:
            stripped = main_context.rstrip()
            if stripped and stripped[-1] == punctuation:
                position = len(stripped) - 1
                return [
                    _make_highlight_token(
                        punctuation,
                        "format",
                        first_only=False,
                        within_text=main_context,
                        within_offset=position,
                    )
                ]
            scopes.append(main_context)
    elif field_name == "company_detail":
        detail_context = extract_company_detail_section(context)
        stripped = str(detail_context or "").rstrip()
        if stripped and stripped[-1] == punctuation:
            position = len(stripped) - 1
            return [
                _make_highlight_token(
                    punctuation,
                    "format",
                    first_only=False,
                    within_text=detail_context,
                    within_offset=position,
                )
            ]
        if detail_context:
            scopes.append(detail_context)
    else:
        scopes.append(context)

    tokens: list[dict[str, object]] = []
    for scope in scopes:
        if punctuation == "。":
            last_index = -1
            for index in range(len(scope) - 1, -1, -1):
                if not scope[index].isspace():
                    last_index = index
                    break
            for index, char in enumerate(scope):
                if char == punctuation and index != last_index:
                    tokens.append(
                        _make_highlight_token(
                            punctuation,
                            "format",
                            first_only=False,
                            within_text=scope,
                            within_offset=index,
                        )
                    )
            continue
        for position in iter_disallowed_punctuation_positions(scope, punctuation):
            tokens.append(
                _make_highlight_token(
                    punctuation,
                    "format",
                    first_only=False,
                    within_text=scope,
                    within_offset=position,
                )
            )
    return [token for token in tokens if str(token.get("text") or "").strip()]


def _build_exception_highlight_tokens(
    exception_id: int,
    field_name: object,
    value: object,
    row: dict,
    company_detail: dict | None = None,
) -> list[object]:
    field_name_text = str(field_name or "").strip()
    value_text = str(value or "").strip()
    if exception_id in {int(ExceptionType.FORMAT_ERROR), int(ExceptionType.COMPANY_FORMAT_ERROR)}:
        return _build_format_highlight_tokens(field_name_text, value_text, row)
    if exception_id == int(ExceptionType.PUNCTUATION_ERROR):
        return _build_punctuation_highlight_tokens(field_name_text, value_text, row)
    if exception_id == int(ExceptionType.COMPANY_DIRECTION_ERROR):
        return _build_company_direction_highlight_tokens(value_text, row)
    if exception_id == int(ExceptionType.COMPANY_AMOUNT_ERROR):
        return _build_company_amount_error_highlight_tokens(value_text, company_detail, row)
    if exception_id == int(ExceptionType.COMPANY_DUPLICATE_ERROR):
        return _build_company_duplicate_highlight_tokens(value_text, row)
    if _is_company_scoped_exception(exception_id, field_name_text):
        return _build_company_highlight_tokens(value_text, company_detail, row)
    if exception_id == int(ExceptionType.BALANCE_MISSING_ERROR):
        return _build_balance_highlight_tokens(field_name_text, row)
    if field_name_text == "code":
        return _unique_tokens(value_text, row.get("word_code", ""))
    if field_name_text == "name":
        return _unique_tokens(value_text, row.get("word_name", ""))
    if field_name_text == "company":
        return _unique_tokens(value_text)
    if field_name_text == "amount":
        return _extract_amount_tokens(value_text)
    if field_name_text in {"amount_unit", "profit_loss_unit", "calc_scope_hint", "main_sentence"}:
        return _unique_tokens(value_text)
    if field_name_text == "direction":
        return _unique_tokens(SIGNED_DIRECTION_TOKENS)
    return _unique_tokens(value_text)


# ====== 聚合查询 ======


async def list_compare_links(db: AsyncSession, batch_id: str) -> list[dict[str, Any]]:
    """返回画线列表所需的关联信息（含异常标记与摘要）。"""

    rows = await repository.list_compare_link_details(db, batch_id)
    exception_word_record_ids = await repository.list_exception_word_record_ids(db, batch_id)
    exception_details = await repository.list_exception_details_by_batch(db, batch_id)
    exception_name_map: dict[int, list[str]] = {}
    for item in exception_details:
        word_record_id = item.get("word_record_id")
        if word_record_id is None:
            continue
        word_record_id_int = int(word_record_id)
        _display_exception_id, exception_name = _presentation_exception_meta(
            item.get("exception_id"), item.get("exception_name")
        )
        if not exception_name:
            continue
        name_list = exception_name_map.setdefault(word_record_id_int, [])
        if exception_name not in name_list:
            name_list.append(exception_name)
    exception_summary_map: dict[int, str] = {
        wid: " | ".join(name_list) for wid, name_list in exception_name_map.items()
    }
    for row in rows:
        word_record_id = int(row["word_record_id"])
        row["has_exception"] = word_record_id in exception_word_record_ids
        row["exception_summary"] = exception_summary_map.get(word_record_id, "")
    return rows


async def get_document_pair_detail(
    db: AsyncSession, batch_id: str, word_file_name: str, excel_file_name: str = ""
) -> dict[str, Any]:
    """返回单个 Word 文件的预览与锚点数据（前端对账工作台详情）。"""

    task = (
        await db.execute(select(CreditCompareTask).where(CreditCompareTask.batch_id == batch_id))
    ).scalars().first()
    if not word_file_name:
        word_file_name = str(task.word_file_name if task else "")
    if not excel_file_name:
        excel_file_name = str(task.excel_file_name if task else "")

    rows = [
        row
        for row in await list_compare_links(db, batch_id)
        if str(row.get("word_file_name") or "") == word_file_name
    ]
    if not excel_file_name:
        excel_file_name = next((str(row.get("excel_file_name") or "") for row in rows if row.get("excel_file_name")), "")

    # Word / Excel 锚点
    word_anchor_map: dict[int, dict] = {}
    excel_anchor_map: dict[int, dict] = {}
    for row in rows:
        word_record_id = int(row["word_record_id"])
        if word_record_id not in word_anchor_map:
            word_anchor_map[word_record_id] = {
                "word_record_id": word_record_id,
                "sheet": row.get("word_sheet", ""),
                "code": row.get("word_code", ""),
                "name": row.get("word_name", ""),
                "paraindex": row.get("word_paraindex"),
                "source_ref": row.get("word_source_ref", ""),
                "context": row.get("word_context", ""),
                "has_exception": bool(row.get("has_exception")),
            }
        else:
            word_anchor_map[word_record_id]["has_exception"] = bool(
                word_anchor_map[word_record_id]["has_exception"] or row.get("has_exception")
            )

        excel_record_id = row.get("excel_record_id")
        if excel_record_id is not None:
            excel_record_id_int = int(excel_record_id)
            if excel_record_id_int not in excel_anchor_map:
                excel_anchor_map[excel_record_id_int] = {
                    "excel_record_id": excel_record_id_int,
                    "sheet": row.get("excel_sheet", ""),
                    "code": row.get("excel_code", ""),
                    "name": row.get("excel_name", ""),
                    "excel_row_index": row.get("excel_row_index"),
                    "has_exception": bool(row.get("has_exception")),
                }
            else:
                excel_anchor_map[excel_record_id_int]["has_exception"] = bool(
                    excel_anchor_map[excel_record_id_int]["has_exception"] or row.get("has_exception")
                )

    pair_word_record_ids = set(word_anchor_map.keys())
    row_by_word_record_id = {int(row["word_record_id"]): row for row in rows}
    rows_by_word_record_id: dict[int, list[dict]] = {}
    for row in rows:
        rows_by_word_record_id.setdefault(int(row["word_record_id"]), []).append(row)

    # 关联公司异常聚合
    company_details_cache: dict[int, list[dict]] = {}
    exception_company_map: dict[str, dict] = {}
    for item in await repository.list_exception_details_by_batch(db, batch_id):
        word_record_id = item.get("word_record_id")
        exception_id = item.get("exception_id")
        if word_record_id is None or int(word_record_id) not in pair_word_record_ids:
            continue
        if not _is_company_scoped_exception(exception_id, item.get("field_name", "")):
            continue
        company_name = str(item.get("value") or "").strip()
        if not company_name:
            continue
        word_record_id_int = int(word_record_id)
        row = row_by_word_record_id.get(word_record_id_int)
        if row is None:
            continue
        if word_record_id_int not in company_details_cache:
            company_details_cache[word_record_id_int] = await repository.list_company_by_word_record(db, word_record_id_int)
        company_details = [
            d
            for d in company_details_cache[word_record_id_int]
            if str(d.get("company") or "").strip() == company_name
        ]
        if not company_details:
            company_details = [None]
        display_exception_id, display_exception_name = _presentation_exception_meta(exception_id, item.get("exception_name"))
        company_item = exception_company_map.setdefault(
            company_name,
            {"company": company_name, "word_file_name": row.get("word_file_name", ""), "entries": []},
        )
        for company_detail in company_details:
            company_item["entries"].append(
                {
                    "word_record_id": word_record_id_int,
                    "compare_link_id": row.get("compare_link_id"),
                    "exception_id": display_exception_id,
                    "exception_name": display_exception_name,
                    "sheet": row.get("word_sheet", ""),
                    "code": row.get("word_code", ""),
                    "name": row.get("word_name", ""),
                    "direction": company_detail.get("direction") if company_detail else None,
                    "profit_loss": company_detail.get("profit_loss") if company_detail else None,
                    "profit_loss_unit": company_detail.get("profit_loss_unit", "") if company_detail else "",
                    "amount_text": _format_company_amount_text(
                        company_detail.get("direction") if company_detail else None,
                        company_detail.get("profit_loss") if company_detail else None,
                        company_detail.get("profit_loss_unit", "") if company_detail else "",
                    ),
                    "highlight_tokens": _build_company_highlight_tokens(company_name, company_detail, row),
                }
            )

    word_anchor_list = list(word_anchor_map.values())
    word_anchor_list.sort(key=lambda item: (item["paraindex"] or 0, item["word_record_id"]))
    excel_anchor_list = list(excel_anchor_map.values())
    excel_anchor_list.sort(key=lambda item: (item["excel_row_index"] or 0, item["excel_record_id"]))
    exception_company_list = list(exception_company_map.values())
    for item in exception_company_list:
        item["entries"].sort(
            key=lambda entry: (str(entry.get("sheet") or ""), str(entry.get("code") or ""), int(entry.get("word_record_id") or 0))
        )
        item["entry_count"] = len(item["entries"])
    exception_company_list.sort(key=lambda item: str(item.get("company") or ""))

    # 异常分组聚合
    exception_group_map: dict[int, dict] = {}
    for item in await repository.list_exception_details_by_batch(db, batch_id):
        word_record_id = item.get("word_record_id")
        if word_record_id is None:
            continue
        word_record_id_int = int(word_record_id)
        if word_record_id_int not in pair_word_record_ids:
            continue
        row = row_by_word_record_id.get(word_record_id_int)
        if row is None:
            continue
        exception_id = int(item.get("exception_id") or 0)
        company_detail = None
        if _is_company_scoped_exception(exception_id, item.get("field_name", "")):
            company_name = str(item.get("value") or "").strip()
            if company_name:
                if word_record_id_int not in company_details_cache:
                    company_details_cache[word_record_id_int] = await repository.list_company_by_word_record(db, word_record_id_int)
                company_detail = next(
                    (
                        detail
                        for detail in company_details_cache[word_record_id_int]
                        if str(detail.get("company") or "").strip() == company_name
                    ),
                    None,
                )
        related_rows = rows_by_word_record_id.get(word_record_id_int, [])
        excel_row_indexes = sorted(
            {
                int(related_row.get("excel_row_index") or 0)
                for related_row in related_rows
                if related_row.get("excel_row_index") is not None
            }
        )
        display_exception_id, exception_name = _presentation_exception_meta(exception_id, item.get("exception_name"))
        if not exception_id or not exception_name:
            continue
        group = exception_group_map.setdefault(
            display_exception_id, {"type_id": display_exception_id, "type_name": exception_name, "items": []}
        )
        group["items"].append(
            {
                "id": int(item.get("id") or 0),
                "word_record_id": word_record_id_int,
                "sheet": row.get("word_sheet", ""),
                "code": row.get("word_code", ""),
                "name": row.get("word_name", ""),
                "field_name": item.get("field_name", ""),
                "value": item.get("value", ""),
                "excel_row_indexes": excel_row_indexes,
                "highlight_first_only": display_exception_id == int(ExceptionType.BALANCE_MISSING_ERROR),
                "highlight_tokens": _build_exception_highlight_tokens(
                    exception_id=exception_id,
                    field_name=item.get("field_name", ""),
                    value=item.get("value", ""),
                    row=row,
                    company_detail=company_detail,
                ),
            }
        )

    hidden_exception_type_ids = {4, 6, 11, int(ExceptionType.COMPANY_FORMAT_ERROR), int(ExceptionType.PUNCTUATION_ERROR)}
    exception_group_list: list[dict] = []
    from src.credit_comparison.core.enums import EXCEPTION_TYPE_NAMES

    for type_id, type_name in EXCEPTION_TYPE_NAMES.items():
        if type_id in hidden_exception_type_ids:
            continue
        group = exception_group_map.get(type_id, {"type_id": type_id, "type_name": type_name, "items": []})
        group["items"].sort(
            key=lambda entry: (
                str(entry.get("sheet") or ""),
                str(entry.get("code") or ""),
                int(entry.get("word_record_id") or 0),
                int(entry.get("id") or 0),
            )
        )
        exception_group_list.append(group)

    word_preview_url = ""
    excel_preview_url = ""
    word_structured_preview_url = ""
    excel_structured_preview_url = ""
    if word_file_name:
        word_preview_url = f"/api/credit-comparison/previews/word?batch_id={quote(batch_id)}&file_name={quote(word_file_name)}"
        word_structured_preview_url = f"/api/credit-comparison/previews/word-structured?batch_id={quote(batch_id)}&file_name={quote(word_file_name)}"
    if excel_file_name:
        excel_preview_url = f"/api/credit-comparison/previews/excel?batch_id={quote(batch_id)}&file_name={quote(excel_file_name)}"
        excel_structured_preview_url = f"/api/credit-comparison/previews/excel-structured?batch_id={quote(batch_id)}&file_name={quote(excel_file_name)}"

    return {
        "word_file_name": word_file_name,
        "excel_file_name": excel_file_name,
        "word_preview_url": word_preview_url,
        "excel_preview_url": excel_preview_url,
        "word_structured_preview_url": word_structured_preview_url,
        "excel_structured_preview_url": excel_structured_preview_url,
        "link_list": rows,
        "exception_company_list": exception_company_list,
        "exception_group_list": exception_group_list,
        "word_anchor_list": word_anchor_list,
        "excel_anchor_list": excel_anchor_list,
    }


async def list_exceptions_by_word_record(db: AsyncSession, word_record_id: int) -> list[dict[str, Any]]:
    """返回某条 Word 主记录的异常详情。"""

    items = await repository.list_exception_details_by_word_record(db, word_record_id)
    normalized_items: list[dict[str, Any]] = []
    for item in items:
        display_exception_id, display_exception_name = _presentation_exception_meta(
            item.get("exception_id"), item.get("exception_name")
        )
        normalized = dict(item)
        normalized["exception_id"] = display_exception_id
        normalized["exception_name"] = display_exception_name
        normalized_items.append(normalized)
    return normalized_items
