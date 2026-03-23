"""
招商银行处理器

处理招商银行流水的特殊格式：
- 多行合并（流水号被拆成多行）
- 单元格格式解析
"""
import re
from typing import List, Any, Optional, Tuple

from ...models.schema import BankSchema
from ..base_processor import BaseBankProcessor
from ..row_merger import RowMerger


class CMBProcessor(BaseBankProcessor):
    """
    招商银行处理器

    招商银行 PDF 特点：
    - 表头被拆成多行
    - 每条交易被拆成多行（3-5行）
    - 流水号格式：C0546RL00032SOZ，被切成多个片段
    """

    def __init__(self, schema: BankSchema):
        super().__init__(schema)
        self.row_merger = RowMerger()

    def detect_format(self, rows: List[List[Any]]) -> bool:
        """检测是否为招商银行格式"""
        # 检查是否有招商银行流水号片段
        cmb_serial_count = 0
        for row in rows[:30]:
            if not row:
                continue
            first = str(row[0] or "").strip()
            if self._is_cmb_serial_start(first):
                cmb_serial_count += 1

        return cmb_serial_count >= 2

    def _is_cmb_serial_start(self, value: str) -> bool:
        """
        检测是否为招商银行流水号的起始部分

        格式：C + 3-5位数字 + 可选字母
        例如：C0546R, C03471N
        """
        if not value:
            return False
        value = value.strip()

        lines = [l.strip() for l in value.split("\n") if l.strip()]
        if not lines:
            return False

        for line in lines[:2]:
            first_word = line.split(" ")[0] if line else ""
            if re.match(r"^C\d{3,5}[A-Z]?$", first_word):
                return True

        return False

    def merge_multiline_rows(self, rows: List[List[Any]]) -> List[List[Any]]:
        """合并招商银行的多行数据"""
        if not rows:
            return rows

        result = []
        i = 0

        # 首先找到表头结束位置
        header_end_idx = 0
        for idx, row in enumerate(rows):
            first = str(row[0] or "").strip() if row else ""
            if self._is_cmb_serial_start(first):
                header_end_idx = idx
                break

        # 合并表头行
        if header_end_idx > 0:
            header_rows = rows[:header_end_idx]
            merged_header = self._merge_cmb_header(header_rows)
            result.append(merged_header)
            i = header_end_idx
        else:
            i = 0

        # 合并数据行
        while i < len(rows):
            row = rows[i]
            first = str(row[0] or "").strip() if row else ""

            if self._is_cmb_serial_start(first):
                merged_row = list(row)
                # 向后合并直到下一个流水号起始
                j = i + 1
                while j < len(rows):
                    next_row = rows[j]
                    next_first = str(next_row[0] or "").strip() if next_row else ""

                    if self._is_cmb_serial_start(next_first):
                        break
                    if self._is_header_row(next_row):
                        break
                    # 检查是否有完整日期（新交易）
                    if self._has_full_date(next_row):
                        break

                    # 合并这一行
                    self._merge_into(merged_row, next_row)
                    j += 1

                result.append(merged_row)
                i = j
            else:
                result.append(list(row))
                i += 1

        return result

    def _merge_cmb_header(self, header_rows: List[List[Any]]) -> List[str]:
        """合并招商银行的多行表头"""
        if not header_rows:
            return []

        # 过滤非表头行
        filtered_rows = []
        for row in header_rows:
            if not row:
                continue
            row_text = "".join(str(c or "") for c in row)

            # 跳过打印时间、URL等
            if re.search(r"\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{2}", row_text):
                continue
            if "http" in row_text.lower():
                continue
            if re.match(r"^公司\s*打印$", row_text.replace("\n", "")):
                continue

            # 保留包含表头关键词的行
            if re.search(r"[交易流日期借方贷方余额收付账号摘要类型通号]", row_text):
                filtered_rows.append(row)

        if not filtered_rows:
            return []

        # 获取最大列数
        max_cols = max(len(row) for row in filtered_rows) if filtered_rows else 0

        # 逐列合并
        merged = [""] * max_cols
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
            h = re.sub(r"\s+", "", h)
            h = h.replace("\n", "")
            h = re.sub(r"^[^:：]+[:：]", "", h)  # 去除前缀
            h = re.sub(r"^(公司|打印)+", "", h)
            cleaned.append(h)

        return cleaned

    def _has_full_date(self, row: List[Any]) -> bool:
        """判断是否包含完整日期时间"""
        for cell in row[:5]:
            val = str(cell or "").strip()
            if re.search(r"\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}\s+\d{1,2}:\d{2}:\d{2}", val):
                return True
            if re.search(r"\d{1,2}[\-/\.]\d{1,2}\s+\d{1,2}:\d{2}:\d{2}", val):
                return True
        return False

    def _is_header_row(self, row: List[Any]) -> bool:
        """判断是否为表头行"""
        row_text = "".join(str(c or "") for c in row)
        header_keywords = ["交易流", "交易日", "借方", "贷方", "余额", "收付方", "摘要"]
        match_count = sum(1 for kw in header_keywords if kw in row_text)
        return match_count >= 3

    def _merge_into(self, target: List[Any], source: List[Any]) -> None:
        """将 source 合并到 target"""
        for i, cell in enumerate(source):
            if cell and str(cell).strip():
                if i < len(target):
                    target_val = str(target[i] or "").strip()
                    cell_val = str(cell).strip()
                    if not target_val:
                        target[i] = cell_val
                    elif cell_val != target_val:
                        target[i] = target_val + "\n" + cell_val

    def clean_field(self, field_name: str, value: str) -> str:
        """清洗招商银行特定字段"""
        if not value:
            return value

        # 清理对方户名
        if field_name in ["counterparty_name", "收(付)方名称"]:
            return self._clean_cmb_name(value)

        # 清理实例号
        if field_name in ["print_instance_no", "实例号"]:
            return self._clean_cmb_instance_no(value)

        # 清理时间
        if field_name in ["transaction_time", "transaction_date"]:
            return self._clean_time_string(value)

        return value

    def _clean_cmb_name(self, value: str) -> str:
        """清理对方户名中的冗余信息"""
        parts = value.split("\n")
        cleaned_parts = []
        noise_patterns = [
            r"网银支付", r"手续费", r"企业银行", r"跨行", r"本地",
            r"普通", r"汇划费", r"对公转", r"还借款", r"电费",
            r"务费", r"实时代收", r"款项", r"提出", r"正常",
        ]

        for p in parts:
            p = p.strip()
            if not p:
                continue
            if any(re.search(pat, p) for pat in noise_patterns):
                continue
            cleaned_parts.append(p)

        return "".join(cleaned_parts)

    def _clean_cmb_instance_no(self, value: str) -> str:
        """清理实例号中的冗余数字"""
        parts = value.split("\n")
        instance_parts = []

        for p in parts:
            p = p.strip()
            if not p:
                continue
            # 丢弃看起来像账号的长数字
            if re.match(r"^\d{7,22}$", p):
                continue
            instance_parts.append(p)

        result = "".join(instance_parts)
        # 提取实例号格式
        m = re.search(r"(\d{3,4}[A-Z]\d+)", result)
        return m.group(1) if m else result

    def _clean_time_string(self, value: str) -> str:
        """清理时间字符串"""
        if not value:
            return value

        # 缝合被切断的时间
        value = re.sub(r"(\d{4}[\-/\.]\d*)\s*\n\s*(\d{1,2}[\-/\.]\d{1,2})", r"\1\2", value)
        value = re.sub(r"(\d{1,2}:\d{1,2}:)\s*\n\s*(\d{1,2})", r"\1\2", value)

        # 移除换行符
        value = value.replace("\n", " ")

        return value.strip()
