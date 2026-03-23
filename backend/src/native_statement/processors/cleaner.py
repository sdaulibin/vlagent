"""
数据清洗器

清洗提取后的数据。
"""
import re
from typing import Any, List


class DataCleaner:
    """数据清洗器"""

    @staticmethod
    def clean_time_string(value: str) -> str:
        """
        清理时间字符串

        - 去除重复的日期
        - 缝合被切断的时间
        - 调整格式
        """
        if not value:
            return value

        # 缝合被切断的字符串
        value = re.sub(r"(\d{4}[\-/\.]\d*)\s*\n\s*(\d{1,2}[\-/\.]\d{1,2})", r"\1\2", value)
        value = re.sub(r"(\d{1,2}:\d{1,2}:)\s*\n\s*(\d{1,2})", r"\1\2", value)
        value = re.sub(r"(\d{1,2}:)\s*\n\s*(\d{1,2}:\d{1,2})", r"\1\2", value)

        # 分离日期、时间和其他内容
        parts = [p.strip() for p in value.replace(" ", "\n").split("\n") if p.strip()]
        dates, times, others = [], [], []

        for p in parts:
            if re.match(r"^\d{4}[\-/\.]\d{1,2}[\-/\.]\d{1,2}$", p):
                if p not in dates:
                    dates.append(p)
            elif re.match(r"^\d{1,2}:\d{1,2}:\d{1,2}$", p):
                if p not in times:
                    times.append(p)
            elif p == "0":
                continue  # 丢弃孤立的 0
            else:
                if p not in others:
                    others.append(p)

        # 组合结果
        result = []
        if dates:
            result.append(dates[0])
        if times:
            result.append(times[0])
        result.extend(others)

        if not others and len(result) <= 2:
            return " ".join(result)
        return "\n".join(result)

    @staticmethod
    def clean_amount(value: str) -> str:
        """
        清理金额字符串

        - 移除逗号
        - 统一格式
        """
        if not value:
            return value
        # 移除千分位逗号
        return value.replace(",", "").strip()

    @staticmethod
    def clean_account_number(value: str) -> str:
        """
        清理账号字符串

        - 移除空格和特殊字符
        """
        if not value:
            return value
        # 只保留数字和字母
        return re.sub(r"[^\dA-Za-z]", "", value)

    @staticmethod
    def remove_newlines(value: str) -> str:
        """移除换行符"""
        if not value:
            return value
        return value.replace("\n", "").replace("\r", "")

    @staticmethod
    def clean_row(row: List[Any], remove_newlines: bool = True) -> List[str]:
        """
        清洗单行数据

        Args:
            row: 原始行
            remove_newlines: 是否移除换行符

        Returns:
            清洗后的行
        """
        result = []
        for cell in row:
            value = str(cell or "").strip()
            if remove_newlines:
                value = DataCleaner.remove_newlines(value)
            result.append(value)
        return result
