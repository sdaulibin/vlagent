"""
提取器工厂

根据配置创建合适的提取器。
"""
from typing import List, Optional, Dict, Type

from ..models.schema import BankSchema
from .base import BaseExtractor, ExtractionResult

# 延迟加载的提取器注册表
_extractors: Dict[str, Type[BaseExtractor]] = {}
_extractors_initialized = False


def _init_extractors():
    """初始化提取器注册表（延迟加载）"""
    global _extractors, _extractors_initialized

    if _extractors_initialized:
        return

    # 尝试导入 Camelot 提取器
    try:
        from .camelot_extractor import CamelotExtractor, CamelotLatticeExtractor
        _extractors["camelot_stream"] = CamelotExtractor
        _extractors["camelot_lattice"] = CamelotLatticeExtractor
    except ImportError:
        pass

    # 尝试导入 pdfplumber 提取器
    try:
        from .pdfplumber_extractor import PdfplumberExtractor, PdfplumberLinesExtractor, PdfplumberTextExtractor
        _extractors["pdfplumber_default"] = PdfplumberExtractor
        _extractors["pdfplumber_lines"] = PdfplumberLinesExtractor
        _extractors["pdfplumber_text"] = PdfplumberTextExtractor
    except ImportError:
        pass

    # 如果没有任何提取器，使用内置的简单提取器
    if not _extractors:
        _extractors["builtin"] = _BuiltinExtractor

    _extractors_initialized = True


class _BuiltinExtractor(BaseExtractor):
    """内置的简单提取器（使用 pdfplumber 直接提取）"""

    name = "builtin"

    def extract(self, pdf_path: str, pages: str = "all") -> ExtractionResult:
        """使用内置的 pdfplumber 提取"""
        try:
            import pdfplumber
        except ImportError:
            return ExtractionResult(
                rows=[],
                strategy="builtin",
                is_valid=False,
                error="pdfplumber 未安装，请运行: pip install pdfplumber"
            )

        all_rows = []
        page_count = 0

        with pdfplumber.open(pdf_path) as pdf:
            page_indices = self._parse_page_range(pages, len(pdf.pages))
            for idx in page_indices:
                page = pdf.pages[idx]
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        if table:
                            all_rows.extend(table)
                    page_count += 1

        if not all_rows:
            return ExtractionResult(
                rows=[],
                strategy="builtin",
                is_valid=False,
                error="未提取到表格数据"
            )

        return ExtractionResult(
            rows=all_rows,
            strategy="builtin",
            page_count=page_count,
            is_valid=self.is_valid_extraction(all_rows)
        )

    def _parse_page_range(self, pages: str, total_pages: int) -> list:
        """解析页面范围"""
        if pages == "all":
            return list(range(total_pages))

        indices = []
        parts = pages.split(",")
        for part in parts:
            part = part.strip()
            if "-" in part:
                start, end = part.split("-")
                start = int(start) - 1
                end = int(end)
                indices.extend(range(start, min(end, total_pages)))
            else:
                idx = int(part) - 1
                if 0 <= idx < total_pages:
                    indices.append(idx)

        return sorted(set(indices))


class ExtractorFactory:
    """提取器工厂"""

    @classmethod
    def create(cls, strategy: str) -> BaseExtractor:
        """
        创建提取器实例

        Args:
            strategy: 策略名称

        Returns:
            提取器实例

        Raises:
            ValueError: 未知的策略名称
        """
        _init_extractors()

        if strategy == "auto":
            return AutoExtractor()

        extractor_class = _extractors.get(strategy)
        if extractor_class is None:
            raise ValueError(f"未知的提取策略: {strategy}")

        return extractor_class()

    @classmethod
    def register(cls, name: str, extractor_class: Type[BaseExtractor]) -> None:
        """
        注册新的提取器

        Args:
            name: 策略名称
            extractor_class: 提取器类
        """
        _extractors[name] = extractor_class

    @classmethod
    def get_available_strategies(cls) -> List[str]:
        """获取所有可用的策略"""
        _init_extractors()
        return list(_extractors.keys()) + ["auto"]


class AutoExtractor(BaseExtractor):
    """
    自动提取器

    按优先级尝试多种提取策略，返回第一个有效的结果。
    """

    name = "auto"

    # 默认策略优先级
    DEFAULT_STRATEGY_ORDER = [
        "camelot_stream",
        "pdfplumber_lines",
        "pdfplumber_default",
        "pdfplumber_text",
    ]

    def __init__(self, strategy_order: Optional[List[str]] = None, min_columns: int = 3):
        """
        初始化自动提取器

        Args:
            strategy_order: 策略优先级顺序
            min_columns: 最小列数要求（默认3，降低门槛以支持多行合并格式）
        """
        self.strategy_order = strategy_order or self.DEFAULT_STRATEGY_ORDER
        self.min_columns = min_columns

    def extract(self, pdf_path: str, pages: str = "all") -> ExtractionResult:
        """
        按优先级尝试多种策略

        Args:
            pdf_path: PDF 文件路径
            pages: 页面范围

        Returns:
            第一个有效的提取结果
        """
        last_error = None

        for strategy in self.strategy_order:
            try:
                extractor = ExtractorFactory.create(strategy)
                result = extractor.extract(pdf_path, pages)

                if result.is_valid and self.is_valid_extraction(result.rows, self.min_columns):
                    result.strategy = f"auto:{strategy}"
                    return result

                if result.error:
                    last_error = result.error

            except ImportError:
                # 跳过未安装的库
                continue
            except Exception as e:
                last_error = str(e)
                continue

        return ExtractionResult(
            rows=[],
            strategy="auto",
            is_valid=False,
            error=f"所有策略均失败: {last_error}"
        )

    def extract_with_schema(self, pdf_path: str, schema: BankSchema) -> ExtractionResult:
        """
        使用模版配置提取

        Args:
            pdf_path: PDF 文件路径
            schema: 银行模版

        Returns:
            提取结果
        """
        # 使用模版中的配置
        preferred = schema.extraction.preferred_strategy
        fallbacks = schema.extraction.fallback_strategies
        min_cols = schema.extraction.min_columns

        # 构建策略顺序
        if preferred != "auto":
            strategy_order = [preferred] + [s for s in fallbacks if s != preferred]
        else:
            strategy_order = self.DEFAULT_STRATEGY_ORDER

        extractor = AutoExtractor(strategy_order=strategy_order, min_columns=min_cols)
        return extractor.extract(pdf_path)
