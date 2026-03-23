"""
pdfplumber 表格提取器

使用 pdfplumber 库提取表格，支持多种策略。
"""
import pdfplumber
from typing import List, Any, Dict, Optional

from .base import BaseExtractor, ExtractionResult


class PdfplumberExtractor(BaseExtractor):
    """pdfplumber 表格提取器"""

    name = "pdfplumber_default"

    # 预定义的表格提取设置
    TABLE_SETTINGS = {
        "default": {},
        "lines": {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
        },
        "text": {
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
        },
    }

    def __init__(self, strategy: str = "default"):
        """
        初始化提取器

        Args:
            strategy: 提取策略，可选 "default", "lines", "text"
        """
        self.strategy = strategy
        self.settings = self.TABLE_SETTINGS.get(strategy, {})
        self.name = f"pdfplumber_{strategy}"

    def extract(self, pdf_path: str, pages: str = "all") -> ExtractionResult:
        """
        使用 pdfplumber 提取表格

        Args:
            pdf_path: PDF 文件路径
            pages: 页面范围

        Returns:
            ExtractionResult
        """
        try:
            all_rows: List[List[Any]] = []
            page_count = 0

            with pdfplumber.open(pdf_path) as pdf:
                # 解析页面范围
                page_indices = self._parse_page_range(pages, len(pdf.pages))

                for idx in page_indices:
                    page = pdf.pages[idx]
                    tables = page.extract_tables(self.settings)
                    if tables:
                        for table in tables:
                            if table:
                                all_rows.extend(table)
                        page_count += 1

            if not all_rows:
                return ExtractionResult(
                    rows=[],
                    strategy=self.name,
                    is_valid=False,
                    error="未提取到表格"
                )

            return ExtractionResult(
                rows=all_rows,
                strategy=self.name,
                page_count=page_count,
                is_valid=self.is_valid_extraction(all_rows)
            )

        except Exception as e:
            return ExtractionResult(
                rows=[],
                strategy=self.name,
                is_valid=False,
                error=str(e)
            )

    def _parse_page_range(self, pages: str, total_pages: int) -> List[int]:
        """
        解析页面范围字符串

        Args:
            pages: 页面范围，如 "all", "1-3", "1,3,5"
            total_pages: 总页数

        Returns:
            页面索引列表（0-based）
        """
        if pages == "all":
            return list(range(total_pages))

        indices = []
        parts = pages.split(",")
        for part in parts:
            part = part.strip()
            if "-" in part:
                start, end = part.split("-")
                start = int(start) - 1  # 转为 0-based
                end = int(end)  # end 是包含的
                indices.extend(range(start, min(end, total_pages)))
            else:
                idx = int(part) - 1  # 转为 0-based
                if 0 <= idx < total_pages:
                    indices.append(idx)

        return sorted(set(indices))


class PdfplumberLinesExtractor(PdfplumberExtractor):
    """pdfplumber Lines 策略提取器"""

    name = "pdfplumber_lines"

    def __init__(self):
        super().__init__(strategy="lines")


class PdfplumberTextExtractor(PdfplumberExtractor):
    """pdfplumber Text 策略提取器"""

    name = "pdfplumber_text"

    def __init__(self):
        super().__init__(strategy="text")
