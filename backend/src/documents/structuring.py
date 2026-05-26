"""
文档结构化模块

将 python-docx 提取的内容流解析为层次化的 StructuredDocument，
包含目录识别、标题层级构建、表格归属、释义块处理。
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field


# ---- 数据结构 ----

@dataclass
class InputLine:
    """python-docx 提取的原子单元，携带样式信息"""
    text: str
    style_hint: str = ""  # "Heading1".."Heading4" / "Normal" / "TOCTitle" / "GlossaryTitle" / "Blank" / "Table"
    is_table: bool = False
    table_rows: list[list[str]] | None = None
    has_page_break: bool = False
    outline_level: int | None = None
    source_index: int = 0


@dataclass
class SectionBlock:
    """层次化文档模型的一个节点"""
    role: str  # "h1"/"h2"/"h3"/"h4"/"body"/"table"/"toc_item"
    title: str = ""
    content: list[InputLine] = field(default_factory=list)
    children: list[SectionBlock] = field(default_factory=list)
    text_content: str = ""


@dataclass
class StructuredDocument:
    """整个文档的结构化表示"""
    main: list[SectionBlock] = field(default_factory=list)
    toc: list[SectionBlock] = field(default_factory=list)
    all_lines: list[InputLine] = field(default_factory=list)


# ---- 文本归一化 ----

def _normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r'[​‌‍⁠﻿­]', '', text)
    text = re.sub(r'[^\S\n]+', ' ', text)
    text = re.sub(r'\n{2,}', '\n', text)
    text = '\n'.join(line.strip() for line in text.split('\n'))
    return text.strip()


def _strip_ws(text: str) -> str:
    return re.sub(r'\s+', '', text)


# ---- 行分类器 ----

_H1_RE = re.compile(r'^第[一二三四五六七八九十百〇零]+[节節]\s*')
_H2_RE = re.compile(r'^([一二三四五六七八九十百〇零]+)[、．.]\s*')
_H4_RE = re.compile(r'^(\d+)[\.．、]\s*(?!\d)')
_H3_RE = re.compile(r'^(\d+)[\.．](\d+)\s*')
_TOC_RE = re.compile(r'^(目\s*录|表\s*目\s*录|图\s*目\s*录)\s*$')
_GLOSSARY_RE = re.compile(r'^(附\s*录|附\s*件|术\s*语|定\s*义|缩\s*略\s*语|釋\s*義)')

_SENTENCE_PUNCT = set('，。；：！？;:!?')
_MONEY_DATE_RE = re.compile(r'[0-9０-９]+\s*(元|万元|亿元|年|月|日)', re.UNICODE)
_PURE_NUMERIC_RE = re.compile(r'^[-+()（）\s0-9０-９.,，%％]+$', re.UNICODE)


def _heading_weak_gate(text: str, match: re.Match, max_tail: int = 40) -> bool:
    """弱门控：检查正则匹配的标题候选是否更像标题而非正文/表格数据。"""
    tail = text[match.end():].strip()
    tail = re.sub(r'^[|｜\s]+', '', tail)
    tail_nfkc = unicodedata.normalize("NFKC", tail)
    if not tail:
        return False
    if '\t' in text:
        return False
    bar_count = text.count('|') + text.count('｜')
    if bar_count >= 3:
        return False
    if len(tail) > max_tail:
        return False
    if any(p in tail for p in _SENTENCE_PUNCT):
        return False
    if _MONEY_DATE_RE.search(tail_nfkc):
        return False
    if _PURE_NUMERIC_RE.fullmatch(tail_nfkc):
        return False
    compact = re.sub(r'\s+', '', text)
    if not compact:
        return False
    digit_ratio = sum(ch.isdigit() for ch in unicodedata.normalize("NFKC", compact)) / len(compact)
    if digit_ratio > 0.65 and len(tail) <= 4:
        return False
    return True


def classify_line(text: str, style_hint: str = "", outline_level: int | None = None) -> str:
    """分类单行文本。

    优先级：内容语义（TOC/Glossary 模式）> style_hint > outline_level > 正则 + 弱门控。
    当文本内容完全匹配 TOC/Glossary 模式时，无论样式如何都优先识别。
    """
    norm = _normalize_text(text).strip()

    # Table 样式优先（表格元素无文本内容，不应被 BLANK 吞掉）
    style = style_hint.strip() if style_hint else ""
    if style == "Table":
        return "Table"

    # 最高优先级：内容语义（无论样式是什么）
    if not norm:
        return "BLANK"
    if _TOC_RE.match(norm):
        return "TOCTitle"
    if _GLOSSARY_RE.match(norm):
        return "GlossaryTitle"

    # 样式信号（信任文档结构，不经过弱门控）
    if style:
        if re.match(r'^Heading\s*1$', style, re.IGNORECASE):
            return "H1"
        if re.match(r'^Heading\s*2$', style, re.IGNORECASE):
            return "H2"
        if re.match(r'^Heading\s*3$', style, re.IGNORECASE):
            return "H3"
        if re.match(r'^Heading\s*4$', style, re.IGNORECASE):
            return "H4"

    # 大纲级别（信任文档结构，不经过弱门控）
    if outline_level is not None:
        if outline_level == 0:
            return "H1"
        if outline_level == 1:
            return "H2"
        if outline_level == 2:
            return "H3"
        if outline_level == 3:
            return "H4"
    if not norm:
        return "BLANK"
    return _classify_by_regex(norm)


def _classify_by_regex(text: str) -> str:
    if _TOC_RE.match(text):
        return "TOCTitle"
    if _GLOSSARY_RE.match(text):
        return "GlossaryTitle"
    if _H1_RE.match(text):
        return "H1"
    m2 = _H2_RE.match(text)
    if m2:
        if not _heading_weak_gate(text, m2, max_tail=40):
            return "NORMAL"
        return "H2"
    m4 = _H4_RE.match(text)
    if m4:
        if not _heading_weak_gate(text, m4, max_tail=28):
            return "NORMAL"
        return "H4"
    m3 = _H3_RE.match(text)
    if m3:
        if not _heading_weak_gate(text, m3, max_tail=40):
            return "NORMAL"
        return "H3"
    return "NORMAL"


# ---- 状态机常量 ----

STATE_NORMAL = "NORMAL"
STATE_TOC = "TOC"
STATE_GLOSSARY = "GLOSSARY"
MAX_REPROCESS = 50


@dataclass
class SectionDiffResult:
    """section 级 diff 结果"""
    section_a: SectionBlock | None = None
    section_b: SectionBlock | None = None
    diff_type: str = "equal"
    diff_ops: list[list] | None = None



@dataclass
class _HandlerResult:
    consumed: bool = True
    reprocess: bool = False


# ---- 状态机主函数 ----

def build_structured_document(lines: list[InputLine]) -> StructuredDocument:
    doc = StructuredDocument(all_lines=lines)

    state = STATE_NORMAL
    section_stack: list[SectionBlock] = []
    toc_buffer: list[InputLine] = []
    toc_ordinals_seen: set[str] = set()
    blank_run = 0
    reprocess_count = 0
    last_h2_zh_ord: int | None = None

    idx = 0
    while idx < len(lines):
        line = lines[idx]
        token = classify_line(line.text, line.style_hint, line.outline_level)

        if line.is_table:
            token = "Table"

        result = _HandlerResult()

        if state == STATE_TOC:
            result = _handle_toc(line, token, doc, toc_buffer, toc_ordinals_seen, blank_run)
            if result.reprocess:
                state = STATE_NORMAL
                blank_run = 0
                toc_buffer.clear()
                toc_ordinals_seen.clear()
        elif state == STATE_GLOSSARY:
            result = _handle_glossary(line, token, doc, section_stack)
            if result.reprocess:
                state = STATE_NORMAL
        else:
            handled_as_heading = False
            if token in ("H2", "H3", "H4"):
                handled_as_heading = _handle_heading_with_gates(
                    token, line, doc, section_stack, last_h2_zh_ord
                )
                if handled_as_heading:
                    if token == "H2":
                        zh_part = _extract_h2_ordinal(line.text)
                        if zh_part is not None:
                            last_h2_zh_ord = zh_part
                    result = _HandlerResult()
                else:
                    _append_body(line, section_stack, doc)
                    result = _HandlerResult()
            elif token == "H1":
                _handle_heading(token, line, doc, section_stack)
                last_h2_zh_ord = None
                result = _HandlerResult()
            elif token == "TOCTitle":
                result = _HandlerResult(consumed=True, reprocess=True)
            elif token == "GlossaryTitle":
                block = SectionBlock(role="h1", title=line.text)
                doc.main.append(block)
                section_stack.clear()
                last_h2_zh_ord = None
                result = _HandlerResult(consumed=True, reprocess=True)
            elif token == "Table":
                _handle_table(line, section_stack, doc)
                result = _HandlerResult()
            else:
                _append_body(line, section_stack, doc)
                result = _HandlerResult()

            if result.reprocess:
                if token == "TOCTitle":
                    state = STATE_TOC
                elif token == "GlossaryTitle":
                    state = STATE_GLOSSARY

        if result.reprocess:
            reprocess_count += 1
            if reprocess_count > MAX_REPROCESS:
                idx += 1
                reprocess_count = 0
        else:
            if token == "BLANK":
                blank_run += 1
            else:
                blank_run = 0
            idx += 1
            reprocess_count = 0

    if state == STATE_TOC and toc_buffer:
        _flush_toc(doc, toc_buffer)

    return doc


# ---- NORMAL 处理 ----

def _is_from_regex(line: InputLine, level: str) -> bool:
    """判断该行的标题分类是否来自正则（而非 style_hint 或 outline_level）。"""
    style = line.style_hint.strip() if line.style_hint else ""
    heading_map = {"H1": 1, "H2": 2, "H3": 3, "H4": 4}
    n = heading_map.get(level, 0)
    if style and re.match(rf'^Heading\s*{n}$', style, re.IGNORECASE):
        return False
    if line.outline_level is not None and line.outline_level == n - 1:
        return False
    return True


def _extract_h2_ordinal(text: str) -> int | None:
    """从 H2 行（如 '一、总则'）提取中文序号的整数值。"""
    m = _H2_RE.match(text.strip())
    if not m:
        return None
    return _cn_to_int(m.group(1))


def _handle_heading_with_gates(
    level: str, line: InputLine, doc: StructuredDocument,
    stack: list[SectionBlock], last_h2_zh_ord: int | None
) -> bool:
    """带上下文门控的标题处理。返回 True 表示接受为标题，False 表示降级为 body。"""
    if not _is_from_regex(line, level):
        _handle_heading(level, line, doc, stack)
        return True

    level_num = int(level[1])

    # H2 序号单调递增检查
    if level == "H2":
        ord_val = _extract_h2_ordinal(line.text)
        if ord_val is not None and last_h2_zh_ord is not None and ord_val <= last_h2_zh_ord:
            return False

    # H3 上下文门控：stack 中需存在 level ≤ 2
    if level == "H3":
        if not any(_stack_level_at(stack, i) <= 2 for i in range(len(stack))):
            return False

    # H4 上下文门控：stack top 需为 3 或 4
    if level == "H4":
        top = _stack_level(stack)
        if top not in (3, 4):
            return False

    _handle_heading(level, line, doc, stack)
    return True


def _stack_level_at(stack: list[SectionBlock], idx: int) -> int:
    role = stack[idx].role
    if role.startswith("h") and len(role) == 2 and role[1:].isdigit():
        return int(role[1])
    return 0


def _handle_heading(level: str, line: InputLine, doc: StructuredDocument,
                    stack: list[SectionBlock]) -> None:
    role = level.lower()
    level_num = int(level[1])
    block = SectionBlock(role=role, title=_normalize_text(line.text))

    while stack and _stack_level(stack) >= level_num:
        stack.pop()

    if stack:
        stack[-1].children.append(block)
    else:
        doc.main.append(block)
    stack.append(block)


def _stack_level(stack: list[SectionBlock]) -> int:
    if not stack:
        return 0
    role = stack[-1].role
    if role.startswith("h") and len(role) == 2 and role[1:].isdigit():
        return int(role[1])
    return 0


def _handle_table(line: InputLine, stack: list[SectionBlock],
                  doc: StructuredDocument) -> None:
    block = SectionBlock(role="table")
    block.content.append(line)
    if stack:
        stack[-1].children.append(block)
    else:
        doc.main.append(block)


def _append_body(line: InputLine, stack: list[SectionBlock],
                 doc: StructuredDocument) -> None:
    if not line.text.strip() and not line.is_table:
        return
    if stack:
        stack[-1].content.append(line)
    else:
        # 合并到 main 末尾已有的 body block
        if doc.main and doc.main[-1].role == "body":
            doc.main[-1].content.append(line)
        else:
            block = SectionBlock(role="body")
            block.content.append(line)
            doc.main.append(block)


# ---- TOC 处理 ----

def _handle_toc(line: InputLine, token: str, doc: StructuredDocument,
                buffer: list[InputLine], ordinals: set[str],
                blank_run: int) -> _HandlerResult:
    if token == "TOCTitle":
        buffer.append(line)
        return _HandlerResult()

    if token == "GlossaryTitle":
        _flush_toc(doc, buffer)
        return _HandlerResult(consumed=True, reprocess=True)

    if token == "H1":
        ord_key = _extract_ordinal(line.text)
        if ord_key and ord_key in ordinals:
            _flush_toc(doc, buffer)
            return _HandlerResult(consumed=True, reprocess=True)
        buffer.append(line)
        if ord_key:
            ordinals.add(ord_key)
        return _HandlerResult()

    if token == "BLANK":
        if buffer and blank_run >= 2:
            _flush_toc(doc, buffer)
            return _HandlerResult()
        buffer.append(line)
        return _HandlerResult()

    if token in ("H2", "H3", "H4", "NORMAL"):
        buffer.append(line)
        return _HandlerResult()

    _flush_toc(doc, buffer)
    return _HandlerResult(consumed=True, reprocess=True)


def _extract_ordinal(text: str) -> str | None:
    m = re.match(r'第([一二三四五六七八九十百〇零]+)[节節]', text)
    if not m:
        return None
    return str(_cn_to_int(m.group(1)))


_CN_DIGITS = {
    '〇': 0, '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
    '十': 10, '百': 100,
}


def _cn_to_int(cn: str) -> int:
    result = 0
    current = 0
    for ch in cn:
        val = _CN_DIGITS.get(ch, 0)
        if val >= 10:
            if current == 0:
                current = 1
            result += current * val
            current = 0
        else:
            current = val
    return result + current


def _flush_toc(doc: StructuredDocument, buffer: list[InputLine]) -> None:
    if not buffer:
        return
    for line in buffer:
        text = _normalize_text(line.text).strip()
        if text:
            doc.toc.append(SectionBlock(role="toc_item", title=text))
    buffer.clear()


# ---- GLOSSARY 处理 ----

def _handle_glossary(line: InputLine, token: str, doc: StructuredDocument,
                     stack: list[SectionBlock]) -> _HandlerResult:
    if token == "H1":
        return _HandlerResult(consumed=True, reprocess=True)
    if token == "GlossaryTitle":
        return _HandlerResult()
    _append_body(line, stack, doc)
    return _HandlerResult()


# ---- 后处理 ----

def flatten_section(block: SectionBlock) -> str:
    parts: list[str] = []
    if block.title:
        parts.append(block.title)
    for line in block.content:
        if line.is_table and line.table_rows:
            for row in line.table_rows:
                parts.append(" ".join(c for c in row if c))
        else:
            parts.append(line.text)
    for child in block.children:
        parts.append(flatten_section(child))
    return "\n".join(p for p in parts if p.strip())


def flatten_document(doc: StructuredDocument) -> None:
    for block in doc.main:
        block.text_content = flatten_section(block)


# ---- python-docx 提取 ----

def extract_input_lines(docx_path: str) -> list[InputLine]:
    """从 DOCX 文件提取 InputLine 列表，保留样式信息和文档顺序。"""
    from docx import Document

    doc = Document(docx_path)
    lines: list[InputLine] = []
    idx = 0

    for item in doc.iter_inner_content():
        # 判断是段落还是表格
        item_type = getattr(item, '__class__', type(None)).__name__

        if item_type == 'Table':
            rows: list[list[str]] = []
            for row in item.rows:
                cells = [cell.text.replace('\n', ' ').strip() for cell in row.cells]
                rows.append(cells)
            lines.append(InputLine(
                text="",
                style_hint="Table",
                is_table=True,
                table_rows=rows,
                source_index=idx,
            ))
            idx += 1
        else:
            # Paragraph
            para = item
            text = para.text or ""
            style_name = para.style.name if para.style else ""
            outline_lvl = _get_outline_level(para)
            has_break = bool(para.contains_page_break) if hasattr(para, 'contains_page_break') else False

            lines.append(InputLine(
                text=text,
                style_hint=style_name,
                is_table=False,
                table_rows=None,
                has_page_break=has_break,
                outline_level=outline_lvl,
                source_index=idx,
            ))
            idx += 1

    return lines


def _get_outline_level(paragraph) -> int | None:
    """从段落属性或样式中获取大纲级别。"""
    # 直接属性
    pPr = paragraph._element.pPr
    if pPr is not None and pPr.outlineLvl is not None:
        return pPr.outlineLvl.val

    # 样式定义
    style = paragraph.style
    if style and style.element is not None and style.element.pPr is not None:
        style_outline = style.element.pPr.outlineLvl
        if style_outline is not None:
            return style_outline.val

    return None


# ---- 页面-段落映射 ----

def build_page_section_map(pdf_path: str, input_lines: list[InputLine]) -> dict[int, list[int]]:
    """构建 PDF 页码 → InputLine source_index 的映射。

    策略：用 pdfplumber 提取每页文本，按文本量贪心分配 InputLine 到各页。
    """
    from src.documents.service import extract_pages_from_pdf

    page_texts = extract_pages_from_pdf(pdf_path)
    if not page_texts:
        return {}

    # 计算每行的去空白文本长度
    line_lengths: list[int] = []
    for line in input_lines:
        if line.is_table and line.table_rows:
            text = " ".join(c for row in line.table_rows for c in row if c)
        else:
            text = line.text
        line_lengths.append(len(_strip_ws(_normalize_text(text))))

    # 计算每页去空白后的文本长度（作为分配目标）
    from src.documents.service import _strip_all_whitespace as _sw, _normalize_text as _nt
    page_target: list[int] = []
    for pt in page_texts:
        page_target.append(len(_sw(_nt(pt))))

    # 贪心分配：按页面顺序，累计行长度直到覆盖当前页文本量
    page_map: dict[int, list[int]] = {i + 1: [] for i in range(len(page_texts))}
    line_idx = 0

    for page_num, target_len in enumerate(page_target, 1):
        if target_len == 0:
            continue
        accumulated = 0
        while line_idx < len(line_lengths) and accumulated < target_len:
            page_map[page_num].append(line_idx)
            accumulated += line_lengths[line_idx]
            line_idx += 1
        # 如果行用完了但还有后续页，后续页留空

    return page_map


def section_diffs_to_page_diffs(
    section_diffs: list,
    page_map_a: dict[int, list[int]],
    page_map_b: dict[int, list[int]],
    input_lines_a: list | None = None,
    input_lines_b: list | None = None,
    pdf_pages_a: list[str] | None = None,
    pdf_pages_b: list[str] | None = None,
) -> list[dict]:
    """将 section 级 diff 结果转为 page 级结果列表。

    以实际 PDF 页码为主单位，按顺序 1:1 配对。
    diff_type 由 section diff 决定，diff_ops 从 PDF 页面文本计算（确保与前端一致）。
    """
    import json
    from src.documents.service import compute_text_diff, _normalize_text, _strip_all_whitespace

    idx_to_page_a = _reverse_map(page_map_a)
    idx_to_page_b = _reverse_map(page_map_b)

    pages_a_set = set(page_map_a.keys())
    pages_b_set = set(page_map_b.keys())

    # page -> 涉及的 section diffs
    page_diff_map_a: dict[int, list] = {p: [] for p in pages_a_set}
    page_diff_map_b: dict[int, list] = {p: [] for p in pages_b_set}
    for sd in section_diffs:
        if sd.section_a:
            for p in _get_pages_for_block(sd.section_a, idx_to_page_a):
                if p in page_diff_map_a:
                    page_diff_map_a[p].append(sd)
        if sd.section_b:
            for p in _get_pages_for_block(sd.section_b, idx_to_page_b):
                if p in page_diff_map_b:
                    page_diff_map_b[p].append(sd)

    results: list[dict] = []
    max_page = max(max(pages_a_set, default=0), max(pages_b_set, default=0))

    for page_num in range(1, max_page + 1):
        pa = page_num if page_num in pages_a_set else None
        pb = page_num if page_num in pages_b_set else None

        if pa is None and pb is None:
            continue

        if pa is None:
            results.append({"page_a": None, "page_b": pb, "diff_type": "added", "diff_ops_json": None})
            continue
        if pb is None:
            results.append({"page_a": pa, "page_b": None, "diff_type": "deleted", "diff_ops_json": None})
            continue

        # 收集该页涉及的 section diffs 判断 diff_type
        sds: list = []
        for sd in page_diff_map_a.get(pa, []):
            if sd not in sds:
                sds.append(sd)
        for sd in page_diff_map_b.get(pb, []):
            if sd not in sds:
                sds.append(sd)

        has_modified = any(sd.diff_type == "modified" for sd in sds)

        if not has_modified:
            results.append({"page_a": pa, "page_b": pb, "diff_type": "equal", "diff_ops_json": None})
            continue

        # 有 modified 的 section：用 PDF 页面文本重新计算 diff_ops
        if pdf_pages_a and pdf_pages_b and pa <= len(pdf_pages_a) and pb <= len(pdf_pages_b):
            text_a = pdf_pages_a[pa - 1]
            text_b = pdf_pages_b[pb - 1]
        else:
            # fallback: 用 InputLine 文本
            text_a = _page_text_from_lines(page_map_a, input_lines_a, pa)
            text_b = _page_text_from_lines(page_map_b, input_lines_b, pb)

        norm_a = _strip_all_whitespace(_normalize_text(text_a))
        norm_b = _strip_all_whitespace(_normalize_text(text_b))

        if norm_a == norm_b:
            results.append({"page_a": pa, "page_b": pb, "diff_type": "equal", "diff_ops_json": None})
        else:
            ops = compute_text_diff(text_a, text_b)
            if all(op == 0 for op, *_ in ops):
                results.append({"page_a": pa, "page_b": pb, "diff_type": "equal", "diff_ops_json": None})
            else:
                results.append({
                    "page_a": pa, "page_b": pb, "diff_type": "modified",
                    "diff_ops_json": json.dumps(ops, ensure_ascii=False),
                })

    return results


def _page_text_from_lines(page_map, input_lines, page_num):
    """从 InputLine 提取指定页的文本（fallback 用）。"""
    if input_lines is None or page_num not in page_map:
        return ""
    parts = []
    for idx in page_map[page_num]:
        if idx < len(input_lines):
            line = input_lines[idx]
            if line.is_table and line.table_rows:
                parts.append(" ".join(c for row in line.table_rows for c in row if c))
            else:
                parts.append(line.text)
    return "\n".join(parts)


def _reverse_map(page_map: dict[int, list[int]]) -> dict[int, int]:
    """{page: [idx,...]} → {idx: page}"""
    result: dict[int, int] = {}
    for page_num, indices in page_map.items():
        for idx in indices:
            result[idx] = page_num
    return result


def _get_pages_for_block(block, idx_to_page: dict[int, int]) -> list[int]:
    """获取 SectionBlock 涉及的所有 PDF 页码（有序去重）。"""
    pages: set[int] = set()
    _collect_pages(block, idx_to_page, pages)
    if not pages:
        return []
    return sorted(pages)


def _collect_pages(block, idx_to_page: dict[int, int], pages: set[int]) -> None:
    for line in block.content:
        if line.source_index in idx_to_page:
            pages.add(idx_to_page[line.source_index])
    for child in block.children:
        _collect_pages(child, idx_to_page, pages)

