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

from src.database import SessionLocal
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
    """用 LibreOffice headless 模式将 DOCX 转为 PDF，返回 PDF 文件路径。
    若文件路径含非 ASCII 字符（如中文），拷贝到临时 ASCII 路径再转换。
    """
    import shutil
    import tempfile
    soffice = _find_soffice()
    if output_dir is None:
        output_dir = os.path.dirname(docx_path)

    tmpdir = None
    actual_docx_path = docx_path
    actual_output_dir = output_dir

    if not docx_path.isascii() or not output_dir.isascii():
        tmpdir = tempfile.mkdtemp(prefix="lo_convert_")
        ext = os.path.splitext(docx_path)[1]
        safe_name = "doc" + ext
        actual_docx_path = os.path.join(tmpdir, safe_name)
        shutil.copy2(docx_path, actual_docx_path)
        actual_output_dir = tmpdir

    # 使用独立 user profile 避免与已运行的 LibreOffice 实例冲突
    profile_dir = tempfile.mkdtemp(prefix="lo_profile_")
    user_env = f"-env:UserInstallation=file://{profile_dir}"

    cmd = [
        soffice, "--headless", "--convert-to", "pdf",
        user_env,
        "--outdir", actual_output_dir, actual_docx_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
        raise RuntimeError(f"LibreOffice 转换失败: {result.stderr} | stdout: {result.stdout}")

    pdf_name = os.path.splitext(os.path.basename(actual_docx_path))[0] + ".pdf"
    generated_pdf = os.path.join(actual_output_dir, pdf_name)
    if not os.path.isfile(generated_pdf):
        # 列出目录内容辅助排查
        _files = os.listdir(actual_output_dir) if tmpdir else []
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
        raise FileNotFoundError(f"转换后未找到 PDF: {generated_pdf}, 目录内容: {_files}, stdout: {result.stdout}")

    final_pdf_name = os.path.splitext(os.path.basename(docx_path))[0] + ".pdf"
    final_pdf_path = os.path.join(output_dir, final_pdf_name)
    if generated_pdf != final_pdf_path:
        shutil.move(generated_pdf, final_pdf_path)

    if tmpdir:
        shutil.rmtree(tmpdir, ignore_errors=True)
    shutil.rmtree(profile_dir, ignore_errors=True)

    return final_pdf_path


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


def _ensure_pdf(file_path: str) -> str:
    """将 DOCX/DOC 转为 PDF（如需），返回 PDF 文件路径。
    已是 PDF 则直接返回原路径。调用方可缓存此结果避免重复转换。
    """
    lower = file_path.lower()
    if lower.endswith(".pdf"):
        return file_path
    elif lower.endswith((".docx", ".doc")):
        if _is_mhtml_file(file_path):
            raise ValueError(
                "上传的文件不是有效的 Word 文档，而是网页另存为格式（MHTML）。"
                "请用 WPS 或 Word 打开后另存为 .docx 格式再上传。"
            )
        return docx_to_pdf(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {file_path}")


def extract_pages(file_path: str, pdf_path: str | None = None) -> tuple[list[str], list[str]]:
    """根据文件类型分发提取，返回 (text_pages, html_pages)
    PDF/DOCX/DOC: 统一走 pdfplumber，html_pages 为空（前端用 PDF.js 渲染）
    pdf_path: 可选，已转换的 PDF 路径，避免重复调用 LibreOffice。
    """
    resolved = pdf_path or _ensure_pdf(file_path)
    return extract_pages_from_pdf(resolved), []


def extract_pages_structured(file_path: str, pdf_path: str | None = None) -> list[list]:
    """根据文件类型分发提取，返回每页的结构化块列表 [TextBlock | TableBlock, ...]
    pdf_path: 可选，已转换的 PDF 路径，避免重复调用 LibreOffice。
    """
    resolved = pdf_path or _ensure_pdf(file_path)
    pages_blocks = []
    with pdfplumber.open(resolved) as pdf:
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

async def process_document_comparison(task_id: int):
    """异步后台任务：根据文件类型分发到对应管线。

    DOCX+DOCX → Plan B（python-docx 结构化提取 + section 级 diff）
    其他情况  → Legacy（pdfplumber 页级 diff）
    """
    start_time = time.time()

    async with SessionLocal() as db:
        task = await db.get(DocumentCompareTask, task_id)
        if not task:
            logger.error("文档比对任务不存在 task=%d", task_id)
            return

        try:
            task.status = "processing"
            db.add(task)
            await db.commit()

            is_a_docx = task.file_a_path.lower().endswith('.docx')
            is_b_docx = task.file_b_path.lower().endswith('.docx')
            loop = asyncio.get_event_loop()

            if is_a_docx and is_b_docx:
                await _compare_docx_plan_b(task, db, loop, start_time)
            else:
                await _compare_legacy(task, db, loop, start_time)

        except Exception as e:
            logger.exception("文档比对失败 task=%d", task.id)
            task.status = "failed"
            task.error_msg = str(e)
            task.comparison_duration = round(time.time() - start_time, 2)
            db.add(task)
            await db.commit()


async def _compare_legacy(task, db, loop, start_time):
    """现有管线：PDF → pdfplumber → 页级对齐 → diff"""
    # 1. 统一转 PDF
    pdf_a = await loop.run_in_executor(None, _ensure_pdf, task.file_a_path)
    pdf_b = await loop.run_in_executor(None, _ensure_pdf, task.file_b_path)

    # 2. 提取纯文本和结构化块
    text_a_pages, _ = await loop.run_in_executor(None, extract_pages, task.file_a_path, pdf_a)
    text_b_pages, _ = await loop.run_in_executor(None, extract_pages, task.file_b_path, pdf_b)
    blocks_a = await loop.run_in_executor(None, extract_pages_structured, task.file_a_path, pdf_a)
    blocks_b = await loop.run_in_executor(None, extract_pages_structured, task.file_b_path, pdf_b)

    task.file_a_page_count = len(text_a_pages)
    task.file_b_page_count = len(text_b_pages)

    # 3. 页级对齐
    aligned = align_pages(text_a_pages, text_b_pages)

    # 4. 逐页计算 diff
    for page_a_idx, page_b_idx, diff_type in aligned:
        text_a = text_a_pages[page_a_idx] if page_a_idx is not None else None
        text_b = text_b_pages[page_b_idx] if page_b_idx is not None else None

        diff_ops = None
        if diff_type == "modified" and text_a is not None and text_b is not None:
            if _is_content_identical(text_a, text_b):
                diff_type = "equal"
            else:
                page_blocks_a = blocks_a[page_a_idx] if page_a_idx is not None and page_a_idx < len(blocks_a) else []
                page_blocks_b = blocks_b[page_b_idx] if page_b_idx is not None and page_b_idx < len(blocks_b) else []
                can_structured = (
                    len(page_blocks_a) == len(page_blocks_b)
                    and all(type(ba) == type(bb) for ba, bb in zip(page_blocks_a, page_blocks_b))
                )

                if can_structured and page_blocks_a:
                    ops = compute_structured_diff(page_blocks_a, page_blocks_b)
                else:
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
            user_id=task.user_id,
            page_a=(page_a_idx + 1) if page_a_idx is not None else None,
            page_b=(page_b_idx + 1) if page_b_idx is not None else None,
            diff_type=diff_type,
            text_a=text_a,
            text_b=text_b,
            diff_ops_json=diff_ops,
        )
        db.add(page_diff)

    task.comparison_mode = "page"
    task.comparison_duration = round(time.time() - start_time, 2)
    task.status = "done"
    db.add(task)
    await db.commit()


# ---- Plan B: DOCX 结构化比对 ----

def _section_own_text(section) -> str:
    """返回 section 自身文本，不包含子 section。"""
    parts = []
    if section.title:
        parts.append(section.title)
    for line in section.content:
        if line.is_table and line.table_rows:
            for row in line.table_rows:
                parts.append(" ".join(c for c in row if c))
        else:
            parts.append(line.text)
    return "\n".join(p for p in parts if p.strip())


def _section_signature(section) -> str:
    """生成 SectionBlock 的匹配签名。"""
    from src.documents.structuring import _strip_ws, _normalize_text
    parts = []
    if section.role:
        parts.append(section.role)
    if section.title:
        parts.append(_strip_ws(_normalize_text(section.title)))
    own_text = _section_own_text(section)
    if own_text:
        sig = _strip_ws(_normalize_text(own_text))[:200]
        if sig:
            parts.append(sig)
    elif section.text_content:
        sig = _strip_ws(_normalize_text(section.text_content))[:120]
        if sig:
            parts.append(sig)
    return " ".join(parts)


def _align_and_diff_sections(sections_a, sections_b):
    """递归 Section 级对齐 + diff。"""
    from src.documents.structuring import SectionDiffResult

    sigs_a = [_section_signature(s) for s in sections_a]
    sigs_b = [_section_signature(s) for s in sections_b]

    matcher = SequenceMatcher(None, sigs_a, sigs_b, autojunk=False)
    results = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                results.extend(_diff_section_tree_pair(sections_a[i], sections_b[j]))
        elif tag == "replace":
            pairs = min(i2 - i1, j2 - j1)
            for k in range(pairs):
                results.extend(_diff_section_tree_pair(sections_a[i1 + k], sections_b[j1 + k]))
            for k in range(pairs, i2 - i1):
                results.extend(_collect_unpaired_sections(sections_a[i1 + k], "deleted"))
            for k in range(pairs, j2 - j1):
                results.extend(_collect_unpaired_sections(sections_b[j1 + k], "added"))
        elif tag == "delete":
            for i in range(i1, i2):
                results.extend(_collect_unpaired_sections(sections_a[i], "deleted"))
        elif tag == "insert":
            for j in range(j1, j2):
                results.extend(_collect_unpaired_sections(sections_b[j], "added"))

    return results


def _diff_section_tree_pair(sa, sb):
    """比对一对 section，并递归比对子 section。"""
    results = [_diff_section_pair(sa, sb)]
    results.extend(_align_and_diff_sections(sa.children, sb.children))
    return results


def _collect_unpaired_sections(section, diff_type: str):
    """收集新增/删除 section 根节点，避免与子节点重复高亮。"""
    from src.documents.structuring import SectionDiffResult

    if diff_type == "added":
        result = SectionDiffResult(
            section_a=None,
            section_b=section,
            diff_type="added",
            diff_ops=[[1, _strip_all_whitespace(_normalize_text(section.text_content)), 0, 0]],
        )
    else:
        result = SectionDiffResult(
            section_a=section,
            section_b=None,
            diff_type="deleted",
            diff_ops=[[-1, _strip_all_whitespace(_normalize_text(section.text_content)), 0, 0]],
        )

    return [result]


def _diff_section_pair(sa, sb):
    """比对两个配对的 SectionBlock。"""
    from src.documents.structuring import SectionDiffResult

    own_text_a = _section_own_text(sa)
    own_text_b = _section_own_text(sb)
    text_a = _strip_all_whitespace(_normalize_text(own_text_a))
    text_b = _strip_all_whitespace(_normalize_text(own_text_b))

    if text_a == text_b:
        return SectionDiffResult(section_a=sa, section_b=sb, diff_type="equal")

    if _is_content_identical(own_text_a, own_text_b):
        return SectionDiffResult(section_a=sa, section_b=sb, diff_type="equal")

    ops = compute_text_diff(own_text_a, own_text_b)

    if all(op == 0 for op, *_ in ops):
        return SectionDiffResult(section_a=sa, section_b=sb, diff_type="equal")

    return SectionDiffResult(section_a=sa, section_b=sb, diff_type="modified", diff_ops=ops)


async def _convert_pdf_async(docx_path, loop):
    """异步转换 DOCX → PDF，结果缓存到同目录。"""
    pdf_path = os.path.splitext(docx_path)[0] + ".pdf"
    if os.path.exists(pdf_path):
        return pdf_path
    return await loop.run_in_executor(None, docx_to_pdf, docx_path, os.path.dirname(docx_path))


def _compare_pdf_pages(pages_a: list[str], pages_b: list[str]) -> list[dict]:
    """直接比较两个 PDF 的逐页文本，返回 page diff 结果。
    不依赖 section 映射，直接按页序 1:1 对齐。
    """
    import json
    max_pages = max(len(pages_a), len(pages_b))
    results = []
    for i in range(max_pages):
        pa = i + 1 if i < len(pages_a) else None
        pb = i + 1 if i < len(pages_b) else None

        if pa is None:
            results.append({"page_a": None, "page_b": pb, "diff_type": "added", "diff_ops_json": None})
            continue
        if pb is None:
            results.append({"page_a": pa, "page_b": None, "diff_type": "deleted", "diff_ops_json": None})
            continue

        text_a = pages_a[i]
        text_b = pages_b[i]
        norm_a = _strip_all_whitespace(_normalize_text(text_a))
        norm_b = _strip_all_whitespace(_normalize_text(text_b))

        if norm_a == norm_b:
            results.append({"page_a": pa, "page_b": pb, "diff_type": "equal", "diff_ops_json": None})
            continue

        ops = compute_text_diff(text_a, text_b)
        if all(op == 0 for op, *_ in ops):
            results.append({"page_a": pa, "page_b": pb, "diff_type": "equal", "diff_ops_json": None})
        else:
            results.append({
                "page_a": pa, "page_b": pb, "diff_type": "modified",
                "diff_ops_json": json.dumps(ops, ensure_ascii=False),
            })
    return results


def _build_section_md(struct, diff_type_map, tag_key) -> str:
    """生成单个文档的 section 结构 Markdown。"""
    def _render_tree(sections, indent=0):
        lines = []
        for block in sections:
            prefix = "  " * indent
            dt = diff_type_map.get(id(block))
            tag = ""
            if dt == "modified":
                tag = " **[已修改]**"
            elif dt == "added":
                tag = " **[新增]**"
            elif dt == "deleted":
                tag = " **[已删除]**"

            if block.role.startswith("h"):
                level = int(block.role[1])
                lines.append(f"{prefix}- {'#' * level} {block.title}{tag}")
            elif block.role == "table":
                preview = block.text_content[:80].replace("\n", " ") if block.text_content else ""
                lines.append(f"{prefix}- [表格] {preview}...{tag}")
            elif block.role == "body":
                preview = block.text_content[:80].replace("\n", " ") if block.text_content else ""
                lines.append(f"{prefix}- [正文] {preview}{tag}")
            elif block.role == "toc_item":
                lines.append(f"{prefix}- [目录] {block.title}{tag}")
            else:
                lines.append(f"{prefix}- [{block.role}] {block.title}{tag}")

            if block.children:
                lines.extend(_render_tree(block.children, indent + 1))
        return lines

    return "\n".join(_render_tree(struct.main))


async def _save_sections(db, task_id, user_id, struct_a, struct_b, section_diffs):
    """将 section 结构信息持久化到 document_sections 表。"""
    import json
    from src.documents.models import DocumentSection

    # 构建两侧 section → (diff_type, diff_ops) 映射。
    # modified 的 ops 同时保存到 A/B，added 仅保存到 B，deleted 仅保存到 A。
    diff_type_map_a = {}
    diff_type_map_b = {}
    diff_ops_map_a = {}
    diff_ops_map_b = {}
    for sd in section_diffs:
        if sd.section_a is not None:
            diff_type_map_a[id(sd.section_a)] = sd.diff_type
            if sd.diff_ops:
                diff_ops_map_a[id(sd.section_a)] = json.dumps(sd.diff_ops, ensure_ascii=False)
        if sd.section_b is not None:
            diff_type_map_b[id(sd.section_b)] = sd.diff_type
            if sd.diff_ops:
                diff_ops_map_b[id(sd.section_b)] = json.dumps(sd.diff_ops, ensure_ascii=False)

    # 扁平化收集所有 section，两遍写入：第一遍写顶层（parent_id=None），第二遍写子层
    order = [0]
    block_to_row = {}

    def _collect(sections, doc_type, parent_block=None):
        for block in sections:
            order[0] += 1
            source_indices = json.dumps([l.source_index for l in block.content])
            row = DocumentSection(
                task_id=task_id,
                user_id=user_id,
                doc_type=doc_type,
                role=block.role,
                title=block.title,
                text_content=block.text_content,
                source_indices=source_indices,
                parent_id=None,
                order_index=order[0],
                diff_type=(diff_type_map_a if doc_type == 'a' else diff_type_map_b).get(id(block)),
                diff_ops_json=(diff_ops_map_a if doc_type == 'a' else diff_ops_map_b).get(id(block)),
            )
            db.add(row)
            block_to_row[id(block)] = (row, parent_block)
            if block.children:
                _collect(block.children, doc_type, block)

    _collect(struct_a.main, 'a')
    _collect(struct_b.main, 'b')
    await db.flush()

    # 第二遍：更新 parent_id
    for block_id, (row, parent_block) in block_to_row.items():
        if parent_block is not None and id(parent_block) in block_to_row:
            row.parent_id = block_to_row[id(parent_block)][0].id
    await db.flush()


def _build_virtual_page_map(input_lines: list) -> dict[int, list[int]]:
    """基于 InputLine 的 page_break 构建虚拟页面映射，不依赖 PDF。
    返回 {page_num: [source_index, ...]}，与 build_page_section_map 格式一致。
    """
    page_map: dict[int, list[int]] = {1: []}
    current_page = 1
    for line in input_lines:
        if line.has_page_break and page_map[current_page]:
            current_page += 1
            page_map[current_page] = []
        page_map[current_page].append(line.source_index)
    # 移除末尾空页
    while len(page_map) > 1 and not page_map[max(page_map)]:
        del page_map[max(page_map)]
    return page_map


async def _compare_docx_plan_b(task, db, loop, start_time):
    """DOCX 原生比对管线：python-docx 结构化提取 → section 级 diff。不依赖 PDF 转换。"""
    from src.documents.structuring import (
        extract_input_lines, build_structured_document, flatten_document,
    )

    # Step 1: python-docx 提取（并行）
    lines_a, lines_b = await asyncio.gather(
        loop.run_in_executor(None, extract_input_lines, task.file_a_path),
        loop.run_in_executor(None, extract_input_lines, task.file_b_path),
    )

    # Step 2: 构建结构化文档
    struct_a = await loop.run_in_executor(None, build_structured_document, lines_a)
    struct_b = await loop.run_in_executor(None, build_structured_document, lines_b)
    flatten_document(struct_a)
    flatten_document(struct_b)

    # Step 3: Section 级对齐 + diff
    section_diffs = _align_and_diff_sections(struct_a.main, struct_b.main)

    # Step 4: 持久化 section 数据（含 diff_ops_json）到 document_sections 表
    await _save_sections(db, task.id, task.user_id, struct_a, struct_b, section_diffs)

    # Step 5: 完成（不写 DocumentPageDiff，不转 PDF）
    task.comparison_mode = "docx_native"
    task.comparison_duration = round(time.time() - start_time, 2)
    diff_map_a = {id(sd.section_a): sd.diff_type for sd in section_diffs if sd.section_a}
    diff_map_b = {id(sd.section_b): sd.diff_type for sd in section_diffs if sd.section_b}
    task.section_summary_a = _build_section_md(struct_a, diff_map_a, "a")
    task.section_summary_b = _build_section_md(struct_b, diff_map_b, "b")
    task.status = "done"
    db.add(task)
    await db.commit()
