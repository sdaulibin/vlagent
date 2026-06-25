"""PDF 页锚点与 DOCX 文本流对齐（DOCX 无页概念）。"""

from __future__ import annotations

import logging
from typing import Callable

from financial_compare.compare.utils.zh_script import norm_for_compare, trad_to_simp
from financial_compare.document.item import DocumentItem, Row, TableBlock, TextLine, TextLoc, TableLoc

logger = logging.getLogger(__name__)

ANCHOR_MIN_LINES = 3
ANCHOR_MAX_LINES = 5
ANCHOR_MIN_CHARS = 4
MATCH_THRESHOLD = 0.80


def norm_anchor_text(text: str) -> str:
    base = norm_for_compare(text, side="a")
    return trad_to_simp(base)


def text_overlap_ratio(a: str, b: str) -> float:
    na, nb = norm_anchor_text(a), norm_anchor_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.85 + 0.15 * min(len(na), len(nb)) / max(len(na), len(nb))
    sa, sb = set(na), set(nb)
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def item_plain_text(item: DocumentItem) -> str:
    if isinstance(item, TextLine):
        return item.text
    return " ".join(row.content for row in item.rows)


def merge_items_text(items: list[DocumentItem], start: int, count: int) -> str:
    parts: list[str] = []
    for item in items[start : start + count]:
        text = item_plain_text(item).strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


def pick_start_anchor_lines(
    page_lines: list[str],
    *,
    is_header: Callable[[str], bool],
    is_footer: Callable[[str], bool],
    min_lines: int = ANCHOR_MIN_LINES,
    max_lines: int = ANCHOR_MAX_LINES,
) -> list[str]:
    picked: list[str] = []
    for line in page_lines:
        text = line.strip()
        if not text or len(text) < ANCHOR_MIN_CHARS:
            continue
        if is_header(text) or is_footer(text):
            continue
        picked.append(text)
        if len(picked) >= max_lines:
            break
    if len(picked) < min_lines:
        raise ValueError(
            f"PDF 起始页可用锚点行不足 {min_lines} 行（过滤页眉页码后仅 {len(picked)} 行）"
        )
    return picked


def pick_end_anchor_lines(
    page_lines: list[str],
    *,
    is_header: Callable[[str], bool],
    is_footer: Callable[[str], bool],
    min_lines: int = ANCHOR_MIN_LINES,
    max_lines: int = ANCHOR_MAX_LINES,
) -> list[str]:
    picked: list[str] = []
    for line in reversed(page_lines):
        text = line.strip()
        if not text or len(text) < ANCHOR_MIN_CHARS:
            continue
        if is_header(text) or is_footer(text):
            continue
        picked.insert(0, text)
        if len(picked) >= max_lines:
            break
    if len(picked) < min_lines:
        return []
    return picked


def find_docx_anchor_index(
    items: list[DocumentItem],
    anchor_lines: list[str],
    *,
    start_from: int = 0,
    min_ratio: float = MATCH_THRESHOLD,
) -> int | None:
    if not anchor_lines or not items:
        return None
    anchor_text = "\n".join(anchor_lines)
    window = len(anchor_lines)
    best_idx: int | None = None
    best_score = 0.0
    for i in range(start_from, len(items)):
        for w in range(window, min(window + 3, len(items) - i + 1)):
            candidate = merge_items_text(items, i, w)
            score = text_overlap_ratio(anchor_text, candidate)
            if score >= min_ratio and score > best_score:
                best_score = score
                best_idx = i
    return best_idx


def slice_document_items(
    items: list[DocumentItem],
    start: int,
    end: int | None = None,
) -> list[DocumentItem]:
    sliced = items[start:end]
    return reindex_document_items(sliced)


def reindex_document_items(items: list[DocumentItem]) -> list[DocumentItem]:
    stream_index = 0
    table_index = 0
    out: list[DocumentItem] = []
    for item in items:
        if isinstance(item, TextLine):
            out.append(
                TextLine(
                    text=item.text,
                    loc=TextLoc(
                        stream_index=stream_index,
                        section_path=item.loc.section_path,
                        element_index=item.loc.element_index,
                        page=item.loc.page,
                        bbox=item.loc.bbox,
                        spans=item.loc.spans,
                    ),
                )
            )
            stream_index += 1
        elif isinstance(item, TableBlock):
            out.append(
                TableBlock(
                    html=item.html,
                    rows=item.rows,
                    loc=TableLoc(
                        stream_index=stream_index,
                        table_index=table_index,
                        section_path=item.loc.section_path,
                        element_index=item.loc.element_index,
                        page=item.loc.page,
                        page_end=item.loc.page_end,
                        bbox=item.loc.bbox,
                    ),
                )
            )
            stream_index += 1
            table_index += 1
    return out


def align_docx_to_pdf_anchors(
    docx_items: list[DocumentItem],
    *,
    start_anchor_lines: list[str],
    end_anchor_lines: list[str] | None,
) -> list[DocumentItem]:
    start_idx = find_docx_anchor_index(docx_items, start_anchor_lines)
    if start_idx is None:
        # 锚点匹配失败时不中止比对：用户可能编辑过文档导致起始内容偏移。
        # fallback 到文档开头，后续章节配对 + 内容对齐会接管定位。
        logger.warning(
            "DOCX 起始锚点匹配失败（简繁归一重合率未达阈值），"
            "回退到文档开头进行比对"
        )
        return slice_document_items(docx_items, 0, None)

    end_idx: int | None = None
    if end_anchor_lines:
        end_idx = find_docx_anchor_index(
            docx_items,
            end_anchor_lines,
            start_from=start_idx + 1,
        )
        if end_idx is None:
            logger.warning("DOCX 结束锚点匹配失败，截断至文档末尾")

    return slice_document_items(docx_items, start_idx, end_idx)
