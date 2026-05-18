"""
文件验证服务

提供三种验证功能：
1. 通用文件格式验证 - 检查扩展名和魔数（支持 PDF/JPG/PNG）
2. PDF 格式验证 - 仅检查 PDF（向后兼容）
3. 银行流水验证 - 使用 AI 判断文档是否为银行流水
"""
import os
import json
from fastapi import UploadFile
from services.core.request_ai import request_qwen35
from src.json_repair import fix_json

# 文件魔数签名表
MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    ".pdf":  [b'%PDF'],
    ".jpg":  [b'\xff\xd8\xff'],
    ".jpeg": [b'\xff\xd8\xff'],
    ".png":  [b'\x89PNG\r\n\x1a\n'],
}

ALL_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def validate_file_content(
    filename: str,
    file_content: bytes,
    allowed_extensions: list[str] | None = None,
) -> tuple[bool, str]:
    """
    验证文件扩展名和内容魔数

    Args:
        filename: 文件名
        file_content: 文件内容（至少前 8 字节）
        allowed_extensions: 允许的扩展名列表，为 None 则允许所有已知类型

    Returns:
        (is_valid, error_message)
    """
    ext = os.path.splitext(filename)[1].lower()

    if not ext:
        return False, "文件缺少扩展名"

    ext_list = allowed_extensions if allowed_extensions else list(MAGIC_SIGNATURES.keys())

    if ext not in ext_list:
        ext_names = ", ".join(ext_list)
        return False, f"不支持的文件类型，仅支持: {ext_names}"

    if ext not in MAGIC_SIGNATURES:
        return True, ""

    signatures = MAGIC_SIGNATURES[ext]
    for sig in signatures:
        if file_content.startswith(sig):
            return True, ""

    return False, f"文件内容与扩展名 .{ext.lstrip('.')} 不匹配，可能存在安全风险"


async def read_file_header(file: UploadFile, size: int = 8) -> bytes:
    """读取上传文件头部字节用于魔数校验，读完后重置文件指针"""
    header = await file.read(size)
    await file.seek(0)
    return header


def validate_pdf_format(filename: str, file_content: bytes) -> tuple[bool, str]:
    """
    验证文件是否为有效的 PDF 格式

    Args:
        filename: 文件名
        file_content: 文件内容（至少前几个字节）

    Returns:
        (is_valid, error_message)
    """
    # 1. 检查扩展名
    if not filename.lower().endswith('.pdf'):
        return False, "仅支持 PDF 格式文件，请上传 .pdf 文件"

    # 2. 检查 PDF 魔数 (magic bytes)
    # PDF 文件以 %PDF- 开头
    if not file_content.startswith(b'%PDF'):
        return False, "文件内容不是有效的 PDF 格式"

    return True, ""


def validate_bank_statement(image_path: str) -> tuple[bool, str, float]:
    """
    使用 AI 判断图片是否为银行流水文件
    
    Args:
        image_path: 图片文件路径（通常是 PDF 转换后的第一页）
        
    Returns:
        (is_bank_statement, reason, confidence)
        - is_bank_statement: 是否为银行流水
        - reason: 判断理由
        - confidence: 置信度 (0.0-1.0)
    """
    prompt = """
请判断这张图片是否为银行流水文件。

银行流水文件的典型特征：
1. 包含银行名称、银行 Logo 或银行公章
2. 有账户信息（账号、户名、开户行等）
3. 有交易明细表格（包含日期、摘要/用途、收入/支出金额等列）
4. 有余额信息

请仔细分析图片内容，返回 JSON 格式结果：
{
    "is_bank_statement": true或false,
    "confidence": 0.0到1.0之间的数值,
    "reason": "简短的判断理由"
}

注意：
- 如果是发票、合同、收据等非流水文件，返回 false
- 只返回 JSON，不要有其他文字
"""
    
    try:
        response = request_qwen35(
            question=prompt,
            file_base=image_path
        ).strip()
        
        # 解析 AI 返回的 JSON
        try:
            result = json.loads(fix_json(response))
        except json.JSONDecodeError:
            # 如果解析失败，尝试简单匹配
            if "true" in response.lower():
                return True, "AI 判断为银行流水", 0.7
            else:
                return False, "AI 判断非银行流水", 0.7
        
        is_statement = result.get("is_bank_statement", False)
        confidence = float(result.get("confidence", 0.5))
        reason = result.get("reason", "未提供理由")
        
        return is_statement, reason, confidence
        
    except Exception as e:
        # 发生异常时默认不通过，避免非流水文件绕过校验
        print(f"银行流水验证异常: {e}")
        return False, f"验证过程出现异常: {str(e)}", 1.0
