"""文本 unit 切分、loc 回填与 diff 转换。"""

from __future__ import annotations

import re
from typing import Any

from financial_compare.compare.models.section_buffer import SectionBuffer
from financial_compare.compare.utils.text_compare import filter_text_diff_pairs
from financial_compare.document.item import DocumentItem, TextLine, is_text_line


class TextUnitUtils:
    _SENTENCE_BOUNDARY_CHARS = "。！？!?"
    _SENTENCE_SPLIT_RE = re.compile(rf"(?<=[{re.escape(_SENTENCE_BOUNDARY_CHARS)}])")
    # 行首序号/条目标记：新行以此开头则开始新 unit（A/B 共用，与母本方向无关）
    _LIST_ITEM_LINE_START_RE = re.compile(
        r"^("
        r"\d+\.\s*"  # 1. 2.
        r"|[一二三四五六七八九十百千零两]+、\s*"  # 一、 二、
        r"|[\(（]\d+[\)）]\s*"  # (1) （2）
        r"|[\(（][一二三四五六七八九十百千零两\d]+[\)）]\s*"  # （四） (五)
        r")"
    )

    @classmethod
    def line_starts_list_item(cls, line: str) -> bool:
        text = line.strip()
        if not text:
            return False
        return cls._LIST_ITEM_LINE_START_RE.match(text) is not None

    @classmethod
    def split_content_units(cls, content: str) -> list[str]:
        normalized = content.strip()
        if not normalized:
            return []
        paras: list[str] = []
        buf: list[str] = []
        for raw in normalized.splitlines():
            line = raw.strip()
            if not line:
                if buf:
                    paras.append("\n".join(buf).strip())
                    buf = []
                continue
            if buf and cls.line_starts_list_item(line):
                paras.append("\n".join(buf).strip())
                buf = [line]
            else:
                buf.append(line)
        if buf:
            paras.append("\n".join(buf).strip())
        units: list[str] = []
        for para in paras:
            units.extend(cls._split_paragraph_to_units(para))
        return [x for x in units if x.strip()]

    @classmethod
    def _split_paragraph_to_units(cls, paragraph: str) -> list[str]:
        text = paragraph.strip()
        if not text:
            return []
        sentences = [x.strip() for x in cls._SENTENCE_SPLIT_RE.split(text) if x.strip()]
        if len(sentences) <= 1:
            return [text]
        return sentences

    @staticmethod
    def units_from_text_items(
        items: list[DocumentItem],
    ) -> tuple[list[str], list[dict[str, Any]], list[list[TextLine]]]:
        text_lines = [i for i in items if is_text_line(i)]
        if not text_lines:
            return [], [], []
        joined_parts: list[str] = []
        line_starts: list[tuple[int, TextLine]] = []
        offset = 0
        for idx, line in enumerate(text_lines):
            if idx > 0:
                joined_parts.append("\n")
                offset += 1
            line_starts.append((offset, line))
            joined_parts.append(line.text)
            offset += len(line.text)
        joined = "".join(joined_parts)
        units = TextUnitUtils.split_content_units(joined)
        locs: list[dict[str, Any]] = []
        line_refs: list[list[TextLine]] = []
        for unit in units:
            pos = joined.find(unit)
            refs: list[TextLine] = []
            if pos >= 0:
                unit_end = pos + len(unit)
                for start, line in line_starts:
                    line_end = start + len(line.text)
                    if start < unit_end and line_end > pos:
                        refs.append(line)
            loc_line = refs[0] if refs else text_lines[0]
            locs.append(TextUnitUtils.text_loc(loc_line))
            line_refs.append(refs)
        return units, locs, line_refs

    @staticmethod
    def consume_aligned_units(
        buffer: SectionBuffer,
        *,
        units: list[str],
        line_refs: list[list[TextLine]],
        missing: list[dict[str, Any]],
    ) -> None:
        """文文终局后：已对齐 unit 对应行从 buffer 摘除；missing 保留。"""
        if not units or not line_refs:
            return
        remaining = {str(item.get("text", "")) for item in missing if isinstance(item, dict)}
        to_remove: list[TextLine] = []
        for unit_text, refs in zip(units, line_refs, strict=False):
            if not refs:
                continue
            if TextUnitUtils._initial_unit_consumed(unit_text, remaining):
                to_remove.extend(refs)
        buffer.remove_many(to_remove)

    @staticmethod
    def _initial_unit_consumed(unit_text: str, remaining: set[str]) -> bool:
        if unit_text in remaining:
            return False
        for rem in remaining:
            if not rem.strip():
                continue
            if rem in unit_text or unit_text in rem:
                return False
        return True

    @staticmethod
    def flow_to_paired_text_diffs(
        flow: dict[str, Any],
        a_locs: list[dict[str, Any]],
        b_locs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """阶段一：仅已配对且有 diff 的 text（不含 text_only_in_*）。"""
        out: list[dict[str, Any]] = []
        for item in flow.get("diff_items", []):
            if not isinstance(item, dict):
                continue
            diff = filter_text_diff_pairs(item.get("diff") or [])
            if not diff:
                continue
            ai = int(item.get("a_index", 0))
            bi = int(item.get("b_index", 0))
            out.append(
                {
                    "diff_type": "text",
                    "loc_a": a_locs[ai] if ai < len(a_locs) else None,
                    "loc_b": b_locs[bi] if bi < len(b_locs) else None,
                    "diff": diff,
                }
            )
        return out

    @staticmethod
    def flow_to_text_diffs(
        flow: dict[str, Any],
        a_locs: list[dict[str, Any]],
        b_locs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        out.extend(TextUnitUtils.flow_to_paired_text_diffs(flow, a_locs, b_locs))
        for item in flow.get("missing_in_b", []):
            if not isinstance(item, dict):
                continue
            ai = int(item.get("a_index", 0))
            out.append(
                {
                    "diff_type": "text_only_in_a",
                    "loc_a": a_locs[ai] if ai < len(a_locs) else None,
                    "loc_b": None,
                    "a_text": item.get("text"),
                }
            )
        for item in flow.get("missing_in_a", []):
            if not isinstance(item, dict):
                continue
            bi = int(item.get("b_index", 0))
            out.append(
                {
                    "diff_type": "text_only_in_b",
                    "loc_a": None,
                    "loc_b": b_locs[bi] if bi < len(b_locs) else None,
                    "b_text": item.get("text"),
                }
            )
        return out

    @staticmethod
    def units_with_locs_from_line(line: TextLine) -> list[tuple[str, dict[str, Any]]]:
        loc = TextUnitUtils.text_loc(line)
        return [(unit, loc) for unit in TextUnitUtils.split_content_units(line.text)]

    @staticmethod
    def units_and_locs_from_text_lines(
        lines: list[TextLine],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        units, locs, _ = TextUnitUtils.units_from_text_items(lines)
        return units, locs

    @staticmethod
    def text_loc(line: TextLine) -> dict[str, Any]:
        loc = line.loc
        out: dict[str, Any] = {
            "stream_index": loc.stream_index,
            "section_path": loc.section_path,
        }
        if loc.element_index is not None:
            out["element_index"] = loc.element_index
        if loc.page is not None:
            out["page"] = loc.page
        if loc.bbox is not None:
            out["bbox"] = loc.bbox
        if loc.spans is not None:
            out["spans"] = loc.spans
        return out
