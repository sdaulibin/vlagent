"""
询证函识别服务

独立的识别处理流程，复用底层 PDF 工具和 AI 请求接口。
"""
import os
import json
import shutil
import tempfile
import re
from datetime import datetime
from typing import Any

from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_stream
from src.config import MODEL_LOCAL
from src.json_repair import fix_json


# 字段提取提示词
FIELD_EXTRACTION_PROMPT = """
Role: 银行询证函信息提取专家

Task: 从银行询证函扫描图片中精确提取以下 13 项字段信息。请仔细阅读整个文档，不要遗漏任何字段。

## 待提取字段及识别规则：

1. **confirmation_no (函证编号)**
   - 这是最重要的字段，请务必仔细查找
   - 常见位置：标题「银行询证函」附近（上方、下方、右侧），或页面右上角
   - 常见格式：「编号：xxx」「函证编号：xxx」「NO.xxx」「索引号：xxx」
   - 编号通常是字母+数字组合，如 hdsy-yh-008、XZ-2024-001 等
   - 关键字优先级：函证编号 > 询证函编号 > 编号 > NO. > 索引号
   - 注意：不包含页码后缀

2. **accounting_firm (事务所名称)** - 关键字：「本公司聘请的」「会计师事务所」，提取事务所全称（含"特殊普通合伙"及分所名称）
3. **reply_address (回函地址)** - 关键字：回函地址、收件地址、回函请寄、回函邮寄地址，提取完整地址
4. **contact_person (联系人)** - 关键字：联系人、收件人、回函快递收件人
5. **phone (电话)** - 关键字：电话、联系电话、收件手机号、收件电话
6. **postal_code (邮编)** - 6位数字格式
7. **debit_account (扣费账号)** - 银行账号格式
8. **cutoff_date (截止日期)** - 「截至xxxx年xx月xx日」或「函证基准日」对应的日期
9. **start_date (起始日期)** - 区间起始日期
10. **end_date (终止日期)** - 区间终止日期
11. **seal_date (印章日期)** - 印章中的日期
12. **seal_name (印章名称)** - 印章中的单位名称
13. **signature_name (落款名称)** - 落款处单位名称（如果没有则返回空字符串）

## 输出要求：
- 返回 JSON 格式
- 无法识别的字段返回空字符串 ""
- 日期格式统一为 YYYY-MM-DD
- 仅输出 JSON，无需解释

## JSON Schema:
{
    "confirmation_no": "",
    "accounting_firm": "",
    "reply_address": "",
    "contact_person": "",
    "phone": "",
    "postal_code": "",
    "debit_account": "",
    "cutoff_date": "",
    "start_date": "",
    "end_date": "",
    "seal_date": "",
    "seal_name": "",
    "signature_name": ""
}
"""

# 所有识别字段
ALL_FIELDS = [
    "confirmation_no", "accounting_firm", "reply_address",
    "contact_person", "phone", "postal_code", "debit_account",
    "cutoff_date", "start_date", "end_date", "seal_date", "seal_name",
    "signature_name"
]

# 编号抓取优先级：函证编号 > 询证函编号 > 编号 > NO. > 索引号 > 项目编号
CONFIRMATION_NO_PATTERNS = [
    r"函证编号\s*[:：]?\s*([A-Za-z0-9\-_/]+)",
    r"询证函编号\s*[:：]?\s*([A-Za-z0-9\-_/]+)",
    r"\b编号\s*[:：]?\s*([A-Za-z0-9\-_/]+)",
    r"\bNO\.?\s*[:：]?\s*([A-Za-z0-9\-_/]+)",
    r"索引号\s*[:：]?\s*([A-Za-z0-9\-_/]+)",
    r"项目编号\s*[:：]?\s*([A-Za-z0-9\-_/]+)",
]

FORMAT_TEMPLATES = {
    "format_1": ["银行询证函", "回函地址", "联系人", "电话", "邮编", "截至"],
    "format_2": ["银行询证函", "回函请寄", "收件人", "联系电话", "函证基准日"],
    "capital_verification": ["验资", "询证函", "出资", "截止日期"],
}


def _extract_plain_text(image_path: str) -> str:
    prompt = """
请提取这张询证函图片的全部文字，保持原文顺序。
只输出纯文本，不要解释。
"""
    text = request_stream(
        question=prompt,
        file_base=image_path,
        model=MODEL_LOCAL,
        show_request=False,
    )
    return (text or "").strip()


def _clean_id_value(value: str) -> str:
    if not value:
        return ""
    cleaned = value.strip().strip("：:.。")
    # 去除页码后缀，如 2024-001/1 或 2024-001 第1页
    cleaned = re.sub(r"[/\\]\d+$", "", cleaned)
    cleaned = re.sub(r"\s*第?\d+\s*页$", "", cleaned)
    cleaned = re.sub(r"^NO\.?\s*[:：]?", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _parse_confirmation_no(text: str, ai_value: str = "") -> str:
    raw = text or ""
    for pattern in CONFIRMATION_NO_PATTERNS:
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if match:
            return _clean_id_value(match.group(1))

    barcode_match = re.search(r"条形码.{0,20}?([A-Za-z0-9\-]{6,})", raw)
    if barcode_match:
        return _clean_id_value(barcode_match.group(1))

    return _clean_id_value(ai_value)


def _normalize_date(value: str) -> str:
    if not value:
        return ""

    value = value.strip()
    patterns = [
        r"(\d{4})[年/\-.](\d{1,2})[月/\-.](\d{1,2})日?",
        r"(\d{4})(\d{2})(\d{2})",
    ]
    for pattern in patterns:
        m = re.search(pattern, value)
        if not m:
            continue
        y, mm, dd = m.groups()
        try:
            dt = datetime(int(y), int(mm), int(dd))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return ""
    return ""


def _normalize_phone(value: str) -> str:
    if not value:
        return ""
    compact = re.sub(r"\s+", "", value)
    mobile = re.search(r"1[3-9]\d{9}", compact)
    if mobile:
        return mobile.group(0)

    landline = re.search(r"(0\d{2,3}-?\d{7,8})", compact)
    if landline:
        return landline.group(1)
    return ""


def _normalize_postal_code(value: str) -> str:
    if not value:
        return ""
    m = re.search(r"\b(\d{6})\b", value)
    return m.group(1) if m else ""


def _normalize_account(value: str) -> str:
    if not value:
        return ""
    compact = re.sub(r"[^\d]", "", value)
    if 10 <= len(compact) <= 30:
        return compact
    return ""


def _extract_signature_name(text: str, ai_value: str = "") -> str:
    patterns = [
        r"(?:落款|单位名称|公司名称)\s*[:：]?\s*([^\n，。]{2,60})",
        r"(?:盖章单位|印章名称)\s*[:：]?\s*([^\n，。]{2,60})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if match:
            return match.group(1).strip()
    return (ai_value or "").strip()


def _validate_and_normalize_fields(data: dict[str, Any], text: str) -> dict[str, Any]:
    normalized = {field: (data.get(field, "") or "").strip() for field in ALL_FIELDS}
    normalized["confirmation_no"] = _parse_confirmation_no(text, normalized.get("confirmation_no", ""))
    normalized["phone"] = _normalize_phone(normalized.get("phone", ""))
    normalized["postal_code"] = _normalize_postal_code(normalized.get("postal_code", ""))
    normalized["debit_account"] = _normalize_account(normalized.get("debit_account", ""))
    normalized["cutoff_date"] = _normalize_date(normalized.get("cutoff_date", ""))
    normalized["start_date"] = _normalize_date(normalized.get("start_date", ""))
    normalized["end_date"] = _normalize_date(normalized.get("end_date", ""))
    normalized["seal_date"] = _normalize_date(normalized.get("seal_date", ""))
    normalized["signature_name"] = _extract_signature_name(text, normalized.get("signature_name", ""))
    return normalized


def _check_format(text: str) -> dict[str, Any]:
    source = text or ""
    best_format = "unknown"
    best_score = -1
    best_keywords: list[str] = []

    for format_name, keywords in FORMAT_TEMPLATES.items():
        score = sum(1 for kw in keywords if kw in source)
        if score > best_score:
            best_score = score
            best_format = format_name
            best_keywords = keywords

    mismatches = []
    if best_format != "unknown":
        for kw in best_keywords:
            if kw not in source:
                mismatches.append(
                    {
                        "item": kw,
                        "expected": f"应包含关键字: {kw}",
                        "actual": "未识别到",
                        "severity": "high",
                    }
                )

    if best_score <= 0:
        best_format = "unknown"
        mismatches.append(
            {
                "item": "template",
                "expected": "格式一/格式二/验资询证函",
                "actual": "无法判定",
                "severity": "high",
            }
        )

    return {
        "format_type": best_format,
        "format_check_passed": len(mismatches) == 0 and best_format != "unknown",
        "format_mismatches": mismatches,
    }


def extract_fields_from_image(image_path: str) -> dict:
    """
    从询证函图片中提取字段信息
    
    Args:
        image_path: 图片文件路径
        
    Returns:
        dict: 提取的字段信息
    """
    response = request_stream(
        question=FIELD_EXTRACTION_PROMPT,
        file_base=image_path,
        model=MODEL_LOCAL,
        show_request=False
    ).strip()
    
    try:
        data = json.loads(fix_json(response))
        return data
    except Exception as e:
        print(f"JSON 解析失败: {e}, 原始响应: {response[:200]}")
        return {}


def process_confirmation_letter(pdf_path: str, output_dir: str = None) -> dict:
    """
    处理询证函 PDF 文件
    
    与测试脚本保持一致：使用 split_pdf_to_images 直接获取图片路径列表，
    处理完成后自动清理临时文件。
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录（可选）
        
    Returns:
        dict: 识别结果
    """
    # 使用临时目录存放图片，处理完自动清理
    tmp_dir = tempfile.mkdtemp(prefix="confirmation_")
    
    try:
        # 1. PDF 转图片（使用 split_pdf_to_images，与测试脚本一致）
        image_paths = split_pdf_to_images(pdf_path, tmp_dir, dpi=200)
        
        if not image_paths:
            raise ValueError("PDF 转换图片失败，未生成任何图片")
        
        # 2. 识别第一页
        first_page = image_paths[0]
        result = extract_fields_from_image(first_page)
        text_pages = [_extract_plain_text(first_page)]

        # 3. 如果有多页，合并结果（多页询证函场景）
        if len(image_paths) > 1:
            pages_results = [result]
            for page_path in image_paths[1:]:
                page_result = extract_fields_from_image(page_path)
                pages_results.append(page_result)
                text_pages.append(_extract_plain_text(page_path))
            result = merge_recognition_results(pages_results)

        merged_text = "\n".join(text_pages)
        normalized = _validate_and_normalize_fields(result, merged_text)
        normalized.update(_check_format(merged_text))
        return normalized
    
    finally:
        # 4. 清理临时文件
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


def merge_recognition_results(pages_results: list) -> dict:
    """
    合并多页识别结果（如果询证函有多页）
    
    Args:
        pages_results: 各页识别结果列表
        
    Returns:
        dict: 合并后的结果，优先取非空值
    """
    if not pages_results:
        return {}
    
    if len(pages_results) == 1:
        return pages_results[0]
    
    # 多页时，优先取非空值
    merged = {}
    for field in ALL_FIELDS:
        for page_result in pages_results:
            value = page_result.get(field, "")
            if value:
                merged[field] = value
                break
        if field not in merged:
            merged[field] = ""
    
    return merged
