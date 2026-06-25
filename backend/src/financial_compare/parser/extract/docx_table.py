"""DOCX 表格：OOXML 行 → HTML。"""

from __future__ import annotations

import html

from financial_compare.document.item import Row, TableBlock


class DocxTableExtractor:
    """DOCX 表格抽取：全表 HTML（表头/表体划分延迟到 compare 阶段）。"""

    @classmethod
    def extract(cls, table: TableBlock) -> TableBlock:
        """填充 ``html``；``row_type`` 仅保留 OOXML ``w:tblHeader`` 预标记。"""
        table.html = cls.rows_to_html(table.rows)
        return table

    @classmethod
    def rows_to_html(cls, rows: list[Row], *, max_rows: int | None = None) -> str:
        """将全部行输出为 ``<table border>``；``header`` 行用 ``th``，其余 ``td``。"""
        use = rows if max_rows is None else rows[:max_rows]
        parts = ["<table border>"]
        for row in use:
            tag = "th" if row.row_type == "header" else "td"
            cells = row.content.split("|")
            cell_html = "".join(
                f"<{tag}>{html.escape(cell, quote=True)}</{tag}>" for cell in cells
            )
            parts.append(f"<tr idx={row.row_index}>{cell_html}</tr>")
        parts.append("</table>")
        return "".join(parts)
