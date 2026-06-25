"""PDF 文本解析器，使用 PyMuPDF 提取 PDF 中的文本内容。"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from financial_compare.document.item import DocumentItem, Row, TableBlock, TableLoc, TextLine, TextLoc
from financial_compare.parser.page_range import SidePageRange
from financial_compare.parser.pdf_header_detect import PdfMarginProfile, load_config_header_keys
from financial_compare.table.span_layout import (
    JOIN_COLUMN_GAP_RATIO,
    JOIN_MIN_COLUMN_GAP,
    JOIN_SMALL_GAP_RATIO,
    ROW_Y_TOL,
    TablePageLayout,
    detect_table_page,
    drawing_anchor_range,
    extract_page_spans_with_bbox,
    extract_table_block,
    group_spans_into_rows,
)


class PDFParser:
    """PDF 文本解析器。

    使用 PyMuPDF 读取 PDF 文件中的所有文本，
    按 ``DocumentItem`` 混合流返回。
    支持根据 headers 配置过滤页眉文本。
    表格页在 block 基线产出后，对 drawing 区间做 LLM 表格替换。
    """

    def __init__(self, *, margin_profile: PdfMarginProfile | None = None) -> None:
        config_keys = load_config_header_keys()
        self.headers = list(config_keys)
        self._margin_profile = margin_profile
        self._stream_index = 0
        self._table_index = 0

    @staticmethod
    def _estimate_char_width(segments: list[dict]) -> float:
        """估算片段平均字符宽度，用于 gap 阈值自适应。"""
        widths: list[float] = []
        for seg in segments:
            text = seg.get("text", "")
            bbox = seg.get("bbox", [0, 0, 0, 0])
            compact = re.sub(r"\s+", "", text, flags=re.UNICODE)
            width = max(0.0, bbox[2] - bbox[0]) if len(bbox) >= 4 else 0.0
            if compact and width > 0:
                widths.append(width / len(compact))
        if not widths:
            return 10.0
        widths.sort()
        return widths[len(widths) // 2]

    def _join_segments_by_gap(
        self,
        segments: list[dict],
        *,
        small_gap_ratio: float = JOIN_SMALL_GAP_RATIO,
        column_gap_ratio: float = JOIN_COLUMN_GAP_RATIO,
        min_column_gap: float = JOIN_MIN_COLUMN_GAP,
    ) -> str:
        """按相邻片段 x 间距拼接文本，减少正文噪声分隔符。"""
        if not segments:
            return ""
        if len(segments) == 1:
            return segments[0].get("text", "")

        char_width = self._estimate_char_width(segments)
        small_gap = max(0.0, char_width * small_gap_ratio)
        column_gap = max(min_column_gap, char_width * column_gap_ratio)

        parts: list[str] = [segments[0].get("text", "")]
        prev_bbox = segments[0].get("bbox", [0, 0, 0, 0])
        for curr in segments[1:]:
            curr_text = curr.get("text", "")
            curr_bbox = curr.get("bbox", [0, 0, 0, 0])
            prev_x1 = prev_bbox[2] if len(prev_bbox) >= 4 else 0.0
            curr_x0 = curr_bbox[0] if len(curr_bbox) >= 4 else 0.0
            gap = curr_x0 - prev_x1

            if gap <= small_gap:
                sep = ""
            elif gap >= column_gap:
                sep = "|"
            else:
                sep = " "

            parts.append(sep)
            parts.append(curr_text)
            prev_bbox = curr_bbox

        return "".join(parts).strip()

    @staticmethod
    def _row_bbox(spans: list[dict[str, Any]]) -> list[float]:
        bboxes = [s["bbox"] for s in spans if s.get("bbox")]
        if not bboxes:
            return [0.0, 0.0, 0.0, 0.0]
        return [
            min(b[0] for b in bboxes),
            min(b[1] for b in bboxes),
            max(b[2] for b in bboxes),
            max(b[3] for b in bboxes),
        ]

    def extract_page_lines(self, page: Any) -> list[dict]:
        """单页 span 分行后一次 gap 拼接，产出带 bbox 的行列表。"""
        spans = extract_page_spans_with_bbox(page)
        if not spans:
            return []

        rows = group_spans_into_rows(spans, y_tol=ROW_Y_TOL)
        lines: list[dict] = []
        for row in rows:
            segments = sorted(row, key=lambda s: s["x"])
            text = self._join_segments_by_gap(segments)
            if not text:
                continue
            lines.append(
                {
                    "text": text,
                    "bbox": self._row_bbox(segments),
                    "spans": [
                        {
                            "text": str(s.get("text", "")),
                            "bbox": list(s["bbox"]) if s.get("bbox") else None,
                            "x": float(s.get("x", 0.0)),
                            "x1": float(s.get("x1", 0.0)),
                            "y": float(s.get("y", 0.0)),
                        }
                        for s in segments
                    ],
                }
            )
        return lines

    @staticmethod
    def _line_y0(line: dict) -> float:
        bbox = line.get("bbox", [0.0, 0.0, 0.0, 0.0])
        return float(bbox[1]) if len(bbox) >= 2 else 0.0

    @staticmethod
    def _normalize_for_table_match(text: str) -> str:
        """表格行严格匹配：去掉空白与标点，保留核心文字。"""
        return "".join(
            c
            for c in text
            if not c.isspace() and not unicodedata.category(c).startswith("P")
        )

    @classmethod
    def _pipe_row_core_parts(cls, text: str) -> list[str]:
        return [
            part
            for part in (cls._normalize_for_table_match(p) for p in text.split("|"))
            if part
        ]

    @classmethod
    def _pipe_row_strict_match(cls, candidate_row: str, table_row: str) -> bool:
        return cls._pipe_row_core_parts(candidate_row) == cls._pipe_row_core_parts(
            table_row
        )

    @classmethod
    def _collect_pipe_candidates(
        cls, lines: list[dict], *, downward: bool
    ) -> tuple[list[dict], list[dict]]:
        """收集连续含 | 的候选行；downward=False 自锚点向上，True 自锚点向下。"""
        if not lines:
            return [], []

        candidates: list[dict] = []
        for line in sorted(lines, key=cls._line_y0, reverse=not downward):
            if "|" not in line.get("text", ""):
                break
            candidates.append(line)
        if not downward:
            candidates.reverse()

        candidate_ids = {id(line) for line in candidates}
        plain = [line for line in lines if id(line) not in candidate_ids]
        return candidates, plain

    @classmethod
    def _recover_unused_pipe_candidates(
        cls,
        candidates: list[dict],
        table_rows: list[Row],
        *,
        from_table_end: bool,
    ) -> list[dict]:
        """候选行与表格 Row 严格匹配；from_table_end 决定自表尾或表首扫描。"""
        if not candidates:
            return []

        row_contents = [row.content for row in table_rows]
        table_ptr = len(row_contents) - 1 if from_table_end else 0
        for index, candidate in enumerate(candidates):
            if from_table_end:
                scan = range(table_ptr, -1, -1)
            else:
                scan = range(table_ptr, len(row_contents))
            for row_index in scan:
                if cls._pipe_row_strict_match(
                    candidate["text"], row_contents[row_index]
                ):
                    table_ptr = row_index - 1 if from_table_end else row_index + 1
                    if index == 0:
                        return []
                    return candidates[:index]

        return list(candidates)

    def resolve_table_page_layout(
        self, page: Any, lines: list[dict]
    ) -> TablePageLayout | None:
        """表格页布局：drawing 锚点 + 上下 pipe 候选行；非表格页或无法定位锚点时返回 None。"""
        if not detect_table_page(page):
            return None

        try:
            anchor_top, anchor_bottom = drawing_anchor_range(page)
        except ValueError:
            return None

        above = [ln for ln in lines if self._line_y0(ln) < anchor_top]
        header_candidates, plain_above = self._collect_pipe_candidates(
            above, downward=False
        )

        below = [ln for ln in lines if self._line_y0(ln) > anchor_bottom]
        footer_candidates, plain_below = self._collect_pipe_candidates(
            below, downward=True
        )

        return TablePageLayout(
            drawing_anchor_top=anchor_top,
            drawing_anchor_bottom=anchor_bottom,
            header_candidates=header_candidates,
            plain_above=plain_above,
            footer_candidates=footer_candidates,
            plain_below=plain_below,
        )

    def _line_to_text_item(self, line: dict, page_num: int) -> TextLine:
        spans = line.get("spans")
        span_list = list(spans) if isinstance(spans, list) else None
        item = TextLine(
            text=line["text"],
            loc=TextLoc(
                stream_index=self._stream_index,
                page=page_num,
                bbox=line.get("bbox"),
                spans=span_list,
            ),
        )
        self._stream_index += 1
        return item

    def _replace_table_region(
        self, page: Any, lines: list[dict], page_num: int
    ) -> list[DocumentItem]:
        """表格页：丢弃表格区内基线行，插入 ``TableBlock``；失败则保留原文本行。"""
        layout = self.resolve_table_page_layout(page, lines)
        if layout is None:
            return [self._line_to_text_item(line, page_num) for line in lines]

        try:
            html, table_rows, bbox = extract_table_block(page, layout)
        except Exception:
            return [self._line_to_text_item(line, page_num) for line in lines]

        recovered_header = self._recover_unused_pipe_candidates(
            layout.header_candidates, table_rows, from_table_end=False
        )
        recovered_footer = self._recover_unused_pipe_candidates(
            layout.footer_candidates, table_rows, from_table_end=True
        )
        above_output = sorted(
            layout.plain_above + recovered_header, key=self._line_y0
        )
        below_output = sorted(
            layout.plain_below + recovered_footer, key=self._line_y0
        )

        items: list[DocumentItem] = []
        for line in above_output:
            items.append(self._line_to_text_item(line, page_num))

        table_block = TableBlock(
            html=html,
            rows=table_rows,
            loc=TableLoc(
                stream_index=self._stream_index,
                table_index=self._table_index,
                page=page_num,
                bbox=bbox,
            ),
        )
        self._stream_index += 1
        self._table_index += 1
        items.append(table_block)

        for line in below_output:
            items.append(self._line_to_text_item(line, page_num))

        return items

    @staticmethod
    def _normalize_header_key(text: str) -> str:
        if not text:
            return ""
        t = text.replace("|", "").replace("｜", "")
        return re.sub(r"\s+", "", t, flags=re.UNICODE)

    def _is_margin_line(self, text: str) -> bool:
        if self._margin_profile is not None:
            if self._margin_profile.is_header(text) or self._margin_profile.is_footer(text):
                return True
        key = self._normalize_header_key(text)
        if not key:
            return False
        for h in self.headers:
            if h in key:
                return True
        return False

    def _filter_margin_items(self, items: list[DocumentItem]) -> list[DocumentItem]:
        """过滤页眉/页码 ``TextLine``（单页内）。"""
        if not items:
            return items
        if not self.headers and self._margin_profile is None:
            return items

        remove_at: set[int] = set()
        for i, item in enumerate(items):
            if not isinstance(item, TextLine):
                continue
            if self._is_margin_line(item.text):
                remove_at.add(i)

        return [item for i, item in enumerate(items) if i not in remove_at]

    def parse_page(self, page: Any, page_num: int) -> list[DocumentItem]:
        """单页完整解析（与 ``parse`` 单页分支一致）。"""
        lines = self.extract_page_lines(page)
        items = self._replace_table_region(page, lines, page_num)
        return self._filter_margin_items(items)

    def parse(
        self,
        pdf_path: str | Path,
        *,
        page_range: SidePageRange | None = None,
    ) -> list[DocumentItem]:
        """解析 PDF，按 ``DocumentItem`` 混合流返回。

        处理逻辑：
        1. span 分行 + 一次 gap 拼接（统一阈值）
        2. 表格页：候选行 + LLM ``TableBlock`` 替换
        3. 过滤页眉/页码行
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        self._stream_index = 0
        self._table_index = 0
        result: list[DocumentItem] = []
        side_range = page_range or SidePageRange()

        try:
            with fitz.open(pdf_path) as doc:
                start_page, end_page = side_range.clamp(doc.page_count)
                for page_num, page in enumerate(doc, start=1):
                    if page_num < start_page or page_num > end_page:
                        continue
                    result.extend(self.parse_page(page, page_num))

        except Exception as e:
            raise RuntimeError(f"解析 PDF 失败: {e}") from e

        return result

    parse_blocks = parse
