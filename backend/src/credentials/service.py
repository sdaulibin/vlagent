"""
类凭证提取与识别服务

负责提取：电子印章、电子凭证、身份证、银行卡、网银申请书、违法犯罪告知书。
"""
import os
import json
import shutil
import tempfile
from typing import List, Dict, Any

from services.pdf.pdf_utils import split_pdf_to_images
from services.core.request_ai import request_qwen35
from src.json_repair import fix_json
from src.credentials.prompts import PROMPT_MAPPING

def _compress_images_for_ai(image_paths: List[str], max_size=1600, quality=85) -> List[str]:
    """压缩图片以减小 API payload 大小"""
    from services.pdf.pdf_utils import resize_image_high_quality
    
    compressed_dir = tempfile.mkdtemp(prefix="compressed_cred_")
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
            compressed_paths.append(path)
            
    return compressed_paths

def extract_fields_from_images(image_paths: List[str], credential_type: str) -> dict:
    """调用 Qwen3.5 进行特定凭证的字段提取"""
    compressed_paths = _compress_images_for_ai(image_paths)
    prompt = PROMPT_MAPPING.get(credential_type)
    
    if not prompt:
        raise ValueError(f"不受支持的凭证类型: {credential_type}")

    try:
        if len(compressed_paths) == 1:
            response = request_qwen35(
                question=prompt,
                file_base=compressed_paths[0],
                show_request=False
            ).strip()
        else:
            response = request_qwen35(
                question=prompt,
                file_ary=compressed_paths,
                show_request=False,
                pic_tip=True,
            ).strip()
        
        try:
            data = json.loads(fix_json(response))
            return data
        except Exception as e:
            print(f"[{credential_type}] JSON 解析失败: {e}, 原始响应: {response[:200]}")
            return {}
            
    finally:
        compressed_dir = os.path.dirname(compressed_paths[0]) if compressed_paths else None
        if compressed_dir and compressed_dir.startswith(tempfile.gettempdir()):
            shutil.rmtree(compressed_dir, ignore_errors=True)

def process_credential(file_path: str, credential_type: str) -> Dict[str, Any]:
    """
    处理凭证文件 (PDF或图片)，提取结构化字段。
    """
    tmp_dir = tempfile.mkdtemp(prefix="cred_process_")
    
    try:
        # 支持 PDF 转化为图片，若本身是图片则处理一下
        ext = os.path.splitext(file_path)[-1].lower()
        if ext == '.pdf':
            image_paths = split_pdf_to_images(file_path, tmp_dir, dpi=200)
            if not image_paths:
                raise ValueError("PDF 转换图片失败，未生成任何图片")
        else:
            # 如果是单张图片，直接使用原图路径
            image_paths = [file_path]
            
        result = extract_fields_from_images(image_paths, credential_type)
        
        # 打印识别结果以供查看
        print(f"\n[凭证识别结果 - {credential_type}] -> {json.dumps(result, ensure_ascii=False)}")
        
        return {
            "credential_type": credential_type,
            "extracted_data": result
        }
    finally:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
