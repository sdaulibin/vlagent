"""
信用金额对账 - 文档预览服务（改造版）。

提供两类能力：
- PDF 预览文件生成（soffice 转 PDF，前端用 iframe 预览）
- 结构化 HTML 预览数据生成（Word 段落 / Excel sheet 重建）

与旧 PreviewService 的差异：
- 源文件路径直接从任务记录（CreditCompareTask）的 word_dir/excel_dir 获取，
  不再扫描多个候选目录。
- 转换/预览目录接入宿主配置（CREDIT_CONVERTED_DIR / CREDIT_PREVIEW_DIR）。
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession

from src.config import CREDIT_CONVERTED_DIR, CREDIT_PREVIEW_DIR
from src.credit_comparison.models import CreditCompareTask
from src.credit_comparison.parsers.excel_parser import (
    extract_sheet_letter_prefix,
    load_excel_workbook,
    normalize_excel_sheet_name,
)
from src.credit_comparison.parsers.word_converter import (
    build_converted_batch_dir,
    convert_doc_to_docx,
)
from src.credit_comparison.parsers.word_parser import read_docx_paragraph_entries
from src.credit_comparison.core.regex_utils import extract_paraindex


def command_exists(command_name: str) -> bool:
    """判断外部命令是否存在。"""

    return shutil.which(command_name) is not None


def _read_excel_display_text(value: Any) -> str:
    """读取 Excel 单元格的前端展示文本。"""

    if value in ("", None):
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        if float(value).is_integer():
            return str(int(value))
        return str(value)
    return str(value).strip()


def _extract_word_sheet_code(text: str) -> str:
    """从 Word 段落中提取表单代码。"""

    match = re.search(r"([A-Z]\d{4})\s*表单", text)
    return match.group(1) if match else ""


def _build_sheet_merged_lookup(sheet_obj) -> dict[tuple[int, int], dict[str, Any]]:
    """构建工作表合并单元格信息。"""

    merged_lookup: dict[tuple[int, int], dict[str, Any]] = {}
    for row_low, row_high, col_low, col_high in getattr(sheet_obj, "merged_cells", []):
        rowspan = row_high - row_low
        colspan = col_high - col_low
        for row_index in range(row_low, row_high):
            for col_index in range(col_low, col_high):
                merged_lookup[(row_index, col_index)] = {
                    "is_anchor": row_index == row_low and col_index == col_low,
                    "rowspan": rowspan,
                    "colspan": colspan,
                }
    return merged_lookup


def _build_preview_key(file_name: str) -> str:
    """为预览文件构建稳定目录名。"""

    digest = hashlib.sha1(file_name.encode("utf-8")).hexdigest()[:12]
    return f"{digest}_{file_name}"


async def _find_source_file(
    db: AsyncSession, batch_id: str, file_type: str, file_name: str
) -> Path:
    """从任务记录中获取源文件路径。

    file_type: "word" 或 "excel"，对应任务的 word_dir/excel_dir。
    """

    stmt = select(CreditCompareTask).where(CreditCompareTask.batch_id == batch_id)
    task = (await db.execute(stmt)).scalars().first()
    if task is None:
        raise FileNotFoundError(f"未找到任务: {batch_id}")
    search_dir = task.word_dir if file_type == "word" else task.excel_dir
    candidate = Path(search_dir) / file_name
    if candidate.exists():
        return candidate
    # 兜底：扫描目录下所有 word/excel 文件。
    suffixes = {".doc", ".docx"} if file_type == "word" else {".xls", ".xlsx"}
    root = Path(search_dir)
    if root.exists():
        for path in root.rglob("*"):
            if path.name == file_name and path.suffix.lower() in suffixes:
                return path
    raise FileNotFoundError(f"未找到源文件: {file_name}")


def _resolve_word_preview_source(source_path: Path, batch_id: str = "") -> Path:
    """为 Word 预览选择更稳定的转换源文件（.doc 优先复用解析阶段的 .docx）。"""

    if source_path.suffix.lower() != ".doc":
        return source_path
    converted_docx_path = build_converted_batch_dir(CREDIT_CONVERTED_DIR, batch_id) / f"{source_path.stem}.docx"
    if converted_docx_path.exists():
        return converted_docx_path
    legacy_converted_docx_path = Path(CREDIT_CONVERTED_DIR) / f"{source_path.stem}.docx"
    if legacy_converted_docx_path.exists():
        return legacy_converted_docx_path
    return source_path


def _convert_with_soffice(source_path: Path, output_dir: Path, target_format: str) -> None:
    """使用 LibreOffice 将文档转换为浏览器可预览文件。"""

    if not command_exists("soffice"):
        raise RuntimeError("当前环境缺少 soffice，无法生成文档预览")

    profile_dir = Path(CREDIT_PREVIEW_DIR) / "_lo_profiles" / uuid4().hex
    profile_dir.mkdir(parents=True, exist_ok=True)
    user_installation = profile_dir.resolve().as_uri()

    try:
        result = subprocess.run(
            [
                "soffice",
                "--headless",
                f"-env:UserInstallation={user_installation}",
                "--convert-to",
                target_format,
                str(source_path),
                "--outdir",
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "soffice 转换失败"
            raise RuntimeError(message)
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)


def _ensure_pdf_preview(
    source_path: Path, file_type: str, preview_name: str, preview_cache_key: str | None = None
) -> Path:
    """确保 PDF 预览文件存在且为最新版本。"""

    preview_root = Path(CREDIT_PREVIEW_DIR)
    preview_dir = preview_root / file_type / _build_preview_key(preview_cache_key or preview_name)
    preview_dir.mkdir(parents=True, exist_ok=True)
    target_path = preview_dir / f"{Path(preview_name).stem}.pdf"

    if target_path.exists() and target_path.stat().st_mtime >= source_path.stat().st_mtime:
        return target_path

    _convert_with_soffice(source_path, preview_dir, "pdf")
    if not target_path.exists():
        raise RuntimeError(f"预览转换失败: {preview_name}")
    return target_path


async def get_word_preview_path(db: AsyncSession, file_name: str, batch_id: str) -> Path:
    """返回 Word 文件对应的 PDF 预览路径。"""

    source_path = await _find_source_file(db, batch_id, "word", file_name)
    source_path = _resolve_word_preview_source(source_path, batch_id)
    cache_key = f"{batch_id}::{file_name}"
    return _ensure_pdf_preview(source_path, "word", file_name, preview_cache_key=cache_key)


async def get_excel_preview_path(db: AsyncSession, file_name: str, batch_id: str) -> Path:
    """返回 Excel 文件对应的 PDF 预览路径。"""

    source_path = await _find_source_file(db, batch_id, "excel", file_name)
    cache_key = f"{batch_id}::{file_name}"
    return _ensure_pdf_preview(source_path, "excel", file_name, preview_cache_key=cache_key)


async def get_word_preview_data(db: AsyncSession, file_name: str, batch_id: str) -> dict[str, Any]:
    """返回 Word 结构化段落预览数据。"""

    source_path = await _find_source_file(db, batch_id, "word", file_name)
    docx_path = _resolve_word_preview_source(source_path, batch_id)
    if docx_path.suffix.lower() == ".doc":
        docx_path = Path(convert_doc_to_docx(str(docx_path), CREDIT_CONVERTED_DIR, batch_id=batch_id))
    entries = read_docx_paragraph_entries(str(docx_path))
    paragraphs: list[dict[str, Any]] = []
    current_sheet = ""
    for index, entry in enumerate(entries, start=1):
        text = str(entry.get("resolved_text") or "").strip()
        if not text:
            continue
        paragraph_index = int(entry.get("paragraph_index") or index)
        source_ref = str(entry.get("source_ref") or "")
        node_id = f"word-paragraph-{paragraph_index}"
        if "." in source_ref:
            node_id = f"{node_id}-{source_ref.rsplit('.', 1)[-1]}"
        sheet_code = _extract_word_sheet_code(text)
        if sheet_code:
            current_sheet = sheet_code
        paragraphs.append(
            {
                "node_id": node_id,
                "paragraph_index": paragraph_index,
                "paraindex": extract_paraindex(text),
                "sheet": current_sheet,
                "is_sheet_title": bool(sheet_code),
                "text": text,
                "raw_text": str(entry.get("raw_text") or ""),
            }
        )
    return {"file_name": file_name, "paragraphs": paragraphs}


async def get_excel_preview_data(db: AsyncSession, file_name: str, batch_id: str) -> dict[str, Any]:
    """返回 Excel 的 sheet 风格预览数据。"""

    source_path = await _find_source_file(db, batch_id, "excel", file_name)
    workbook = load_excel_workbook(str(source_path))
    raw_sheet_names = workbook.sheet_names()
    default_sheet_prefix = extract_sheet_letter_prefix(raw_sheet_names[0]) if raw_sheet_names else ""
    sheets: list[dict[str, Any]] = []
    for raw_sheet_name in raw_sheet_names:
        normalized_sheet_name = normalize_excel_sheet_name(raw_sheet_name, default_sheet_prefix)
        sheet_obj = workbook.sheet_by_name(raw_sheet_name)
        merged_lookup = _build_sheet_merged_lookup(sheet_obj)
        rows: list[dict[str, Any]] = []
        for row_index in range(sheet_obj.nrows):
            row_cells: list[dict[str, Any]] = []
            for col_index in range(sheet_obj.ncols):
                merged_meta = merged_lookup.get((row_index, col_index))
                if merged_meta and not merged_meta["is_anchor"]:
                    continue
                cell_text = _read_excel_display_text(sheet_obj.cell_value(row_index, col_index))
                cell_info = {
                    "col_index": col_index + 1,
                    "text": cell_text,
                    "rowspan": 1,
                    "colspan": 1,
                }
                if merged_meta and merged_meta["is_anchor"]:
                    cell_info["rowspan"] = merged_meta["rowspan"]
                    cell_info["colspan"] = merged_meta["colspan"]
                row_cells.append(cell_info)
            rows.append({"row_index": row_index + 1, "cells": row_cells})
        sheets.append(
            {
                "raw_name": raw_sheet_name,
                "name": normalized_sheet_name,
                "row_count": sheet_obj.nrows,
                "col_count": sheet_obj.ncols,
                "rows": rows,
            }
        )
    return {"file_name": file_name, "sheets": sheets}
