"""
询证函格式比对 - 核心服务

流程：
1. 上传询证函 PDF → 转图片
2. AI 一次性提取：格式类型识别 + 按模板结构输出内容
3. 加载对应 JSON 模板，逐项比对 section 和 table_headers
4. 返回差异列表

三阶段日志输出：
- 阶段一：类型识别结果
- 阶段二：提取的 JSON 格式数据
- 阶段三：比对结果
"""
import os
import json
import tempfile
import shutil
import re
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

# 模板 JSON 文件名映射（新版模板）
TEMPLATE_JSON_FILES = {
    "format_1": "template1.json",
    "format_2": "template2.json",
    "capital_verification": "template3.json",
}

# 格式中文标签
FORMAT_LABELS = {
    "format_1": "格式一",
    "format_2": "格式二",
    "capital_verification": "验资",
    "unknown": "未知",
}


# ========== AI 提示词 ==========

FORMAT_EXTRACT_PROMPT = """
Role: 询证函格式分析专家

Task: 分析这份银行询证函图片，完成以下两项任务：

## 任务一：识别格式类型
根据文档内容判断属于以下哪种格式：
- "format_1": 格式一银行询证函（特征："回函地址"、"联系人"、部分表格下方有补充描述文字等）
- "format_2": 格式二银行询证函（特征："回函请寄"、"收件人"、"函证基准日"；通常在银行存款表格上方有“以下由被询证银行填列”字样；并且表格下方**没有**补充描述文字）
- "capital_verification": 验资业务银行询证函（包含"验资"、"出资者缴入投资资金"等字段）

## 任务二：提取文档结构
找出文档中所有编号的询证事项（如 1、2、3... 或附表等），提取每个事项的：
- section: 完整的节次标题（如 "1. 银行存款"、"附表 资金归集..."、"出资者缴入投资资金明细表"）
- table_headers: 该事项下表格的所有列名（按从左到右顺序）。注意：如果是多级表头（例如“款项来源细分”下有“境内”和“境外”），请使用嵌套字典，如 {"款项来源细分": ["境内", "境外"]}
- description: 提取表格下方的补充描述文字（如果没有则为空或不输出）
- subsections: 如果某节有子节（如"担保"下的(1)(2)），用 subsections 数组包含，每个子节对应包含 subsection 标题、table_headers 和 description

## 输出 JSON 格式示例（务必严格遵循此结构）：
{
    "format_type": "format_1",
    "highlighted_content": [
        {
            "section": "1. 银行存款",
            "table_headers": ["账户名称", "银行账号", "币种"],
            "description": "除上述列示的银行存款外..."
        },
        {
            "section": "6. 担保",
            "subsections": [
                {
                    "subsection": "（1）本公司为其他单位提供的、以贵行作为受益人的担保",
                    "table_headers": ["被担保人", "担保方式"],
                    "description": "除上述列示的担保外..."
                }
            ]
        },
        {
            "section": "出资者缴入投资资金明细表",
            "table_headers": [
                "缴款人",
                {
                    "款项来源细分": ["境内", "境外"]
                }
            ]
        }
    ]
}

【重要】函件可能有多页图片，请综合所有图片内容提取，不要遗漏。
仅输出 JSON，不要解释。
"""


# ========== 模板加载 ==========

_templates_cache: dict[str, dict] = {}


def _load_template(format_key: str) -> dict | None:
    """加载指定格式的 JSON 模板"""
    filename = TEMPLATE_JSON_FILES.get(format_key)
    if not filename:
        return None
    template_path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(template_path):
        print(f"⚠️ 模板文件不存在: {template_path}")
        return None
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_all_templates() -> dict[str, dict]:
    """加载所有模板文件，带缓存"""
    global _templates_cache
    if _templates_cache:
        return _templates_cache
    for fmt_key in TEMPLATE_JSON_FILES:
        tpl = _load_template(fmt_key)
        if tpl:
            _templates_cache[fmt_key] = tpl
    return _templates_cache


# ========== 工具函数 ==========

def _normalize_section_name(name: str) -> str:
    """
    标准化 section 名称用于比较：
    - 去除编号前缀（如 "3. "）
    - 将实际日期替换为占位符 "xxxx年x月x日"，使不同日期值可以匹配
    - 去除多余空格
    """
    s = re.sub(r"^\d+\.\s*", "", name.strip())
    # 将实际日期（如 2024年01月01日）替换为占位符 xxxx年x月x日
    s = re.sub(r"\d{4}年\d{1,2}月\d{1,2}日", "xxxx年x月x日", s)
    s = re.sub(r"\s+", "", s)
    return s


def _normalize_text(text: str) -> str:
    """标准化普通文本（特别是表头）：去空格、换行，全角转半角标点"""
    s = str(text)
    s = re.sub(r"\s+", "", s)
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("，", ",").replace("。", ".")
    s = s.replace("：", ":").replace("；", ";")
    return s


def _collect_headers(item: dict) -> list[str]:
    """从一个 section 项收集所有 table_headers（包括 subsections）"""
    headers: list[str] = []
    if "table_headers" in item:
        for h in item["table_headers"]:
            if isinstance(h, str):
                # 去除 #[] 标记（模板中的可选标记）
                headers.append(h.replace("#[", "").replace("]", ""))
            elif isinstance(h, dict):
                for k in h:
                    headers.append(k)
    if "subsections" in item:
        for sub in item["subsections"]:
            for h in sub.get("table_headers", []):
                if isinstance(h, str):
                    headers.append(h)
    return headers


# ========== AI 内容提取 ==========

def _extract_content_from_images(image_paths: list[str]) -> dict:
    """
    从询证函图片中提取格式类型和结构化内容（一次 AI 调用）
    
    Returns:
        dict: {"format_type": "...", "highlighted_content": [...]}
    """
    if len(image_paths) == 1:
        response = request_stream(
            question=FORMAT_EXTRACT_PROMPT,
            file_base=image_paths[0],
            model=MODEL_LOCAL,
            show_request=False,
        ).strip()
    else:
        response = request_stream(
            question=FORMAT_EXTRACT_PROMPT,
            file_ary=image_paths,
            model=MODEL_LOCAL,
            show_request=False,
            pic_tip=True,
        ).strip()

    try:
        data = json.loads(fix_json(response))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[FormatCompare] JSON 解析失败: {e}, 原始响应: {response[:300]}")
        return {}


# ========== 比对引擎 ==========

def _compare_with_template(
    format_type: str, actual_content: list[dict],
) -> list[dict]:
    """将 AI 提取的结构化内容与模板逐项比对，返回差异列表"""
    template = _load_template(format_type)
    if not template:
        return [{
            "section": "",
            "item": "模板文件",
            "location": "format",
            "expected": f"{TEMPLATE_JSON_FILES.get(format_type, '?')}",
            "actual": "模板文件不存在",
            "severity": "high",
        }]

    expected_sections = template.get("highlighted_content", [])
    mismatches: list[dict] = []

    # 1. 节次数量比对
    if len(actual_content) != len(expected_sections):
        mismatches.append({
            "section": "",
            "item": "节次数量",
            "location": "section",
            "expected": f"{len(expected_sections)} 个节次",
            "actual": f"{len(actual_content)} 个节次",
            "severity": "medium",
        })

    # 2. 逐节比对
    max_len = max(len(expected_sections), len(actual_content)) if expected_sections or actual_content else 0
    for i in range(max_len):
        exp = expected_sections[i] if i < len(expected_sections) else None
        act = actual_content[i] if i < len(actual_content) else None

        if exp and not act:
            mismatches.append({
                "section": exp.get("section", ""),
                "item": f"节次 [{exp.get('section', '')}]",
                "location": "section",
                "expected": "应存在",
                "actual": "缺失",
                "severity": "high",
            })
            continue
        if act and not exp:
            mismatches.append({
                "section": act.get("section", ""),
                "item": f"节次 [{act.get('section', '')}]",
                "location": "section",
                "expected": "不应存在",
                "actual": "多余节次",
                "severity": "medium",
            })
            continue

        # 比较 section 名称（完全比对，但日期部分只需满足格式）
        exp_name = _normalize_section_name(exp.get("section", ""))
        act_name = _normalize_section_name(act.get("section", ""))
        if exp_name != act_name:
            mismatches.append({
                "section": exp.get("section", ""),
                "item": "节次名称",
                "location": "section",
                "expected": exp.get("section", ""),
                "actual": act.get("section", ""),
                "severity": "high",
            })

        # 比较 table_headers
        exp_headers = _collect_headers(exp)
        act_headers = _collect_headers(act)

        if exp_headers or act_headers:
            section_label = exp.get("section", act.get("section", ""))
            
            # 使用 normalize_text 对表头进行标准化（忽略空格换行和全半角括号差异）
            norm_exp_headers = [_normalize_text(h) for h in exp_headers]
            norm_act_headers = [_normalize_text(h) for h in act_headers]
            
            # 缺少的表头
            for orig_eh, norm_eh in zip(exp_headers, norm_exp_headers):
                if norm_eh not in norm_act_headers:
                    mismatches.append({
                        "section": section_label,
                        "item": f"{section_label} - 表头",
                        "location": "table_field",
                        "expected": orig_eh,
                        "actual": "缺失",
                        "severity": "high",
                    })
            
            # 多余的表头
            for orig_ah, norm_ah in zip(act_headers, norm_act_headers):
                if norm_ah not in norm_exp_headers:
                    mismatches.append({
                        "section": section_label,
                        "item": f"{section_label} - 表头",
                        "location": "table_field",
                        "expected": "模板中无此字段",
                        "actual": orig_ah,
                        "severity": "low",
                    })

    return mismatches


# ========== 主入口 ==========

def compare_with_template(pdf_path: str) -> dict:
    """
    格式比对主函数

    流程：PDF → 转图片 → AI 一次性提取(类型+结构) → 模板比对
    三阶段日志输出：类型识别 → 提取的 JSON → 比对结果

    Args:
        pdf_path: 上传的询证函 PDF 文件路径

    Returns:
        dict: {format_type, passed, mismatches: [...]}
    """
    tmp_dir = tempfile.mkdtemp(prefix="format_compare_")
    filename = os.path.basename(pdf_path)

    try:
        # 1. PDF 转图片
        image_paths = split_pdf_to_images(pdf_path, tmp_dir, dpi=200)
        if not image_paths:
            raise ValueError("PDF 转换图片失败")

        # 2. AI 一次性提取格式类型 + 结构化内容
        extract_result = _extract_content_from_images(image_paths)
        format_type = extract_result.get("format_type", "unknown")
        highlighted_content = extract_result.get("highlighted_content", [])

        # ===== 阶段一：类型识别 =====
        print(f"\n{'=' * 60}")
        print(f"  📋 [{filename}] 阶段一：类型识别")
        print(f"  识别结果: {FORMAT_LABELS.get(format_type, format_type)} ({format_type})")
        print(f"{'=' * 60}")

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

        # ===== 阶段二：提取的 JSON 格式数据 =====
        print(f"\n{'=' * 60}")
        print(f"  📄 [{filename}] 阶段二：提取的 JSON 格式数据")
        print(f"{'-' * 60}")
        if extract_result:
            print(json.dumps(extract_result, ensure_ascii=False, indent=2))
        else:
            print("  ⚠️ 未提取到任何数据 (AI 提取失败或无内容)")
        print(f"{'=' * 60}")

        # 3. 模板比对
        mismatches = _compare_with_template(format_type, highlighted_content)
        passed = len(mismatches) == 0

        # ===== 阶段三：比对结果 =====
        print(f"\n{'=' * 60}")
        print(f"  🔍 [{filename}] 阶段三：模板比对结果")
        print(f"{'-' * 60}")
        print(f"  格式类型: {FORMAT_LABELS.get(format_type, format_type)}")
        print(f"  比对通过: {'✅ 是' if passed else '❌ 否'}")
        if mismatches:
            print(f"  差异项 ({len(mismatches)} 个):")
            for m in mismatches:
                severity_icon = {"high": "🔴", "medium": "🟡", "low": "🔵"}.get(m.get("severity", ""), "⚪")
                print(f"    {severity_icon} {m['item']}: 期望[{m['expected']}] 实际[{m['actual']}]")
        else:
            print("  ✅ 无差异")
        print(f"{'=' * 60}")

        return {
            "format_type": format_type,
            "passed": passed,
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
