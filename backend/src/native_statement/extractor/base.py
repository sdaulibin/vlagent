"""
提取器基类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Any


@dataclass
class ExtractionResult:
    """提取结果"""
    rows: List[List[Any]]           # 提取的表格行
    strategy: str                    # 使用的策略名称
    page_count: int = 0              # 提取的页数
    is_valid: bool = True            # 结果是否有效
    error: Optional[str] = None      # 错误信息


class BaseExtractor(ABC):
    """PDF 表格提取器基类"""

    # 提取器名称
    name: str = "base"

    @abstractmethod
    def extract(self, pdf_path: str, pages: str = "all") -> ExtractionResult:
        """
        从 PDF 中提取表格数据

        Args:
            pdf_path: PDF 文件路径
            pages: 页面范围，如 "all", "1-3", "1,3,5"

        Returns:
            ExtractionResult
        """
        pass

    def is_valid_extraction(self, rows: List[List[Any]], min_columns: int = 3) -> bool:
        """
        验证提取结果是否有效

        Args:
            rows: 提取的行
            min_columns: 最小非空列数

        Returns:
            是否有效
        """
        if not rows or len(rows) < 2:
            return False

        # 检查是否有足够的多列行（检查前20行，降低验证门槛）
        multi_col_count = 0
        for row in rows[:20]:  # 扩大到20行
            if not row:
                continue
            non_empty = sum(1 for cell in row if cell and str(cell).strip())
            if non_empty >= min_columns:
                multi_col_count += 1

        # 只要有1行满足条件就认为有效（支持多行合并格式）
        return multi_col_count >= 1

    def _clean_row(self, row: List[Any]) -> List[str]:
        """清洗单行数据"""
        return [str(cell or "").strip() for cell in row]
