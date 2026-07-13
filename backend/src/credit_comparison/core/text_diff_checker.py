from __future__ import annotations

import difflib
from itertools import zip_longest


def normalize_text_for_compare(text: str) -> str:
    """将文本转换为适合比较的形式。"""

    return text.replace("\r\n", "\n").replace("\r", "\n")


def compare_texts(source_text: str, converted_text: str) -> tuple[bool, str]:
    """比较两份文本是否一致，并返回差异摘要。"""

    source_lines = normalize_text_for_compare(source_text).split("\n")
    converted_lines = normalize_text_for_compare(converted_text).split("\n")

    for index, (left_line, right_line) in enumerate(zip_longest(source_lines, converted_lines, fillvalue=""), start=1):
        if left_line == right_line:
            continue
        diff = "".join(
            difflib.unified_diff(
                [left_line + "\n"],
                [right_line + "\n"],
                fromfile="doc",
                tofile="docx",
                lineterm="",
            )
        )
        return False, f"第 {index} 行存在差异: {diff}"
    return True, ""
