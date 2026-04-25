"""
文档比对核心服务

流程：DOCX 先转 PDF（LibreOffice）→ 结构化文本提取（pdfplumber）→ 页级对齐 → 分区域 diff → 结果入库
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import time
import logging
import unicodedata
from dataclasses import dataclass, field

import pdfplumber
from difflib import SequenceMatcher
from diff_match_patch import diff_match_patch
from sqlmodel.ext.asyncio.session import AsyncSession

from src.documents.models import DocumentCompareTask, DocumentPageDiff

logger = logging.getLogger(__name__)

dmp = diff_match_patch()


# ---- 结构化页面块 ----

@dataclass
class TextBlock:
    """非表格区域的纯文本"""
    text: str


@dataclass
class TableBlock:
    """表格区域，保留行/单元格结构"""
    rows: list[list[str]]  # 每行是单元格列表


def _find_soffice() -> str:
    """查找 soffice 可执行文件路径"""
    if sys.platform == "darwin":
        path = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        if os.path.isfile(path):
            return path
    # Linux 或 Darwin 回退
    return "soffice"


def docx_to_pdf(docx_path: str, output_dir: str | None = None) -> str:
    """用 LibreOffice headless 模式将 DOCX 转为 PDF，返回 PDF 文件路径"""
    soffice = _find_soffice()
    if output_dir is None:
        output_dir = os.path.dirname(docx_path)

    cmd = [
        soffice,
        "--headless",
        "--convert-to", "pdf",
        "--outdir", output_dir,
        docx_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice 转换失败: {result.stderr}")

    pdf_name = os.path.splitext(os.path.basename(docx_path))[0] + ".pdf"
    pdf_path = os.path.join(output_dir, pdf_name)
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"转换后未找到 PDF: {pdf_path}")
    return pdf_path


def _normalize_text(text: str) -> str:
    """归一化文本用于对齐和 diff 比较"""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r'[​‌‍⁠﻿­]', '', text)
    text = re.sub(r'[^\S\n]+', ' ', text)
    text = re.sub(r'\n{2,}', '\n', text)
    text = '\n'.join(line.strip() for line in text.split('\n'))
    return text.strip()


def _strip_all_whitespace(text: str) -> str:
    """去掉所有空白字符，用于判断两页内容是否真正相同"""
    return re.sub(r'\s+', '', text)


# ---- PDF 提取（pdfplumber）----

def _bbox_overlap_y(top: tuple, bot: tuple) -> bool:
    """判断两个 bbox 在 Y 轴上是否有重叠"""
    return top[3] > bot[1] and bot[3] > top[1]


_NUM_RE = re.compile(r'^[\d,.\-()（）\s%]+$')


def _normalize_table_rows(raw_rows: list[list]) -> list[str]:
    """归一化表格行：合并视觉换行行 + 配对标签-数值行。

    解决同一表格内容在不同 PDF 中因列宽不同导致的提取差异：
    1. 视觉换行：单元格内容过长换行，pdfplumber 生成多行
       文件1: | "青岛莱西元泰村镇银行股份有限公司" | 2025年11月 | 95,075 |
       文件2: | "青岛莱西元泰" | 2025年 | 95,075 | 100% | 股权 | 2025年 | ...
              | "村镇银行股份" | 11月   |       |      | 转让 | 11月   | ...
              | "有限公司"     |        |       |      |      |        | ...
    2. 标签-数值分离：标签和数值分别在不同行
    """
    if not raw_rows:
        return []

    # 预处理：单元格内换行替换为空格
    rows: list[list[str]] = []
    for row in raw_rows:
        rows.append([(cell or "").replace("\n", " ").strip() for cell in row])

    # ── 第一步：合并视觉换行行 ──
    # 关键：以【上一行】的非空单元格数为基准，当前行显著更少则视为续行。
    # 旧的阈值用总列数做基准，对宽表（10+列）太严格——
    # 换行续行可能有 5 个非空单元格（文本、日期、方式等一起换行），仍远少于主行的 10 个。
    merged: list[list[str]] = [rows[0]]
    for row in rows[1:]:
        prev_count = sum(1 for c in merged[-1] if c)
        curr_count = sum(1 for c in row if c)
        # 当前行为空 → 跳过
        if curr_count == 0:
            continue
        # 续行判定：当前行非空格数 < 上一行的 80%，或只有 1 个非空格
        is_continuation = curr_count <= 1 or curr_count < prev_count * 0.8
        if is_continuation:
            prev = merged[-1]
            for i in range(min(len(row), len(prev))):
                if row[i]:
                    prev[i] = (prev[i] + row[i]).strip()
        else:
            merged.append(row)

    # ── 第二步：配对标签行与后续纯数值行 ──
    result: list[str] = []
    pending_labels: list[int] = []

    for cells in merged:
        non_empty = [c for c in cells if c]
        row_text = " ".join(non_empty)
        if not row_text:
            continue

        if len(non_empty) == 1 and _NUM_RE.match(non_empty[0]):
            if pending_labels:
                idx = pending_labels.pop(0)
                result[idx] += " " + non_empty[0]
            else:
                result.append(row_text)
            continue

        has_num = any(_NUM_RE.match(c) for c in non_empty if c)
        if not has_num:
            pending_labels.append(len(result))
        else:
            pending_labels.clear()

        result.append(row_text)

    return result


def _extract_page_text(page) -> str:
    """分三层提取页面文本：表格上方 → 表格区域 → 表格下方

    有边框表格用 table.extract() 逐行逐单元格提取，保持单元格内容完整。
    非表格区域直接用 extract_text()。
    """
    tables = page.find_tables()
    if not tables:
        return page.extract_text() or ""

    page_height = page.height
    parts: list[str] = []

    # 构建表格的 Y 轴覆盖区间（合并重叠的表格）
    table_bboxes = [t.bbox for t in tables]
    table_bboxes.sort(key=lambda b: b[1])
    merged: list[tuple] = [table_bboxes[0]]
    for bbox in table_bboxes[1:]:
        if _bbox_overlap_y(merged[-1], bbox):
            merged[-1] = (merged[-1][0], min(merged[-1][1], bbox[1]),
                          merged[-1][2], max(merged[-1][3], bbox[3]))
        else:
            merged.append(bbox)

    cursor = 0
    for tbl_bbox in merged:
        _, tbl_top, _, tbl_bottom = tbl_bbox

        # 1) 表格上方的非表格文本
        if tbl_top > cursor + 1:
            parts.append(page.within_bbox((0, cursor, page.width, tbl_top)).extract_text() or "")

        # 2) 表格区域 — 逐行逐单元格提取
        for table in tables:
            if not _bbox_overlap_y(table.bbox, tbl_bbox):
                continue
            for line in _normalize_table_rows(table.extract()):
                parts.append(line)

        cursor = tbl_bottom

    # 3) 最后一个表格下方的非表格文本
    if cursor < page_height - 1:
        parts.append(page.within_bbox((0, cursor, page.width, page_height)).extract_text() or "")

    return "\n".join(parts)


def _extract_page_blocks(page) -> list:
    """分区域提取页面内容，返回 TextBlock 和 TableBlock 的交替列表。

    用于结构化 diff：表格区域保留行/单元格结构，非表格区域保留纯文本。
    """
    tables = page.find_tables()
    if not tables:
        return [TextBlock(text=page.extract_text() or "")]

    page_height = page.height
    blocks: list = []

    # 构建表格的 Y 轴覆盖区间（合并重叠的表格）
    table_bboxes = [t.bbox for t in tables]
    table_bboxes.sort(key=lambda b: b[1])
    merged_bboxes: list[tuple] = [table_bboxes[0]]
    for bbox in table_bboxes[1:]:
        if _bbox_overlap_y(merged_bboxes[-1], bbox):
            merged_bboxes[-1] = (merged_bboxes[-1][0], min(merged_bboxes[-1][1], bbox[1]),
                                 merged_bboxes[-1][2], max(merged_bboxes[-1][3], bbox[3]))
        else:
            merged_bboxes.append(bbox)

    cursor = 0
    for tbl_bbox in merged_bboxes:
        _, tbl_top, _, tbl_bottom = tbl_bbox

        # 1) 表格上方的非表格文本
        if tbl_top > cursor + 1:
            text = page.within_bbox((0, cursor, page.width, tbl_top)).extract_text() or ""
            if text.strip():
                blocks.append(TextBlock(text=text))

        # 2) 表格区域 — 收集所有重叠表格的原始行数据
        table_rows: list[list[str]] = []
        for table in tables:
            if not _bbox_overlap_y(table.bbox, tbl_bbox):
                continue
            raw_rows = table.extract()
            for row in raw_rows:
                cells = [(cell or "").replace("\n", " ").strip() for cell in row]
                if any(c for c in cells):
                    table_rows.append(cells)

        if table_rows:
            blocks.append(TableBlock(rows=table_rows))

        cursor = tbl_bottom

    # 3) 最后一个表格下方的非表格文本
    if cursor < page_height - 1:
        text = page.within_bbox((0, cursor, page.width, page_height)).extract_text() or ""
        if text.strip():
            blocks.append(TextBlock(text=text))

    return blocks


def _blocks_to_text(blocks: list) -> str:
    """将结构化块列表转换为纯文本（兼容原有的页面级对齐逻辑）"""
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, TextBlock):
            parts.append(block.text)
        elif isinstance(block, TableBlock):
            for row in block.rows:
                parts.append(" ".join(c for c in row if c))
    return "\n".join(parts)


def extract_pages_from_pdf(file_path: str) -> list[str]:
    text_pages = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = _extract_page_text(page)
            text_pages.append(text)
    return text_pages


def _is_mhtml_file(file_path: str) -> bool:
    """检测 .doc/.docx 文件是否实际为 MHTML 格式（网页另存为后重命名）"""
    try:
        with open(file_path, 'rb') as f:
            header = f.read(512).lower()
        # MHTML 特征：MIME Content-Type 头 或 boundary 分隔符
        return b'content-type:' in header and (
            b'multipart/related' in header or
            b'boundary=' in header or
            b'message/rfc822' in header
        )
    except Exception:
        return False


def extract_pages(file_path: str) -> tuple[list[str], list[str]]:
    """根据文件类型分发提取，返回 (text_pages, html_pages)
    PDF/DOCX/DOC: 统一走 pdfplumber，html_pages 为空（前端用 PDF.js 渲染）
    """
    lower = file_path.lower()
    if lower.endswith(".pdf"):
        return extract_pages_from_pdf(file_path), []
    elif lower.endswith((".docx", ".doc")):
        if _is_mhtml_file(file_path):
            raise ValueError(
                "上传的文件不是有效的 Word 文档，而是网页另存为格式（MHTML）。"
                "请用 WPS 或 Word 打开后另存为 .docx 格式再上传。"
            )
        pdf_path = docx_to_pdf(file_path)
        return extract_pages_from_pdf(pdf_path), []
    else:
        raise ValueError(f"不支持的文件格式: {file_path}")


def extract_pages_structured(file_path: str) -> list[list]:
    """根据文件类型分发提取，返回每页的结构化块列表 [TextBlock | TableBlock, ...]"""
    lower = file_path.lower()
    if lower.endswith(".pdf"):
        pdf_path = file_path
    elif lower.endswith((".docx", ".doc")):
        if _is_mhtml_file(file_path):
            raise ValueError(
                "上传的文件不是有效的 Word 文档，而是网页另存为格式（MHTML）。"
                "请用 WPS 或 Word 打开后另存为 .docx 格式再上传。"
            )
        pdf_path = docx_to_pdf(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {file_path}")

    pages_blocks = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages_blocks.append(_extract_page_blocks(page))
    return pages_blocks


# ---- 页级对齐 ----

def _page_similarity(sa: str, sb: str) -> float:
    """计算两页 stripped 文本的相似度（0~1），基于较短页面被覆盖的比例。"""
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0

    matcher = SequenceMatcher(None, sa, sb, autojunk=False)
    matches = matcher.get_matching_blocks()
    matched_chars = sum(size for _, _, size in matches)

    shorter = min(len(sa), len(sb))
    return matched_chars / shorter if shorter > 0 else 0.0


def align_pages(pages_a: list[str], pages_b: list[str]) -> list[tuple]:
    """页级对齐，返回 [(page_a_index, page_b_index, diff_type), ...]

    等页数时直接按序配对（O(n)），不等页数时用带状 DP 找最优对齐。
    """
    if not pages_a and not pages_b:
        return []

    na, nb = len(pages_a), len(pages_b)

    # 预计算 stripped 文本（每页只算一次）
    sa = [_strip_all_whitespace(_normalize_text(p)) for p in pages_a]
    sb = [_strip_all_whitespace(_normalize_text(p)) for p in pages_b]

    # 快速路径：页数相同，直接按序配对
    if na == nb:
        return [(i, i, "equal" if sa[i] == sb[i] else "modified") for i in range(na)]

    # DP 路径：页数不同，带状 DP
    SIM_THRESHOLD = 0.3
    BAND = max(5, abs(na - nb) + 3)

    NEG_INF = float('-inf')
    dp = [[0.0] * (nb + 1) for _ in range(na + 1)]
    choice = [[''] * (nb + 1) for _ in range(na + 1)]

    for i in range(1, na + 1):
        j_lo = max(1, i - BAND)
        j_hi = min(nb, i + BAND)
        for j in range(j_lo, j_hi + 1):
            # 相似度：精确相等 → 1.0，否则按需计算
            if sa[i - 1] == sb[j - 1]:
                s = 1.0
            else:
                s = _page_similarity(sa[i - 1], sb[j - 1])
            match_val = dp[i - 1][j - 1] + (s if s >= SIM_THRESHOLD else NEG_INF)
            skip_a = dp[i - 1][j]
            skip_b = dp[i][j - 1]

            best = max(match_val, skip_a, skip_b)
            dp[i][j] = best
            if best == match_val:
                choice[i][j] = 'match'
            elif best == skip_a:
                choice[i][j] = 'skip_a'
            else:
                choice[i][j] = 'skip_b'

    # 回溯
    aligned = []
    i, j = na, nb
    while i > 0 and j > 0:
        if choice[i][j] == 'match':
            diff_type = "equal" if sa[i - 1] == sb[j - 1] else "modified"
            aligned.append((i - 1, j - 1, diff_type))
            i -= 1
            j -= 1
        elif choice[i][j] == 'skip_a':
            aligned.append((i - 1, None, "deleted"))
            i -= 1
        else:
            aligned.append((None, j - 1, "added"))
            j -= 1

    while i > 0:
        aligned.append((i - 1, None, "deleted"))
        i -= 1
    while j > 0:
        aligned.append((None, j - 1, "added"))
        j -= 1

    aligned.reverse()
    return aligned


# ---- 文本 diff ----

def _is_content_identical(text_a: str, text_b: str) -> bool:
    """判断两段文本的实际内容是否相同（忽略由排版导致的字符顺序差异）。

    extract_text() 对无边框多栏布局会因列宽不同产生不同的字符读取顺序，
    导致 strip_whitespace 后字符序列不同，但实际内容完全一致。
    通过比较字符频率分布（Counter）来判断：字符相同、仅顺序不同则视为内容一致。
    """
    stripped_a = _strip_all_whitespace(_normalize_text(text_a))
    stripped_b = _strip_all_whitespace(_normalize_text(text_b))

    if stripped_a == stripped_b:
        return True

    from collections import Counter
    return Counter(stripped_a) == Counter(stripped_b)


def compute_text_diff(text_a: str, text_b: str) -> list[list]:
    """计算文本差异，同时记录每个段落在归一化文本中的字符偏移。
    返回 [[op, text, offset_a, offset_b], ...]
    op: -1=删除, 0=相同, 1=新增
    offset_a: 该段落在文档A去空白文本中的起始位置
    offset_b: 该段落在文档B去空白文本中的起始位置
    """
    norm_a = _strip_all_whitespace(_normalize_text(text_a))
    norm_b = _strip_all_whitespace(_normalize_text(text_b))
    diffs = dmp.diff_main(norm_a, norm_b)
    dmp.diff_cleanupMerge(diffs)

    result = []
    pos_a = 0
    pos_b = 0
    for op, text in diffs:
        result.append([op, text, pos_a, pos_b])
        if op == -1:
            pos_a += len(text)
        elif op == 1:
            pos_b += len(text)
        else:
            pos_a += len(text)
            pos_b += len(text)
    return result


def _block_signature(block) -> str:
    """生成块的文本签名，用于 SequenceMatcher 对齐"""
    if isinstance(block, TextBlock):
        return _strip_all_whitespace(_normalize_text(block.text))[:300]
    elif isinstance(block, TableBlock):
        # 表格签名：所有单元格值拼接后取前300字符
        all_text = " ".join(c for row in block.rows for c in row if c)
        return _strip_all_whitespace(_normalize_text(all_text))[:300]
    return ""


def _row_signature(row: list[str]) -> str:
    """生成表格行的签名，用于行级对齐"""
    return _strip_all_whitespace(_normalize_text(" ".join(c for c in row if c)))


def compute_structured_diff(blocks_a: list, blocks_b: list) -> list[list]:
    """分区域比对：表格按行/单元格比对，非表格用字符级 diff。

    返回格式与 compute_text_diff 相同：[[op, text, offset_a, offset_b], ...]
    """
    # 对齐两边的 blocks
    sigs_a = [_block_signature(b) for b in blocks_a]
    sigs_b = [_block_signature(b) for b in blocks_b]

    matcher = SequenceMatcher(None, sigs_a, sigs_b, autojunk=False)
    ops: list[list] = []
    pos_a = 0
    pos_b = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                ba, bb = blocks_a[i], blocks_b[j]
                block_ops = _diff_aligned_blocks(ba, bb, pos_a, pos_b)
                ops.extend(block_ops)
                pos_a += sum(len(o[1]) for o in block_ops if o[0] in (-1, 0))
                pos_b += sum(len(o[1]) for o in block_ops if o[0] in (1, 0))
        elif tag == "replace":
            pairs = min(i2 - i1, j2 - j1)
            for k in range(pairs):
                ba, bb = blocks_a[i1 + k], blocks_b[j1 + k]
                block_ops = _diff_aligned_blocks(ba, bb, pos_a, pos_b)
                ops.extend(block_ops)
                pos_a += sum(len(o[1]) for o in block_ops if o[0] in (-1, 0))
                pos_b += sum(len(o[1]) for o in block_ops if o[0] in (1, 0))
            for k in range(pairs, i2 - i1):
                ba = blocks_a[i1 + k]
                text = _block_to_normalized(ba)
                ops.append([-1, text, pos_a, pos_b])
                pos_a += len(text)
            for k in range(pairs, j2 - j1):
                bb = blocks_b[j1 + k]
                text = _block_to_normalized(bb)
                ops.append([1, text, pos_a, pos_b])
                pos_b += len(text)
        elif tag == "delete":
            for i in range(i1, i2):
                text = _block_to_normalized(blocks_a[i])
                ops.append([-1, text, pos_a, pos_b])
                pos_a += len(text)
        elif tag == "insert":
            for j in range(j1, j2):
                text = _block_to_normalized(blocks_b[j])
                ops.append([1, text, pos_a, pos_b])
                pos_b += len(text)

    return ops


def _block_to_normalized(block) -> str:
    """将块转换为归一化纯文本"""
    if isinstance(block, TextBlock):
        return _strip_all_whitespace(_normalize_text(block.text))
    elif isinstance(block, TableBlock):
        text = "\n".join(" ".join(c for c in row if c) for row in block.rows)
        return _strip_all_whitespace(_normalize_text(text))
    return ""


def _block_to_line_text(block) -> str:
    """将任意块转为保留行结构的文本（TextBlock 直接取 text，TableBlock 逐行拼接单元格）"""
    if isinstance(block, TextBlock):
        return block.text
    elif isinstance(block, TableBlock):
        return "\n".join(" ".join(c for c in row if c) for row in block.rows)
    return ""


def _diff_aligned_blocks(ba, bb, pos_a: int, pos_b: int) -> list[list]:
    """所有块类型统一使用行级对齐 + 逐行 diff。

    无论 TextBlock 还是 TableBlock，都先转为文本，按行拆分后用
    SequenceMatcher 按内容对齐行。内容相同的行直接标 equal，
    不同的行才做字符级 diff。这解决了因排版/列宽不同导致行顺序
    或拆分不同的问题。
    """
    norm_a = _normalize_text(_block_to_line_text(ba))
    norm_b = _normalize_text(_block_to_line_text(bb))
    lines_a = [l for l in norm_a.split('\n') if l.strip()]
    lines_b = [l for l in norm_b.split('\n') if l.strip()]
    stripped_a = [_strip_all_whitespace(l) for l in lines_a]
    stripped_b = [_strip_all_whitespace(l) for l in lines_b]

    if not stripped_a and not stripped_b:
        return []

    matcher = SequenceMatcher(None, stripped_a, stripped_b, autojunk=False)

    result = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i in range(i1, i2):
                text = stripped_a[i]
                if text:
                    result.append([0, text, pos_a, pos_b])
                    pos_a += len(text)
                    pos_b += len(text)
        elif tag == "replace":
            pairs = min(i2 - i1, j2 - j1)
            for k in range(pairs):
                sa, sb = stripped_a[i1 + k], stripped_b[j1 + k]
                if sa == sb:
                    if sa:
                        result.append([0, sa, pos_a, pos_b])
                        pos_a += len(sa)
                        pos_b += len(sb)
                else:
                    diffs = dmp.diff_main(sa, sb)
                    dmp.diff_cleanupMerge(diffs)
                    for op, text in diffs:
                        result.append([op, text, pos_a, pos_b])
                        if op == -1:
                            pos_a += len(text)
                        elif op == 1:
                            pos_b += len(text)
                        else:
                            pos_a += len(text)
                            pos_b += len(text)
            for k in range(pairs, i2 - i1):
                text = stripped_a[i1 + k]
                if text:
                    result.append([-1, text, pos_a, pos_b])
                    pos_a += len(text)
            for k in range(pairs, j2 - j1):
                text = stripped_b[j1 + k]
                if text:
                    result.append([1, text, pos_a, pos_b])
                    pos_b += len(text)
        elif tag == "delete":
            for i in range(i1, i2):
                text = stripped_a[i]
                if text:
                    result.append([-1, text, pos_a, pos_b])
                    pos_a += len(text)
        elif tag == "insert":
            for j in range(j1, j2):
                text = stripped_b[j]
                if text:
                    result.append([1, text, pos_a, pos_b])
                    pos_b += len(text)

    return result


def _diff_table_blocks(ta: TableBlock, tb: TableBlock, pos_a: int, pos_b: int) -> list[list]:
    """表格块 diff：行级对齐 → 逐单元格比对"""
    rows_a = ta.rows
    rows_b = tb.rows

    # 行级对齐
    sigs_a = [_row_signature(r) for r in rows_a]
    sigs_b = [_row_signature(r) for r in rows_b]
    matcher = SequenceMatcher(None, sigs_a, sigs_b, autojunk=False)

    ops: list[list] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                row_ops = _diff_table_rows(rows_a[i], rows_b[j])
                for op, text in row_ops:
                    ops.append([op, text, pos_a, pos_b])
                    if op == -1:
                        pos_a += len(text)
                    elif op == 1:
                        pos_b += len(text)
                    else:
                        pos_a += len(text)
                        pos_b += len(text)
        elif tag == "replace":
            pairs = min(i2 - i1, j2 - j1)
            for k in range(pairs):
                row_ops = _diff_table_rows(rows_a[i1 + k], rows_b[j1 + k])
                for op, text in row_ops:
                    ops.append([op, text, pos_a, pos_b])
                    if op == -1:
                        pos_a += len(text)
                    elif op == 1:
                        pos_b += len(text)
                    else:
                        pos_a += len(text)
                        pos_b += len(text)
            for k in range(pairs, i2 - i1):
                text = _strip_all_whitespace(_normalize_text(" ".join(c for c in rows_a[i1 + k] if c)))
                ops.append([-1, text, pos_a, pos_b])
                pos_a += len(text)
            for k in range(pairs, j2 - j1):
                text = _strip_all_whitespace(_normalize_text(" ".join(c for c in rows_b[j1 + k] if c)))
                ops.append([1, text, pos_a, pos_b])
                pos_b += len(text)
        elif tag == "delete":
            for i in range(i1, i2):
                text = _strip_all_whitespace(_normalize_text(" ".join(c for c in rows_a[i] if c)))
                ops.append([-1, text, pos_a, pos_b])
                pos_a += len(text)
        elif tag == "insert":
            for j in range(j1, j2):
                text = _strip_all_whitespace(_normalize_text(" ".join(c for c in rows_b[j] if c)))
                ops.append([1, text, pos_a, pos_b])
                pos_b += len(text)

    return ops


def _diff_table_rows(row_a: list[str], row_b: list[str]) -> list[tuple[int, str]]:
    """逐单元格比对两行表格数据。

    返回 [(op, text), ...]，op: -1=删除, 0=相同, 1=新增
    """
    # 对齐单元格数量（补空格）
    max_cols = max(len(row_a), len(row_b))
    ra = row_a + [""] * (max_cols - len(row_a))
    rb = row_b + [""] * (max_cols - len(row_b))

    ops: list[tuple[int, str]] = []
    for i in range(max_cols):
        ca = _strip_all_whitespace(_normalize_text(ra[i]))
        cb = _strip_all_whitespace(_normalize_text(rb[i]))

        if not ca and not cb:
            continue
        elif ca == cb:
            if ca:
                ops.append((0, ca))
        else:
            if ca:
                ops.append((-1, ca))
            if cb:
                ops.append((1, cb))

    return ops

async def process_document_comparison(db: AsyncSession, task: DocumentCompareTask):
    """异步后台任务：提取 → 对齐 → diff → 写库"""
    start_time = time.time()

    try:
        task.status = "processing"
        db.add(task)
        await db.commit()

        # 1. 提取页面文本（在线程池中执行，避免阻塞事件循环）
        loop = asyncio.get_event_loop()
        text_a_pages, _ = await loop.run_in_executor(None, extract_pages, task.file_a_path)
        text_b_pages, _ = await loop.run_in_executor(None, extract_pages, task.file_b_path)

        task.file_a_page_count = len(text_a_pages)
        task.file_b_page_count = len(text_b_pages)

        # 2. 页级对齐（基于纯文本）
        aligned = align_pages(text_a_pages, text_b_pages)

        # 3. 逐页计算 diff 并写入
        for page_a_idx, page_b_idx, diff_type in aligned:
            text_a = text_a_pages[page_a_idx] if page_a_idx is not None else None
            text_b = text_b_pages[page_b_idx] if page_b_idx is not None else None

            diff_ops = None
            if diff_type == "modified" and text_a is not None and text_b is not None:
                # 先检查内容是否实际相同（排版差异导致的字符顺序不同）
                if _is_content_identical(text_a, text_b):
                    diff_type = "equal"
                else:
                    # 直接对整页文本做行级对齐，绕过 block 级别对齐
                    # （两份 PDF 的 block 结构可能不同：一个有边框表格 TableBlock，一个无边框 TextBlock）
                    ops = _diff_aligned_blocks(
                        TextBlock(text=text_a),
                        TextBlock(text=text_b),
                        0, 0,
                    )
                    if all(op == 0 for op, *_ in ops):
                        diff_type = "equal"
                    else:
                        diff_ops = json.dumps(ops, ensure_ascii=False)

            page_diff = DocumentPageDiff(
                task_id=task.id,
                page_a=(page_a_idx + 1) if page_a_idx is not None else None,
                page_b=(page_b_idx + 1) if page_b_idx is not None else None,
                diff_type=diff_type,
                text_a=text_a,
                text_b=text_b,
                diff_ops_json=diff_ops,
            )
            db.add(page_diff)

        task.comparison_duration = round(time.time() - start_time, 2)
        task.status = "done"
        db.add(task)
        await db.commit()

    except Exception as e:
        logger.exception("文档比对失败 task=%d", task.id)
        task.status = "failed"
        task.error_msg = str(e)
        task.comparison_duration = round(time.time() - start_time, 2)
        db.add(task)
        await db.commit()
