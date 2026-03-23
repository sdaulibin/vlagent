"""
通用行合并器

处理 PDF 提取时被拆成多行的单元格。
"""
import re
from typing import List, Any, Optional


class RowMerger:
    """
    通用行合并器

    处理 pdfplumber 等工具将一条记录拆成多行的情况：
    - 日期行（在主数据行之前）：只有时间列有日期值
    - 数据行：包含序号、时间、金额等主要数据
    - 续行（在主数据行之后）：只有少数列有值
    """

    def __init__(
        self,
        has_anchor_col: bool = True,
        anchor_patterns: Optional[List[str]] = None
    ):
        """
        初始化行合并器

        Args:
            has_anchor_col: 是否有锚点列（序号或日期）
            anchor_patterns: 锚点列的正则模式列表
        """
        self.has_anchor_col = has_anchor_col
        self.anchor_patterns = anchor_patterns or [
            r"^\d+$",  # 纯数字序号
            r"^\d{4}[\-/\.]\d{1,2}",  # 日期开头
        ]

    def merge(self, rows: List[List[Any]]) -> List[List[Any]]:
        """
        合并多行单元格

        Args:
            rows: 原始行数据

        Returns:
            合并后的行
        """
        if not rows:
            return rows

        # 分类每一行
        classified = self._classify_rows(rows)

        # 合并 fragment 到 main
        return self._merge_fragments(classified)

    def _classify_rows(self, rows: List[List[Any]]) -> List[tuple]:
        """
        分类每一行为 header / main / fragment

        Returns:
            [(type, row), ...]
        """
        classified = []

        for row in rows:
            if not row:
                continue

            non_empty_count = sum(1 for cell in row if cell and str(cell).strip())

            if non_empty_count == 0:
                continue

            # 检查是否为表头行
            if self._is_header_row(row):
                classified.append(("header", list(row)))
                continue

            # 检查是否为主行
            if self._is_main_row(row, non_empty_count, len(row)):
                classified.append(("main", list(row)))
            else:
                classified.append(("fragment", list(row)))

        return classified

    def _is_header_row(self, row: List[Any]) -> bool:
        """判断是否为表头行"""
        header_keywords = [
            "交易时间", "交易日期", "记账日期", "日期",
            "收入", "支出", "借方", "贷方", "余额",
            "对方账号", "对方户名", "摘要", "流水号",
        ]
        row_text = "".join(str(c or "") for c in row)
        match_count = sum(1 for kw in header_keywords if kw in row_text)
        return match_count >= 3

    def _is_main_row(self, row: List[Any], non_empty_count: int, total_cols: int) -> bool:
        """判断是否为主数据行"""
        if not row:
            return False

        first_cell = str(row[0] or "").strip()

        # 检查第一列是否为锚点
        for pattern in self.anchor_patterns:
            if re.match(pattern, first_cell):
                return True

        # 检查前几列是否有日期
        for cell in row[:5]:
            val = str(cell or "").strip()
            if re.search(r"\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}", val):
                return True

        # 如果有足够多的非空列，也认为是主行
        if non_empty_count >= max(3, total_cols * 0.3):
            return True

        return False

    def _merge_fragments(self, classified: List[tuple]) -> List[List[Any]]:
        """将 fragment 合并到 main"""
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
                # 向后合并 fragment
                j = i + 1
                while j < len(classified) and classified[j][0] == "fragment":
                    frag_row = classified[j][1]
                    # 检查是否应该停止合并
                    if self._should_stop_merge(frag_row):
                        break
                    self._merge_into(merged_row, frag_row)
                    j += 1

                result.append(merged_row)
                i = j
                continue

            # fragment 在 main 之前，收集并等待 main
            if typ == "fragment":
                pending = [list(row)]
                j = i + 1
                while j < len(classified) and classified[j][0] == "fragment":
                    pending.append(list(classified[j][1]))
                    j += 1

                if j < len(classified) and classified[j][0] == "main":
                    # 合并到 main
                    merged_row = list(classified[j][1])
                    for frag in pending:
                        self._merge_into(merged_row, frag, prepend=True)
                    result.append(merged_row)
                    i = j + 1
                else:
                    # 没有后续 main，直接添加
                    for frag in pending:
                        result.append(frag)
                    i = j
                continue

            i += 1

        return result

    def _should_stop_merge(self, row: List[Any]) -> bool:
        """判断是否应该停止合并"""
        for cell in row[:5]:
            val = str(cell or "").strip()
            # 如果包含完整日期时间，可能是新交易的起点
            if re.search(r"\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}\s+\d{1,2}:\d{2}:\d{2}", val):
                return True
        return False

    def _merge_into(self, target: List[Any], source: List[Any], prepend: bool = False) -> None:
        """
        将 source 合并到 target

        Args:
            target: 目标行
            source: 源行
            prepend: 是否将源值放在前面
        """
        for i, cell in enumerate(source):
            if cell and str(cell).strip():
                if i < len(target):
                    target_val = str(target[i] or "").strip()
                    cell_val = str(cell).strip()
                    if not target_val:
                        target[i] = cell_val
                    elif cell_val != target_val:
                        if prepend:
                            target[i] = cell_val + "\n" + target_val
                        else:
                            target[i] = target_val + "\n" + cell_val
