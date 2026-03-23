"""
原生 PDF 解析器

使用 pdfplumber 从原生电子版 PDF 中提取表格数据和汇总信息。
不使用任何 OCR 或 AI 模型。
"""
import re
import pdfplumber
from typing import Optional

try:
    import camelot
except ImportError:
    camelot = None

from src.native_statement.bank_rules import (
    detect_bank_type,
    map_headers,
    is_noise_row,
    is_header_row,
    DEFAULT_SUMMARY_PATTERNS,
)


# pdfplumber 文本策略表格提取设置
TEXT_TABLE_SETTINGS = {
    "vertical_strategy": "text",
    "horizontal_strategy": "text",
}


def is_native_pdf(pdf_path: str) -> bool:
    """
    判断 PDF 是否为原生电子版（非扫描件）

    通过检测前几页是否包含可提取的文本来判断。
    原生 PDF 有文本层，扫描件 PDF 只有图片层。

    Args:
        pdf_path: PDF 文件路径

    Returns:
        True 表示原生电子版，False 表示扫描件
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # 检查前 3 页（或全部页面，取较小值）
            pages_to_check = min(3, len(pdf.pages))
            total_chars = 0
            for i in range(pages_to_check):
                text = pdf.pages[i].extract_text() or ""
                total_chars += len(text.strip())
            # 如果平均每页超过 50 个字符，认为是原生 PDF
            return (total_chars / max(pages_to_check, 1)) > 50
    except Exception:
        return False


def extract_full_text(pdf_path: str) -> str:
    """
    提取 PDF 全部文本

    Args:
        pdf_path: PDF 文件路径

    Returns:
        全部页面文本拼接
    """
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            texts.append(text)
    return "\n".join(texts)


def extract_summary(full_text: str, patterns: dict = None) -> dict:
    """
    从全文文本中用正则提取汇总信息

    Args:
        full_text: PDF 全文文本
        patterns: 正则模式字典，默认使用 DEFAULT_SUMMARY_PATTERNS

    Returns:
        汇总信息字典
    """
    patterns = patterns or DEFAULT_SUMMARY_PATTERNS
    summary = {}
    for field, pattern_list in patterns.items():
        for pattern in pattern_list:
            m = re.search(pattern, full_text)
            if m:
                summary[field] = m.group(1).strip()
                break
    return summary


def _is_valid_table_extraction(rows: list) -> bool:
    """
    检查 extract_tables() 的提取结果是否有效。

    有效的标准：
    - 至少有 2 行
    - 至少有一行包含 3 个以上非空列（排除只提取到单列序号的情况）
    - 包含可识别的表头行
    """
    if not rows or len(rows) < 2:
        return False

    # 检查是否有表头行
    has_header = False
    for row in rows[:5]:  # 只检查前5行
        if is_header_row(row):
            has_header = True
            break

    if has_header:
        return True

    # 检查列数 — 如果大部分行只有1-2列，说明提取失败
    multi_col_count = 0
    for row in rows[:10]:
        non_empty = sum(1 for cell in row if cell and str(cell).strip())
        if non_empty >= 3:
            multi_col_count += 1

    return multi_col_count >= 2


def _is_cmb_serial_start(val: str) -> bool:
    """
    检测是否为招商银行流水号的起始部分

    招商银行流水号格式：C0546RL00032SOZ
    起始部分特征：C + 4-5位数字 + 可选字母

    注意：
    - Camelot可能将流水号和日期合并在一起，如 "C05471\\n2024-1"
    - 需要区分：
      - 纯流水号起始：C0546R, C05471 → 有效
      - 流水号+日期（2行）：C05471\\n2024-1 → 有效
      - 多行复合（3+行）：C0546R\\n2024-0\\n企业银 → 无效
    """
    if not val:
        return False
    val = val.strip()

    lines = val.split('\n')

    # 如果超过2行，说明是多字段复合，不是单纯的流水号起始
    if len(lines) > 2:
        return False

    # 取第一行
    first_line = lines[0].strip()

    # 流水号起始：C + 4-5位数字 + 可选字母（如 C0546R, C05471）
    return bool(re.match(r'^C\d{4,5}[A-Z]?$', first_line))


def _merge_cmb_rows(rows: list) -> list:
    """
    专门处理招商银行PDF的多行合并

    招商银行PDF特点：
    - 表头被拆成多行（3-4行）
    - 每条交易被拆成多行（3-5行）
    - 流水号格式：C0546RL00032SOZ，被切成 C0546R, L00032, SOZ 等
    """
    if not rows:
        return rows

    result = []
    i = 0

    # 首先找到表头结束位置
    header_end_idx = 0
    for idx, row in enumerate(rows):
        first = str(row[0] or "").strip() if row else ""
        # 流水号起始（C + 数字）表示数据开始
        if _is_cmb_serial_start(first):
            header_end_idx = idx
            break

    # 合并表头行
    if header_end_idx > 0:
        header_rows = rows[:header_end_idx]
        merged_header = _merge_cmb_header(header_rows)
        result.append(merged_header)
        i = header_end_idx
    else:
        # 没找到明确的表头边界，使用原有逻辑
        i = 0

    # 合并数据行
    while i < len(rows):
        row = rows[i]
        first = str(row[0] or "").strip() if row else ""

        # 检测新交易的起始：流水号起始（C + 数字）
        if _is_cmb_serial_start(first):
            merged_row = list(row)
            # 向后合并直到遇到下一个流水号起始或表头关键词
            j = i + 1
            while j < len(rows):
                next_row = rows[j]
                next_first = str(next_row[0] or "").strip() if next_row else ""

                # 如果遇到新的流水号起始，停止合并
                if _is_cmb_serial_start(next_first):
                    break
                # 如果遇到表头关键词，停止合并
                if is_header_row(next_row):
                    break
                # 如果第一列为空但第二列包含完整日期时间（新交易），停止合并
                if not next_first and len(next_row) > 1:
                    second = str(next_row[1] or "").strip()
                    if re.match(r'^\d{4}[\-/]', second):
                        break

                # 合并这一行
                _merge_into(merged_row, next_row, prepend=False)
                j += 1

            result.append(merged_row)
            i = j
        else:
            # 不是交易起始行，可能是孤立的碎片或表头
            result.append(list(row))
            i += 1

    return result


def _merge_cmb_header(header_rows: list) -> list:
    """
    合并招商银行的多行表头

    例如：
    行1: ['交易流', '交易日', '借方(出', '贷方(入', '', '', '收(付)方账', '', '交易', '', '']
    行2: ['', '', '', '', '余额', '收(付)方名称', '', '摘要', '', '一卡', '实例']
    行3: ['水号', '期', '账)', '账)', '', '', '号', '', '类型', '', '']
    行4: ['', '', '', '', '', '', '', '', '', '通号', '号']

    合并后：
    ['交易流水号', '交易日期', '借方(出账)', '贷方(入账)', '余额', '收(付)方名称', '收(付)方账号', '摘要', '交易类型', '公司一卡通号', '打印实例号']
    """
    if not header_rows:
        return []

    # 过滤掉非表头行（如打印时间、URL等）
    filtered_rows = []
    for row in header_rows:
        if not row:
            continue
        # 检查是否包含表头关键词
        row_text = ''.join(str(c or '') for c in row)
        # 跳过打印时间、URL等非表头内容
        if re.search(r'\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}', row_text):
            continue
        if 'http' in row_text.lower():
            continue
        # 跳过单独的"公司 打印"等页面标记
        if re.match(r'^公司\s*打印$', row_text.replace('\n', '')):
            continue
        # 跳过纯"打印"或"公司"标记
        if row_text.strip() in ['公司', '打印', '公司打印']:
            continue
        # 保留包含表头关键词的行
        if re.search(r'[交易流日期借方贷方余额收付账号摘要类型通号]', row_text):
            filtered_rows.append(row)

    if not filtered_rows:
        return []

    # 获取最大列数
    max_cols = max(len(row) for row in filtered_rows) if filtered_rows else 0

    # 逐列合并
    merged = [''] * max_cols
    for row in filtered_rows:
        for col_idx, cell in enumerate(row):
            if col_idx < max_cols:
                cell_val = str(cell or "").strip()
                if cell_val:
                    if merged[col_idx]:
                        merged[col_idx] += cell_val
                    else:
                        merged[col_idx] = cell_val

    # 清理合并后的表头
    cleaned = []
    for h in merged:
        # 去除多余空格
        h = re.sub(r'\s+', '', h)
        # 处理换行符
        h = h.replace('\n', '')
        # 去除公司名称等前缀（如 "集团公司名称:交易日期" -> "交易日期"）
        h = re.sub(r'^[^:：]+[:：]', '', h)
        # 去除用户所属公司等前缀
        h = re.sub(r'^用户所属公司[^:]*[:：]', '', h)
        # 去除"公司"和"打印"等噪声前缀
        h = re.sub(r'^(公司|打印)+', '', h)
        cleaned.append(h)

    return cleaned


def _merge_multiline_cells(tables: list) -> list:
    """
    合并 pdfplumber 提取的表格中的多行单元格

    pdfplumber 的文本策略可能将一条记录拆成多行：
    - 日期行（在主数据行之前）：只有时间列有日期值，其余为空
    - 数据行：包含序号、时间、金额等主要数据
    - 续行（在主数据行之后）：只有少数列有值（如对方户名的续行）

    该函数使用两遍扫描合并：
    1. 分类每一行：header / main / fragment
    2. 将 fragment 行合并到最近的 main 行（前方的 fragment 向后合并，后方的向前合并）
    """
    if not tables:
        return tables

    # ---- 自动探测第一列是否具有主键/锚点特征（序号或日期） ----
    has_anchor_col = False
    for row in tables[1:20]:  # 检查前20行数据
        if not row: continue
        first_val = str(row[0] or "").strip()
        if re.match(r"^\d+$", first_val) or re.match(r"^\d{4}[\-/\.]\d{1,2}", first_val):
            has_anchor_col = True
            break

    # ---- 第一遍：分类行 ----
    classified = []  # list of (type, row)  type: 'header' | 'main' | 'fragment'
    for row in tables:
        if not row:
            continue

        non_empty_count = sum(1 for cell in row if cell and str(cell).strip())
        total_cols = len(row)

        if non_empty_count == 0:
            continue

        if is_header_row(row):
            classified.append(("header", list(row)))
            continue

        first_cell = str(row[0] or "").strip()
        is_main = False
        non_empty_count = sum(1 for cell in row if cell and str(cell).strip())
        total_cols = len(row)

        if non_empty_count > 0:
            # 强化型主键：以序号开头
            if re.match(r"^\d+$", first_cell):
                is_main = True
            # 招商银行流水号片段模式：C0546R 后面跟着日期碎片 2024-0
            elif _is_cmb_serial_start(first_cell):
                is_main = True
            else:
                # 强化型主键：在大概率的时间栏位内存在明显带有年份前缀（如 2024-）的核心日期碎片
                for cell in row[:5]:
                    val = str(cell or "").strip()
                    if re.search(r"(?:^|\s)\d{4}[\-/\.]\d*", val):
                        is_main = True
                        break

            # 若无强锚点，列数兜底判定（极度保守，必须没有出现过哪怕一行明确主键，才允许列数判定生效）
            if not is_main and non_empty_count >= max(3, total_cols * 0.3):
                # 如果这个 PDF 之前已经成功出现过带明确日期的主记录，说明系统进入了"多行切分的连续业务流"
                # 在连续业务流中，没有日期的长文本行（哪怕凑够了3列）往往只是上一条业务的多字段换行碎片
                if not any((t == "main" for t, r in classified)):
                    is_main = True

        if is_main:
            classified.append(("main", list(row)))
        else:
            classified.append(("fragment", list(row)))

    # ---- 特殊处理：合并多行表头 ----
    # 解决招商银行表头被切断成多行的问题：
    # 行1: 交易流 交易日, 借方(出, 贷方(入, ...
    # 行2: 水号 期, 账), 账), ...
    # 行3: 通号, 号
    i = 0
    while i < len(classified):
        if classified[i][0] == "header":
            j = i + 1
            while j < len(classified) and classified[j][0] == "fragment":
                # 检查这个碎片是否是表头的延续
                text = "".join(str(c or "") for c in classified[j][1]).strip()

                # 表头碎片的特征：
                # 1. 纯文字（无数字）且短
                # 2. 或者包含表头关键词片段（水号、期、账)、号、通号等）
                is_header_fragment = False

                # 纯文字碎片（无数字）
                if not re.search(r"\d", text) and len(text) < 30:
                    is_header_fragment = True
                # 包含表头关键词片段
                elif re.search(r"[水号期账\)通号]", text) and len(text) < 50:
                    is_header_fragment = True

                if not is_header_fragment:
                    break

                # 是表头碎片，缝回表头
                _merge_into(classified[i][1], classified[j][1], prepend=False)
                classified[j] = ("resolved", None)
                j += 1
            i = j
        else:
            i += 1

    # 清理掉已经被安全吸收到表头的碎片
    classified = [c for c in classified if c[0] != "resolved"]

    # ---- 第二遍：合并 fragment 到 main ----
    result = []
    i = 0
    while i < len(classified):
        typ, row = classified[i]

        if typ == "header":
            result.append(row)
            i += 1
            continue

        if typ == "main":
            merged_row = list(row)
            # 向后合并后续的续行 fragment
            j = i + 1
            while j < len(classified) and classified[j][0] == "fragment":
                frag_row = classified[j][1]
                frag_first = str(frag_row[0] or "").strip() if frag_row else ""

                # 如果碎片的第一列是新的流水号片段（如 L00032），这是同一条记录的续行
                if _is_cmb_serial_start(frag_first):
                    _merge_into(merged_row, frag_row, prepend=False)
                    j += 1
                    continue

                # 如果碎片包含完整日期（新的交易起点），停止合并
                if _has_full_date(frag_row):
                    break

                # 否则合并（如对方名称续行）
                _merge_into(merged_row, frag_row, prepend=False)
                j += 1

            result.append(merged_row)
            i = j
            continue

        if typ == "fragment":
            # fragment 在 main 之前 → 收集到找到 main 行
            pending_fragments = [list(row)]
            j = i + 1
            while j < len(classified) and classified[j][0] == "fragment":
                pending_fragments.append(list(classified[j][1]))
                j += 1

            if j < len(classified) and classified[j][0] == "main":
                # 将前面的 fragment 合并到 main 行（日期在前，前置合并）
                merged_row = list(classified[j][1])
                for frag in pending_fragments:
                    _merge_into(merged_row, frag, prepend=True)
                # 继续向后合并后续的续行 fragment
                k = j + 1
                while k < len(classified) and classified[k][0] == "fragment":
                    frag_row = classified[k][1]
                    frag_first = str(frag_row[0] or "").strip() if frag_row else ""

                    if _is_cmb_serial_start(frag_first):
                        _merge_into(merged_row, frag_row, prepend=False)
                        k += 1
                        continue

                    if _has_full_date(frag_row):
                        break
                    _merge_into(merged_row, frag_row, prepend=False)
                    k += 1

                result.append(merged_row)
                i = k
            else:
                # 没有后续 main 行，fragment 作为独立行
                for frag in pending_fragments:
                    result.append(frag)
                i = j
            continue

        i += 1

    return result


def _has_full_date(row: list) -> bool:
    """
    判断一行是否包含完整日期（年-月-日 时:分:秒 格式）

    用于区分：
    - 日期碎片（如 2024-0）不应触发停止合并
    - 完整日期（如 2024-01-04 07:49:24）是新的交易起点
    """
    for cell in row[:5]:
        val = str(cell or "").strip()
        # 完整日期格式：2024-01-04 07:49:24 或 2024/01/04 07:49:24
        if re.search(r"\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}\s+\d{1,2}:\d{2}:\d{2}", val):
            return True
        # 或者日期后缀片段：1-04 07:49:24（被切断的日期后半部分）
        if re.search(r"\d{1,2}[\-/\.]\d{1,2}\s+\d{1,2}:\d{2}:\d{2}", val):
            return True
    return False


def _has_date(row: list) -> bool:
    """
    判断一行是否包含日期（扫描前4列）
    如果某个片段包含日期，那它通常是新交易的起点，不应该合并到前一条记录的尾部。
    """
    for cell in row[:4]:
        val = str(cell or "").strip()
        if re.search(r"(?:^|\s)\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}(?:\s|$)", val):
            return True
    return False


def _clean_raw_tables(tables: list) -> list:
    """
    在多行合并之前，先清洗掉绝对是页脚、表尾汇总的强特征噪声行。
    防止其被错误当做 Fragment 追加到上一页末尾的正常记录中。
    """
    cleaned = []
    # 强特征汇总关键字，绝不会自然出现在真实的单行交易备注片段中
    strict_noise_patterns = [
        r"本页小计", r"本页合计", r"期初余额", r"期末余额", r"本期贷方", r"本期借方",
        r"起止日期", r"打印日期", r"打印时间", r"以下空白", r"以上内容",
        r"收入总(?:金额|笔数)", r"支出总(?:金额|笔数)",
        r"第\s*\d+\s*[页/]", r"共\s*\d+\s*[页条笔]\s*记录?",
        r"总笔数", r"总金额",
        r"https?://",  # 过滤 URL
        r"ebank\.cmbchina",  # 招商银行网银 URL
        r"^\d+/\d+$",  # 页码标记如 "1/5"
    ]
    for row in tables:
        if not row: continue
        text = "".join(str(c or "") for c in row).strip()
        if not text: continue

        first = str(row[0] or "").strip()
        sec = str(row[1] or "") if len(row) > 1 else ""

        # 受保护的主键行（如果有明确序号+日期，或直接纯日期，绝对放行）
        is_seq = bool(re.match(r"^\d+$", first))
        has_date_near = bool(re.search(r"(?:^|\s)\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}", sec) or (len(row)>2 and re.search(r"(?:^|\s)\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}", str(row[2] or ""))))
        is_date_start = bool(re.match(r"^\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}", first))

        if (is_seq and has_date_near) or is_date_start:
            cleaned.append(row)
            continue

        is_strict = False
        for p in strict_noise_patterns:
            if re.search(p, text):
                is_strict = True
                break

        if not is_strict:
            cleaned.append(row)

    return cleaned


def _merge_into(target: list, source: list, prepend: bool = False):
    """
    将 source 行的非空单元格合并到 target 行

    Args:
        target: 目标行（会被修改）
        source: 源行
        prepend: True 表示源值放在前面（用于日期行合并到时间前面）
                 False 表示源值放在后面（用于续行追加）
    """
    for i, cell in enumerate(source):
        if cell and str(cell).strip():
            if i < len(target):
                target_val = str(target[i] or "").strip()
                cell_val = str(cell).strip()
                if not target_val:
                    target[i] = cell_val
                elif cell_val == target_val:
                    # 值相同，跳过避免重复
                    pass
                elif prepend:
                    target[i] = cell_val + "\n" + target_val
                else:
                    target[i] = target_val + "\n" + cell_val


def _detect_cmb_format(rows: list) -> bool:
    """
    检测是否为招商银行格式的PDF

    特征：存在多行以 C + 数字 开头的流水号片段
    """
    cmb_serial_count = 0
    for row in rows[:30]:  # 检查前30行
        if not row:
            continue
        first = str(row[0] or "").strip()
        if _is_cmb_serial_start(first):
            cmb_serial_count += 1
    # 如果有2个以上招商银行流水号起始，认为是招商银行格式
    return cmb_serial_count >= 2


def extract_tables(pdf_path: str) -> list:
    """
    从 PDF 中提取所有表格数据

    采用双策略：
    1. 先用默认策略（基于线条检测）尝试提取
    2. 如果提取结果无效（只提取到单列序号等），改用文本策略

    Args:
        pdf_path: PDF 文件路径

    Returns:
        所有页面的表格行合并后的列表
    """
    # === 策略1：Camelot Stream 模式（优先用于招商银行等无边框表格） ===
    camelot_rows = []
    if camelot is not None:
        try:
            tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
            if tables.n > 0:
                # 对每个表格单独检测格式并合并
                all_merged_rows = []
                first_header = None
                is_first_table = True
                MIN_COLUMNS = 8  # 最小列数要求，过滤掉结构不正确的表格

                for table in tables:
                    rows = table.df.values.tolist()

                    # 跳过列数不足的表格（可能是错误识别的表格结构）
                    if not rows or len(rows[0]) < MIN_COLUMNS:
                        continue

                    rows = _clean_raw_tables(rows)

                    # 检测是否为招商银行格式
                    if _detect_cmb_format(rows):
                        merged = _merge_cmb_rows(rows)
                        # 保存第一个表头用于后续表格
                        if first_header is None and merged:
                            first_header = merged[0]

                        # 跳过后续表格的表头行（只保留数据行）
                        if not is_first_table and merged:
                            # 检查第一行是否是表头，如果是则跳过
                            if is_header_row(merged[0]):
                                all_merged_rows.extend(merged[1:])
                            else:
                                all_merged_rows.extend(merged)
                        elif merged:
                            all_merged_rows.extend(merged)
                        is_first_table = False
                    # else: 跳过非招商银行格式的表格（如页面头部信息）

                if _is_valid_table_extraction(all_merged_rows):
                    camelot_rows = all_merged_rows
        except Exception as e:
            print(f"Camelot extraction failed: {e}")

    # === 策略1.5：pdfplumber lines 策略（补充 Camelot 未提取的页面）===
    # 某些 PDF（如招商银行第二页）使用 Camelot 会提取失败，
    # 但 lines 策略可以把每条交易提取为单行
    LINES_TABLE_SETTINGS = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
    }
    lines_rows = []
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            tables = page.extract_tables(LINES_TABLE_SETTINGS)
            for table in tables:
                if table:
                    # 解析单行格式的交易数据
                    parsed = _parse_single_cell_transactions(table)
                    if parsed and len(parsed) > 1:  # 有数据行
                        lines_rows.extend(parsed[1:])  # 跳过表头

    # 合并 Camelot 和 lines 策略的结果（按流水号去重）
    if camelot_rows and lines_rows:
        # 从 Camelot 结果中提取已有的流水号（去除换行符）
        existing_serials = set()
        for row in camelot_rows[1:]:  # 跳过表头
            if row and row[0]:
                # 清理流水号中的换行符
                clean_serial = re.sub(r'[\n\s]', '', str(row[0]))
                existing_serials.add(clean_serial)

        # 添加 lines 策略提取的新数据
        header = camelot_rows[0]
        for row in lines_rows:
            if row and row[0]:
                clean_serial = re.sub(r'[\n\s]', '', str(row[0]))
                if clean_serial not in existing_serials:
                    camelot_rows.append(row)
                    existing_serials.add(clean_serial)

        return camelot_rows
    elif camelot_rows:
        return camelot_rows
    elif lines_rows:
        # 只有 lines 策略有结果，添加表头
        header = ['交易流水号', '交易日期', '借方(出账)', '贷方(入账)', '余额',
                  '收(付)方名称', '收(付)方账号', '摘要', '交易类型', '一卡通号', '实例号']
        return [header] + lines_rows

    # === 策略2：pdfplumber 默认策略 ===
    all_rows_default = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if table:
                    all_rows_default.extend(table)

    all_rows_default = _clean_raw_tables(all_rows_default)

    # 检测是否为招商银行格式
    if _detect_cmb_format(all_rows_default):
        merged_default = _merge_cmb_rows(all_rows_default)
    else:
        merged_default = _merge_multiline_cells(all_rows_default)

    if _is_valid_table_extraction(merged_default):
        return merged_default

    # === 策略3：文本策略（作为兜底）===
    all_rows_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables(TEXT_TABLE_SETTINGS)
            for table in tables:
                if table:
                    all_rows_text.extend(table)

    all_rows_text = _clean_raw_tables(all_rows_text)

    # 检测是否为招商银行格式
    if _detect_cmb_format(all_rows_text):
        merged_text = _merge_cmb_rows(all_rows_text)
    else:
        merged_text = _merge_multiline_cells(all_rows_text)

    if _is_valid_table_extraction(merged_text):
        return merged_text

    # === 策略4：pdfplumber lines 策略（处理无边框表格）===
    # 某些 PDF（如招商银行第二页）使用其他策略会提取失败，
    # 但 lines 策略可以把每条交易提取为单行（虽然在一个单元格里）
    LINES_TABLE_SETTINGS = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
    }
    all_rows_lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables(LINES_TABLE_SETTINGS)
            for table in tables:
                if table:
                    all_rows_lines.extend(table)

    # 解析单行格式的交易数据
    merged_lines = _parse_single_cell_transactions(all_rows_lines)
    if _is_valid_table_extraction(merged_lines):
        return merged_lines

    # 都不行，返回默认策略的结果（可能为空）
    return merged_default if merged_default else merged_text


def _parse_single_cell_transactions(rows: list) -> list:
    """
    解析单行格式的招商银行交易数据

    某些 PDF 提取后每条交易在一个单元格里，格式如下：
    C05471 2024-1 对公转 269B0
    青岛******仁和控 9020301002
    K000EJ 2-28 1 260000.00 316,447.18 还借款 账正常 41294
    股集团有限公司 0100092264
    PZZ 5:36:47 提出 661

    需要将其解析为标准的11列格式
    """
    if not rows:
        return []

    # 标准表头
    HEADER = ['交易流水号', '交易日期', '借方(出账)', '贷方(入账)', '余额',
              '收(付)方名称', '收(付)方账号', '摘要', '交易类型', '一卡通号', '实例号']

    result = [HEADER]
    seen_serials = set()

    for row in rows:
        if not row or not row[0]:
            continue

        cell = str(row[0]).strip()
        if not cell:
            continue

        # 跳过非交易行（表头、URL、打印时间等）
        if '交易流' in cell and '水号' in cell:
            continue
        if 'http' in cell.lower():
            continue
        if re.match(r'^\d{4}/\d{1,2}/\d{1,2}\s+\d', cell):
            continue
        if '公司' in cell and '打印' in cell and len(cell) < 20:
            continue

        # 尝试解析交易数据
        parsed = _parse_cmb_single_cell(cell)
        if parsed and parsed[0] not in seen_serials:
            seen_serials.add(parsed[0])
            result.append(parsed)

    return result


def _parse_cmb_single_cell(cell: str) -> list:
    """
    解析单个单元格中的招商银行交易数据

    返回11列数据或 None
    """
    lines = [l.strip() for l in cell.split('\n') if l.strip()]
    if len(lines) < 3:
        return None

    # 合并所有文本
    full_text = ' '.join(lines)

    # 提取流水号：招商银行流水号被分散在多行
    # 格式：C + 4-5位数字 + 字母 + 5位字符 + 3位字母（共15位）
    # 例如：C05471K000EJPZZ
    #
    # 分散模式（5行结构）：
    # 行0: C05471 2024-1...  (第1部分：C + 4-5位数字)
    # 行1: 对方名称 账号...
    # 行2: K000EJ 2-28 1 金额 余额... (第2部分：字母 + 5位字符)
    # 行3: 对方名称续行 账号续行
    # 行4: PZZ 5:36:47... (第3部分：3位字母)

    serial_no = ''

    # 方法1：尝试从5行结构中提取
    if len(lines) >= 5:
        # 第1部分：行0开头，C + 4-5位数字（可能后面跟字母）
        part1_match = re.match(r'(C\d{4,5}[A-Z]?)', lines[0])
        # 第2部分：行2开头，字母 + 4-5位字符
        part2_match = re.match(r'([A-Z][A-Z0-9]{4,5})', lines[2])
        # 第3部分：行4开头，3-4位字符（字母或数字）
        part3_match = re.match(r'([A-Z0-9]{3,4})', lines[4])

        if part1_match and part2_match and part3_match:
            serial_no = part1_match.group(1) + part2_match.group(1) + part3_match.group(1)
            # 验证总长度
            if len(serial_no) != 15:
                serial_no = ''

    # 方法2：尝试从无空格文本中匹配完整流水号
    if not serial_no or len(serial_no) != 15:
        full_text_no_space = re.sub(r'[^A-Z0-9]', '', full_text)  # 只保留字母和数字
        serial_match = re.search(r'(C\d{4,5}[A-Z][A-Z0-9]{5}[A-Z]{3})', full_text_no_space)
        if serial_match:
            serial_no = serial_match.group(1)

    # 方法3：更宽松的匹配 - 找C开头的15位序列
    if not serial_no or len(serial_no) != 15:
        full_text_no_space = re.sub(r'[^A-Z0-9]', '', full_text)
        serial_match = re.search(r'(C[A-Z0-9]{14})', full_text_no_space)
        if serial_match:
            serial_no = serial_match.group(1)

    if not serial_no or len(serial_no) != 15:
        return None

    # 验证流水号格式
    # 有效格式：C0546RL00032SOZ, C05471K000EJPZZ, C05471N000HOB3Z
    # 无效格式：C0546R20240269B（包含日期年份）
    #
    # 规则：
    # 1. 长度必须是15位
    # 2. 以C + 数字开头
    # 3. 不包含明显的年份（2020-2029）
    if not re.match(r'^C\d{4,5}[A-Z]', serial_no):
        return None
    if re.search(r'202\d', serial_no):  # 排除包含年份的无效流水号
        return None

    # 提取金额：格式为 数字.数字（支出或收入）
    # 金额通常在第二或第三行，格式如 "260000.00 316,447.18"
    amounts = re.findall(r'([\d,]+\.\d{2})', full_text)

    expense = ''
    income = ''
    balance = ''

    if len(amounts) >= 2:
        # 第一个金额可能是支出/收入，第二个是余额
        # 通过上下文判断是支出还是收入
        balance = amounts[-1].replace(',', '')

        # 检查金额前面的文字来判断是支出还是收入
        for i, line in enumerate(lines):
            if amounts[0].replace(',', '') in line.replace(',', ''):
                # 检查这行是否有"还借款"等关键词，通常是支出
                if '还借款' in line or '工资' in line or '电费' in line or '加油' in line or '外包' in line:
                    expense = amounts[0].replace(',', '')
                else:
                    # 默认为支出
                    expense = amounts[0].replace(',', '')
                break
    elif len(amounts) == 1:
        balance = amounts[0].replace(',', '')

    # 提取日期时间
    # 格式通常是分散的：2024-1, 2-28, 5:36:47
    date_parts = re.findall(r'(\d{4}-\d{1,2})', full_text)
    time_match = re.search(r'(\d{1,2}:\d{2}:\d{2})', full_text)

    date_str = ''
    if date_parts:
        # 合并日期部分：2024-1 + 2-28 -> 2024-12-28
        date_part1 = date_parts[0]  # 2024-1
        # 从 full_text 中找到完整的日期
        full_date_match = re.search(r'(\d{4})-(\d{1,2})\s*(\d{1,2})-(\d{1,2})', full_text)
        if full_date_match:
            year = full_date_match.group(1)
            month = full_date_match.group(2) + full_date_match.group(3)
            day = full_date_match.group(4)
            date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        else:
            date_str = date_parts[0]

    if time_match:
        date_str = f"{date_str} {time_match.group(1)}"

    # 提取对方名称和账号
    counterparty_name = ''
    counterparty_account = ''

    # 对方名称通常是公司名，包含"公司"、"有限"等
    for line in lines:
        if '公司' in line or '有限' in line:
            # 提取公司名
            name_match = re.search(r'([^\d\n]+(?:公司|有限)[^\d\n]*)', line)
            if name_match:
                counterparty_name = name_match.group(1).strip()
            # 提取账号（通常是19位数字）
            acct_match = re.search(r'(\d{15,22})', line)
            if acct_match:
                counterparty_account = acct_match.group(1)
            break

    # 提取摘要
    description = ''
    desc_keywords = ['还借款', '工资', '电费', '加油费', '外包服务费', '手续费', '服务费', '往来款', '利息']
    for kw in desc_keywords:
        if kw in full_text:
            description = kw
            break

    # 提取交易类型
    transaction_type = ''
    if '对公转' in full_text:
        transaction_type = '对公转账正常提出'
    elif '企业银' in full_text:
        transaction_type = '企业银行各项费用'
    elif '实时代' in full_text:
        transaction_type = '实时代收业务付款'

    # 提取实例号：269B + 数字
    instance_match = re.search(r'(269B\d+)', full_text)
    instance_no = instance_match.group(1) if instance_match else ''

    # 一卡通号通常为空
    card_no = ''

    return [serial_no, date_str, expense, income, balance,
            counterparty_name, counterparty_account, description,
            transaction_type, card_no, instance_no]


def _find_header_row(rows: list) -> tuple:
    """
    在表格行中找到表头行

    Returns:
        (header_index, header_row) 或 (None, None) 如果未找到
    """
    for i, row in enumerate(rows):
        if is_header_row(row):
            return i, row
    return None, None


def _clean_time_string(val: str) -> str:
    """
    清理合并后的时间字符串，去除重复的日期，缝合被暴切的时间，并调整最终格式
    """
    if not val: return val
    
    # 针对被无情物理水平切断的字符串进行缝合（例如招商银行的 "2024-0\n1-04 0" -> 缝合并踢出单独的0 -> "2024-01-04"）
    val = re.sub(r"(\d{4}[\-/\.]\d*)\s*\n\s*(\d{1,2}[\-/\.]\d{1,2})", r"\1\2", val)
    
    parts = [p.strip() for p in val.replace(" ", "\n").split('\n') if p.strip()]
    dates, times, others = [], [], []
    for p in parts:
        if re.match(r"^\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}$", p):
            if p not in dates: dates.append(p)
        elif re.match(r"^\d{1,2}:\d{1,2}:\d{1,2}$", p):
            if p not in times: times.append(p)
        # 很多时候数字 0 会单独占一行（被空格隔开的时间前导0之类），直接丢掉它
        elif p == "0":
            continue
        else:
            if p not in others: others.append(p)
    res = []
    if dates: res.append(dates[0])
    if times: res.append(times[0])
    res.extend(others)
    if not others and len(res) <= 2:
        return " ".join(res)
    return "\n".join(res)


def _fix_camelot_shifted_row(row: list, mapped_len: int) -> list:
    """如果 Camelot 在某一页因为无边框少识别了一列（比如余额和币种挤在一起），尝试动态拆分修复"""
    if len(row) == mapped_len - 1:
        currencies = ["人民币", "美元", "欧元", "港币", "日元", "CNY", "USD", "RMB"]
        for i in range(len(row)):
            val = str(row[i] or "").replace("\n", "").strip()
            for curr in currencies:
                if curr in val and len(val) > len(curr):
                    num = val.replace(curr, "").strip()
                    if re.match(r"^[\d,\.\-]+$", num):
                        # Assume standard order: Balance -> Currency
                        return row[:i] + [num, curr] + row[i+1:]
    return row


def parse_native_pdf(pdf_path: str) -> dict:
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
        }
    """
    # 1. 检测是否为原生 PDF
    if not is_native_pdf(pdf_path):
        return {
            "error": "该 PDF 不是原生电子版，请使用 AI 识别功能处理扫描件",
            "is_native": False,
        }

    # 2. 提取全文文本
    full_text = extract_full_text(pdf_path)

    # 3. 识别银行类型
    bank_type = detect_bank_type(full_text)

    # 4. 提取汇总信息
    summary = extract_summary(full_text)

    # 5. 提取表格数据
    all_rows = extract_tables(pdf_path)

    if not all_rows:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
        return {
            "is_native": True,
            "bank_type": bank_type,
            "summary": summary,
            "transactions": [],
            "headers": [],
            "raw_headers": [],
            "page_count": page_count,
            "total_rows": 0,
            "error": "未检测到表格数据",
        }

    # 6. 查找表头行
    header_idx, header_row = _find_header_row(all_rows)

    if header_idx is None:
        # 没找到表头，使用第一行作为表头
        header_idx = 0
        header_row = all_rows[0]

    # 7. 表头映射
    raw_headers = [str(h or "").strip() for h in header_row]
    mapped_headers = map_headers(raw_headers)

    # 8. 解析数据行
    transactions = []
    seen_records = set()
    for row in all_rows[header_idx + 1:]:
        # 跳过噪声行和重复表头行
        if is_noise_row(row) or is_header_row(row):
            continue

        # 尝试修复因为缺少边界导致金额与币种合并的漂移问题
        row = _fix_camelot_shifted_row(row, len(mapped_headers))

        record = {}
        for j, cell in enumerate(row):
            if j < len(mapped_headers):
                field = mapped_headers[j]
                val = str(cell or "").strip()
                if field in ["transaction_time", "transaction_date"]:
                    val = _clean_time_string(val)
                else:
                    # 原生PDF跨行合并后含有 \n，按用户要求将其剔除，防止Excel中撑大行高
                    val = val.replace('\n', '')
                record[field] = val
        
        # 过滤全空记录
        if any(v for v in record.values()):
            # 全表字段级别去重机制：防止底层提取器因为嵌套边框等复杂结构，把同一页的同一整块表格重叠提取了两遍
            record_tuple = tuple((k, v) for k, v in record.items())
            if record_tuple not in seen_records:
                seen_records.add(record_tuple)
                transactions.append(record)

    # 获取页数
    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)

    return {
        "is_native": True,
        "bank_type": bank_type,
        "summary": summary,
        "transactions": transactions,
        "headers": mapped_headers,
        "raw_headers": raw_headers,
        "page_count": page_count,
        "total_rows": len(transactions),
    }
