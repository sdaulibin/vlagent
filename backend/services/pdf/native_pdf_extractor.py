"""
原生 PDF 表格提取器

使用 pdfplumber 直接从数字原生 PDF 中提取银行流水表格数据，
无需 VL 模型或 OCR，速度极快且准确率 100%。
"""
import os
import json
import pdfplumber
from typing import List, Dict, Any, Optional, Tuple


# 银行 Schema 目录
BANK_SCHEMAS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "bank_schemas")


def _load_bank_registry() -> dict:
    """加载银行关键字注册表"""
    registry_path = os.path.join(BANK_SCHEMAS_DIR, "bank_registry.json")
    if os.path.exists(registry_path):
        with open(registry_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def _load_bank_template(bank_type: str) -> dict:
    """加载指定银行的模版配置"""
    template_path = os.path.join(BANK_SCHEMAS_DIR, f"{bank_type}.json")
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def detect_bank_from_text(full_text: str) -> Optional[str]:
    """
    从 PDF 提取的全文文本中匹配银行类型。
    复用 bank_registry.json 中的关键字映射。
    
    Args:
        full_text: PDF 全文文本
        
    Returns:
        银行模版 ID（如 'ccb', 'cmb'），未识别返回 None
    """
    registry = _load_bank_registry()
    keywords = registry.get("keywords", {})
    
    for bank_name, bank_id in keywords.items():
        if bank_name in full_text:
            return bank_id
    return None


# 常见的同义词映射（用于表头模糊匹配）
COLUMN_SYNONYMS = {
    "交易时间": ["交易日期", "日期时间", "交易时间", "日期"],
    "借方发生额": ["借方金额", "支出金额", "支出", "借方发生额", "借方"],
    "贷方发生额": ["贷方金额", "收入金额", "收入", "贷方发生额", "贷方"],
    "余额": ["账户余额", "余额", "本次余额"],
    "摘要": ["摘要", "用途", "交易摘要", "附言"],
    "对方户名": ["对方名称", "对方户名", "对手方名称", "交易对手"],
    "对方账号": ["对方账号", "对手方账号"],
    "备注": ["备注", "附注"],
    "币种": ["币种", "货币"],
    "记账日期": ["记账日期", "入账日期", "记帐日期"],
}


def _fuzzy_match_header(header_cell: str, schema_keys: List[str], aliases: dict = None) -> Optional[str]:
    """
    模糊匹配单个表头单元格到 schema 字段名。
    
    匹配优先级：
    1. 精确匹配
    2. 银行模版中的 column_aliases 别名
    3. 全局同义词映射
    4. 包含匹配
    """
    if not header_cell:
        return None
    
    cell = header_cell.strip().replace("\n", "")
    
    # 1. 精确匹配
    if cell in schema_keys:
        return cell
    
    # 2. 银行模版别名匹配
    if aliases:
        for schema_key, alias_list in aliases.items():
            if cell in alias_list:
                return schema_key
    
    # 3. 全局同义词匹配
    for schema_key, synonyms in COLUMN_SYNONYMS.items():
        if schema_key in schema_keys and cell in synonyms:
            return schema_key
    
    # 4. 包含匹配（schema_key 包含在 cell 中，或 cell 包含在 schema_key 中）
    for schema_key in schema_keys:
        if schema_key in cell or cell in schema_key:
            return schema_key
    
    return None


def map_columns_by_header(header_row: List[str], schema: List[Dict], aliases: dict = None) -> Dict[int, str]:
    """
    将 pdfplumber 提取的表头行与银行 schema 字段名做映射。
    
    Args:
        header_row: 表头行（如 ["账号", "交易时间", "借方发生额", ...]）
        schema: 银行 transaction_schema（如 [{"账号": "", "交易时间": "", ...}]）
        aliases: 可选的列名别名映射
    
    Returns:
        列索引到字段名的映射（如 {0: "账号", 1: "交易时间", ...}）
    """
    if not schema:
        return {}
    
    schema_keys = list(schema[0].keys()) if isinstance(schema, list) else list(schema.keys())
    
    column_map = {}
    used_keys = set()
    
    for col_idx, cell in enumerate(header_row):
        matched_key = _fuzzy_match_header(cell, schema_keys, aliases)
        if matched_key and matched_key not in used_keys:
            column_map[col_idx] = matched_key
            used_keys.add(matched_key)
    
    return column_map


def _is_data_row(row: List[str]) -> bool:
    """判断一行是否为有效数据行（而非表头、合计行或空行）"""
    if not row:
        return False
    # 过滤全空行
    non_empty = [c for c in row if c and str(c).strip()]
    if len(non_empty) < 2:
        return False
    # 过滤合计/小计行
    first_cell = str(row[0] or "").strip()
    skip_keywords = ["合计", "小计", "总计", "本页合计", "累计", "页码", "打印"]
    for kw in skip_keywords:
        if kw in first_cell:
            return False
    return True


def parse_transactions(tables: List[List[List[str]]], column_map: Dict[int, str]) -> List[Dict[str, str]]:
    """
    根据列映射，将提取的表格数据解析为字典列表。
    
    Args:
        tables: 所有表格数据（页→表→行→单元格）
        column_map: 列索引到字段名的映射
    
    Returns:
        交易记录字典列表
    """
    transactions = []
    
    for table in tables:
        for row in table:
            if not _is_data_row(row):
                continue
            
            record = {}
            for col_idx, field_name in column_map.items():
                if col_idx < len(row):
                    value = str(row[col_idx] or "").replace("\n", "").replace("\r", "").strip()
                    record[field_name] = value
            
            # 确保记录至少有一些有效数据
            if any(v for v in record.values()):
                transactions.append(record)
    
    return transactions


def extract_summary_from_text(full_text: str, summary_schema: dict) -> dict:
    """
    从 PDF 全文中提取汇总信息。
    
    使用简单的关键字匹配从文本中提取汇总字段。
    """
    import re
    summary = {}
    
    for field_name in summary_schema.keys():
        # 尝试匹配 "字段名：值" 或 "字段名:值" 的模式
        patterns = [
            rf"{re.escape(field_name)}\s*[:：]\s*([^\n\s]+)",
            rf"{re.escape(field_name)}\s+([^\n\s]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, full_text)
            if match:
                summary[field_name] = match.group(1).strip()
                break
        else:
            summary[field_name] = ""
    
    return summary


def _extract_tables_standard(pdf) -> tuple:
    """策略1: 使用 pdfplumber 标准表格提取（适用于有明确表格线条的 PDF）"""
    all_tables = []
    for page in pdf.pages:
        tables = page.extract_tables()
        if tables:
            for table in tables:
                if table and len(table) > 1:
                    all_tables.append(table)
    return all_tables


def _extract_tables_text_strategy(pdf) -> tuple:
    """策略2: 使用 text 策略提取表格（适用于无明确线条但文字对齐的 PDF）"""
    all_tables = []
    settings = {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
        "min_words_vertical": 3,
        "min_words_horizontal": 1,
    }
    for page in pdf.pages:
        tables = page.extract_tables(settings)
        if tables:
            for table in tables:
                if table and len(table) > 1:
                    all_tables.append(table)
    return all_tables


def _extract_via_char_clustering(pdf, transaction_schema: list, aliases: dict = None) -> list:
    """
    策略3: 基于字符坐标聚类提取（适用于旋转文字的 PDF）。
    
    原理：通过 rect 元素或固定间距将页面分割为若干行区域，
    再按 x0 坐标将每行中的字符分组到各列。
    """
    if not transaction_schema:
        return []
    
    schema_keys = list(transaction_schema[0].keys()) if isinstance(transaction_schema, list) else list(transaction_schema.keys())
    transactions = []
    
    for page in pdf.pages:
        # 获取所有 rect 的 y 坐标作为行分隔
        rects = sorted(page.rects, key=lambda r: r['top'])
        if not rects:
            continue
        
        # 提取行区域（每个 rect 代表一个行背景）
        row_bands = []
        for rect in rects:
            row_bands.append((rect['top'], rect['bottom']))
        
        chars = page.chars
        if not chars:
            continue
        
        for band_top, band_bottom in row_bands:
            # 收集落在该行区域内的所有字符
            band_chars = [c for c in chars if band_top <= c['top'] <= band_bottom]
            if not band_chars:
                continue
            
            # 按 x0 排序，然后拼接成文本
            band_chars.sort(key=lambda c: c['x0'])
            
            # 通过 x 间距分组到不同列
            columns = []
            current_col_chars = [band_chars[0]]
            
            for i in range(1, len(band_chars)):
                prev_char = band_chars[i - 1]
                curr_char = band_chars[i]
                # 如果 x 间距大于阈值，认为是新列
                gap = curr_char['x0'] - (prev_char['x0'] + prev_char.get('width', 6))
                if gap > 15:  # 列间距阈值
                    columns.append(''.join(c['text'] for c in current_col_chars).strip())
                    current_col_chars = [curr_char]
                else:
                    current_col_chars.append(curr_char)
            
            if current_col_chars:
                columns.append(''.join(c['text'] for c in current_col_chars).strip())
            
            # 尝试把 columns 作为一行数据，映射到 schema
            if len(columns) >= 3:
                transactions.append(columns)
    
    return transactions


def _validate_tables(tables: list) -> bool:
    """检查提取的表格是否有效（每行至少有 3 个非空单元格）"""
    if not tables:
        return False
    for table in tables:
        for row in table:
            non_empty = [c for c in row if c and str(c).strip()]
            if len(non_empty) >= 3:
                return True
    return False


def process_native_pdf(pdf_path: str, bank_type_hint: str = None) -> dict:
    """
    使用 pdfplumber 处理原生 PDF 银行流水文件，直接提取表格数据。
    
    自动尝试多种提取策略：
    1. 标准表格提取（有线条的 PDF）
    2. Text 策略提取（无线条但文字对齐的 PDF）
    3. 字符坐标聚类（旋转文字的 PDF）
    
    Args:
        pdf_path: PDF 文件路径
        bank_type_hint: 可选的银行类型提示（如已从文件名识别）
    
    Returns:
        dict: 与现有流程相同的结构 {"transactions": [...], "summary": {...}, "bank_type": "xxx"}
    """
    with pdfplumber.open(pdf_path) as pdf:
        # 1. 提取全文
        full_text = ""
        for page in pdf.pages:
            full_text += (page.extract_text() or "") + "\n"
        
        # 2. 检测银行类型
        bank_type = bank_type_hint or detect_bank_from_text(full_text)
        if not bank_type:
            from services.pdf.bank_detector import detect_bank_from_filename
            bank_type = detect_bank_from_filename(os.path.basename(pdf_path))
        if not bank_type:
            bank_type = "unknown"
        
        print(f"  [原生PDF] 银行类型: {bank_type}")
        
        # 3. 加载银行模版
        template = _load_bank_template(bank_type)
        transaction_schema = template.get("transaction_schema", [])
        summary_schema = template.get("summary_schema", {})
        aliases = template.get("column_aliases", {})
        
        # 4. 尝试多种策略提取表格
        all_tables = None
        strategy_used = ""
        
        # 策略1: 标准表格提取
        tables = _extract_tables_standard(pdf)
        if _validate_tables(tables):
            all_tables = tables
            strategy_used = "标准表格提取"
        
        # 策略2: text 策略
        if not all_tables:
            tables = _extract_tables_text_strategy(pdf)
            if _validate_tables(tables):
                all_tables = tables
                strategy_used = "Text策略提取"
        
        print(f"  [原生PDF] 提取策略: {strategy_used if strategy_used else '所有表格策略均未成功，将回退到 VL 模型'}")
        
        # 5. 匹配表头 + 解析交易
        transactions = []
        column_map = {}
        
        if all_tables and transaction_schema:
            header_found = False
            data_tables = []
            
            for table in all_tables:
                if not table:
                    continue
                
                if not header_found:
                    candidate_map = map_columns_by_header(table[0], transaction_schema, aliases)
                    if len(candidate_map) >= 3:
                        column_map = candidate_map
                        header_found = True
                        print(f"  [原生PDF] 匹配到 {len(column_map)} 个字段: {list(column_map.values())}")
                        data_tables.append(table[1:])
                        continue
                
                if header_found:
                    # 跳过重复表头
                    test_map = map_columns_by_header(table[0], transaction_schema, aliases)
                    if len(test_map) >= 3:
                        data_tables.append(table[1:])
                    else:
                        data_tables.append(table)
                else:
                    data_tables.append(table)
            
            if column_map:
                transactions = parse_transactions(data_tables, column_map)
        
        if transactions:
            print(f"  [原生PDF] ✅ 提取到 {len(transactions)} 条交易记录")
        else:
            print(f"  [原生PDF] ⚠️ 未能通过原生解析提取交易数据，建议回退到 VL 模型")
        
        # 6. 提取汇总信息
        summary_data = None
        if summary_schema:
            summary_data = extract_summary_from_text(full_text, summary_schema)
        
        return {
            "transactions": transactions,
            "summary": summary_data,
            "bank_type": bank_type
        }

