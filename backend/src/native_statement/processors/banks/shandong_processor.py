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
        # 1. 找到表头行
        header_idx, header_row = self._find_header_row(rows)
        if header_idx is None:
            return [], []

        # 2. 映射表头
        raw_headers = [str(h or "").strip() for h in header_row]
        mapped_headers = self._map_headers(raw_headers)

        # 3. 合并多行数据
        data_rows = rows[header_idx + 1:]
        merged_rows = self._merge_multiline_rows(data_rows, len(mapped_headers))

        # 4. 清洗并转换为交易记录
        transactions = []
        for row in merged_rows:
            if self._is_noise_row(row):
                continue

            # 补齐列数
            while len(row) < len(mapped_headers):
                row.append("")
            row = row[:len(mapped_headers)]

            transaction = self._row_to_transaction(row, mapped_headers)
            if transaction:
                transactions.append(transaction)

        return mapped_headers, transactions

    def _is_header_row(self, row: List[str]) -> bool:
        """检测是否为表头行（分页时重复出现的表头）"""
        header_keywords = ["序号", "交易时间", "交易渠道", "收入", "支出", "账户余额", "币种", "对方账号", "对方户名", "摘要备注"]
        row_text = "".join(str(c or "") for c in row)
        match_count = sum(1 for kw in header_keywords if kw in row_text)
        # 如果包含3个以上表头关键词，认为是表头行
        return match_count >= 3

    def _merge_multiline_rows(self, rows: List[List[Any]], num_columns: int) -> List[List[Any]]:
        """
        合并多行数据

        山东地方银行格式：
        - 日期行: ['', '2024-01-02', '', '', '', '', '', '', '', '']
        - 主数据行: ['1', '10:48:41', '网上银行', '1000000.00', '0.00', '1361270.91', '人民币', '80901320101421032', '禹城市宏昌建设有限', '网银转账|工程进度款']
        - 续行: ['', '', '', '', '', '', '', '681', '公司', '']
        - 表头行（分页重复）: ['序号', '交易时间', '交易渠道', ...]  需要跳过
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
                            # 合并非空单元格
                            if current_row[i]:
                                current_row[i] = current_row[i] + cell
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
