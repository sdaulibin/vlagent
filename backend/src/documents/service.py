"""
文档比对核心服务

流程：纯文本提取（pdfplumber） → 页级对齐 → 逐页 diff → 结果入库
"""
import json
import re
import time
import logging
import unicodedata

import pdfplumber
import mammoth
from difflib import SequenceMatcher
from diff_match_patch import diff_match_patch
from sqlmodel.ext.asyncio.session import AsyncSession

from src.documents.models import DocumentCompareTask, DocumentPageDiff

logger = logging.getLogger(__name__)

dmp = diff_match_patch()


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


def _html_to_text(html: str) -> str:
    """从 mammoth HTML 中提取纯文本"""
    text = re.sub(r'<br\s*/?>', '\n', html)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ---- PDF 提取（pdfplumber）----

def extract_pages_from_pdf(file_path: str) -> list[str]:
    """用 pdfplumber 提取 PDF 每页纯文本"""
    text_pages = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            text_pages.append(text)
    return text_pages


# ---- DOCX 提取（mammoth）----

def extract_pages_from_docx(file_path: str) -> tuple[list[str], list[str]]:
    """用 mammoth 将 DOCX 转为纯文本和 HTML，整体视为单页。
    返回 (text_pages, html_pages)
    """
    with open(file_path, "rb") as f:
        result = mammoth.convert_to_html(f)
    html = result.value
    text = _html_to_text(html)
    return [text], [html]


def extract_pages(file_path: str) -> tuple[list[str], list[str]]:
    """根据文件类型分发提取，返回 (text_pages, html_pages)
    PDF: text_pages 有内容，html_pages 为空（前端用 PDF.js 渲染）
    DOCX: text_pages 和 html_pages 都有内容
    """
    lower = file_path.lower()
    if lower.endswith(".pdf"):
        return extract_pages_from_pdf(file_path), []
    elif lower.endswith((".docx", ".doc")):
        return extract_pages_from_docx(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {file_path}")


# ---- 页级对齐 ----

def _page_signature(text: str, max_chars: int = 200) -> str:
    normalized = _normalize_text(text)
    stripped = normalized.replace("\n", " ").replace(" ", "")
    return stripped[:max_chars]


def align_pages(pages_a: list[str], pages_b: list[str]) -> list[tuple]:
    """页级对齐：使用归一化文本比较，返回 [(page_a_index, page_b_index, diff_type), ...]"""
    if not pages_a and not pages_b:
        return []

    norm_a = [_normalize_text(p) for p in pages_a]
    norm_b = [_normalize_text(p) for p in pages_b]
    # 去空白版本，用于判断内容是否真正相同
    stripped_a = [_strip_all_whitespace(n) for n in norm_a]
    stripped_b = [_strip_all_whitespace(n) for n in norm_b]

    if len(norm_a) == 1 and len(norm_b) == 1:
        diff_type = "equal" if stripped_a[0] == stripped_b[0] else "modified"
        return [(0, 0, diff_type)]

    sigs_a = [_page_signature(p) for p in pages_a]
    sigs_b = [_page_signature(p) for p in pages_b]

    matcher = SequenceMatcher(None, sigs_a, sigs_b)
    aligned = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                diff_type = "equal" if stripped_a[i] == stripped_b[j] else "modified"
                aligned.append((i, j, diff_type))
        elif tag == "replace":
            pairs = min(i2 - i1, j2 - j1)
            for k in range(pairs):
                aligned.append((i1 + k, j1 + k, "modified"))
            for k in range(pairs, i2 - i1):
                aligned.append((i1 + k, None, "deleted"))
            for k in range(pairs, j2 - j1):
                aligned.append((None, j1 + k, "added"))
        elif tag == "delete":
            for i in range(i1, i2):
                aligned.append((i, None, "deleted"))
        elif tag == "insert":
            for j in range(j1, j2):
                aligned.append((None, j, "added"))

    return aligned


# ---- 文本 diff ----

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
    dmp.diff_cleanupSemantic(diffs)

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


# ---- 异步后台任务 ----

async def process_document_comparison(db: AsyncSession, task: DocumentCompareTask):
    """异步后台任务：提取 → 对齐 → diff → 写库"""
    start_time = time.time()

    try:
        task.status = "processing"
        db.add(task)
        await db.commit()

        # 1. 提取纯文本和 HTML
        text_a_pages, html_a_pages = extract_pages(task.file_a_path)
        text_b_pages, html_b_pages = extract_pages(task.file_b_path)

        task.file_a_page_count = len(text_a_pages)
        task.file_b_page_count = len(text_b_pages)

        # 2. 页级对齐（基于纯文本）
        aligned = align_pages(text_a_pages, text_b_pages)

        # 3. 逐页计算 diff 并写入
        for page_a_idx, page_b_idx, diff_type in aligned:
            text_a = text_a_pages[page_a_idx] if page_a_idx is not None else None
            text_b = text_b_pages[page_b_idx] if page_b_idx is not None else None

            html_a = html_a_pages[page_a_idx] if page_a_idx is not None and html_a_pages else None
            html_b = html_b_pages[page_b_idx] if page_b_idx is not None and html_b_pages else None

            diff_ops = None
            if diff_type == "modified" and text_a is not None and text_b is not None:
                ops = compute_text_diff(text_a, text_b)
                # 如果 diff 结果全是 op=0（相同），说明内容实际一致，升级为 equal
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
                html_a=html_a,
                html_b=html_b,
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
