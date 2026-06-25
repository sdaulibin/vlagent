"""按文件类型抽取文本，经语言门禁后调用对应结构化解析器。"""

from __future__ import annotations

import re
from pathlib import Path

from financial_compare.document.item import DocumentItem, TextLine, item_text
from financial_compare.document.types import StructuredDocument
from financial_compare.parser.chinese_parser import ChineseParser
from financial_compare.parser.exceptions import LanguageGateError
from financial_compare.parser.page_range import PageRange
from financial_compare.parser.pair_extract import extract_pair_items, extract_single_items


class StructuredParser:
    """输入文件路径，委托 PDF/DOCX 解析器得到文本行列表，再结构化。

    - ``pdf_parser`` / ``docx_parser`` 仅负责抽取文本行；
    - 语言门禁与章节规则在门禁通过后的解析器中完成（当前中文：``ChineseParser``）。
    """

    def parse(
        self,
        file_path: str | Path,
        *,
        page_range: PageRange | None = None,
        side: str = "a",
    ) -> StructuredDocument:
        """解析文件为 ``StructuredDocument``（Parser 文档树 + ``toc`` 目录块）。"""
        items = self.extract_document_items(file_path, page_range=page_range, side=side)
        assert_primary_chinese([item_text(item) for item in items])
        return ChineseParser().structure_document(items)

    def parse_pair(
        self,
        path_a: str | Path,
        path_b: str | Path,
        *,
        page_range: PageRange | None = None,
    ) -> tuple[StructuredDocument, StructuredDocument, bool]:
        items_a, items_b, swapped = extract_pair_items(
            path_a, path_b, page_range=page_range
        )
        assert_primary_chinese([item_text(item) for item in items_a])
        assert_primary_chinese([item_text(item) for item in items_b])
        parser = ChineseParser()
        return (
            parser.structure_document(items_a),
            parser.structure_document(items_b),
            swapped,
        )

    def extract_text_lines(self, file_path: str | Path) -> list[str]:
        """仅抽取文本行，不做门禁与结构化。

        DOCX 中空段落会保留为 ``""``；PDF 侧当前仅在块内有文本时产出一行，
        版式上的「空行」不一定出现为列表中的空串。
        """
        return document_items_to_text_lines(self.extract_document_items(file_path))

    def extract_document_items(
        self,
        file_path: str | Path,
        *,
        page_range: PageRange | None = None,
        side: str = "a",
    ) -> list[DocumentItem]:
        """抽取 ``DocumentItem`` 混合流，不做门禁与结构化。"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        suffix = path.suffix.lower()
        if suffix not in {".pdf", ".docx"}:
            raise ValueError(f"不支持的文件扩展名: {suffix}（当前支持 .pdf、.docx）")
        return extract_single_items(path, page_range=page_range, side=side)


def document_items_to_text_lines(items: list[DocumentItem]) -> list[str]:
    """将 DocumentItem 混合流展平为文本行（raw 导出用）。"""
    lines: list[str] = []
    for item in items:
        if isinstance(item, TextLine):
            lines.append(item.text)
        else:
            lines.extend(row.content for row in item.rows)
    return lines


def assert_primary_chinese(lines: list[str]) -> None:
    """抽样判断是否为中文主体文档；否则抛出 ``LanguageGateError``。"""
    if not lines:
        return

    max_chars = 8000
    buf: list[str] = []
    n = 0
    for row in lines:
        buf.append(row)
        n += len(row) + 1
        if n >= max_chars:
            break
    text = "\n".join(buf)

    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[a-zA-Z]", text))
    total = cjk + latin
    if total < 24:
        return

    if latin >= cjk * 2 and cjk < 40:
        raise LanguageGateError(
            "语言门禁未通过：抽样中英文拉丁字母显著多于中日韩汉字，"
            "当前 StructuredParser 仅支持简体中文/繁体中文文档。"
        )
