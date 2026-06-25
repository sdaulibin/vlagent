"""双文件 parse 前抽取：页码范围、DOCX 锚点对齐、混合类型 A=docx。"""

from __future__ import annotations

import logging
from pathlib import Path

from financial_compare.document.item import DocumentItem
from financial_compare.parser.docx_anchor import (
    align_docx_to_pdf_anchors,
    pick_end_anchor_lines,
    pick_start_anchor_lines,
)
from financial_compare.parser.extract.docx_parser import DOCXParser
from financial_compare.parser.extract.pdf_parser import PDFParser
from financial_compare.parser.page_range import PageRange, SidePageRange, normalize_docx_pdf_paths
from financial_compare.parser.pdf_header_detect import (
    PdfMarginProfile,
    detect_margin_profile,
    extract_page_line_texts,
    load_config_header_keys,
)

logger = logging.getLogger(__name__)


def extract_pdf_items(
    pdf_path: str | Path,
    *,
    page_range: SidePageRange,
    margin_profile: PdfMarginProfile | None = None,
) -> list[DocumentItem]:
    profile = margin_profile or detect_margin_profile(
        pdf_path,
        config_header_keys=load_config_header_keys(),
    )
    parser = PDFParser(margin_profile=profile)
    return parser.parse(pdf_path, page_range=page_range)


def extract_docx_items(docx_path: str | Path) -> list[DocumentItem]:
    return DOCXParser().parse(docx_path)


def extract_docx_pdf_pair_items(
    docx_path: str | Path,
    pdf_path: str | Path,
    *,
    page_range: PageRange,
) -> tuple[list[DocumentItem], list[DocumentItem]]:
    margin_profile = detect_margin_profile(
        pdf_path,
        config_header_keys=load_config_header_keys(),
    )
    pdf_side = page_range.for_side("b")
    pdf_items = extract_pdf_items(
        pdf_path,
        page_range=pdf_side,
        margin_profile=margin_profile,
    )

    docx_items = extract_docx_items(docx_path)
    if not page_range.specified:
        return docx_items, pdf_items

    start_page, end_page = pdf_side.clamp(_pdf_page_count(pdf_path))
    start_lines = extract_page_line_texts(
        pdf_path, start_page, margin_profile=margin_profile
    )
    is_header = margin_profile.is_header
    is_footer = margin_profile.is_footer
    start_anchors = pick_start_anchor_lines(
        start_lines,
        is_header=is_header,
        is_footer=is_footer,
    )

    end_anchors: list[str] | None = None
    if page_range.specified and pdf_side.end is not None:
        end_lines = extract_page_line_texts(
            pdf_path, end_page, margin_profile=margin_profile
        )
        end_anchors = pick_end_anchor_lines(
            end_lines,
            is_header=is_header,
            is_footer=is_footer,
        )
        if not end_anchors:
            logger.warning("PDF 结束页可用锚点行不足，DOCX 将截断至末尾")

    docx_items = align_docx_to_pdf_anchors(
        docx_items,
        start_anchor_lines=start_anchors,
        end_anchor_lines=end_anchors,
    )
    return docx_items, pdf_items


def extract_pair_items(
    path_a: str | Path,
    path_b: str | Path,
    *,
    page_range: PageRange | None = None,
) -> tuple[list[DocumentItem], list[DocumentItem], bool]:
    """返回 (items_a, items_b, swapped)。混合类型时在 parse 阶段交换为 A=docx。"""
    pa, pb = Path(path_a), Path(path_b)
    ext_a, ext_b = pa.suffix.lower(), pb.suffix.lower()
    pr = page_range or PageRange.full()

    if ext_a == ".docx" and ext_b == ".docx":
        if pr.specified:
            logger.info("docx+docx 组合忽略页码参数")
        return extract_docx_items(pa), extract_docx_items(pb), False

    if ext_a == ".pdf" and ext_b == ".pdf":
        profile_a = detect_margin_profile(pa, config_header_keys=load_config_header_keys())
        profile_b = detect_margin_profile(pb, config_header_keys=load_config_header_keys())
        parser_a = PDFParser(margin_profile=profile_a)
        parser_b = PDFParser(margin_profile=profile_b)
        items_a = parser_a.parse(pa, page_range=pr.for_side("a"))
        items_b = parser_b.parse(pb, page_range=pr.for_side("b"))
        return items_a, items_b, False

    docx_path, pdf_path, swapped = normalize_docx_pdf_paths(pa, pb)
    if swapped:
        pr = pr.swap_sides()
        logger.info(
            "混合类型已在 parse 阶段交换: A=%s, B=%s；页码 A=%s-%s, B=%s-%s",
            docx_path.name,
            pdf_path.name,
            pr.a.start,
            pr.a.end,
            pr.b.start,
            pr.b.end,
        )
    items_a, items_b = extract_docx_pdf_pair_items(
        docx_path,
        pdf_path,
        page_range=pr,
    )
    return items_a, items_b, swapped


def extract_single_items(
    file_path: str | Path,
    *,
    page_range: PageRange | None = None,
    side: str = "a",
) -> list[DocumentItem]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    pr = page_range or PageRange.full()

    if suffix == ".docx":
        if pr.specified:
            logger.info("单文件 DOCX 忽略页码参数")
        return extract_docx_items(path)

    if suffix == ".pdf":
        side_range = pr.for_side(side)
        return extract_pdf_items(path, page_range=side_range)

    raise ValueError(f"不支持的文件扩展名: {suffix}")


def _pdf_page_count(pdf_path: str | Path) -> int:
    import fitz

    with fitz.open(pdf_path) as doc:
        return doc.page_count
