"""
Camelot 表格提取器

使用 Camelot 库提取表格，支持 stream 和 lattice 两种模式。
"""
from typing import List, Any

try:
    import camelot
except ImportError:
    camelot = None

from .base import BaseExtractor, ExtractionResult


class CamelotExtractor(BaseExtractor):
    """Camelot 表格提取器"""

    name = "camelot_stream"

    def __init__(self, flavor: str = "stream"):
        """
        初始化提取器

        Args:
            flavor: 提取模式，"stream"（无边框）或 "lattice"（有边框）
        """
        if camelot is None:
            raise ImportError("Camelot 未安装，请运行: pip install camelot-py[cv]")
        self.flavor = flavor

    def extract(self, pdf_path: str, pages: str = "all") -> ExtractionResult:
        """
        使用 Camelot 提取表格

        Args:
            pdf_path: PDF 文件路径
            pages: 页面范围

        Returns:
            ExtractionResult
        """
        try:
            tables = camelot.read_pdf(pdf_path, pages=pages, flavor=self.flavor)

            if tables.n == 0:
                return ExtractionResult(
                    rows=[],
                    strategy=self.name,
                    is_valid=False,
                    error="未提取到表格"
                )

            # 合并所有表格的行
            all_rows: List[List[Any]] = []
            for table in tables:
                rows = table.df.values.tolist()
                all_rows.extend(rows)

            return ExtractionResult(
                rows=all_rows,
                strategy=self.name,
                page_count=len(tables),
                is_valid=self.is_valid_extraction(all_rows)
            )

        except Exception as e:
            return ExtractionResult(
                rows=[],
                strategy=self.name,
                is_valid=False,
                error=str(e)
            )


class CamelotLatticeExtractor(CamelotExtractor):
    """Camelot Lattice 模式提取器（适用于有边框表格）"""

    name = "camelot_lattice"

    def __init__(self):
        super().__init__(flavor="lattice")
