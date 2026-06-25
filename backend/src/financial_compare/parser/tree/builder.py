"""从 DocumentItem 流构建 Parser 文档树。"""

from __future__ import annotations

from financial_compare.document.item import DocumentItem, TableBlock, TextLine
from financial_compare.document.tree import DocumentNode
from financial_compare.document.tree_utils import extract_number_hint, normalize_title
from financial_compare.parser.chinese_parser import ChineseParser

_SKIP_LINE = object()


class DocumentTreeBuilder:
    def __init__(self, parser: ChineseParser | None = None) -> None:
        self._parser = parser or ChineseParser()

    def build_tree(self, items: list[DocumentItem]) -> DocumentNode:
        root = DocumentNode(
            level=0,
            title="ROOT",
            role="root",
            path="ROOT",
            number_hint="",
            title_norm="root",
        )
        stack: list[DocumentNode] = [root]
        outline_levels: list[int] = []
        last_h2_zh_ord: int | None = None
        main_l1_ord: str | None = None
        main_l1_norm: str | None = None

        idx = 0
        while idx < len(items):
            item = items[idx]
            if isinstance(item, TableBlock):
                item.loc.section_path = stack[-1].path
                stack[-1].content_items.append(item)
                idx += 1
                continue

            raw = item.text
            token = self._parser.classify_line(raw)
            heading = self._try_heading(
                token,
                raw,
                items,
                idx,
                outline_levels=outline_levels,
                last_h2_zh_ord=last_h2_zh_ord,
                main_l1_ord=main_l1_ord,
                main_l1_norm=main_l1_norm,
            )
            if heading is _SKIP_LINE:
                idx += 1
                continue
            if heading is not None:
                level, title, new_idx, main_l1_ord, main_l1_norm, last_h2_zh_ord, outline_levels = heading
                while stack and stack[-1].level >= level:
                    stack.pop()
                parent = stack[-1]
                node = DocumentNode(
                    level=level,
                    title=title,
                    role={1: "section", 2: "h2", 3: "h3", 4: "h4"}.get(level, "section"),
                    path=f"{parent.path}/{title}",
                    number_hint=extract_number_hint(title),
                    title_norm=normalize_title(title),
                    title_stream_index=item.loc.stream_index,
                )
                item.loc.section_path = node.path
                parent.children.append(node)
                stack.append(node)
                idx = new_idx + 1
                continue

            text = raw.strip()
            if text:
                item.loc.section_path = stack[-1].path
                stack[-1].content_items.append(item)
            idx += 1
        return root

    def _try_heading(
        self,
        token: str,
        raw: str,
        items: list[DocumentItem],
        idx: int,
        *,
        outline_levels: list[int],
        last_h2_zh_ord: int | None,
        main_l1_ord: str | None,
        main_l1_norm: str | None,
    ) -> tuple[int, str, int, str | None, str | None, int | None, list[int]] | None:
        from financial_compare.parser.chinese_parser import _l1_ordinal_key, _normalize_for_dup, _parse_zh_ordinal

        stripped = raw.strip()
        if token == "H1":
            merged, display, new_idx = self._parser._merge_l1_continuation(items, idx, stripped)
            ord_key = _l1_ordinal_key(merged)
            norm = _normalize_for_dup(merged)
            if ord_key is not None and main_l1_ord == ord_key and main_l1_norm == norm:
                return _SKIP_LINE
            new_levels = [1]
            new_l1_ord = ord_key if ord_key is not None else main_l1_ord
            new_l1_norm = norm if ord_key is not None else main_l1_norm
            return 1, display, new_idx, new_l1_ord, new_l1_norm, None, new_levels

        if token == "H2":
            if not outline_levels or outline_levels[-1] not in (1, 2, 3, 4):
                return None
            m = self._parser._RE_L2_ZH.match(stripped)
            if m is None or not self._parser._heading_weak_gate(stripped, m, max_tail_len=40, check_numeric=True):
                return None
            zh_part = m.group(0).rstrip("、，")
            ord_val = _parse_zh_ordinal(zh_part)
            if ord_val is not None and last_h2_zh_ord is not None and ord_val <= last_h2_zh_ord:
                return _SKIP_LINE
            new_levels = outline_levels.copy()
            while new_levels and new_levels[-1] >= 2:
                new_levels.pop()
            new_levels.append(2)
            return 2, raw.rstrip(), idx, main_l1_ord, main_l1_norm, ord_val, new_levels

        if token == "H3":
            m = self._parser._RE_AR_L2_PAIR.match(stripped)
            if m is None or 2 not in outline_levels:
                return None
            if not outline_levels or outline_levels[-1] not in (2, 3, 4):
                return None
            if not self._parser._heading_weak_gate(stripped, m, max_tail_len=40, check_numeric=True):
                return None
            new_levels = outline_levels.copy()
            while new_levels and new_levels[-1] >= 3:
                new_levels.pop()
            new_levels.append(3)
            return 3, raw.rstrip(), idx, main_l1_ord, main_l1_norm, last_h2_zh_ord, new_levels

        if token == "H4":
            m = self._parser._RE_AR_L4_DOT.match(stripped)
            if m is None or not outline_levels or outline_levels[-1] not in (3, 4):
                return None
            if not self._parser._heading_weak_gate(stripped, m, max_tail_len=28, check_numeric=False):
                return None
            new_levels = outline_levels.copy()
            while new_levels and new_levels[-1] >= 4:
                new_levels.pop()
            new_levels.append(4)
            return 4, raw.rstrip(), idx, main_l1_ord, main_l1_norm, last_h2_zh_ord, new_levels
        return None
