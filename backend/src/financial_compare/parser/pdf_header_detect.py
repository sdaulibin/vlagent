"""PDF 页眉/页码自动识别（统计规则 + 可选 LLM 兜底）。"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz

logger = logging.getLogger(__name__)

DEFAULT_SAMPLE_PAGES = 5
HEADER_SIM_THRESHOLD = 0.90
_FOOTER_MAX_LEN = 40
_PAGE_NUM_RE = re.compile(r"^\s*[-–—]?\s*\d+\s*[-–—]?\s*$")


@dataclass
class PdfMarginProfile:
    header_norm_keys: frozenset[str] = frozenset()
    footer_templates: frozenset[str] = frozenset()
    config_header_keys: frozenset[str] = field(default_factory=frozenset)

    def is_header(self, text: str) -> bool:
        key = _normalize_margin_key(text)
        if not key:
            return False
        if key in self.config_header_keys:
            return True
        for header_key in self.header_norm_keys:
            if header_key in key or key in header_key:
                return True
            if _line_similarity(key, header_key) >= HEADER_SIM_THRESHOLD:
                return True
        return False

    def is_footer(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        if len(stripped) > _FOOTER_MAX_LEN:
            return False
        if not re.search(r"\d", stripped):
            return False
        template = _line_template(stripped)
        if template in self.footer_templates:
            return True
        if _PAGE_NUM_RE.match(stripped):
            return True
        return False


def _normalize_margin_key(text: str) -> str:
    if not text:
        return ""
    t = text.replace("|", "").replace("｜", "")
    t = re.sub(r"\d+", "", t)
    return re.sub(r"\s+", "", t, flags=re.UNICODE)


def _line_template(text: str) -> str:
    t = re.sub(r"\d+", "#", text)
    t = unicodedata.normalize("NFKC", t)
    return re.sub(r"\s+", "", t)


def _line_similarity(a: str, b: str) -> float:
    na, nb = _normalize_margin_key(a), _normalize_margin_key(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.92
    sa, sb = set(na), set(nb)
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def detect_margin_profile_from_lines(
    first_lines: list[str],
    last_lines: list[str],
    *,
    config_header_keys: frozenset[str] | None = None,
) -> PdfMarginProfile:
    header_keys: set[str] = set()
    if len(first_lines) >= 2:
        counts: Counter[str] = Counter()
        for ref in first_lines:
            if not ref.strip():
                continue
            norm_ref = _normalize_margin_key(ref)
            if not norm_ref:
                continue
            matches = sum(
                1 for other in first_lines if _line_similarity(ref, other) >= HEADER_SIM_THRESHOLD
            )
            if matches >= max(2, int(len(first_lines) * 0.6)):
                counts[norm_ref] = matches
        if counts:
            header_keys.add(counts.most_common(1)[0][0])

    footer_templates: set[str] = set()
    templates: Counter[str] = Counter()
    for line in last_lines:
        stripped = line.strip()
        if not stripped or len(stripped) > _FOOTER_MAX_LEN:
            continue
        if not re.search(r"\d", stripped):
            continue
        templates[_line_template(stripped)] += 1
    if templates:
        common, count = templates.most_common(1)[0]
        if count >= max(2, int(len(last_lines) * 0.5)):
            footer_templates.add(common)

    return PdfMarginProfile(
        header_norm_keys=frozenset(header_keys),
        footer_templates=frozenset(footer_templates),
        config_header_keys=config_header_keys or frozenset(),
    )


def collect_sample_page_lines(
    pdf_path: str | Path,
    *,
    sample_pages: int = DEFAULT_SAMPLE_PAGES,
) -> tuple[list[str], list[str]]:
    from financial_compare.parser.extract.pdf_parser import PDFParser

    parser = PDFParser()
    first_lines: list[str] = []
    last_lines: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page_num, page in enumerate(doc, start=1):
            if page_num > sample_pages:
                break
            lines = parser.extract_page_lines(page)
            texts = [ln["text"] for ln in lines if ln.get("text", "").strip()]
            if texts:
                first_lines.append(texts[0])
                last_lines.append(texts[-1])
    return first_lines, last_lines


def detect_margin_profile(
    pdf_path: str | Path,
    *,
    config_header_keys: frozenset[str] | None = None,
    sample_pages: int = DEFAULT_SAMPLE_PAGES,
    use_llm_fallback: bool = True,
) -> PdfMarginProfile:
    first_lines, last_lines = collect_sample_page_lines(
        pdf_path, sample_pages=sample_pages
    )
    profile = detect_margin_profile_from_lines(
        first_lines,
        last_lines,
        config_header_keys=config_header_keys,
    )
    if use_llm_fallback and not profile.header_norm_keys and not profile.footer_templates:
        llm_profile = _llm_detect_margins(first_lines, last_lines)
        if llm_profile is not None:
            profile = PdfMarginProfile(
                header_norm_keys=profile.header_norm_keys | llm_profile.header_norm_keys,
                footer_templates=profile.footer_templates | llm_profile.footer_templates,
                config_header_keys=profile.config_header_keys,
            )
    return profile


def _llm_detect_margins(
    first_lines: list[str],
    last_lines: list[str],
) -> PdfMarginProfile | None:
    if not first_lines and not last_lines:
        return None
    try:
        from financial_compare.llm.model import chat
    except Exception:
        return None

    payload = {
        "first_lines_per_page": first_lines[:DEFAULT_SAMPLE_PAGES],
        "last_lines_per_page": last_lines[:DEFAULT_SAMPLE_PAGES],
    }
    system = (
        "你是 PDF 版式分析助手。根据多页的首行/末行样本，识别重复页眉与页码行。"
        "返回 JSON："
        '{"header_substrings":["..."], "footer_templates":["- # -"]} '
        "footer_templates 中用 # 代替数字。"
    )
    try:
        raw = chat(system, json.dumps(payload, ensure_ascii=False))
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text.strip())
        parsed = json.loads(text)
    except Exception as exc:
        logger.debug("LLM 页眉页码识别失败: %s", exc)
        return None

    header_keys: set[str] = set()
    for item in parsed.get("header_substrings") or []:
        key = _normalize_margin_key(str(item))
        if key:
            header_keys.add(key)

    footer_templates: set[str] = set()
    for item in parsed.get("footer_templates") or []:
        template = _line_template(str(item))
        if template:
            footer_templates.add(template)

    if not header_keys and not footer_templates:
        return None
    return PdfMarginProfile(
        header_norm_keys=frozenset(header_keys),
        footer_templates=frozenset(footer_templates),
    )


def load_config_header_keys() -> frozenset[str]:
    from financial_compare.app_config import get_app_config
    from financial_compare.parser.extract.pdf_parser import PDFParser

    raw = get_app_config().get("headers") or []
    keys: set[str] = set()
    for item in raw:
        if item is None:
            continue
        key = PDFParser._normalize_header_key(str(item))
        if key:
            keys.add(key)
    return frozenset(keys)


def extract_page_line_texts(
    pdf_path: str | Path,
    page_num: int,
    *,
    margin_profile: PdfMarginProfile | None = None,
) -> list[str]:
    from financial_compare.parser.extract.pdf_parser import PDFParser

    parser = PDFParser(margin_profile=margin_profile)
    with fitz.open(pdf_path) as doc:
        if page_num < 1 or page_num > doc.page_count:
            raise ValueError(f"PDF page={page_num} 超出范围（共 {doc.page_count} 页）")
        page = doc[page_num - 1]
        lines = parser.extract_page_lines(page)
    return [ln["text"] for ln in lines if ln.get("text")]
