from __future__ import annotations

import re
import unicodedata


def _build_alt_pattern(tokens: tuple[str, ...]) -> str:
    return "|".join(re.escape(token) for token in tokens)


CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN = "本期"
MAIN_SENTENCE_ASSIGNMENT_TOKENS = ("为", "：", ":", "=")
DIRECTION_TOKENS = ("增加", "减少")
COMPANY_DIRECTION_TOKENS = ("增加", "减少", "增", "减")
DIRECTION_SUFFIX_TOKENS = ("了", "约", "共", "合计", "累计", "达", "为", "至", "计")
DIRECTION_MODIFIER_TOKENS = tuple(token for token in DIRECTION_SUFFIX_TOKENS if token != "了")
COMPANY_NAME_TRAILING_TOKENS = ("增", "减", "加")
SIGNED_DIRECTION_TOKENS = ("+", "-", "－", "−", "—", "–")
WEAK_NEGATIVE_DIRECTION_TOKENS = ("减", "少", "小")
WEAK_POSITIVE_DIRECTION_TOKENS = ("增", "加", "多")
FORMAT_TAG_DIRECTION_WITH_MODIFIER = "增加/减少后含修饰词"
FORMAT_TAG_DIRECTION_WITH_SUFFIX = "增加/减少后含后缀"
FORMAT_TAG_CANONICAL_ASSIGNMENT = "本期为"
FORMAT_TAG_NON_STANDARD_INC_DEC = "非标准增减主句"
FORMAT_TAG_NON_STANDARD_MAIN = "非标准主句"
FORMAT_TAG_MISSING_INC_DEC = "缺少增加/减少"
FORMAT_TAG_SIGNED_DIRECTION = "+/-"
ALLOWED_CHINESE_PUNCTUATION = ("“", "”", "（", "）", "，", "。", "：","、")
SEGMENT_DELIMITER_PUNCTUATION = {"，", "。", "；", ";", ",", ".", '"', "“", "”"}

SHEET_PATTERN = re.compile(r"([A-Z]\d{4})\s*表单[:：]?")
QUOTE_PATTERN = re.compile(r"[“\"]([^”\"]+)[”\"]")
PARA_INDEX_PATTERN = re.compile(r"^[（(]\s*(\d+)\s*[）)]")
CODE_PREFIX_PATTERN = re.compile(r"^([A-Za-z0-9]+)[\s\-_:：、，,.]*(.*)$")
MAIN_SENTENCE_PERIOD_PATTERN = rf"({re.escape(CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN)})"
MAIN_SENTENCE_UNIT_PATTERN = r"(亿美元|万美元|美元|亿元|亿|万元|万|元)"
MAIN_SENTENCE_INC_DEC_PATTERN = re.compile(
    rf"{MAIN_SENTENCE_PERIOD_PATTERN}\s*({_build_alt_pattern(DIRECTION_TOKENS)})\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*{MAIN_SENTENCE_UNIT_PATTERN}"
)
MAIN_SENTENCE_INC_DEC_WITH_SUFFIX_PATTERN = re.compile(
    rf"{MAIN_SENTENCE_PERIOD_PATTERN}\s*({_build_alt_pattern(DIRECTION_TOKENS)}){re.escape('了')}\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*{MAIN_SENTENCE_UNIT_PATTERN}"
)
MAIN_SENTENCE_INC_DEC_WITH_MODIFIER_PATTERN = re.compile(
    rf"{MAIN_SENTENCE_PERIOD_PATTERN}\s*({_build_alt_pattern(DIRECTION_TOKENS)})\s*({_build_alt_pattern(DIRECTION_MODIFIER_TOKENS)})\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*{MAIN_SENTENCE_UNIT_PATTERN}"
)
MAIN_SENTENCE_VALUE_PATTERN = re.compile(
    rf"{MAIN_SENTENCE_PERIOD_PATTERN}\s*(?:{_build_alt_pattern(MAIN_SENTENCE_ASSIGNMENT_TOKENS)})?\s*([{re.escape(''.join(SIGNED_DIRECTION_TOKENS))}]?[0-9][0-9,]*(?:\.[0-9]+)?)\s*{MAIN_SENTENCE_UNIT_PATTERN}"
)
COMPANY_DETAIL_PATTERN = re.compile(
    rf"([^,，。、；]+?)\s*({_build_alt_pattern(COMPANY_DIRECTION_TOKENS)})\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*{MAIN_SENTENCE_UNIT_PATTERN}"
)
COMPANY_DETAIL_WITH_MODIFIER_PATTERN = re.compile(
    rf"([^,，。、；]+?)\s*({_build_alt_pattern(COMPANY_DIRECTION_TOKENS)})\s*({_build_alt_pattern(DIRECTION_MODIFIER_TOKENS)})\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*{MAIN_SENTENCE_UNIT_PATTERN}"
)
COMPANY_DETAIL_WITH_SUFFIX_PATTERN = re.compile(
    rf"([^,，。、；]+?)\s*({_build_alt_pattern(COMPANY_DIRECTION_TOKENS)}){re.escape('了')}\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*{MAIN_SENTENCE_UNIT_PATTERN}"
)
DETAIL_START_PATTERN = re.compile(r"(主要是|主要为|主要由|主要原因是)")
AMOUNT_WITH_UNIT_PATTERN = re.compile(rf"([0-9][0-9,]*(?:\.[0-9]+)?)\s*{MAIN_SENTENCE_UNIT_PATTERN}")
INC_DEC_AMOUNT_PATTERN = re.compile(
    rf"({_build_alt_pattern(DIRECTION_TOKENS)})\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*{MAIN_SENTENCE_UNIT_PATTERN}"
)


def extract_sheet(text: str) -> str | None:
    """提取表单代码。"""

    match = SHEET_PATTERN.search(text)
    return match.group(1) if match else None


def extract_paraindex(text: str) -> int | None:
    """提取段落序号。"""

    match = PARA_INDEX_PATTERN.search(text.strip())
    return int(match.group(1)) if match else None


def extract_quoted_text(text: str) -> str | None:
    """提取首个引号内文本。"""

    match = QUOTE_PATTERN.search(text)
    return match.group(1).strip() if match else None


def extract_code_and_name(text: str) -> tuple[str | None, str | None]:
    """从引号内容中拆分指标代码和指标名称。"""

    match = CODE_PREFIX_PATTERN.match(text.strip())
    if not match:
        return None, None
    code = match.group(1).strip()
    name = match.group(2).strip().lstrip("：:、，,.。 ")
    return code or None, name or None


def extract_direction_amount_unit(text: str) -> tuple[int | None, float | None, str | None]:
    """提取主句方向、金额和单位。"""

    match = MAIN_SENTENCE_INC_DEC_PATTERN.search(text)
    if match:
        _, direction_text, amount_text, unit = match.groups()
        direction = 1 if direction_text == "增加" else -1
        return direction, float(str(amount_text).replace(",", "")), unit

    match = MAIN_SENTENCE_INC_DEC_WITH_SUFFIX_PATTERN.search(text)
    if match:
        _, direction_text, amount_text, unit = match.groups()
        direction = 1 if direction_text == "增加" else -1
        return direction, float(str(amount_text).replace(",", "")), unit

    match = MAIN_SENTENCE_INC_DEC_WITH_MODIFIER_PATTERN.search(text)
    if match:
        _, direction_text, _modifier_text, amount_text, unit = match.groups()
        direction = 1 if direction_text == "增加" else -1
        return direction, float(str(amount_text).replace(",", "")), unit

    amount_match = AMOUNT_WITH_UNIT_PATTERN.search(text)
    if amount_match:
        prefix = text[: int(amount_match.start())]
        period_index = prefix.rfind(CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN)
        if period_index >= 0:
            between = prefix[period_index + len(CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN) :].strip()
            has_negative = any(token in between for token in WEAK_NEGATIVE_DIRECTION_TOKENS)
            has_positive = any(token in between for token in WEAK_POSITIVE_DIRECTION_TOKENS)
            if has_negative != has_positive:
                direction = -1 if has_negative else 1
                amount_text, unit = amount_match.groups()
                return direction, float(str(amount_text).replace(",", "")), unit
            if has_negative and has_positive:
                amount_text, unit = amount_match.groups()
                return None, float(str(amount_text).replace(",", "")), unit

    match = MAIN_SENTENCE_VALUE_PATTERN.search(text)
    if not match:
        return None, None, None
    _, amount_text, unit = match.groups()
    normalized = str(amount_text).strip().replace(",", "")
    normalized = normalized.replace("－", "-").replace("−", "-").replace("—", "-").replace("–", "-")
    try:
        amount_value = float(normalized)
    except ValueError:
        return None, None, None
    if amount_value < 0:
        return -1, abs(amount_value), unit
    return 1, amount_value, unit


def _is_numeric_separator(text: str, index: int) -> bool:
    if index <= 0 or index >= len(text) - 1:
        return False
    return text[index] in {".", ","} and text[index - 1].isdigit() and text[index + 1].isdigit()


def extract_first_disallowed_punctuation(text: str) -> str:
    positions = iter_disallowed_punctuation_positions(text)
    if not positions:
        return ""
    normalized = str(text or "")
    return normalized[positions[0]]


def iter_disallowed_punctuation_positions(text: str, target: str = "") -> list[int]:
    normalized = str(text or "")
    target_text = str(target or "").strip()
    positions: list[int] = []
    for index, char in enumerate(normalized):
        if char.isspace() or char in ALLOWED_CHINESE_PUNCTUATION:
            continue
        if _is_numeric_separator(normalized, index):
            continue
        is_signed = char in SIGNED_DIRECTION_TOKENS
        if not is_signed and not unicodedata.category(char).startswith("P"):
            continue
        if target_text and char != target_text:
            continue
        positions.append(index)
    return positions


def extract_structural_tail_token(text: str) -> str:
    normalized = str(text or "")
    token_chars: list[str] = []
    collecting = False
    for index, char in enumerate(normalized):
        if char.isspace():
            if collecting:
                break
            continue
        if unicodedata.category(char).startswith("P"):
            if collecting:
                break
            continue
        token_chars.append(char)
        collecting = True
    token = "".join(token_chars).strip()
    return "" if token == "等小额增加" else token


_COMPANY_SUFFIX_PATTERN = re.compile(r"(有限责任公司|股份有限公司|集团有限公司|有限公司|公司|集团|银行)")


def _split_company_prefix(prefix: str) -> tuple[str, str]:
    normalized = str(prefix or "").strip()
    if not normalized:
        return "", ""
    direction_indexes = [normalized.find(token) for token in DIRECTION_TOKENS]
    direction_indexes = [index for index in direction_indexes if index >= 0]
    if direction_indexes:
        index = min(direction_indexes)
        return normalized[:index].strip(), normalized[index:].strip()
    suffix_end = -1
    for match in _COMPANY_SUFFIX_PATTERN.finditer(normalized):
        suffix_end = match.end()
    if suffix_end > 0:
        company = normalized[:suffix_end].strip()
        between = normalized[suffix_end:].strip()
        return company, between
    return normalized, ""


def split_text_segments(text: str) -> list[str]:
    normalized = str(text or "")
    if not normalized:
        return []
    segments: list[str] = []
    current_chars: list[str] = []
    for index, char in enumerate(normalized):
        current_chars.append(char)
        if char in SEGMENT_DELIMITER_PUNCTUATION and not _is_numeric_separator(normalized, index):
            segment = "".join(current_chars).strip()
            if segment:
                segments.append(segment)
            current_chars = []
    tail = "".join(current_chars).strip()
    if tail:
        segments.append(tail)
    return segments


def _strip_leading_detail_token(segment: str) -> str:
    normalized = str(segment or "").strip()
    if not normalized:
        return ""
    trimmed = normalized.lstrip("（(").lstrip()
    match = DETAIL_START_PATTERN.match(trimmed)
    if not match:
        candidate_match = re.match(r"^\s*([^\s，,。；;:：]{1,12}[是原因为由])", trimmed)
        if not candidate_match:
            return normalized
        candidate = str(candidate_match.group(1) or "").strip()
        if not candidate or candidate == "主要是":
            return normalized
        trimmed = trimmed[candidate_match.end() :].lstrip("：:、，,.。；; ").lstrip()
        return trimmed or normalized
    trimmed = trimmed[match.end() :].lstrip("：:、，,.。；; ").lstrip()
    return trimmed


def has_amount_without_inc_dec(text: str) -> bool:
    """判断文本中是否存在“带单位金额”但未以增加/减少引导的表达。"""

    normalized = str(text or "")
    if not normalized:
        return False

    covered_spans: list[tuple[int, int]] = []
    parsed_direction, parsed_amount, parsed_unit = extract_direction_amount_unit(normalized)
    if parsed_direction in (-1, 1) and parsed_amount is not None and parsed_unit:
        amount_match = AMOUNT_WITH_UNIT_PATTERN.search(normalized)
        if amount_match:
            prefix = normalized[: amount_match.start()]
            if CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN in prefix:
                covered_spans.append(amount_match.span())
    for match in INC_DEC_AMOUNT_PATTERN.finditer(normalized):
        covered_spans.append(match.span())
    for pattern in (
        MAIN_SENTENCE_INC_DEC_WITH_SUFFIX_PATTERN,
        MAIN_SENTENCE_INC_DEC_WITH_MODIFIER_PATTERN,
        COMPANY_DETAIL_WITH_SUFFIX_PATTERN,
        COMPANY_DETAIL_WITH_MODIFIER_PATTERN,
    ):
        for match in pattern.finditer(normalized):
            covered_spans.append(match.span())

    def is_covered(start: int, end: int) -> bool:
        for span_start, span_end in covered_spans:
            if span_start <= start and end <= span_end:
                return True
        return False

    for amount_match in AMOUNT_WITH_UNIT_PATTERN.finditer(normalized):
        if not is_covered(amount_match.start(), amount_match.end()):
            return True
    return False


def is_absolute_main_sentence(text: str) -> bool:
    return MAIN_SENTENCE_VALUE_PATTERN.search(text) is not None and MAIN_SENTENCE_INC_DEC_PATTERN.search(text) is None


def extract_amount_scale(text: str) -> int | None:
    """提取主句金额的小数位数。"""

    match = MAIN_SENTENCE_INC_DEC_PATTERN.search(text)
    if match:
        amount_text = str(match.group(3) or "")
    else:
        match = MAIN_SENTENCE_INC_DEC_WITH_SUFFIX_PATTERN.search(text)
        if match:
            amount_text = str(match.group(3) or "")
        else:
            match = MAIN_SENTENCE_INC_DEC_WITH_MODIFIER_PATTERN.search(text)
            if not match:
                match = MAIN_SENTENCE_VALUE_PATTERN.search(text)
                if not match:
                    return None
                amount_text = str(match.group(2) or "")
            else:
                amount_text = str(match.group(4) or "")
    normalized = amount_text.strip().replace(",", "")
    normalized = normalized.replace("－", "-").replace("−", "-").replace("—", "-").replace("–", "-")
    if "." not in normalized:
        return 0
    return max(0, len(normalized.split(".", 1)[1]))


def extract_non_standard_main_sentence_token(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    amount_match = AMOUNT_WITH_UNIT_PATTERN.search(normalized)
    if amount_match:
        prefix = normalized[: amount_match.start()].strip()
        if prefix.startswith(CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN):
            between = prefix[len(CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN) :].strip()
            if between:
                for token in ("增", "减", "少", "加"):
                    if token in between:
                        return token
                return between
            return CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN
        for token in (*DIRECTION_TOKENS, *MAIN_SENTENCE_ASSIGNMENT_TOKENS):
            token_index = prefix.find(token)
            if token_index > 0:
                return prefix[:token_index].strip() or token
        return prefix
    if CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN in normalized:
        return CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN
    return ""


def is_canonical_main_sentence(text: str) -> bool:
    match = MAIN_SENTENCE_INC_DEC_PATTERN.search(text)
    if not match:
        return False
    return str(match.group(1) or "") == "本期"


def is_soft_main_sentence_format(text: str) -> bool:
    for pattern in (MAIN_SENTENCE_INC_DEC_WITH_SUFFIX_PATTERN, MAIN_SENTENCE_INC_DEC_WITH_MODIFIER_PATTERN):
        match = pattern.search(text)
        if match and str(match.group(1) or "") == "本期":
            return True
    return False


def has_blocking_main_sentence_format(text: str) -> bool:
    if not str(text or "").strip():
        return False
    if is_canonical_main_sentence(text) or is_soft_main_sentence_format(text):
        return False
    parsed_direction, parsed_amount, parsed_unit = extract_direction_amount_unit(str(text or ""))
    if parsed_direction in (-1, 1) and parsed_amount is not None and parsed_unit:
        return False
    if MAIN_SENTENCE_INC_DEC_PATTERN.search(text):
        return True
    if MAIN_SENTENCE_INC_DEC_WITH_MODIFIER_PATTERN.search(text):
        return True
    if MAIN_SENTENCE_VALUE_PATTERN.search(text):
        return True
    return "增加" in text or "减少" in text


def classify_main_sentence_format(text: str) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    amount_match = AMOUNT_WITH_UNIT_PATTERN.search(normalized)
    if not amount_match:
        non_standard_token = extract_non_standard_main_sentence_token(normalized)
        if non_standard_token:
            return non_standard_token
        if "增加" in normalized or "减少" in normalized:
            return FORMAT_TAG_NON_STANDARD_INC_DEC
        return FORMAT_TAG_NON_STANDARD_MAIN
    prefix = normalized[: amount_match.start()].strip()
    if CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN not in prefix:
        non_standard_token = extract_non_standard_main_sentence_token(normalized)
        if non_standard_token:
            return non_standard_token
        return prefix

    between = prefix.split(CANONICAL_MAIN_SENTENCE_PERIOD_TOKEN, 1)[1].strip()
    if not between:
        return FORMAT_TAG_MISSING_INC_DEC
    if between.startswith("增加"):
        modifier = between[len("增加") :].strip()
        if modifier:
            return modifier
    elif between.startswith("减少"):
        modifier = between[len("减少") :].strip()
        if modifier:
            return modifier
    elif between in MAIN_SENTENCE_ASSIGNMENT_TOKENS:
        return between
    elif between and between[0] in SIGNED_DIRECTION_TOKENS:
        return between[0]
    else:
        return between

    trailing_token = extract_structural_tail_token(normalized[amount_match.end() :])
    return trailing_token


def extract_company_details(text: str) -> list[tuple[str, int, float, str]]:
    """提取企业明细列表。"""

    results: list[tuple[str, int, float, str]] = []
    for company, direction_text, amount_text, unit in COMPANY_DETAIL_PATTERN.findall(text):
        direction = 1 if direction_text in {"增加", "增"} else -1
        results.append((company.strip(), direction, float(amount_text), unit))
    return results


def extract_company_detail_items(text: str) -> list[dict[str, object]]:
    normalized = str(text or "")
    if not normalized:
        return []

    results: list[dict[str, object]] = []
    seen: set[tuple[str, int, float | None, str, str, str]] = set()
    segments = split_text_segments(normalized)
    for segment in segments:
        segment = _strip_leading_detail_token(segment)
        punctuation_token = extract_first_disallowed_punctuation(segment)
        item: dict[str, object] | None = None
        standard_match = COMPANY_DETAIL_PATTERN.search(segment)
        if standard_match:
            company, direction_text, amount_text, unit = standard_match.groups()
            direction = 1 if direction_text in {"增加", "增"} else -1
            amount = float(str(amount_text).replace(",", ""))
            trailing_token = extract_structural_tail_token(segment[standard_match.end() :])
            item = {
                "company": company.strip(),
                "direction": direction,
                "amount": amount,
                "unit": str(unit or "").strip(),
                "format_tag": trailing_token,
                "punctuation_token": punctuation_token,
            }
        else:
            suffix_match = COMPANY_DETAIL_WITH_SUFFIX_PATTERN.search(segment)
            if suffix_match:
                company, direction_text, amount_text, unit = suffix_match.groups()
                direction = 1 if direction_text in {"增加", "增"} else -1
                amount = float(str(amount_text).replace(",", ""))
                trailing_token = extract_structural_tail_token(segment[suffix_match.end() :])
                item = {
                    "company": company.strip(),
                    "direction": direction,
                    "amount": amount,
                    "unit": str(unit or "").strip(),
                    "format_tag": trailing_token or "了",
                    "punctuation_token": punctuation_token,
                }
            else:
                modifier_match = COMPANY_DETAIL_WITH_MODIFIER_PATTERN.search(segment)
                if modifier_match:
                    company, direction_text, _modifier_text, amount_text, unit = modifier_match.groups()
                    direction = 1 if direction_text in {"增加", "增"} else -1
                    amount = float(str(amount_text).replace(",", ""))
                    trailing_token = extract_structural_tail_token(segment[modifier_match.end() :])
                    modifier_text = str(modifier_match.group(3) or "").strip()
                    item = {
                        "company": company.strip(),
                        "direction": direction,
                        "amount": amount,
                        "unit": str(unit or "").strip(),
                        "format_tag": trailing_token or modifier_text,
                        "punctuation_token": punctuation_token,
                    }
                else:
                    amount_match = AMOUNT_WITH_UNIT_PATTERN.search(segment)
                    if not amount_match:
                        continue
                    prefix = segment[: amount_match.start()].strip().rstrip("：:、，,.。；; ")
                    company_text, between = _split_company_prefix(prefix)
                    company_text = str(company_text or "").strip()
                    between = str(between or "").strip()
                    if not company_text:
                        continue
                    amount_text = str(amount_match.group(1) or "").replace(",", "")
                    try:
                        amount_value = float(amount_text)
                    except ValueError:
                        continue
                    unit_text = str(amount_match.group(2) or "").strip()
                    trailing_token = extract_structural_tail_token(segment[amount_match.end() :])
                    between_error = ""
                    if between.startswith("增加"):
                        between_error = between[len("增加") :].strip()
                    elif between.startswith("减少"):
                        between_error = between[len("减少") :].strip()
                    elif between.startswith("增"):
                        between_error = between[len("增") :].strip()
                    elif between.startswith("减"):
                        between_error = between[len("减") :].strip()
                    else:
                        between_error = between.strip()
                    item = {
                        "company": company_text,
                        "direction": 0,
                        "amount": amount_value,
                        "unit": unit_text,
                        "format_tag": trailing_token or between_error or FORMAT_TAG_MISSING_INC_DEC,
                        "punctuation_token": punctuation_token,
                    }
        if item is None:
            continue
        seen_key = (
            str(item["company"]),
            int(item["direction"]),
            float(item["amount"]),
            str(item["unit"]),
            str(item["format_tag"]),
            str(item.get("punctuation_token") or ""),
        )
        if seen_key in seen:
            continue
        seen.add(seen_key)
        results.append(item)

    return results


def extract_company_detail_section(text: str) -> str:
    """提取企业明细区间。

    只截取“主要是/主要为/主要由/主要原因是”之后的内容，
    避免把段落主句中的“本期增加/减少”误识别为企业明细。
    """

    match = DETAIL_START_PATTERN.search(text)
    if not match:
        fallback_match = re.search(r"([^,，。；]{0,50}(?:公司|银行|集团)[^,，。；]{0,12}(?:增加|减少|增|减)\s*[0-9])", text)
        if not fallback_match:
            return ""
        return text[fallback_match.start(1) :].strip(",，。； ")
    return text[match.end() :].strip(",，。； ")


def strip_company_detail_section(text: str) -> str:
    normalized = str(text or "")
    if not normalized:
        return ""
    match = DETAIL_START_PATTERN.search(normalized)
    if match:
        return normalized[: match.start()].strip()
    fallback_match = re.search(r"([^,，。；]{0,50}(?:公司|银行|集团)[^,，。；]{0,12}(?:增加|减少|增|减)\s*[0-9])", normalized)
    return normalized[: fallback_match.start(1)].strip() if fallback_match else normalized


def detect_calc_scope_hint(text: str) -> str:
    """识别单独说明行中的计算口径提示。

    返回值说明：
    - `foreign`: 使用本外币差值
    - `usd_total`: 使用美元合计差值
    - `rmb`: 使用人民币差值
    - ``: 未识别到口径提示
    """

    normalized = re.sub(r"\s+", "", str(text or ""))
    if not normalized:
        return ""
    if "本外币" in normalized:
        return "foreign"
    if "美元合计" in normalized or "外币" in normalized:
        return "usd_total"
    if "人民币" in normalized:
        return "rmb"
    return ""
