"""
山东地方银行处理器（潍坊银行、莱商银行、齐鲁银行、德州银行等）

这些银行的 PDF 格式特点：
1. 每条交易占用多行（日期行 + 主数据行 + 续行）
2. 对方户名经常跨行显示
3. pdfplumber text 策略可以提取，但需要合并多行
"""
import re
from typing import List, Any, Tuple, Optional

from ..base_processor import BaseBankProcessor
from ...models.schema import BankSchema
from ...models.result import Transaction


class ShandongLocalProcessor(BaseBankProcessor):
    """山东地方银行处理器"""

    def __init__(self, schema: BankSchema):
        super().__init__(schema)
        self.date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        self.time_pattern = re.compile(r'^\d{2}:\d{2}:\d{2}$')
        self.serial_pattern = re.compile(r'^\d+$')

    def _find_header_row(self, rows: List[List[Any]]) -> Tuple[Optional[int], Optional[List[Any]]]:
        """
        找到表头行

        山东地方银行的表头特征：包含"序号"和"交易时间"
        """
        for i, row in enumerate(rows):
            if not row:
                continue
            # 检查是否包含"序号"和"交易时间"
            row_text = " ".join(str(c or "") for c in row)
            if "序号" in row_text and "交易时间" in row_text:
                return i, row
        return None, None

    def detect_format(self, rows: List[List[Any]]) -> bool:
        """检测是否为山东地方银行格式"""
        if not rows or len(rows) < 3:
            return False

        # 检查是否有日期单独一行的特征
        for row in rows[:20]:
            if len(row) >= 2:
                second_cell = str(row[1] or "").strip()
                if self.date_pattern.match(second_cell):
                    return True
        return False

    def process(self, rows: List[List[Any]], headers: List[str]) -> Tuple[List[str], List[Transaction]]:
        """
        处理表格数据

        Args:
            rows: 提取的表格行（包含表头）
            headers: 识别出的表头

        Returns:
            (标准表头, 交易记录列表)
        """
        # 1. 找到第一个表头行
        header_idx, header_row = self._find_header_row(rows)
        if header_idx is None:
            return [], []

        # 2. 映射表头
        raw_headers = [str(h or "").strip() for h in header_row]
        mapped_headers = self._map_headers(raw_headers)

        # 3. 检查是否有合并列"对方户名 摘要备注"（只有9列的情况）
        merged_col_idx = self._find_merged_column(mapped_headers)
        has_merged_column = merged_col_idx is not None

        # 4. 分段处理数据（每页可能有不同的列结构）
        # 找出所有表头行的位置
        header_indices = []
        for i, row in enumerate(rows):
            if self._is_header_row(row):
                # 检查这行的列数和是否是合并列格式
                row_headers = [str(h or "").strip() for h in row]
                merged_idx = self._find_merged_column(row_headers)
                header_indices.append((i, len(row), merged_idx))

        # 5. 合并多行数据
        data_rows = rows[header_idx + 1:]
        merged_rows = self._merge_multiline_rows_v2(data_rows, header_indices, len(mapped_headers))

        # 6. 如果有合并列，拆分并调整表头
        if has_merged_column:
            mapped_headers = self._split_merged_header(mapped_headers, merged_col_idx)
            merged_rows = [self._split_merged_row(row, merged_col_idx) for row in merged_rows]

        # 7. 清洗并转换为交易记录
        transactions = []
        for row in merged_rows:
            if self._is_noise_row(row):
                continue

            # 先检测并拆分9列格式的行（在补齐列数之前）
            if len([c for c in row if c and str(c).strip()]) == 9:
                row = self._auto_split_row(row)

            # 补齐列数
            while len(row) < len(mapped_headers):
                row.append("")
            row = row[:len(mapped_headers)]

            transaction = self._row_to_transaction(row, mapped_headers)
            if transaction:
                transactions.append(transaction)

        return mapped_headers, transactions

    def _merge_multiline_rows_v2(self, rows: List[List[Any]], header_indices: List[Tuple], num_columns: int) -> List[List[Any]]:
        """
        合并多行数据（支持不同页不同列结构）
        """
        merged = []
        current_row = None
        current_date = None
        pending_parts = []  # 待合并的部分数据行（日期行之后、主数据行之前）
        current_has_merged = False  # 当前交易是否是9列合并格式

        for row_idx, row in enumerate(rows):
            if not row or not any(row):
                continue

            # 清理行数据
            row = [str(c or "").strip() for c in row]
            original_len = len(row)  # 保存原始长度

            # 检测是否是9列格式（合并列）
            is_9col_format = original_len == 9 and any(c for c in row)

            # 补齐列数
            while len(row) < num_columns:
                row.append("")
            row = row[:num_columns]

            # 检测并跳过重复的表头行（分页时出现）
            if self._is_header_row(row):
                continue

            # 检测日期行（日期在第二列）
            date_val = row[1] if len(row) > 1 else ""
            if self.date_pattern.match(date_val):
                current_date = date_val
                pending_parts = []
                continue

            # 检测主数据行（序号在第一列，时间在第二列）
            first_cell = row[0]
            second_cell = row[1] if len(row) > 1 else ""

            if self.serial_pattern.match(first_cell) and self.time_pattern.match(second_cell):
                # 这是主数据行，开始新记录
                if current_row is not None:
                    merged.append(current_row)

                # 合并日期到时间列
                if current_date:
                    row[1] = f"{current_date} {second_cell}"

                # 更新当前交易的合并格式状态
                current_has_merged = is_9col_format

                # 先合并待处理的部分数据
                for part_row, part_is_9col in pending_parts:
                    self._merge_contination_row(row, part_row, part_is_9col)
                pending_parts = []

                current_row = row
                current_date = None
            else:
                # 这是续行
                if current_date:
                    # 日期行之后的数据，先暂存，等主数据行出现后合并
                    pending_parts.append((row, is_9col_format))
                elif current_row is not None:
                    # 合并到当前行
                    self._merge_contination_row(current_row, row, is_9col_format)

        # 添加最后一行
        if current_row is not None:
            merged.append(current_row)

        return merged

    def _merge_contination_row(self, current_row: List[str], cont_row: List[str], is_9col_format: bool):
        """合并续行数据到当前行"""
        for i, cell in enumerate(cont_row):
            if cell and i < len(current_row):
                current_val = current_row[i]
                if current_val:
                    # 如果续行是9列格式，最后一列需要特殊处理
                    if is_9col_format and i == 8:
                        safe_current_val = current_val.replace("\n", " ")
                        safe_cell = cell.replace("\n", " ")
                        
                        # 续行格式: "司 联汇兑"（空格分隔对方户名续接和摘要续接）
                        if " " in safe_cell:
                            sub_parts = safe_cell.split(" ", 1)
                            name_suffix = sub_parts[0].strip()
                            desc_suffix = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                            
                            # 智能拆分当前值：查找摘要起始位置
                            split_pos = self._find_desc_start(safe_current_val)
                            if split_pos > 0:
                                curr_name = safe_current_val[:split_pos].strip()
                                curr_desc = safe_current_val[split_pos:].strip()
                            else:
                                if " " in safe_current_val:
                                    curr_parts = safe_current_val.split(" ", 1)
                                    curr_name = curr_parts[0]
                                    curr_desc = curr_parts[1] if len(curr_parts) > 1 else ""
                                else:
                                    curr_name = safe_current_val
                                    curr_desc = ""
                            
                            new_name = (curr_name + name_suffix).strip()
                            new_desc = (curr_desc + desc_suffix).strip()
                            current_row[i] = f"{new_name} {new_desc}" if new_desc else new_name
                        else:
                            # 只有一个词，需要启发式判断属于户名还是摘要
                            if "\n" in current_val:
                                curr_parts = current_val.split("\n", 1)
                                curr_name = curr_parts[0].strip()
                                curr_desc = curr_parts[1].strip()
                            else:
                                split_pos = self._find_desc_start(safe_current_val)
                                if split_pos > 0:
                                    curr_name = safe_current_val[:split_pos].strip()
                                    curr_desc = safe_current_val[split_pos:].strip()
                                else:
                                    if " " in safe_current_val:
                                        curr_parts = safe_current_val.split(" ", 1)
                                        curr_name = curr_parts[0]
                                        curr_desc = curr_parts[1] if len(curr_parts) > 1 else ""
                                    else:
                                        curr_name = safe_current_val
                                        curr_desc = ""
                                        
                            name_keywords = ["公司", "厂", "店", "部", "中心", "合作社", "局", "学校", "院", "所", "处"]
                            if any(kw in safe_cell for kw in name_keywords):
                                name_suffix = safe_cell
                                desc_suffix = ""
                            elif not curr_desc and self._find_desc_start(safe_cell) > 0:
                                name_suffix = ""
                                desc_suffix = safe_cell
                            else:
                                # 默认追加到户名末尾
                                name_suffix = safe_cell
                                desc_suffix = ""
                                
                            new_name = (curr_name + name_suffix).strip()
                            new_desc = (curr_desc + desc_suffix).strip()
                            current_row[i] = f"{new_name} {new_desc}" if new_desc else new_name
                    else:
                        current_row[i] = current_val + cell
                else:
                    current_row[i] = cell

    def _find_desc_start(self, text: str) -> int:
        """找到摘要的起始位置"""
        # 常见的摘要前缀关键词
        desc_keywords = [
            "网银转账", "网银互联", "网银汇兑", "转账支取", "汇款|", "货款|",
            "税款|", "费用|", "工程款|", "往来款|", "投标|", "招标|"
        ]
        for kw in desc_keywords:
            pos = text.find(kw)
            if pos > 0:  # 找到了，且不在开头
                return pos
        # 如果没找到，尝试用 | 分隔符
        if "|" in text:
            # 找到 | 之前最后一个非公司名后缀的位置
            pos = text.find("|")
            # 向前查找摘要开始位置
            for i in range(pos - 1, 0, -1):
                if text[i:i+2] in ["网银", "转账", "汇款", "税款", "费用"]:
                    return i
        return 0

    def _find_merged_column(self, headers: List[str]) -> Optional[int]:
        """查找合并列"对方户名 摘要备注"的索引"""
        for i, h in enumerate(headers):
            h_clean = str(h or "").strip()
            # 检查是否是合并列（包含两个标题）
            if "对方户名" in h_clean and "摘要备注" in h_clean:
                return i
        return None

    def _split_merged_header(self, headers: List[str], idx: int) -> List[str]:
        """拆分合并的表头"""
        result = headers[:idx]
        result.extend(["对方户名", "摘要备注"])
        result.extend(headers[idx + 1:])
        return result

    def _split_merged_row(self, row: List[Any], idx: int) -> List[Any]:
        """拆分合并的数据行（对方户名 摘要备注格式）"""
        if idx >= len(row):
            return row

        cell_value = str(row[idx] or "").strip()

        # 优先用空格分隔符拆分（如 "袁秀玲 网银转账|汇款"）
        if " " in cell_value:
            parts = cell_value.split(" ", 1)
            counterparty_name = parts[0].strip()
            description = parts[1].strip() if len(parts) > 1 else ""
        else:
            # 没有空格，全部作为对方户名
            counterparty_name = cell_value
            description = ""

        result = row[:idx]
        result.extend([counterparty_name, description])
        result.extend(row[idx + 1:])
        return result

    def _needs_split(self, row: List[Any]) -> bool:
        """检测行数据是否需要拆分（9列格式且最后一列包含空格）"""
        # 统计非空列数
        non_empty = [c for c in row if c and str(c).strip()]
        if len(non_empty) == 9:
            # 数据已经被补齐到10列，第9列（索引8）包含了合并的内容，第10列应该是空的
            target_cell = str(row[8] if len(row) > 8 else row[-1] or "").strip()
            # 如果该列包含空格，可能需要拆分
            if " " in target_cell:
                return True
        return False

    def _auto_split_row(self, row: List[Any]) -> List[Any]:
        """自动检测并拆分9列格式的行"""
        if self._needs_split(row):
            return self._split_merged_row(row, 8)  # 索引8是最后一列
        return row

    def _is_header_row(self, row: List[str]) -> bool:
        """检测是否为表头行（分页时重复出现的表头）"""
        header_keywords = ["序号", "交易时间", "交易渠道", "收入", "支出", "账户余额", "币种", "对方账号", "对方户名", "摘要备注"]
        row_text = "".join(str(c or "") for c in row)
        match_count = sum(1 for kw in header_keywords if kw in row_text)
        # 如果包含3个以上表头关键词，认为是表头行
        return match_count >= 3

    def _merge_multiline_rows(self, rows: List[List[Any]], num_columns: int, has_merged_column: bool = False) -> List[List[Any]]:
        """
        合并多行数据

        山东地方银行格式：
        - 日期行: ['', '2024-01-02', '', '', '', '', '', '', '', '']
        - 主数据行: ['1', '10:48:41', '网上银行', '1000000.00', '0.00', '1361270.91', '人民币', '80901320101421032', '禹城市宏昌建设有限', '网银转账|工程进度款']
        - 续行: ['', '', '', '', '', '', '', '681', '公司', '']
        - 表头行（分页重复）: ['序号', '交易时间', '交易渠道', ...]  需要跳过

        当has_merged_column=True时，最后一列是"对方户名 摘要备注"合并列：
        - 主数据行: ['43', '14:40:19', ..., '16120453192000450', '德州永安置业有限公网银互联汇兑|网银互']
        - 续行: ['', '', ..., '75', '司 联汇兑']  # 空格分隔的两部分
        """
        merged = []
        current_row = None
        current_date = None

        for row in rows:
            if not row or not any(row):
                continue

            # 清理行数据
            row = [str(c or "").strip() for c in row]
            while len(row) < num_columns:
                row.append("")
            row = row[:num_columns]

            # 检测并跳过重复的表头行（分页时出现）
            if self._is_header_row(row):
                continue

            # 检测日期行（日期在第二列）
            date_val = row[1] if len(row) > 1 else ""
            if self.date_pattern.match(date_val):
                current_date = date_val
                continue

            # 检测主数据行（序号在第一列，时间在第二列）
            first_cell = row[0]
            second_cell = row[1] if len(row) > 1 else ""

            if self.serial_pattern.match(first_cell) and self.time_pattern.match(second_cell):
                # 这是主数据行，开始新记录
                if current_row is not None:
                    merged.append(current_row)

                # 合并日期到时间列
                if current_date:
                    row[1] = f"{current_date} {second_cell}"

                current_row = row
                current_date = None
            else:
                # 这是续行，合并到当前行
                if current_row is not None:
                    for i, cell in enumerate(row):
                        if cell and i < len(current_row):
                            current_val = current_row[i]
                            if current_val:
                                # 如果是合并列（最后一列），需要特殊处理
                                if has_merged_column and i == num_columns - 1:
                                    # 续行格式: "司 联汇兑"（空格分隔对方户名续接和摘要续接）
                                    if " " in cell:
                                        sub_parts = cell.split(" ", 1)
                                        name_suffix = sub_parts[0].strip()
                                        desc_suffix = sub_parts[1].strip() if len(sub_parts) > 1 else ""
                                        # 用空格拆分当前值
                                        if " " in current_val:
                                            curr_parts = current_val.split(" ", 1)
                                            curr_name = curr_parts[0]
                                            curr_desc = curr_parts[1] if len(curr_parts) > 1 else ""
                                            current_row[i] = curr_name + name_suffix + " " + curr_desc + desc_suffix
                                        else:
                                            # 当前值没有空格，直接追加
                                            current_row[i] = current_val + name_suffix + " " + desc_suffix
                                    else:
                                        # 续行没有空格，直接追加
                                        current_row[i] = current_val + cell
                                else:
                                    # 普通列，直接追加
                                    current_row[i] = current_val + cell
                            else:
                                current_row[i] = cell

        # 添加最后一行
        if current_row is not None:
            merged.append(current_row)

        return merged

    def _map_headers(self, raw_headers: List[str]) -> List[str]:
        """保留原始中文表头"""
        result = []
        seen = {}
        for h in raw_headers:
            h_clean = str(h or "").strip()
            # 保留原始中文表头，只清理空白
            if not h_clean:
                h_clean = ""

            # 确保唯一性
            if h_clean in seen:
                seen[h_clean] += 1
                h_clean = f"{h_clean}_{seen[h_clean]}"
            else:
                seen[h_clean] = 0

            result.append(h_clean)

        return result

    def _is_noise_row(self, row: List[Any]) -> bool:
        """判断是否为噪声行"""
        if not row:
            return True

        text = "".join(str(c or "") for c in row).strip()
        if not text:
            return True

        # 噪声关键词
        noise_keywords = [
            "本页小计", "本页合计", "累计", "合计",
            "以上内容", "以下空白", "共计",
            "打印时间", "打印日期",
            "期初余额", "期末余额",
            "总金额", "总笔数",
            "第.*页", "单位:元",
        ]

        for kw in noise_keywords:
            if re.search(kw, text):
                return True

        return False
