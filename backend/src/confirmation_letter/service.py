"""
询证函识别服务

独立的识别处理流程，复用底层 PDF 工具和 AI 请求接口。
"""
import os
import json
import shutil
import tempfile
from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_stream
from src.config import MODEL_LOCAL
from src.json_repair import fix_json


# 字段提取提示词
FIELD_EXTRACTION_PROMPT = """
Role: 银行询证函信息提取专家

Task: 从银行询证函扫描图片中精确提取以下 12 项字段信息。请仔细阅读整个文档，不要遗漏任何字段。

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
    "seal_name": ""
}
"""

# 所有识别字段
ALL_FIELDS = [
    "confirmation_no", "accounting_firm", "reply_address",
    "contact_person", "phone", "postal_code", "debit_account",
    "cutoff_date", "start_date", "end_date", "seal_date", "seal_name"
]


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
        
        # 3. 如果有多页，合并结果（多页询证函场景）
        if len(image_paths) > 1:
            pages_results = [result]
            for page_path in image_paths[1:]:
                page_result = extract_fields_from_image(page_path)
                pages_results.append(page_result)
            result = merge_recognition_results(pages_results)
        
        return result
    
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
