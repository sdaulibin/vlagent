"""
银行处理器基类
"""
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple

from ..models.schema import BankSchema
from ..models.result import Transaction


class BaseBankProcessor(ABC):
    """
    银行流水处理器基类

    每个银行可以有自己的处理器来处理特定的格式问题。
    """

    def __init__(self, schema: BankSchema):
        self.schema = schema

    @abstractmethod
    def detect_format(self, rows: List[List[Any]]) -> bool:
        """
        检测数据是否匹配该银行的格式

        Args:
            rows: 提取的表格行

        Returns:
            是否匹配
        """
        pass

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

        # 3. 合并多行（如果需要）
        if self.schema.extraction.multiline_merge:
            data_rows = self.merge_multiline_rows(rows[header_idx + 1:])
        else:
            data_rows = rows[header_idx + 1:]

        # 4. 清洗并转换为交易记录
        transactions = []
        for row in data_rows:
            if self._is_noise_row(row):
                continue

            transaction = self._row_to_transaction(row, mapped_headers)
            if transaction:
                transactions.append(transaction)

        return mapped_headers, transactions

    def _find_header_row(self, rows: List[List[Any]]) -> Tuple[Optional[int], Optional[List[Any]]]:
        """找到表头行（支持多行表头）"""
        header_keywords = [
            "交易时间", "交易日期", "记账日期", "日期",
            "收入", "支出", "借方", "贷方", "余额",
            "对方账号", "对方户名", "摘要", "流水号",
            "收(付)方", "账号", "交易类型", "实例",
        ]

        # 扩展搜索范围到前20行
        for i, row in enumerate(rows[:20]):
            if not row:
                continue
            row_text = "".join(str(c or "") for c in row)
            match_count = sum(1 for kw in header_keywords if kw in row_text)
            if match_count >= 2:  # 降低门槛
                # 尝试合并后续几行作为表头
                merged_header = list(row)
                for j in range(i + 1, min(i + 4, len(rows))):
                    next_row = rows[j]
                    next_text = "".join(str(c or "") for c in next_row)
                    # 如果下一行也是表头相关的内容，合并
                    if sum(1 for kw in header_keywords if kw in next_text) >= 1:
                        # 合并到 merged_header
                        for k, cell in enumerate(next_row):
                            if k < len(merged_header):
                                cell_val = str(cell or "").strip()
                                if cell_val:
                                    if merged_header[k]:
                                        merged_header[k] = str(merged_header[k]) + cell_val
                                    else:
                                        merged_header[k] = cell_val
                            else:
                                merged_header.append(str(cell or "").strip())
                    else:
                        break

                return i, merged_header

        return None, None

    def _map_headers(self, raw_headers: List[str]) -> List[str]:
        """映射表头到标准字段名"""
        # 从模版获取映射
        header_mapping = self.schema.get_header_mapping()

        # 默认映射
        default_mapping = {
            "序号": "sequence",
            "交易时间": "transaction_time",
            "交易日期": "transaction_date",
            "记账日期": "transaction_date",
            "日期": "transaction_date",
            "收入": "income",
            "收入金额": "income",
            "贷方发生额": "income",
            "贷方金额": "income",
            "贷方(入账)": "income",
            "入账金额": "income",
            "支出": "expense",
            "支出金额": "expense",
            "借方发生额": "expense",
            "借方金额": "expense",
            "借方(出账)": "expense",
            "出账金额": "expense",
            "余额": "balance",
            "账户余额": "balance",
            "币种": "currency",
            "对方账号": "counterparty_account",
            "对方户名": "counterparty_name",
            "对方名称": "counterparty_name",
            "收(付)方名称": "counterparty_name",
            "收(付)方账号": "counterparty_account",
            "摘要": "description",
            "摘要备注": "description",
            "用途": "purpose",
            "备注": "remark",
            "流水号": "serial_no",
            "交易流水号": "serial_no",
            "凭证号": "voucher_no",
            "借贷标志": "debit_credit",
            "交易渠道": "channel",
            "交易类型": "transaction_type",
        }

        # 合并映射（模版优先）
        mapping = {**default_mapping, **header_mapping}

        result = []
        seen = {}
        for h in raw_headers:
            h_clean = re.sub(r"\s+", "", h)
            mapped = mapping.get(h) or mapping.get(h_clean, h)

            # 确保唯一性
            if mapped in seen:
                seen[mapped] += 1
                mapped = f"{mapped}_{seen[mapped]}"
            else:
                seen[mapped] = 0

            result.append(mapped)

        return result

    def merge_multiline_rows(self, rows: List[List[Any]]) -> List[List[Any]]:
        """
        合并多行单元格（子类可覆盖）

        Args:
            rows: 数据行

        Returns:
            合并后的行
        """
        return rows

    def _is_noise_row(self, row: List[Any]) -> bool:
        """判断是否为噪声行"""
        if not row:
            return True

        text = "".join(str(c or "") for c in row).strip()
        if not text:
            return True

        noise_keywords = [
            "本页小计", "本页合计", "累计", "合计",
            "以上内容", "以下空白", "共计",
            "打印时间", "打印日期",
            "期初余额", "期末余额",
            "总金额", "总笔数",
        ]

        for kw in noise_keywords:
            if kw in text:
                return True

        return False

    def _row_to_transaction(self, row: List[Any], headers: List[str]) -> Optional[Transaction]:
        """将行数据转换为 Transaction 对象"""
        if not row or not any(row):
            return None

        # 确保行长度与表头一致
        while len(row) < len(headers):
            row.append("")
        row = row[:len(headers)]

        tx = Transaction()
        extra = {}

        for i, cell in enumerate(row):
            field = headers[i]
            value = str(cell or "").strip()

            # 根据后处理配置清洗值
            if self.schema.post_processing.remove_newlines:
                value = value.replace("\n", "")

            # 设置字段值
            if hasattr(tx, field):
                setattr(tx, field, value)
            else:
                extra[field] = value

        tx.extra = extra
        return tx

    def clean_field(self, field_name: str, value: str) -> str:
        """
        清洗特定字段的值（子类可覆盖）

        Args:
            field_name: 字段名
            value: 原始值

        Returns:
            清洗后的值
        """
        return value
