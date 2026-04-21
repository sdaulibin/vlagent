"""
法律服务联络人信息提取服务

独立的识别处理流程，负责提取法律服务联络人信息表中的姓名、电话、邮箱、律所名称。
"""
import os
import json
import shutil
import tempfile
from typing import Any

from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_qwen35
from src.json_repair import fix_json

# 字段提取提示词
FIELD_EXTRACTION_PROMPT = """
Role: 法律服务联络人信息表提取专家

Task: 从法律服务联络人信息表扫描图片中精确提取以下 2 项核心字段信息。

## 待提取字段及识别规则：

1. **contacts (联络人列表)**
   - 从表格中提取所有填写的联络人信息。
   - 提取其 "name" (姓名)、"phone" (联系电话) 和 "email" (电子邮箱)。
   - 如果遇到有的行未填写姓名但有内容，请直接跳过。
2. **law_firm_name (律所名称)**
   - 从页面下方的落款处或红色圆形印章处提取打印、手写或印章形式的单位名称。
   - 提取被指定为合作机构的律师事务所全称，例如"山西某某律师事务所"等。
   - 【重要】请提取完整的律所名称，如果印章中有完整的名字请优先提取印章名，注意去除诸如"公章"、"财务专用章"等无关文字。

## 输出要求：
- 返回 JSON 格式
- 无法识别的字段返回空字符串 "" 或空数组 []
- 仅输出 JSON，无需解释，不要输出markdown标记

## JSON Schema:
{
    "contacts": [
        {
            "name": "",
            "phone": "",
            "email": ""
        }
    ],
    "law_firm_name": ""
}
"""


def _compress_images_for_ai(image_paths: list[str], max_size=1600, quality=85) -> list[str]:
    """
    压缩图片以减小 API payload 大小，避免网关 502 错误。
    将 PNG 转为 JPEG 并限制最大尺寸。
    
    Returns:
        list[str]: 压缩后的图片路径列表（存放在临时目录）
    """
    from services.pdf.pdf_utils import resize_image_high_quality
    
    compressed_dir = tempfile.mkdtemp(prefix="compressed_")
    compressed_paths = []
    
    for i, path in enumerate(image_paths):
        out_path = os.path.join(compressed_dir, f"page_{i:03d}.jpg")
        success = resize_image_high_quality(
            path, out_path,
            max_width=max_size, max_height=max_size, quality=quality
        )
        if success:
            compressed_paths.append(out_path)
        else:
            # 压缩失败时使用原图
            compressed_paths.append(path)
    
    return compressed_paths


def extract_fields_from_images(image_paths: list[str]) -> dict:
    """
    从图片中提取联络人信息记录（支持多张图片一次性提交）
    """
    compressed_paths = _compress_images_for_ai(image_paths)
    
    try:
        if len(compressed_paths) == 1:
            response = request_qwen35(
                question=FIELD_EXTRACTION_PROMPT,
                file_base=compressed_paths[0],
                show_request=False
            ).strip()
        else:
            response = request_qwen35(
                question=FIELD_EXTRACTION_PROMPT,
                file_ary=compressed_paths,
                show_request=False,
                pic_tip=True,
            ).strip()
        
        try:
            data = json.loads(fix_json(response))
            return data
        except Exception as e:
            print(f"JSON 解析失败: {e}, 原始响应: {response[:200]}")
            return {}
    finally:
        compressed_dir = os.path.dirname(compressed_paths[0]) if compressed_paths else None
        if compressed_dir and compressed_dir.startswith(tempfile.gettempdir()):
            shutil.rmtree(compressed_dir, ignore_errors=True)


def process_legal_contact(pdf_path: str) -> dict:
    """
    处理法律服务联络人信息表 PDF 文件，提取核心字段。
    
    Args:
        pdf_path: PDF 文件路径
        
    Returns:
        dict: 识别结果，如果某字段提取失败则为空字符串
    """
    tmp_dir = tempfile.mkdtemp(prefix="legal_contact_")
    
    try:
        # 1. PDF 转图片
        image_paths = split_pdf_to_images(pdf_path, tmp_dir, dpi=200)
        
        if not image_paths:
            raise ValueError("PDF 转换图片失败，未生成任何图片")
        
        # 2. 所有页面一次性提交 AI 提取
        result = extract_fields_from_images(image_paths)

        # 3. 后处理：简单的格式规范化
        contacts = result.get("contacts", [])
        if not isinstance(contacts, list):
            contacts = []
            
        # 组装联系人字符串: "姓名: 电话" 换行 "姓名: 电话"
        contact_str_list = []
        email_str_list = []
        for c in contacts:
            name = (c.get("name", "") or "").strip()
            phone = (c.get("phone", "") or "").strip()
            email = (c.get("email", "") or "").strip()
            
            if name or phone:
                contact_str_list.append(f"{name}：{phone}" if name and phone else f"{name}{phone}")
            if email:
                email_str_list.append(email)

        normalized = {
            "name_and_phone": "\n".join(contact_str_list),
            "email": "\n".join(email_str_list),
            "law_firm_name": (result.get("law_firm_name", "") or "").strip()
        }
        
        # 打印识别结果以供查看
        print(f"\n[AI 提取原始返回] -> {json.dumps(result, ensure_ascii=False)}")
        print(f"[标准化返回结果] -> {json.dumps(normalized, ensure_ascii=False)}")
        
        return normalized
    
    finally:
        # 4. 清理临时文件
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
