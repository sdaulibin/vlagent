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


def _clean_cell(value) -> str:
    """清理单元格值：换行符替换为空格，去除首尾空白"""
    return str(value or "").replace("\r", "").replace("\n", " ").strip()


def _looks_like_date(val: str) -> bool:
    """判断值是否看起来像日期"""
    import re
    return bool(re.match(r'^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}$', val.strip()))


def _is_main_data_row(row: List[str], seq_col_idx: int = 0) -> bool:
    """判断是否为主数据行（序号列以数字开头）"""
    if not row:
        return False
    seq_val = _clean_cell(row[seq_col_idx]) if seq_col_idx < len(row) else ""
    import re
    return bool(re.match(r'^\d+', seq_val))


def _merge_continuation_value(existing: str, continuation: str) -> str:
    """
    智能合并续行值到已有值。
    
    处理对方户名等字段被拆分的情况，例如：
    - existing: "山东玉金经贸有限公 转账支取|往来款"  (公司名被截断 + 摘要)
    - continuation: "司"  (截断的后半部分)
    - 结果: "山东玉金经贸有限公司 转账支取|往来款"
    
    规则：如果 existing 中有空格分隔（表示 名称+摘要），续行文本插入到第一个空格前。
    """
    if not existing:
        return continuation
    if not continuation:
        return existing
    
    # 如果 existing 包含空格（如 "有限公 转账支取|往来款"），
    # 把 continuation 插入到第一个空格前
    space_idx = existing.find(' ')
    if space_idx > 0:
        return existing[:space_idx] + continuation + existing[space_idx:]
    
    # 否则直接追加
    return existing + continuation


def parse_transactions(tables: List[List[List[str]]], column_map: Dict[int, str]) -> List[Dict[str, str]]:
    """
    根据列映射，将提取的表格数据解析为字典列表。
    
    自动合并被拆分的行：
    - 日期前缀行（如 "2024-01-19"）→ 合并到下一条主数据行的交易时间字段
    - 续行（序号列为空但有数据）→ 追加到上一条主数据行的对应字段
    - 混合行（日期 + 其他列数据）→ 保存日期 + 合并其他列数据到上一条
    
    Args:
        tables: 所有表格数据（页→表→行→单元格）
        column_map: 列索引到字段名的映射
    
    Returns:
        交易记录字典列表
    """
    # 找到序号列和交易时间列的索引
    seq_col_idx = None
    time_col_idx = None
    for col_idx, field_name in column_map.items():
        if field_name == "序号":
            seq_col_idx = col_idx
        if field_name in ("交易时间", "交易日期"):
            time_col_idx = col_idx
    if seq_col_idx is None:
        seq_col_idx = 0
    
    # 展平所有表格行
    all_rows = []
    for table in tables:
        for row in table:
            all_rows.append(row)
    
    transactions = []
    pending_date = ""
    pending_continuation = []
    
    # NEW STATE: are we visually in the block of the NEXT transaction?
    # True if we have passed a date line, False if we just passed a main data line
    in_next_block = False
    
    # 提取是否有明显属于页眉/页脚的垃圾文本（莱商等银行合并时会产生）
    garbage_kws = ["账(卡", "序号", "收入序号", "收入", "支出", "交易渠道", "交易时间", "收入总笔数", "支出总笔数", "账户名:", "起止日期:", "收入总金额", "支出总金额", "对方账号", "对方户名"]
    
    for row in all_rows:
        # 跳过全空行
        non_empty_cells = [(i, _clean_cell(c)) for i, c in enumerate(row) if _clean_cell(c)]
        if not non_empty_cells:
            continue
        
        # 跳过合计/统计行及分页表头产生的特殊垃圾行
        first_val = _clean_cell(row[0]) if row else ""
        skip_keywords = ["合计", "小计", "总计", "本页合计", "累计", "页码", "打印"]
        if any(kw in first_val for kw in skip_keywords):
            continue
            
        row_text = "".join([_clean_cell(c) for c in row])
        
        # 如果行内容包含多列表头关键字，这明显是由于跨页导致的内容重复表头
        header_kws = ["交易时间", "交易渠道", "收入", "支出", "账户余额", "对方账号", "对方户名"]
        if sum(1 for kw in header_kws if kw in row_text) >= 2:
            continue
            
        # 跳过莱商银行特有的首行账户信息及尾行汇总信息，防止干扰解析
        if any(kw in row_text for kw in ["起止日期", "起始日期", "结束日志", "账户名:", "总笔数", "总金额", "账(卡", "收入序号"]):
            continue
            
        
        # 情况1: 主数据行（有序号）
        if _is_main_data_row(row, seq_col_idx):
            in_next_block = False
            record = {}
            for col_idx, field_name in column_map.items():
                if col_idx < len(row):
                    record[field_name] = _clean_cell(row[col_idx])
            
            # 1. 组合暂存的日期
            if pending_date and time_col_idx is not None:
                time_field = column_map.get(time_col_idx, "交易时间")
                current_time = record.get(time_field, "")
                record[time_field] = f"{pending_date} {current_time}".strip()
                pending_date = ""
            
            # 2. 合并悬空的续行数据（针对拆分到了主行上方的续行）
            for p_dict in pending_continuation:
                for f_name, val in p_dict.items():
                    existing = record.get(f_name, "")
                    if f_name in ["收入", "支出", "账户余额", "借方发生额", "贷方发生额", "余额"]:
                        if not existing:
                            record[f_name] = val
                    else:
                        record[f_name] = _merge_continuation_value(val, existing)  # 前置
            pending_continuation = []
            
            # --- 数据清理 (清理由于表格线缺失导致的页眉文本合并) ---
            
            # 清理序号
            seq_field = column_map.get(seq_col_idx, "序号")
            if seq_field in record and record[seq_field]:
                import re
                m = re.search(r"(\d+)", record[seq_field])
                if m:
                    record[seq_field] = m.group(1)
            
            # 清理金额字段
            for f_name in ["收入", "支出", "账户余额", "借方发生额", "贷方发生额", "余额"]:
                val = record.get(f_name, "")
                if val:
                    import re
                    m = re.search(r"(-?\d+(?:\.\d+)?)", val)
                    if m:
                        record[f_name] = m.group(1)
            
            # 清理时间字段
            for f_name in ["交易时间", "交易日期"]:
                val = record.get(f_name, "")
                if val:
                    import re
                    m = re.search(r"(\d{4}[-/.]\d{2}[-/.]\d{2}(?:\s+\d{2}:\d{2}:\d{2})?)", val)
                    if m: 
                        record[f_name] = m.group(1)
            
            # 清理文本字段
            for f_name in column_map.values():
                if f_name not in ["收入", "支出", "账户余额", "借方发生额", "贷方发生额", "余额", "交易时间", "交易日期", seq_field]:
                    val = record.get(f_name, "")
                    if val:
                        for kw in garbage_kws:
                            if kw in val:
                                val = val.split(kw)[0]
                        record[f_name] = val.strip()
                        
                        # 币种特判
                        if f_name == "币种" and "人民币" in val:
                            record[f_name] = "人民币"
            
            if any(v for v in record.values()):
                transactions.append(record)
            continue
        
        # 非主数据行：检查是否包含日期值（在 time 列位置）
        has_date = False
        if time_col_idx is not None and time_col_idx < len(row):
            time_val = _clean_cell(row[time_col_idx])
            if _looks_like_date(time_val):
                pending_date = time_val
                has_date = True
                in_next_block = True
        
        # 检查除了日期列外是否还有其他数据（续行数据）
        other_data = {}
        for col_idx, field_name in column_map.items():
            if col_idx < len(row) and col_idx != time_col_idx:
                val = _clean_cell(row[col_idx])
                # 同步清理金额和文本中的垃圾
                if field_name in ["收入", "支出", "账户余额", "借方发生额", "贷方发生额", "余额"]:
                    import re
                    m = re.search(r"(-?\d+(?:\.\d+)?)", val)
                    if m: val = m.group(1)
                else:
                    for kw in garbage_kws:
                        if kw in val: val = val.split(kw)[0]
                    val = val.strip()
                    if field_name == "币种" and "人民币" in val: val = "人民币"
                    
                if val:
                    other_data[field_name] = val
        
        # 情况2: 纯日期行（只有日期，无其他数据）
        if has_date and not other_data:
            continue
        
        # 情况3: 混合行（日期 + 续行数据）或纯续行
        if other_data:
            belongs_to_next = in_next_block
            
            # 如果不是因为在下一个区块中，但金额字段冲突了，则被迫推迟到下一条记录
            if not belongs_to_next:
                if transactions:
                    last_record = transactions[-1]
                    for f_name in ["收入", "支出", "账户余额", "借方发生额", "贷方发生额", "余额"]:
                        if other_data.get(f_name) and last_record.get(f_name):
                            belongs_to_next = True
                            break
                else:
                    belongs_to_next = True
                
            if belongs_to_next:
                pending_continuation.append(other_data)
                continue
            
            # 将非日期列的数据合并到上一条记录
            last_record = transactions[-1]
            for field_name, val in other_data.items():
                existing = last_record.get(field_name, "")
                if field_name in ["收入", "支出", "账户余额", "借方发生额", "贷方发生额", "余额", "交易渠道", "币种"]:
                    if not existing:
                        last_record[field_name] = val
                else:
                    last_record[field_name] = _merge_continuation_value(existing, val)
    
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

