"""
PDF 表格提取器
"""
from .base import BaseExtractor, ExtractionResult
from .factory import ExtractorFactory

# 延迟导入，避免依赖未安装时报错
try:
    from .camelot_extractor import CamelotExtractor
except ImportError:
    CamelotExtractor = None

try:
    from .pdfplumber_extractor import PdfplumberExtractor
except ImportError:
    PdfplumberExtractor = None

__all__ = [
    "BaseExtractor",
    "ExtractionResult",
    "CamelotExtractor",
    "PdfplumberExtractor",
    "ExtractorFactory",
]
