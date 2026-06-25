"""文表跨形态对齐：门控 → 虚拟表 → 行匹配（table_cell）。

虚拟表重建仅适用于 PDF TextLine（``loc.spans``）。
DOCX 侧文本不参与重建；典型场景为 DOCX ``TableBlock`` ↔ PDF ``TextLine``。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from financial_compare.compare.aligners.kv_table_text_gate import gate_table_text
from financial_compare.compare.aligners.kv_virtual_table_rebuild import rebuild_virtual_table
from financial_compare.compare.aligners.table_aligner import TableAligner
from financial_compare.compare.utils.span_text_utils import is_pdf_text_line
from financial_compare.document.item import TableBlock, TextLine

_LlmFn = Callable[[str, str, str], str]


@dataclass
class TableTextCrossAlignResult:
    table_diffs: list[dict[str, Any]] = field(default_factory=list)
    text_diffs: list[dict[str, Any]] = field(default_factory=list)
    table_remainder_a: list[TableBlock] = field(default_factory=list)
    table_remainder_b: list[TableBlock] = field(default_factory=list)
    text_remainder_a: list[TextLine] = field(default_factory=list)
    text_remainder_b: list[TextLine] = field(default_factory=list)


class TableTextCrossAligner:
    """表 ↔ PDF TextLine：LLM 门控 + 虚拟表 + 行匹配。"""

    @classmethod
    def align_in_global_remainder(
        cls,
        *,
        tables_a: list[TableBlock],
        tables_b: list[TableBlock],
        text_lines_a: list[TextLine],
        text_lines_b: list[TextLine],
        llm_call: _LlmFn,
    ) -> TableTextCrossAlignResult:
        return cls.align_in_section(
            tables_a=tables_a,
            tables_b=tables_b,
            text_lines_a=text_lines_a,
            text_lines_b=text_lines_b,
            llm_call=llm_call,
            section_scoped=False,
        )

    @classmethod
    def align_in_section(
        cls,
        *,
        tables_a: list[TableBlock],
        tables_b: list[TableBlock],
        text_lines_a: list[TextLine],
        text_lines_b: list[TextLine],
        llm_call: _LlmFn,
        section_scoped: bool = True,
    ) -> TableTextCrossAlignResult:
        table_diffs: list[dict[str, Any]] = []
        text_a = list(text_lines_a)
        text_b = list(text_lines_b)
        table_rem_a: list[TableBlock] = []
        table_rem_b: list[TableBlock] = []

        if tables_a:
            r = cls.align_tables_to_text(
                tables_a, text_b, table_side="a", llm_call=llm_call, section_scoped=section_scoped
            )
            table_diffs.extend(r.table_diffs)
            text_b = r.text_remainder_b
            table_rem_a.extend(r.table_remainder_a)

        if tables_b:
            r = cls.align_tables_to_text(
                tables_b, text_a, table_side="b", llm_call=llm_call, section_scoped=section_scoped
            )
            table_diffs.extend(r.table_diffs)
            text_a = r.text_remainder_a
            table_rem_b.extend(r.table_remainder_b)

        return TableTextCrossAlignResult(
            table_diffs=table_diffs,
            text_diffs=[],
            table_remainder_a=table_rem_a,
            table_remainder_b=table_rem_b,
            text_remainder_a=text_a,
            text_remainder_b=text_b,
        )

    @classmethod
    def align_tables_to_text(
        cls,
        tables: list[TableBlock],
        text_pool: list[TextLine],
        *,
        table_side: Literal["a", "b"],
        llm_call: _LlmFn,
        section_scoped: bool = False,
    ) -> TableTextCrossAlignResult:
        table_diffs: list[dict[str, Any]] = []
        table_rem: list[TableBlock] = []
        pool = list(text_pool)
        for table in tables:
            pdf_indices = [i for i, line in enumerate(pool) if is_pdf_text_line(line)]
            pdf_lines = [pool[i] for i in pdf_indices]
            if not pdf_lines:
                table_rem.append(table)
                continue

            gate = gate_table_text(
                table, pdf_lines, llm_call=llm_call, section_scoped=section_scoped
            )

            if gate is None or not gate.ok:
                table_rem.append(table)
                continue

            virtual = rebuild_virtual_table(table, pdf_lines, gate, llm_call=llm_call)
            if virtual is None:
                table_rem.append(table)
                continue

            if table_side == "a":
                diffs, matched, _ = TableAligner.align_matched_tables(
                    table, virtual, llm_call=llm_call
                )
            else:
                diffs, matched, _ = TableAligner.align_matched_tables(
                    virtual, table, llm_call=llm_call
                )

            if matched == 0:
                table_rem.append(table)
                continue

            table_diffs.extend(diffs)
            cls._apply_gate_consumption(pool, gate, pdf_indices)

        if table_side == "a":
            return TableTextCrossAlignResult(
                table_diffs=table_diffs,
                text_remainder_b=pool,
                table_remainder_a=table_rem,
            )
        return TableTextCrossAlignResult(
            table_diffs=table_diffs,
            text_remainder_a=pool,
            table_remainder_b=table_rem,
        )

    @staticmethod
    def _clone_text_line(line: TextLine, text: str) -> TextLine:
        return TextLine(text=text.strip(), loc=line.loc)

    @classmethod
    def _apply_gate_consumption(
        cls,
        text_pool: list[TextLine],
        gate: Any,
        pdf_indices: list[int],
    ) -> None:
        consumed = set(pdf_indices[gate.start_line_index : gate.end_line_index])
        pool_start = pdf_indices[gate.start_line_index]
        pool_end = pdf_indices[gate.end_line_index - 1]
        kept: list[TextLine] = []
        for i, line in enumerate(text_pool):
            if i not in consumed:
                kept.append(line)
                continue
            if i == pool_start and gate.header_peel_text.strip():
                kept.append(cls._clone_text_line(line, gate.header_peel_text))
            if i == pool_end and gate.tail_peel_text.strip():
                kept.append(cls._clone_text_line(line, gate.tail_peel_text))
        text_pool[:] = kept
