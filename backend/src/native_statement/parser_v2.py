"""
原生 PDF 解析器（重构版）

使用模版驱动的方式解析银行流水 PDF。
保持与原有 API 的兼容性。
"""
import re
import pdfplumber
from typing import Optional, Dict, Any, List

# 复用旧版的招商银行处理逻辑
from .parser import (
    _merge_cmb_rows,
    _merge_cmb_header,
    _is_cmb_serial_start,
    _merge_into,
    is_header_row,
    is_noise_row,
    map_headers,
    extract_tables,  # 使用旧版的表格提取函数
)

# 新模块导入
from .models.schema import BankSchema
from .models.result import ParseResult, Transaction, Summary
from .schema.loader import SchemaLoader
from .schema.registry import registry
from .extractor.factory import ExtractorFactory, AutoExtractor
from .processors.factory import ProcessorFactory
from .processors.cleaner import DataCleaner


# ============================================================
# 辅助函数（保持与旧 API 兼容）
# ============================================================

def _get_strategy_order(schema: BankSchema) -> List[str]:
    """根据 schema 配置获取提取策略顺序"""
    preferred = schema.extraction.preferred_strategy
    fallbacks = schema.extraction.fallback_strategies

    if preferred and preferred != "auto":
        # 使用配置的首选策略
        order = [preferred]
        for s in fallbacks:
            if s not in order:
                order.append(s)
        return order
    else:
        # 使用默认顺序
        return AutoExtractor.DEFAULT_STRATEGY_ORDER


def is_native_pdf(pdf_path: str) -> bool:
    """
    判断 PDF 是否为原生电子版（非扫描件）

    通过检测前几页是否包含可提取的文本来判断。
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_to_check = min(3, len(pdf.pages))
            total_chars = 0
            for i in range(pages_to_check):
                text = pdf.pages[i].extract_text() or ""
                total_chars += len(text.strip())
            return (total_chars / max(pages_to_check, 1)) > 50
    except Exception:
        return False


def extract_full_text(pdf_path: str) -> str:
    """
    提取 PDF 全部文本
    """
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            texts.append(text)
    return "\n".join(texts)


def extract_summary(full_text: str, patterns: Dict[str, List[str]] = None) -> Dict[str, str]:
    """
    从全文文本中用正则提取汇总信息
    """
    # 默认汇总模式
    default_patterns = {
        "account_number": [
            r"账\s*号[：:]\s*(\d[\d\s\-]*\d)",
            r"账\(?卡\)?号[：:]\s*(\d[\d\s\-]*\d)",
        ],
        "account_name": [
            r"(?:户\s*名|账户名称|账户名|客户名称)[：:]\s*(.+?)(?:\s{2,}|$)",
        ],
        "currency": [
            r"币\s*种[：:]\s*(.+?)(?:\s{2,}|$)",
        ],
        "bank_name": [
            r"(?:开户行|开户机构|开户网点)[：:]\s*(.+?)(?:\s{2,}|$)",
        ],
        "date_range": [
            r"(?:起止日期|交易期间|查询期间|打印期间)[：:]\s*(.+?)(?:\s{2,}|$)",
        ],
        "income_total": [
            r"(?:收入总金额|贷方合计|总收入金额)[：:]\s*([\d,\.]+)",
        ],
        "expense_total": [
            r"(?:支出总金额|借方合计|总支出金额)[：:]\s*([\d,\.]+)",
        ],
    }

    patterns = patterns or default_patterns
    summary = {}
    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            m = re.search(pattern, full_text, re.MULTILINE)
            if m:
                summary[field] = m.group(1).strip()
                break
    return summary


# ============================================================
# 主解析函数
# ============================================================

def parse_native_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    解析原生电子版 PDF，提取汇总信息和交易明细

    Args:
        pdf_path: PDF 文件路径

    Returns:
        {
            "bank_type": "icbc",
            "summary": {"account_name": "xxx", ...},
            "transactions": [{"transaction_time": "...", ...}, ...],
            "headers": ["transaction_time", "income", ...],
            "raw_headers": ["交易时间", "收入", ...],
            "page_count": 5,
            "total_rows": 100,
            "is_native": True,
            "extraction_strategy": "camelot_stream",
        }
    """
    # 1. 检测是否为原生 PDF
    if not is_native_pdf(pdf_path):
        return {
            "error": "该 PDF 不是原生电子版，请使用 AI 识别功能处理扫描件",
            "is_native": False,
        }

    # 2. 初始化注册表
    registry.initialize()

    # 3. 提取全文文本
    full_text = extract_full_text(pdf_path)

    # 4. 识别银行类型并加载模版
    schema = SchemaLoader.detect_and_load(full_text)
    bank_type = schema.template_id

    # 5. 提取表格数据（使用 schema 配置的提取策略）
    extractor = AutoExtractor(
        min_columns=schema.extraction.min_columns,
        strategy_order=_get_strategy_order(schema)
    )
    extraction_result = extractor.extract(pdf_path)

    if not extraction_result.is_valid:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
        return {
            "is_native": True,
            "bank_type": bank_type,
            "summary": {},
            "transactions": [],
            "headers": [],
            "raw_headers": [],
            "page_count": page_count,
            "total_rows": 0,
            "extraction_strategy": extraction_result.strategy,
            "error": extraction_result.error or "未检测到表格数据",
        }

    # 6. 处理数据（招商银行使用旧版完善的处理逻辑）
    if bank_type == "cmb":
        # 使用旧版的表格提取函数（返回11列格式）
        all_rows = extract_tables(pdf_path)
        merged_rows = _merge_cmb_rows(all_rows)

        # 查找表头行
        header_idx = None
        for i, row in enumerate(merged_rows[:10]):
            if is_header_row(row):
                header_idx = i
                break

        if header_idx is None:
            header_idx = 0

        # 获取表头
        raw_headers = [str(h or "").strip() for h in merged_rows[header_idx]]
        mapped_headers = map_headers(raw_headers)

        # 解析数据行
        transactions = []
        for row in merged_rows[header_idx + 1:]:
            if is_noise_row(row) or is_header_row(row):
                continue

            record = {}
            for j, cell in enumerate(row):
                if j < len(mapped_headers):
                    field = mapped_headers[j]
                    val = str(cell or "").strip()
                    val = val.replace('\n', '')  # 移除换行符
                    record[field] = val

            if any(v for v in record.values()):
                transactions.append(record)

        extraction_strategy = "legacy:cmb"
    else:
        # 其他银行使用新版处理器
        processor = ProcessorFactory.create(schema)
        mapped_headers, tx_list = processor.process(extraction_result.rows, [])
        transactions = [tx.to_dict() for tx in tx_list]
        extraction_strategy = extraction_result.strategy

    # 7. 提取汇总信息
    summary = extract_summary(full_text)

    # 8. 获取页数
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)

    return {
        "is_native": True,
        "bank_type": bank_type,
        "summary": summary,
        "transactions": transactions,
        "headers": mapped_headers,
        "raw_headers": mapped_headers,
        "page_count": page_count,
        "total_rows": len(transactions),
        "extraction_strategy": extraction_strategy,
    }


# ============================================================
# 兼容旧 API 的函数
# ============================================================

def extract_tables(pdf_path: str) -> List[List]:
    """
    从 PDF 中提取所有表格数据（兼容旧 API）
    """
    extractor = AutoExtractor()
    result = extractor.extract(pdf_path)
    return result.rows if result.is_valid else []


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python parser.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    result = parse_native_pdf(pdf_path)

    print(f"银行类型: {result.get('bank_type')}")
    print(f"提取策略: {result.get('extraction_strategy')}")
    print(f"页数: {result.get('page_count')}")
    print(f"交易行数: {result.get('total_rows')}")
    print(f"汇总信息: {result.get('summary')}")

    if result.get('transactions'):
        print(f"\n前3条交易:")
        for tx in result['transactions'][:3]:
            print(f"  {tx}")
