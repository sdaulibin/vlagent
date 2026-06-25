"""PDF 页 span 按坐标分行排列，并可选调用大模型还原 HTML 表格。"""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal

from financial_compare.document.item import Row
from financial_compare.table.span_bbox import (
    all_row_geometries_from_html,
    build_table_span_matrix,
    script_aware_texts_match,
)

TABLE_ANALYST_SYSTEM = (
"""你是银行、金融、审计相关领域的专家，精通H股会计准则、审计准则、相关法律法规、领域名词。请根据下面的输入，判断哪些文本span应该纳入表格，就把他们填充到表格中，用HTML的<table border>返回表格。

# 要求
1. 返回HTML的<table border>，用<th>标签表示表头，用<td>标签表示表体。不要输出markdown代码块。
2. 填入表格cell的文本必须使用文档原文并且仅出现一次，不得修改，不得切分但可以垂直同列拼接。
3. 如果输入可以拆分为多个表格，就进行拆分。

# 输入示例
[y≈186] '固定拨款'@(357,410) | '扣除所得'@(509,547)
[y≈200] '年薪及'@(306,338) | '退休金'@(377,410) | '其他'@(457,476) | '稅前的'@(518,547)
[y≈214] '姓名'@(71,90) | '袍金'@(244,264) | '每月绩效'@(296,338) | '比例拨款'@(357,410) | '各种福利'@(438,476) | '薪酬总额'@(509,547)
[y≈228] '-------------------------'@(65,198) | '-------------'@(198,269) | '-------------'@(269,340) | '-------------'@(340,411) | '-------------'@(411,482) | '-------------'@(482,553)

说明：
- [y≈186] : 是表格行的垂直坐标
- '固定拨款'@(357,410) : 是一个完整的候选单元格，'固定拨款'是候选单元格的文本，@(357,410) 是候选单元格的左、右坐标。
- '-------------'@(340,411) : 是表格水平边框， 确定了输出列的左右边界。表格水平边框只是表格的**视觉辅助线**，不要在<table>中输出。
- 如果两个候选单元格之间有明显的水平空白，比如'年薪及'@(306,338)的右边界和'退休金'@(377,410)的左边界之间有明显的水平空白，并且垂直来看，'年薪及'@(306,338)和'每月绩效'@(296,338)的右边界对齐，那么即使'年薪及'、'退休金'有一定语义相关性，也不能输出到一个<th>或<td>单元格。这个单元格的输出就是<th>年薪及每月绩效</th>。
- 如果几个候选单元格在垂直方向上重叠，并且有语义相关性，就可以输出到一个<th>或<td>单元格。比如'固定拨款'@(357,410)、'退休金'@(377,410) 、'比例拨款'@(357,410)在垂直方向上坐标基本重叠，所以同属一列。他们的文本内容又有相关性，所以可以合并为一个候选单元格，并且他们属于'-------------'@(340,411)这一列。这个单元格的输出就是<th>定額供款退休金比例拨款</th>。
- 完整输出是：<th>姓名</th><th>袍金</th><th>年薪及每月绩效</th><th>固定拨款退休金比例拨款</th><th>其他各种福利</th><th>扣除所得稅前的薪酬总额</th>
"""
)

DEFAULT_DASH_WIDTH_PT = 5.0
MIN_DASH_COUNT = 3

# 与 PDFParser 基线及表格流程统一的布局参数
ROW_Y_TOL = 3.0
DRAWING_WIDTH_RATIO_MIN = 1.5
MAX_TABLE_DRAWING_ROWS = 20
MIN_TABLE_COL_SEGMENTS = 3
MIN_SAME_COL_SEGMENT_ROWS = 2
JOIN_SMALL_GAP_RATIO = 1.0
JOIN_COLUMN_GAP_RATIO = 1.4
JOIN_MIN_COLUMN_GAP = 8.0


def estimate_char_width(page: Any) -> float:
    """从页内文本 span 估算单字符宽度（pt），无文本时返回 DEFAULT_DASH_WIDTH_PT。"""
    widths: list[float] = []
    blocks = page.get_text("dict").get("blocks", [])
    for block in blocks:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text or not text.strip():
                    continue
                bbox = span.get("bbox", [0, 0, 0, 0])
                char_w = (float(bbox[2]) - float(bbox[0])) / len(text)
                if char_w > 0:
                    widths.append(char_w)
    if not widths:
        return DEFAULT_DASH_WIDTH_PT
    widths.sort()
    return widths[len(widths) // 2]


def drawing_placeholder(width_pt: float, char_width_pt: float) -> str:
    """按线段宽度生成等比例数量的短横占位符。"""
    if char_width_pt <= 0:
        char_width_pt = DEFAULT_DASH_WIDTH_PT
    count = max(MIN_DASH_COUNT, round(width_pt / char_width_pt))
    return "-" * count


def _span_dict_from_bbox(text: str, bbox: list[float]) -> dict[str, Any]:
    return {
        "text": text,
        "x": round(float(bbox[0]), 2),
        "x1": round(float(bbox[2]), 2),
        "y": round(float(bbox[1]), 2),
        "bbox": [
            float(bbox[0]),
            float(bbox[1]),
            float(bbox[2]),
            float(bbox[3]),
        ],
    }


def extract_page_spans(page: Any, *, full_bbox: bool = False) -> list[dict[str, Any]]:
    """提取单页所有非空 span；full_bbox=True 时保留完整 bbox 供基线行拼接。"""
    spans: list[dict[str, Any]] = []
    blocks = page.get_text("dict").get("blocks", [])
    for block in blocks:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text or not text.strip():
                    continue
                bbox = span.get("bbox", [0, 0, 0, 0])
                normalized = text.strip() if full_bbox else text
                item = _span_dict_from_bbox(normalized, bbox)
                if full_bbox:
                    spans.append(item)
                else:
                    spans.append({k: v for k, v in item.items() if k != "bbox"})
    return spans


def extract_page_spans_with_bbox(page: Any) -> list[dict[str, Any]]:
    """提取单页所有非空 span，含完整 bbox，供 PDF 基线行拼接使用。"""
    return extract_page_spans(page, full_bbox=True)


def extract_page_drawings(
    page: Any,
    *,
    char_width_pt: float | None = None,
) -> list[dict[str, Any]]:
    """提取单页 drawing 线段，转为伪 span（短横数量按线段宽度等比填充）。"""
    dash_width = char_width_pt if char_width_pt is not None else estimate_char_width(page)
    drawings: list[dict[str, Any]] = []
    for path in page.get_drawings():
        for item in path.get("items", []):
            if item[0] != "l":
                continue
            p1, p2 = item[1], item[2]
            x0 = min(float(p1.x), float(p2.x))
            width = abs(float(p2.x) - float(p1.x))
            if width < 1:
                continue
            drawings.append(
                {
                    "text": drawing_placeholder(width, dash_width),
                    "x": round(x0, 2),
                    "x1": round(x0 + width, 2),
                    "y": round(float(p1.y), 2),
                    "width": round(width, 2),
                    "kind": "drawing",
                }
            )
    return drawings


def merge_drawing_rows(
    text_rows: list[list[dict[str, Any]]],
    drawing_spans: list[dict[str, Any]],
    y_tol: float,
) -> list[list[dict[str, Any]]]:
    """文本分行完成后，将 drawing 行按 y 插入序列，不并入已有文本行。"""
    if not drawing_spans:
        return text_rows

    drawing_rows = group_spans_into_rows(drawing_spans, y_tol=y_tol)
    merged = text_rows + drawing_rows
    merged.sort(key=lambda row: row[0]["y"] if row else 0.0)
    return merged


def group_spans_into_rows(spans: list[dict[str, Any]], y_tol: float) -> list[list[dict[str, Any]]]:
    """先垂直分行（y 容差），行内再按 x 从左到右排序。"""
    if not spans:
        return []

    sorted_spans = sorted(spans, key=lambda s: (s["y"], s["x"]))
    rows: list[list[dict[str, Any]]] = []
    current_row: list[dict[str, Any]] = [sorted_spans[0]]
    current_y = sorted_spans[0]["y"]

    for span in sorted_spans[1:]:
        if abs(span["y"] - current_y) <= y_tol:
            current_row.append(span)
        else:
            rows.append(sorted(current_row, key=lambda s: s["x"]))
            current_row = [span]
            current_y = span["y"]

    rows.append(sorted(current_row, key=lambda s: s["x"]))
    return rows


def merge_small_gap_spans_in_row(
    row: list[dict[str, Any]],
    char_width_pt: float,
) -> list[dict[str, Any]]:
    """同一行内，相邻 span 间隙严格小于 1 字符宽时合并，并修正 bbox。"""
    if not row:
        return []
    if char_width_pt <= 0:
        char_width_pt = DEFAULT_DASH_WIDTH_PT

    merged: list[dict[str, Any]] = [dict(row[0])]
    for span in row[1:]:
        prev = merged[-1]
        gap = span["x"] - prev["x1"]
        if gap < char_width_pt:
            prev["text"] = prev["text"] + span["text"]
            prev["x"] = min(prev["x"], span["x"])
            prev["x1"] = max(prev["x1"], span["x1"])
        else:
            merged.append(dict(span))
    return merged


def merge_small_gap_spans_in_rows(
    rows: list[list[dict[str, Any]]],
    char_width_pt: float,
) -> list[list[dict[str, Any]]]:
    """对所有文本行做相邻小间隙 span 合并，供大模型与日志使用。"""
    return [merge_small_gap_spans_in_row(row, char_width_pt) for row in rows]


def _drawing_row_width_ratio(row: list[dict[str, Any]]) -> float | None:
    widths: list[float] = []
    for item in row:
        if "width" in item:
            widths.append(float(item["width"]))
        else:
            widths.append(float(item["x1"]) - float(item["x"]))
    widths = [w for w in widths if w > 0]
    if len(widths) < 2:
        return None
    return max(widths) / min(widths)


def _qualifying_drawing_rows(
    page: Any,
    *,
    y_tol: float = ROW_Y_TOL,
) -> list[list[dict[str, Any]]]:
    char_width = estimate_char_width(page)
    drawings = extract_page_drawings(page, char_width_pt=char_width)
    if not drawings:
        return []
    drawing_rows = group_spans_into_rows(drawings, y_tol=y_tol)
    qualifying: list[list[dict[str, Any]]] = []
    for row in drawing_rows:
        if len(row) < 2:
            continue
        ratio = _drawing_row_width_ratio(row)
        if ratio is not None and ratio >= DRAWING_WIDTH_RATIO_MIN:
            qualifying.append(row)
    return qualifying


def detect_table_page(page: Any, *, y_tol: float = ROW_Y_TOL) -> bool:
    """当前页是否存在多段、长短不一的表格横线 drawing。"""
    from collections import Counter

    char_width = estimate_char_width(page)
    drawings = extract_page_drawings(page, char_width_pt=char_width)
    if not drawings:
        return False
    drawing_rows = group_spans_into_rows(drawings, y_tol=y_tol)
    if len(drawing_rows) < 2 or len(drawing_rows) > MAX_TABLE_DRAWING_ROWS:
        return False
    qualifying = _qualifying_drawing_rows(page, y_tol=y_tol)
    if len(qualifying) < 2:
        return False
    seg_counts = Counter(len(row) for row in qualifying)
    for segment_count, frequency in seg_counts.items():
        if segment_count >= MIN_TABLE_COL_SEGMENTS and frequency >= MIN_SAME_COL_SEGMENT_ROWS:
            return True
    return False


def drawing_anchor_range(page: Any, *, y_tol: float = ROW_Y_TOL) -> tuple[float, float]:
    """首/末 qualifying drawing 行的 y，仅作上下候选扫描锚点。"""
    qualifying = _qualifying_drawing_rows(page, y_tol=y_tol)
    if not qualifying:
        raise ValueError("当前页无 qualifying drawing 行，无法定位表格锚点")
    ys = [row[0]["y"] for row in qualifying if row]
    return min(ys), max(ys)


@dataclass(frozen=True)
class TablePageLayout:
    """表格页布局：drawing 锚点 + 上下 pipe 候选行 + 普通正文。"""

    drawing_anchor_top: float
    drawing_anchor_bottom: float
    header_candidates: list[dict[str, Any]]
    plain_above: list[dict[str, Any]]
    footer_candidates: list[dict[str, Any]]
    plain_below: list[dict[str, Any]]


def _row_ref_y(row: list[dict[str, Any]]) -> float:
    return float(row[0]["y"])


def _find_row_index_near_y(
    rows: list[list[dict[str, Any]]],
    y: float,
    *,
    y_tol: float,
) -> int | None:
    best_index: int | None = None
    best_distance = y_tol + 1.0
    for index, row in enumerate(rows):
        distance = abs(_row_ref_y(row) - y)
        if distance <= y_tol and distance < best_distance:
            best_distance = distance
            best_index = index
    return best_index


def build_merged_page_rows(
    page: Any,
    *,
    y_tol: float = ROW_Y_TOL,
) -> list[list[dict[str, Any]]]:
    """整页文本 span + drawing 按 y 合并分行。"""
    char_width = estimate_char_width(page)
    spans = extract_page_spans(page, full_bbox=True)
    drawings = extract_page_drawings(page, char_width_pt=char_width)
    text_rows = group_spans_into_rows(spans, y_tol=y_tol)
    text_rows = merge_small_gap_spans_in_rows(text_rows, char_width)
    return merge_drawing_rows(text_rows, drawings, y_tol=y_tol)


def select_table_llm_rows(
    merged_rows: list[list[dict[str, Any]]],
    layout: TablePageLayout,
    *,
    y_tol: float = ROW_Y_TOL,
) -> list[list[dict[str, Any]]]:
    """在 y 排序行序列上，由锚点与候选行索引截取 LLM 输入（不用几何上下界框选）。"""
    if not merged_rows:
        return []

    first_idx = _find_row_index_near_y(
        merged_rows, layout.drawing_anchor_top, y_tol=y_tol
    )
    last_idx = _find_row_index_near_y(
        merged_rows, layout.drawing_anchor_bottom, y_tol=y_tol
    )
    if first_idx is None or last_idx is None:
        raise ValueError("无法在合并行中定位 drawing 锚点")

    start_idx = first_idx
    for line in layout.header_candidates:
        bbox = line.get("bbox", [0.0, 0.0, 0.0, 0.0])
        idx = _find_row_index_near_y(merged_rows, float(bbox[1]), y_tol=y_tol)
        if idx is not None:
            start_idx = min(start_idx, idx)

    end_idx = last_idx
    for line in layout.footer_candidates:
        bbox = line.get("bbox", [0.0, 0.0, 0.0, 0.0])
        idx = _find_row_index_near_y(merged_rows, float(bbox[1]), y_tol=y_tol)
        if idx is not None:
            end_idx = max(end_idx, idx)

    if start_idx > end_idx:
        raise ValueError("表格 LLM 行区间无效")
    return merged_rows[start_idx : end_idx + 1]


def _strip_html_wrapper(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
    start = stripped.lower().find("<table")
    if start > 0:
        stripped = stripped[start:]
    end = stripped.lower().rfind("</table>")
    if end >= 0:
        stripped = stripped[: end + len("</table>")]
    return stripped


def html_table_to_rows(
    html: str,
    *,
    implicit_first_row_header: bool = True,
) -> list[tuple[list[str], str]]:
    """将 HTML <table> 解析为 (cells, row_type) 列表。

    ``row_type`` 为 ``header``（``th`` / ``thead`` 内行）或 ``body``。
    若 ``implicit_first_row_header`` 为真且 HTML 未区分 th/td，首行标为 header，其余 body。
    KV 虚拟表重建应传 ``implicit_first_row_header=False``（无表头，全为 body 行）。
    """

    class _TableHTMLParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.rows: list[tuple[list[str], str]] = []
            self._current_row: list[str] | None = None
            self._current_row_type: str = "body"
            self._in_cell = False
            self._cell_parts: list[str] = []
            self._thead_depth = 0
            self._row_has_th = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == "thead":
                self._thead_depth += 1
            elif tag == "tr":
                self._current_row = []
                self._row_has_th = False
                self._current_row_type = "header" if self._thead_depth > 0 else "body"
            elif tag in ("td", "th"):
                self._in_cell = True
                self._cell_parts = []
                if tag == "th":
                    self._row_has_th = True

        def handle_endtag(self, tag: str) -> None:
            if tag in ("td", "th"):
                self._in_cell = False
                if self._current_row is not None:
                    self._current_row.append("".join(self._cell_parts).strip())
            elif tag == "tr" and self._current_row is not None:
                row_type = self._current_row_type
                if self._row_has_th:
                    row_type = "header"
                if self._current_row:
                    self.rows.append((self._current_row, row_type))
                self._current_row = None
            elif tag == "thead" and self._thead_depth > 0:
                self._thead_depth -= 1

        def handle_data(self, data: str) -> None:
            if self._in_cell:
                self._cell_parts.append(data)

    parser = _TableHTMLParser()
    parser.feed(_strip_html_wrapper(html))
    rows = parser.rows
    if (
        implicit_first_row_header
        and rows
        and not any(row_type == "header" for _, row_type in rows)
    ):
        cells, _ = rows[0]
        rows[0] = (cells, "header")
    return rows


def prepare_table_region_rows(
    page: Any,
    layout: TablePageLayout,
    *,
    y_tol: float = ROW_Y_TOL,
) -> list[list[dict[str, Any]]]:
    """按布局在 y 排序行序列上截取 LLM 输入行。"""
    merged_rows = build_merged_page_rows(page, y_tol=y_tol)
    return select_table_llm_rows(merged_rows, layout, y_tol=y_tol)


def _table_region_bbox(page: Any, layout: TablePageLayout) -> list[float]:
    """由 drawing 锚点与上下候选行估算表格区域 bbox。"""
    page_rect = page.rect
    x0 = float(page_rect.x0)
    x1 = float(page_rect.x1)
    y0 = float(layout.drawing_anchor_top)
    y1 = float(layout.drawing_anchor_bottom)

    for line in (
        *layout.header_candidates,
        *layout.footer_candidates,
        *layout.plain_above,
        *layout.plain_below,
    ):
        bbox = line.get("bbox", [0.0, 0.0, 0.0, 0.0])
        if len(bbox) >= 4:
            x0 = min(x0, float(bbox[0]))
            y0 = min(y0, float(bbox[1]))
            x1 = max(x1, float(bbox[2]))
            y1 = max(y1, float(bbox[3]))

    return [x0, y0, x1, y1]


def extract_table_block(
    page: Any,
    layout: TablePageLayout,
    *,
    y_tol: float = ROW_Y_TOL,
) -> tuple[str, list[Row], list[float]]:
    """表格 LLM 输入行 → HTML → ``Row`` 列表与区域 bbox。"""
    llm_rows = prepare_table_region_rows(page, layout, y_tol=y_tol)
    prompt, flat_spans = build_table_span_matrix(llm_rows)
    from financial_compare.llm.model import chat

    html = chat(TABLE_ANALYST_SYSTEM, prompt)
    parsed_rows = html_table_to_rows(html)
    if not parsed_rows:
        raise ValueError("LLM 返回的 HTML 表格未解析出任何行")

    geometries = all_row_geometries_from_html(
        parsed_rows,
        flat_spans,
        texts_match=script_aware_texts_match,
    )
    rows: list[Row] = []
    for row_index, ((cells, row_type), (row_bbox, cell_bboxes)) in enumerate(
        zip(parsed_rows, geometries, strict=True)
    ):
        typed_row_type: Literal["header", "body"] = (
            "header" if row_type == "header" else "body"
        )
        rows.append(
            Row(
                content="|".join(cells),
                row_type=typed_row_type,
                row_index=row_index,
                bbox=row_bbox,
                cell_bboxes=cell_bboxes,
            )
        )

    return html, rows, _table_region_bbox(page, layout)


def rows_to_html_table(
    rows: list[list[dict[str, Any]]],
    *,
    user_prompt: str | None = None,
) -> str:
    """将坐标分行摘要交给大模型，返回 HTML <table>。"""
    from financial_compare.llm.model import chat

    if user_prompt is None:
        user_prompt, _ = build_table_span_matrix(rows)
    return chat(TABLE_ANALYST_SYSTEM, user_prompt)
