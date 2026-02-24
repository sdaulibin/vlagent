"""
询证函格式比对 - 核心服务

流程：
1. 上传询证函 PDF → 转图片
2. 通过关键词识别格式类型（格式一/格式二/验资）
3. AI 提取文档结构（每页的询证事项、表格字段）
4. 加载对应 JSON 模板，逐项比对
5. 返回差异列表
"""
import os
import re
import json
import tempfile
import shutil
from difflib import SequenceMatcher
from typing import Any

from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_stream
from src.config import MODEL_LOCAL
from src.json_repair import fix_json

# ========== 配置 ==========

TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "docs", "templates"
)

TEMPLATE_PDF_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "docs"
)

# 模板 PDF 文件名映射
TEMPLATE_PDFS = {
    "format_1": "格式一.pdf",
    "format_2": "格式二.pdf",
    "capital_verification": "验资.pdf",
}

# 模板中文名映射
TEMPLATE_NAMES = {
    "format_1": "格式一（银行询证函）",
    "format_2": "格式二（银行询证函）",
    "capital_verification": "验资询证函",
}

# 格式识别关键词
FORMAT_TYPE_KEYWORDS = {
    "format_1": ["银行询证函", "回函地址", "联系人", "邮编", "截至"],
    "format_2": ["银行询证函", "回函请寄", "收件人", "联系电话", "函证基准日", "以下由被询证银行填列"],
    "capital_verification": ["验资", "询证函", "出资", "缴款"],
}

# ========== AI 提示词 ==========

FORMAT_COMPARE_PROMPT = """
Role: 询证函格式分析专家

Task: 分析这份询证函图片，提取其中每个询证事项的结构信息。

## 提取规则：
1. 找出文档中所有编号的询证事项（如 1、2、3... 或附表等）
2. 对于每个事项，提取：
   - section: 事项编号（如 "1", "2", "3", "6(1)", "6(2)", "附表"）
   - title: 事项简短标题（如 "银行存款", "银行借款"）
   - description: 事项的完整描述文字（将具体日期、金额用xxx代替）
   - table_fields: 该事项下表格的所有列名（按从左到右顺序）

## 输出格式：
返回 JSON 数组：
[
  {
    "section": "1",
    "title": "银行存款",
    "description": "截至xxxx年xx月xx日止，本公司在贵行的存款情况如下",
    "table_fields": ["账户名称", "银行账号", "币种", "利率", "账户类型", "账户余额"]
  }
]

仅输出 JSON，不要解释。如果此页没有询证事项（如封面、签章页），返回空数组 []。
"""


# ========== 工具函数 ==========

# 模板 JSON 文件名映射
TEMPLATE_JSON_FILES = {
    "format_1": "format1_template.json",
    "format_2": "format2_template.json",
    "capital_verification": "capital_verification_template.json",
}


def _load_template(format_key: str) -> dict | None:
    """加载指定格式的 JSON 模板"""
    filename = TEMPLATE_JSON_FILES.get(format_key)
    if not filename:
        return None
    template_path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(template_path):
        return None
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _identify_format_type(text: str) -> str:
    """通过关键词计分识别文件所属格式"""
    # 1. 优先检查文档中是否有明确的格式标注
    if "格式二" in text or "（格式二）" in text:
        return "format_2"
    if "格式一" in text or "（格式一）" in text:
        return "format_1"

    # 2. 检查验资询证函
    capital_score = sum(1 for kw in FORMAT_TYPE_KEYWORDS["capital_verification"] if kw in text)
    if capital_score >= 2:
        return "capital_verification"

    # 3. 检查格式二独有标志（格式一没有这些内容）
    format2_exclusive = ["以下由被询证银行填列", "函证基准日", "回函请寄"]
    if any(kw in text for kw in format2_exclusive):
        return "format_2"

    # 4. 关键词计分（回退方案）
    best_format = "unknown"
    best_score = 0
    for fmt, keywords in FORMAT_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_format = fmt
    return best_format if best_score >= 2 else "unknown"


def _fuzzy_match(a: str, b: str) -> float:
    """计算两个字符串的相似度（0~1）"""
    clean = lambda s: re.sub(r"[\s，。、；：""''（）\[\]【】]", "", s)
    return SequenceMatcher(None, clean(a), clean(b)).ratio()


def _extract_plain_text(image_path: str) -> str:
    """提取图片中的纯文本"""
    prompt = "请提取这张询证函图片的全部文字，保持原文顺序。只输出纯文本，不要解释。"
    text = request_stream(
        question=prompt,
        file_base=image_path,
        model=MODEL_LOCAL,
        show_request=False,
    )
    return (text or "").strip()


def _extract_structure(image_path: str) -> list:
    """从单张图片提取文档结构"""
    try:
        response = request_stream(
            question=FORMAT_COMPARE_PROMPT,
            file_base=image_path,
            model=MODEL_LOCAL,
            show_request=False,
        ).strip()
        items = json.loads(fix_json(response))
        return items if isinstance(items, list) else []
    except Exception as e:
        print(f"[FormatCompare] 结构提取失败: {e}")
        return []


# ========== 比对引擎 ==========

def _compare_with_template(template: dict, doc_items: list) -> list:
    """将文档提取的事项与模板比对，返回差异列表"""
    mismatches = []
    template_items = template.get("items", [])

    # 建立文档事项索引（按 section）
    doc_index = {}
    for item in doc_items:
        section = item.get("section", "")
        if section:
            doc_index[section] = item

    for t_item in template_items:
        section = t_item.get("section", "")
        t_title = t_item.get("title", "")
        t_desc = t_item.get("description", "")
        t_fields = t_item.get("table_fields", [])

        d_item = doc_index.get(section)

        if not d_item:
            # 整个事项缺失
            mismatches.append({
                "section": section,
                "item": f"第{section}项 {t_title}",
                "location": "section",
                "expected": f"应包含第{section}项：{t_title}",
                "actual": "未找到该事项",
                "severity": "high",
            })
            continue

        # 比对描述文字（模糊匹配）
        d_desc = d_item.get("description", "")
        if t_desc and d_desc:
            similarity = _fuzzy_match(t_desc, d_desc)
            if similarity < 0.8:
                mismatches.append({
                    "section": section,
                    "item": f"第{section}项描述",
                    "location": "description",
                    "expected": t_desc,
                    "actual": d_desc,
                    "severity": "medium",
                })

        # 比对表格字段
        d_fields = d_item.get("table_fields", [])
        if t_fields:
            for t_field in t_fields:
                found = any(_fuzzy_match(t_field, df) >= 0.7 for df in d_fields)
                if not found:
                    mismatches.append({
                        "section": section,
                        "item": f"第{section}项表格字段",
                        "location": "table_field",
                        "expected": t_field,
                        "actual": f"缺少字段：{t_field}",
                        "severity": "high",
                    })

            for d_field in d_fields:
                found = any(_fuzzy_match(tf, d_field) >= 0.7 for tf in t_fields)
                if not found:
                    mismatches.append({
                        "section": section,
                        "item": f"第{section}项表格字段",
                        "location": "table_field",
                        "expected": "模板中无此字段",
                        "actual": f"多出字段：{d_field}",
                        "severity": "low",
                    })

    return mismatches


# ========== 主入口 ==========

def compare_with_template(pdf_path: str) -> dict:
    """
    格式比对主函数

    Args:
        pdf_path: 上传的询证函 PDF 文件路径

    Returns:
        dict: {format_type, passed, mismatches: [...]}
    """
    tmp_dir = tempfile.mkdtemp(prefix="format_compare_")

    try:
        # 1. PDF 转图片
        image_paths = split_pdf_to_images(pdf_path, tmp_dir, dpi=200)
        if not image_paths:
            raise ValueError("PDF 转换图片失败")

        # 2. 提取纯文本用于格式类型识别
        text_pages = [_extract_plain_text(img) for img in image_paths]
        merged_text = "\n".join(text_pages)

        # 3. 识别格式类型
        format_type = _identify_format_type(merged_text)
        if format_type == "unknown":
            return {
                "format_type": "unknown",
                "passed": False,
                "mismatches": [{
                    "section": "",
                    "item": "格式类型",
                    "location": "format",
                    "expected": "格式一/格式二/验资询证函",
                    "actual": "无法判定文件格式",
                    "severity": "high",
                }],
            }

        # 4. 加载模板
        template = _load_template(format_type)
        if not template:
            return {
                "format_type": format_type,
                "passed": False,
                "mismatches": [{
                    "section": "",
                    "item": "模板文件",
                    "location": "format",
                    "expected": f"{format_type}_template.json",
                    "actual": "模板文件不存在",
                    "severity": "high",
                }],
            }

        # 5. AI 提取文档结构
        all_items = []
        for img_path in image_paths:
            items = _extract_structure(img_path)
            all_items.extend(items)

        # 去重合并（相同 section 的合并 table_fields）
        merged_items = {}
        for item in all_items:
            section = item.get("section", "")
            if not section:
                continue
            if section not in merged_items:
                merged_items[section] = item
            else:
                existing = merged_items[section]
                for f in item.get("table_fields", []):
                    if f not in existing.get("table_fields", []):
                        existing.setdefault("table_fields", []).append(f)

        doc_items = list(merged_items.values())

        # 6. 比对
        mismatches = _compare_with_template(template, doc_items)

        return {
            "format_type": format_type,
            "passed": len(mismatches) == 0,
            "mismatches": mismatches,
        }

    finally:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)


def get_template_list() -> list:
    """获取所有可用模板信息"""
    templates = []
    for key, name in TEMPLATE_NAMES.items():
        pdf_file = TEMPLATE_PDFS.get(key, "")
        templates.append({
            "format_key": key,
            "format_name": name,
            "pdf_filename": pdf_file,
        })
    return templates


def get_template_pdf_path(format_key: str) -> str | None:
    """获取模板 PDF 的文件路径"""
    pdf_file = TEMPLATE_PDFS.get(format_key)
    if not pdf_file:
        return None
    path = os.path.join(TEMPLATE_PDF_DIR, pdf_file)
    return path if os.path.exists(path) else None
