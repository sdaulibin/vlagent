"""中文 PDF/DOCX 抽取文本的结构化解析（章节层级）。"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from financial_compare.document.item import DocumentItem, TableBlock, TextLine
from financial_compare.document.types import StructuredDocument, StructuredLine, TocBlock

State = Literal["NORMAL", "TOC", "GLOSSARY"]
Token = Literal["BLANK", "TOC_TITLE", "GLOSSARY_TITLE", "H1", "H2", "H3", "H4", "NORMAL"]


@dataclass
class _Context:
    state: State = "NORMAL"
    outline_levels: list[int] = field(default_factory=list)
    toc_lines_buffer: list[StructuredLine] = field(default_factory=list)
    toc_blocks: list[TocBlock] = field(default_factory=list)
    toc_ordinals_seen: set[str] = field(default_factory=set)
    toc_body_started: bool = False
    blank_run: int = 0

    def outline_top(self) -> int:
        return self.outline_levels[-1] if self.outline_levels else 0

    def outline_push(self, level: int) -> None:
        while self.outline_levels and self.outline_levels[-1] >= level:
            self.outline_levels.pop()
        self.outline_levels.append(level)

    def flush_toc(self) -> None:
        if self.toc_lines_buffer:
            self.toc_blocks.append(TocBlock(lines=tuple(self.toc_lines_buffer)))
            self.toc_lines_buffer.clear()

    def reset_toc_session(self) -> None:
        self.toc_lines_buffer.clear()
        self.toc_ordinals_seen.clear()
        self.toc_body_started = False


def _normalize_for_dup(s: str) -> str:
    if not s:
        return ""
    t = s.replace("|", "").replace("｜", "")
    return re.sub(r"\s+", "", t, flags=re.UNICODE)


def _normalize_spaces_nfkc(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s.strip()), flags=re.UNICODE)


def _is_toc_heading_line(line: str) -> bool:
    return _normalize_spaces_nfkc(line) in ("目录", "目錄")


def _is_glossary_heading_line(line: str) -> bool:
    return _normalize_spaces_nfkc(line) in ("释义", "釋義")


_RE_L1_ORDINAL = re.compile(r"^第([一二三四五六七八九十百千万零〇○\d]+)[节節]", re.UNICODE)


def _l1_ordinal_key(line: str) -> str | None:
    m = _RE_L1_ORDINAL.match(line.strip())
    if not m:
        return None
    return _normalize_spaces_nfkc(m.group(1))


_CN_ORDINAL_DIGIT = {
    "零": 0,
    "〇": 0,
    "○": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _parse_zh_ordinal(text: str) -> int | None:
    s = unicodedata.normalize("NFKC", text.strip())
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s in _CN_ORDINAL_DIGIT:
        return _CN_ORDINAL_DIGIT[s]
    if s == "十":
        return 10
    if s.startswith("十") and len(s) == 2:
        low = _CN_ORDINAL_DIGIT.get(s[1])
        return 10 + low if low is not None else None
    if s.endswith("十") and len(s) == 2:
        high = _CN_ORDINAL_DIGIT.get(s[0])
        return high * 10 if high is not None else None
    if "十" in s:
        high_part, _, low_part = s.partition("十")
        tens = 1 if not high_part else _CN_ORDINAL_DIGIT.get(high_part)
        ones = 0 if not low_part else _CN_ORDINAL_DIGIT.get(low_part)
        if tens is None or ones is None:
            return None
        return tens * 10 + ones
    return None


def _nfkc_digit_class() -> str:
    return r"0-9０-９"


_DOT = r"(?:\.|．)"


@dataclass(frozen=True)
class _Decision:
    consumed: bool = True
    reprocess: bool = False


class ChineseParser:
    """基于行的章节层级识别（简繁、全角半角标点兼容）。"""

    _RE_L1 = re.compile(r"^第[一二三四五六七八九十百千万零〇○\d]+[节節]", re.UNICODE)
    _RE_L2_ZH = re.compile(r"^[一二三四五六七八九十百千]+[、，]", re.UNICODE)
    _RE_AR_L2_PAIR = re.compile(
        rf"^([{_nfkc_digit_class()}]+){_DOT}([{_nfkc_digit_class()}]+)(?=\D|$)",
        re.UNICODE,
    )
    _RE_AR_L4_DOT = re.compile(
        rf"^([{_nfkc_digit_class()}]+){_DOT}(?![{_nfkc_digit_class()}])",
        re.UNICODE,
    )
    _RE_L1_SUFFIX_ONLY_SEP = re.compile(r"^[|｜\s]+$", re.UNICODE)

    def classify_line(self, line: str) -> Token:
        if not line.strip():
            return "BLANK"
        stripped = line.strip()
        if _is_toc_heading_line(stripped):
            return "TOC_TITLE"
        if _is_glossary_heading_line(stripped):
            return "GLOSSARY_TITLE"
        if self._RE_L1.match(stripped):
            return "H1"
        if self._RE_AR_L2_PAIR.match(stripped):
            return "H3"
        if self._RE_AR_L4_DOT.match(stripped):
            return "H4"
        if self._RE_L2_ZH.match(stripped):
            return "H2"
        return "NORMAL"

    @staticmethod
    def _is_integer_token(tok: str) -> bool:
        s = unicodedata.normalize("NFKC", tok).strip()
        return bool(s) and s.isdigit()

    def _l1_suffix_is_continuation_only(self, line: str) -> bool:
        m = self._RE_L1.match(line.strip())
        if not m:
            return False
        suffix = line.strip()[m.end() :].strip()
        return bool(suffix) and bool(self._RE_L1_SUFFIX_ONLY_SEP.fullmatch(suffix))

    def _l1_next_line_valid_continuation(self, nxt: str) -> bool:
        st = nxt.strip()
        if not st:
            return False
        if _is_toc_heading_line(st) or _is_glossary_heading_line(st):
            return False
        if self._RE_L1.match(st):
            return False
        return True

    def _merge_l1_continuation(
        self, items: list[DocumentItem], idx: int, stripped: str
    ) -> tuple[str, str, int]:
        raw_first = items[idx].text.rstrip() if isinstance(items[idx], TextLine) else ""
        if not self._l1_suffix_is_continuation_only(stripped):
            return stripped, raw_first, idx
        nxt_idx = idx + 1
        if nxt_idx >= len(items) or not isinstance(items[nxt_idx], TextLine):
            return stripped, raw_first, idx
        raw_next = items[nxt_idx].text
        if not self._l1_next_line_valid_continuation(raw_next):
            return stripped, raw_first, idx
        merged = (stripped + " " + raw_next.strip()).strip()
        display = (raw_first + " " + raw_next.rstrip()).strip()
        return merged, display, nxt_idx

    def _heading_weak_gate(
        self,
        line: str,
        m: re.Match[str],
        *,
        max_tail_len: int,
        check_numeric: bool,
    ) -> bool:
        # 弱约束：标题后应更像标题短语，而非正文说明句或表格数值行。
        tail = line[m.end() :].strip()
        tail = re.sub(r"^[|｜\s]+", "", tail)
        tail_nfkc = unicodedata.normalize("NFKC", tail)
        if not tail:
            return False
        bar_count = line.count("|") + line.count("｜")
        if "\t" in line:
            return False
        # 单个/少量竖线常是 PDF 版式噪声；大量竖线更可能是表格列。
        if bar_count >= 3:
            return False
        if len(tail) > max_tail_len:
            return False
        if any(p in tail for p in ("，", "。", "；", ";", "：", ":", "！", "!", "？", "?")):
            return False
        if not check_numeric:
            return True
        # 数字+金额/日期单位通常是表格或正文数据列，不应被识别为标题。
        if re.search(r"[0-9０-９]+\s*(元|万元|亿元|年|月|日)", tail_nfkc):
            return False
        # 保留对“纯数值百分比列”的拦截，但允许“30%以上……”这类叙述型标题。
        if re.fullmatch(r"[-+()（）\s0-9０-９.,，%％]+", tail_nfkc):
            return False
        compact = re.sub(r"\s+", "", line)
        if not compact:
            return False
        digit_ratio = sum(ch.isdigit() for ch in unicodedata.normalize("NFKC", compact)) / len(
            compact
        )
        if digit_ratio > 0.65 and len(tail) <= 4:
            return False
        return True

    def structure_document(self, items: list[DocumentItem]) -> StructuredDocument:
        from financial_compare.parser.tree.builder import DocumentTreeBuilder

        toc = self.extract_toc_blocks(items)
        root = DocumentTreeBuilder(self).build_tree(items)
        return StructuredDocument(root=root, toc=toc)

    def extract_toc_blocks(self, items: list[DocumentItem]) -> list[TocBlock]:
        ctx = _Context()
        idx = 0
        while idx < len(items):
            if not isinstance(items[idx], TextLine):
                idx += 1
                continue
            raw = items[idx].text
            token = self.classify_line(raw)
            if token == "BLANK":
                ctx.blank_run += 1
            else:
                ctx.blank_run = 0

            if ctx.state == "TOC":
                decision, new_idx = self.handle_toc(token, raw, items, idx, ctx)
            elif ctx.state == "GLOSSARY":
                decision = self.handle_glossary(token, raw, ctx)
                new_idx = idx
            else:
                if token == "TOC_TITLE":
                    decision, new_idx = self.handle_toc(token, raw, items, idx, ctx)
                elif token == "GLOSSARY_TITLE":
                    decision = self.handle_glossary(token, raw, ctx)
                    new_idx = idx
                else:
                    decision, new_idx = _Decision(), idx

            if decision.reprocess:
                continue
            idx = new_idx + 1

        if ctx.state == "TOC" and ctx.toc_lines_buffer:
            ctx.flush_toc()
            ctx.reset_toc_session()
        return ctx.toc_blocks

    def handle_glossary(self, token: Token, raw: str, ctx: _Context) -> _Decision:
        if token == "GLOSSARY_TITLE" and ctx.state != "GLOSSARY":
            ctx.state = "GLOSSARY"
            ctx.outline_levels.clear()
            ctx.outline_push(1)
            return _Decision()
        if ctx.state == "GLOSSARY" and token == "GLOSSARY_TITLE":
            return _Decision()
        if ctx.state == "GLOSSARY" and token == "H1":
            ctx.state = "NORMAL"
            return _Decision(reprocess=True)
        return _Decision()

    def handle_toc(self, token: Token, raw: str, items: list[DocumentItem], idx: int, ctx: _Context) -> tuple[_Decision, int]:
        stripped = raw.strip()
        if token == "TOC_TITLE" and ctx.state != "TOC":
            ctx.state = "TOC"
            ctx.reset_toc_session()
            ctx.toc_lines_buffer.append(StructuredLine(level=0, role="body", text=raw.rstrip()))
            return _Decision(), idx

        if ctx.state != "TOC":
            return _Decision(reprocess=True), idx

        if token == "GLOSSARY_TITLE":
            ctx.flush_toc()
            ctx.reset_toc_session()
            ctx.state = "NORMAL"
            return _Decision(reprocess=True), idx

        if token == "H1":
            merged, display, new_idx = self._merge_l1_continuation(items, idx, stripped)
            ord_key = _l1_ordinal_key(merged)
            if ord_key is not None and ord_key in ctx.toc_ordinals_seen:
                ctx.flush_toc()
                ctx.reset_toc_session()
                ctx.state = "NORMAL"
                return _Decision(reprocess=True), idx
            ctx.toc_lines_buffer.append(StructuredLine(level=0, role="body", text=display))
            ctx.toc_body_started = True
            if ord_key is not None:
                ctx.toc_ordinals_seen.add(ord_key)
            return _Decision(), new_idx

        if token == "BLANK":
            if ctx.toc_body_started and ctx.blank_run >= 2:
                ctx.flush_toc()
                ctx.reset_toc_session()
                ctx.state = "NORMAL"
            return _Decision(), idx

        ctx.flush_toc()
        ctx.reset_toc_session()
        ctx.state = "NORMAL"
        return _Decision(reprocess=True), idx
